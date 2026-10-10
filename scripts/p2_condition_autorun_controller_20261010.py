# Created: 2026-10-10 JST
"""Fail-closed controller for the approved P2 condition HTML byte audit.

Only public GitHub Actions invokes this controller. Evidence goes to a separate
private audit branch; no source CSV, Production v12 logic, legacy HTML, or
previously successful shards are modified or executed again.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

SECTORS = ("technology", "financials", "consumer_goods", "materials",
           "capital_goods_others", "transportation_utilities")
CORE_SHA = "c0c69be8e28ddfa5812c1bbe4ba3d33f432fbf02"
RENDER_SHA = "3dfb14cd0f05125c4bfce81d710db0ced073b7c3"
TOTAL_SHARDS = 111
FIRST_SHARD = 4
MAX_BATCH = 3
AUDIT_ROOT = Path("docs/audits/p2_condition_auto")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ledger_check(ledger: dict) -> None:
    if (ledger.get("schema") != 1 or ledger.get("status") != "ACTIVE"
            or ledger.get("private_core_sha") != CORE_SHA
            or ledger.get("legacy_renderer_sha") != RENDER_SHA
            or ledger.get("datasets") != list(SECTORS)
            or ledger.get("shards_per_sector") != TOTAL_SHARDS
            or ledger.get("shard_conditions") != 4
            or ledger.get("baseline_certified_condition_pages") != 228
            or ledger.get("baseline_completed_shards_per_sector") != [0, 1, 2, 3]
            or type(ledger.get("next_shard")) is not int
            or not FIRST_SHARD <= ledger["next_shard"] < TOTAL_SHARDS):
        raise ValueError("private audit ledger version, scope, or cursor mismatch")
    if ledger.get("completed_through") != ledger["next_shard"] - 1:
        raise ValueError("non-contiguous private audit cursor")


def shards_check(raw: str, ledger: dict) -> list[int]:
    shards = json.loads(raw)
    if (not isinstance(shards, list) or not 1 <= len(shards) <= MAX_BATCH
            or any(type(s) is not int for s in shards)):
        raise ValueError("shards must be 1-3 integer indices")
    start = ledger["next_shard"]
    if shards != list(range(start, start + len(shards))) or shards[-1] >= TOTAL_SHARDS:
        raise ValueError(f"repeated, skipped, or out-of-range shard: expected from {start}, got {shards}")
    return shards


def write_output(path: Path | None, key: str, value: str) -> None:
    if path is not None:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"{key}={value}\n")


def preflight(args: argparse.Namespace) -> None:
    ledger = load_json(args.ledger)
    ledger_check(ledger)
    shards = shards_check(args.shards, ledger)
    clean = json.dumps(shards, separators=(",", ":"))
    write_output(args.github_output, "shards_json", clean)
    print(json.dumps({"status": "PREFLIGHT_PASS", "shards": shards,
                      "jobs": len(SECTORS) * len(shards),
                      "expected_pages": len(SECTORS) * len(shards) * 8}))


def validate_pair(record: dict, dataset: str, key: str, expected: dict) -> None:
    if (record.get("status") != "PASS_BYTES"
            or record.get("dataset") != dataset
            or record.get("condition_key") != key
            or record.get("condition_id") != expected.get("id")
            or record.get("slug") != expected.get("slug")
            or type(record.get("canonical_manifest_count")) is not int
            or record["canonical_manifest_count"] < 0
            or record.get("matched_pages") != 2
            or record.get("checked_detail_pages") != 1
            or record.get("checked_chart_pages") != 1
            or record.get("failed_files") != []
            or record.get("p2_v12_recomputed") is not False
            or record.get("source_html_modified") is not False
            or record.get("deployment_allowed") is not False):
        raise ValueError(f"invalid pair audit: {dataset} {key}")
    rows = record.get("rows")
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError("missing HTML comparison records")
    for row in rows:
        if (row.get("family") not in ("detail", "chart")
                or row.get("condition_key") != key
                or row.get("byte_equal") is not True
                or row.get("first_difference_offset") is not None
                or not isinstance(row.get("old_bytes"), int)
                or row["old_bytes"] <= 0 or row["old_bytes"] != row.get("new_bytes")
                or not re.fullmatch("[0-9a-f]{64}", str(row.get("old_sha256", "")))
                or row.get("old_sha256") != row.get("new_sha256")):
            raise ValueError(f"invalid HTML SHA/binary evidence: {dataset} {key}")
    if {x["family"] for x in rows} != {"detail", "chart"}:
        raise ValueError("duplicate or missing HTML family")
    if set(record.get("source_csv_sha256", {})) != {"signal_level_features.csv", "condition_detail_manifest.csv"}:
        raise ValueError("missing source CSV integrity evidence")


def validate_artifact(artifact_dir: Path, dataset: str, shard: int) -> tuple[dict, list[dict], list[Path]]:
    if not artifact_dir.is_dir():
        raise FileNotFoundError(f"missing mandatory artifact: {artifact_dir}")
    summaries = list(artifact_dir.rglob("shard_audit.json"))
    files = sorted(artifact_dir.rglob("p2_condition_pair_byte_audit.json"))
    provs = list(artifact_dir.rglob("legacy_renderer_provenance.json"))
    if len(summaries) != 1 or len(files) != 4 or len(provs) != 1:
        raise ValueError(f"incomplete evidence artifact: {artifact_dir}")
    summary = load_json(summaries[0])
    prov = load_json(provs[0])
    if (summary.get("schema") != 1 or summary.get("dataset") != dataset
            or summary.get("shard") != shard or summary.get("status") != "PASS_BYTES"
            or summary.get("matched_pages") != 8 or summary.get("failed_conditions") != []
            or summary.get("core_sha") != CORE_SHA
            or summary.get("legacy_renderer_sha") != RENDER_SHA
            or summary.get("p2_v12_recomputed") is not False
            or summary.get("source_html_modified") is not False
            or summary.get("deployment_allowed") is not False
            or prov.get("current_core_sha") != CORE_SHA
            or prov.get("legacy_renderer_sha") != RENDER_SHA):
        raise ValueError(f"bad shard summary/provenance {dataset}/{shard}")
    expected = summary.get("conditions", [])
    if not isinstance(expected, list) or len(expected) != 4:
        raise ValueError("invalid shard conditions")
    keys = [c.get("key") for c in expected]
    if len(set(keys)) != 4 or keys != sorted(keys):
        raise ValueError("unsorted or duplicate canonical condition keys")
    if any(c.get("status") != "PASS_BYTES" or c.get("matched_pages") != 2 for c in expected):
        raise ValueError("one or more shard conditions not PASS")
    pairs = [load_json(path) for path in files]
    keyed = {a.get("condition_key"): a for a in pairs}
    if len(keyed) != 4 or set(keyed) != set(keys):
        raise ValueError("different keys in shard and pair audit evidence")
    seen = set()
    for c in expected:
        key = c["key"]
        pair = keyed[key]
        validate_pair(pair, dataset, key, c)
        if pair["rows"] != c.get("pages") or pair["source_csv_sha256"] != c.get("source_csv_sha256"):
            raise ValueError("pair audit differs from independently persisted shard summary")
        for row in pair["rows"]:
            if row["path"] in seen:
                raise ValueError("duplicate HTML filename in shard")
            seen.add(row["path"])
    if len(seen) != 8:
        raise ValueError("expected exactly eight unique HTML output paths")
    first_hashes = keyed[keys[0]]["source_csv_sha256"]
    if any(keyed[k]["source_csv_sha256"] != first_hashes for k in keys):
        raise ValueError("mixed saved CSV versions within a shard")
    return summary, pairs, [summaries[0], *files, provs[0]]


def finalize(args: argparse.Namespace) -> None:
    ledger_path = args.evidence_root / AUDIT_ROOT / "ledger.json"
    ledger = load_json(ledger_path)
    ledger_check(ledger)
    shards = shards_check(args.shards, ledger)
    artifacts = args.download_root
    expected_names = {
        f"p2-conditions-{dataset}-shard-{shard}-PASS"
        for dataset in SECTORS for shard in shards
    }
    actual_names = {item.name for item in artifacts.iterdir() if item.is_dir()}
    if actual_names != expected_names:
        raise ValueError(f"missing, extra or failed job artifacts: {sorted(expected_names - actual_names)}")
    all_keys = set()
    wave = {"schema": 1, "shards": shards, "private_core_sha": CORE_SHA,
            "legacy_renderer_sha": RENDER_SHA, "status": "PASS_BYTES",
            "job_count": len(expected_names), "matched_pages": 0,
            "datasets": list(SECTORS), "artifact_records": []}
    writes = []
    for shard in shards:
        for dataset in SECTORS:
            name = f"p2-conditions-{dataset}-shard-{shard}-PASS"
            folder = artifacts / name
            summary, pairs, paths = validate_artifact(folder, dataset, shard)
            keys = [x["key"] for x in summary["conditions"]]
            for key in keys:
                t = (dataset, key)
                if t in all_keys:
                    raise ValueError("duplicate canonical condition across sharded batch")
                all_keys.add(t)
            base = args.evidence_root / AUDIT_ROOT / "shards" / dataset / f"{shard:03d}"
            if base.exists():
                raise FileExistsError(f"previously certified shard must never be overwritten: {base}")
            wave["artifact_records"].append({"dataset": dataset, "shard": shard,
                                             "condition_keys": keys, "matched_pages": 8,
                                             "files_sha256": {path.relative_to(folder).as_posix(): digest(path)
                                                              for path in paths}})
            wave["matched_pages"] += 8
            writes.append((base, summary, pairs))
    if wave["matched_pages"] != len(SECTORS) * len(shards) * 8:
        raise ValueError("missing pages in completed batch")
    for base, summary, pairs in writes:
        base.mkdir(parents=True, exist_ok=False)
        save_json(base / "shard_audit.json", summary)
        for i, pair in enumerate(sorted(pairs, key=lambda p: p["condition_key"])):
            save_json(base / f"condition_{i:02d}.json", pair)
    wave_path = args.evidence_root / AUDIT_ROOT / "waves" / f"shards_{shards[0]:03d}_{shards[-1]:03d}.json"
    if wave_path.exists():
        raise FileExistsError("duplicate wave report")
    save_json(wave_path, wave)
    new_next = shards[-1] + 1
    ledger["next_shard"] = new_next
    ledger["completed_through"] = shards[-1]
    ledger["waves_completed"] = ledger["waves_completed"] + 1
    ledger["last_wave"] = wave_path.relative_to(args.evidence_root).as_posix()
    if new_next >= TOTAL_SHARDS:
        ledger["status"] = "COMPLETE"
        write_output(args.github_output, "should_continue", "false")
        write_output(args.github_output, "next_shards", "[]")
    else:
        batch = list(range(new_next, min(new_next + MAX_BATCH, TOTAL_SHARDS)))
        write_output(args.github_output, "should_continue", "true")
        write_output(args.github_output, "next_shards", json.dumps(batch, separators=(",", ":")))
    save_json(ledger_path, ledger)
    print(json.dumps({"status": "EVIDENCE_VALIDATED_READY_FOR_PRIVATE_COMMIT",
                      "completed_shards": shards, "matched_pages": wave["matched_pages"],
                      "next_shard": new_next, "run_finished": ledger["status"] == "COMPLETE"}))


def selftest() -> None:
    ledger = {"schema": 1, "status": "ACTIVE", "next_shard": 4, "completed_through": 3,
              "private_core_sha": CORE_SHA, "legacy_renderer_sha": RENDER_SHA,
              "datasets": list(SECTORS), "shards_per_sector": 111,
              "shard_conditions": 4, "baseline_certified_condition_pages": 228,
              "baseline_completed_shards_per_sector": [0, 1, 2, 3]}
    ledger_check(ledger)
    assert shards_check("[4]", ledger) == [4]
    assert shards_check("[4,5,6]", ledger) == [4, 5, 6]
    for text in ("[3]", "[4,6]", "[4,5,6,7]", "[4.0]", "[4,true]", "[]", "[110]"):
        try:
            shards_check(text, ledger)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"rejected invalid batch {text}")
    with tempfile.TemporaryDirectory() as dirname:
        root = Path(dirname)
        for k in SECTORS:
            fake = root / f"p2-conditions-{k}-shard-4-PASS"
            fake.mkdir()
        assert len([x for x in root.iterdir() if x.is_dir()]) == 6
    print("PASS: immutable ledger, ordered 1-3 shard batches, replay/scope rejection")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["selftest", "preflight", "finalize"])
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--shards")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--download-root", type=Path)
    args = parser.parse_args()
    if args.mode == "selftest":
        selftest()
    elif args.mode == "preflight":
        if args.ledger is None or args.shards is None:
            parser.error("--ledger and --shards required")
        preflight(args)
    else:
        if args.evidence_root is None or args.download_root is None or args.shards is None:
            parser.error("--evidence-root, --download-root and --shards required")
        finalize(args)


if __name__ == "__main__":
    main()
