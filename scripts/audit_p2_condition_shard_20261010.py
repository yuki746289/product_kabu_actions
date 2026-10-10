# Created: 2026-10-10 JST
"""Deterministic, fail-closed audit of P2 condition HTML shards (public runner only).

This orchestration script never changes Production P2 logic or saved source
artifacts; the existing private p01-p07 HTML engine and pair auditor remain
authoritative. Each 4-condition shard produces at most 8 isolated HTML files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

SECTORS = ("technology", "financials", "consumer_goods", "materials",
           "capital_goods_others", "transportation_utilities")
REPRESENTATIVES = {
    "S:fan=CONVERGED",
    "P:fan=CONVERGED&ema=STRONG_CONTINUING",
    "T:fan=CONVERGED&ema=DECELERATING&daily_rci14_position=LOW",
}
PAGE_ROOT = "preview/kabu/analysis/225_group_all_period"
SHARD_SIZE = 4
EXPECTED_CONDITIONS = 447
SHARDS_PER_SECTOR = 111


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def condition_slug(key: str) -> str:
    return key[0].lower() + "-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def condition_id(key: str) -> str:
    return "P2C-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12].upper()


def canonical_rows(manifest: Path) -> list[dict[str, str]]:
    with manifest.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != EXPECTED_CONDITIONS:
        raise ValueError(f"expected 447 canonical conditions, got {len(rows)}")
    keys = [r["condition_key"] for r in rows]
    slugs = [r["slug"] for r in rows]
    if len(set(keys)) != len(keys) or len(set(slugs)) != len(slugs):
        raise ValueError("duplicate condition keys or slugs")
    if not REPRESENTATIVES.issubset(keys):
        raise ValueError("previously-certified S/P/T keys not in manifest")
    expected_types = {"S": "single", "P": "pair", "T": "triple"}
    for row in rows:
        key = row["condition_key"]
        if (not re.fullmatch(r"[SPT]:[A-Za-z0-9_=&.-]+", key)
                or row["slug"] != condition_slug(key)
                or row["condition_type"] != expected_types[key[0]]):
            raise ValueError(f"invalid canonical slug/key/type: {key}")
    return sorted((r for r in rows if r["condition_key"] not in REPRESENTATIVES),
                  key=lambda x: x["condition_key"])


def plan_shard(manifest: Path, dataset: str, shard: int, core_sha: str, legacy_sha: str) -> dict:
    if dataset not in SECTORS:
        raise ValueError("unsupported dataset")
    if not 0 <= shard < SHARDS_PER_SECTOR:
        raise ValueError("invalid shard index")
    rows = canonical_rows(manifest)
    if len(rows) != 444:
        raise ValueError("representative exclusion not exactly three keys")
    chosen = rows[shard * SHARD_SIZE:(shard + 1) * SHARD_SIZE]
    if len(chosen) != SHARD_SIZE:
        raise ValueError("incomplete or empty shard")
    base = f"{PAGE_ROOT}/{dataset}/conditions"
    paths = []
    conditions = []
    for row in chosen:
        slug = row["slug"]
        paths += [f"/{base}/{slug}.html", f"/{base}/charts/{slug}.html"]
        conditions.append({"key": row["condition_key"], "condition_id": condition_id(row["condition_key"]),
                           "slug": slug, "kind": row["condition_type"], "canonical_count": int(row["count"])})
    return {
        "schema": 1, "dataset": dataset, "shard": shard, "shard_count": SHARDS_PER_SECTOR,
        "shard_size": SHARD_SIZE, "conditions": conditions,
        "legacy_html_sparse_paths": paths, "manifest_sha256": digest(manifest),
        "private_core_sha": core_sha, "legacy_renderer_sha": legacy_sha,
        "source_signals_recomputed": False, "promotion_allowed": False,
    }


def write_plan(args: argparse.Namespace) -> None:
    plan = plan_shard(args.manifest, args.dataset, args.shard, args.core_sha, args.legacy_sha)
    if args.out.exists():
        raise FileExistsError(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as f:
            f.write("sparse_paths<<P2_SHARD_PATHS_END\n")
            f.write("\n".join(plan["legacy_html_sparse_paths"]) + "\n")
            f.write("P2_SHARD_PATHS_END\n")
    print(json.dumps({"dataset": plan["dataset"], "shard": plan["shard"],
                      "keys": [c["key"] for c in plan["conditions"]],
                      "old_html_paths": len(plan["legacy_html_sparse_paths"]),
                      "manifest_sha256": plan["manifest_sha256"]}, ensure_ascii=False), flush=True)


def run_shard(args: argparse.Namespace) -> None:
    core = args.core.resolve()
    stage = args.stage.resolve()
    site = core / "preview/kabu"
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if plan.get("schema") != 1 or plan.get("dataset") != args.dataset:
        raise ValueError("plan mismatch")
    if plan.get("private_core_sha") != args.core_sha or plan.get("legacy_renderer_sha") != args.legacy_sha:
        raise ValueError("code version drift")
    manifest = core / PAGE_ROOT / args.dataset / "condition_detail_manifest.csv"
    if digest(manifest) != plan["manifest_sha256"]:
        raise ValueError("source manifest SHA drift")
    fresh_plan = plan_shard(manifest, args.dataset, plan["shard"], args.core_sha, args.legacy_sha)
    if fresh_plan != plan:
        raise ValueError("shard plan mismatch against checked-out canonical manifest")
    if stage == core or not stage.is_relative_to(core / "build") or not (stage / "scripts").is_dir():
        raise ValueError("staging renderer path is invalid")
    output = args.output.resolve()
    if not output.is_relative_to(core / "build") or output.exists():
        raise ValueError("must use a new isolated build output directory")
    output.mkdir(parents=True)
    records = []
    results = {"schema": 1, "dataset": args.dataset, "shard": plan["shard"],
               "status": "IN_PROGRESS", "core_sha": args.core_sha,
               "legacy_renderer_sha": args.legacy_sha,
               "manifest_sha256": plan["manifest_sha256"],
               "conditions": records, "matched_pages": 0, "failed_conditions": [],
               "p2_v12_recomputed": False, "source_html_modified": False,
               "deployment_allowed": False}
    summary_path = output / "shard_audit.json"

    def persist() -> None:
        summary_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    persist()
    for i, cond in enumerate(plan["conditions"]):
        key = cond["key"]
        build_dir = output / f"condition_{i:02d}_html"
        audit_dir = output / f"condition_{i:02d}_audit"
        record = {"key": key, "id": cond["condition_id"], "slug": cond["slug"], "status": "PENDING"}
        records.append(record)
        persist()
        try:
            subprocess.run([sys.executable, str(core / "scripts/p2_html_build.py"),
                            "--repo-root", str(core), "--site-root", str(site),
                            "--stage-root", str(stage), "--dataset", args.dataset,
                            "--family", "conditions", "--condition-id", cond["condition_id"],
                            "--output-dir", str(build_dir)], check=True)
            subprocess.run([sys.executable, str(core / "scripts/verify_p2_condition_pair_byte_audit_20261010.py"),
                            "--repo-root", str(core), "--site-root", str(site),
                            "--build-root", str(build_dir), "--output-dir", str(audit_dir),
                            "--dataset", args.dataset, "--condition-key", key], check=True)
            audit_file = audit_dir / "p2_condition_pair_byte_audit.json"
            audit = json.loads(audit_file.read_text(encoding="utf-8"))
            rows = audit.get("rows", [])
            if not (audit["status"] == "PASS_BYTES" and audit["matched_pages"] == 2
                    and audit["failed_files"] == [] and len(rows) == 2
                    and all(r["byte_equal"] and r["first_difference_offset"] is None
                            and r["old_sha256"] == r["new_sha256"] and r["old_bytes"] == r["new_bytes"]
                            for r in rows)
                    and audit["condition_key"] == key and audit["condition_id"] == cond["condition_id"]
                    and audit["canonical_manifest_count"] == cond["canonical_count"]
                    and audit["p2_v12_recomputed"] is False and audit["source_html_modified"] is False):
                raise RuntimeError("fail-closed detailed byte audit contract violation")
            record.update(status="PASS_BYTES", matched_pages=2, pages=rows,
                          source_csv_sha256=audit["source_csv_sha256"])
            results["matched_pages"] += 2
        except Exception as error:
            record.update(status="FAIL", error=str(error)[:512])
            results["failed_conditions"].append(key)
            results["status"] = "FAIL_CLOSED"
            persist()
            raise
        persist()
    if (len(records) != SHARD_SIZE or results["matched_pages"] != SHARD_SIZE * 2
            or any(r["status"] != "PASS_BYTES" for r in records)):
        raise RuntimeError("shard total invariant failed")
    results["status"] = "PASS_BYTES"
    persist()
    print(json.dumps({"dataset": args.dataset, "shard": plan["shard"],
                      "status": results["status"], "matched_pages": results["matched_pages"]},
                     ensure_ascii=False), flush=True)


def self_test() -> None:
    with tempfile.TemporaryDirectory() as root:
        manifest = Path(root) / "manifest.csv"
        rows = sorted(REPRESENTATIVES) + [f"S:fake_{n}=V" for n in range(444)]
        with manifest.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=("condition_key", "condition_label",
                                                   "condition_type", "slug", "count", "stability_label"))
            writer.writeheader()
            for key in rows:
                writer.writerow({"condition_key": key, "condition_label": key,
                                 "condition_type": {"S": "single", "P": "pair", "T": "triple"}[key[0]],
                                 "slug": condition_slug(key), "count": 10,
                                 "stability_label": "CANONICAL_CONDITION"})
        seen = []
        for n in range(SHARDS_PER_SECTOR):
            plan = plan_shard(manifest, "technology", n, "a"*40, "b"*40)
            assert len(plan["conditions"]) == 4
            assert len(plan["legacy_html_sparse_paths"]) == 8
            seen.extend(x["key"] for x in plan["conditions"])
        assert len(seen) == len(set(seen)) == 444
        assert not REPRESENTATIVES.intersection(seen)
        try:
            plan_shard(manifest, "technology", SHARDS_PER_SECTOR, "a"*40, "b"*40)
        except ValueError:
            pass
        else:
            raise AssertionError("out of range shard accepted")
    print("PASS: 111 disjoint shards, 444 unique keys, 888 pages, previous representatives excluded")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("plan", "run", "selftest"), required=True)
    ap.add_argument("--dataset", choices=SECTORS)
    ap.add_argument("--shard", type=int)
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--github-output", type=Path)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--core", type=Path)
    ap.add_argument("--stage", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--core-sha")
    ap.add_argument("--legacy-sha")
    args = ap.parse_args()
    if args.mode == "selftest":
        self_test()
    elif args.mode == "plan":
        if not all((args.manifest, args.dataset, args.shard is not None, args.out,
                    args.core_sha, args.legacy_sha)):
            ap.error("missing plan arguments")
        write_plan(args)
    else:
        if not all((args.plan, args.dataset, args.core, args.stage, args.output,
                    args.core_sha, args.legacy_sha)):
            ap.error("missing run arguments")
        run_shard(args)


if __name__ == "__main__":
    main()
