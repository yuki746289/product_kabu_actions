# Created: 2026-10-11 JST
"""Artifact-only staging of candidate P2 HTML after independent canary PASS.

Read-only source data. Create a NEW ZIP, inventory and SHA proof below build/.
Never copy stale old HTML; never write or deploy preview/kabu.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

import pandas as pd

SECTORS = (
    "technology", "financials", "consumer_goods", "materials",
    "capital_goods_others", "transportation_utilities",
)
KINDS = ("single", "pair", "triple")
CSV = {
    "single": "advantage_single_candidates.csv",
    "pair": "advantage_pairwise_candidates.csv",
    "triple": "advantage_triple_candidates.csv",
}


def checksum(file: Path) -> str:
    d = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            d.update(block)
    return d.hexdigest()


def js_data(raw: str) -> list:
    m = re.search(r",D=(\[[\s\S]*?\]),HI=new Set", raw)
    if m is None:
        raise AssertionError("canonical HTML JS dataset missing")
    data = json.loads(m.group(1))
    if not isinstance(data, list):
        raise AssertionError("invalid canonical data list")
    return data


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--core", type=Path, required=True)
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--sector", choices=SECTORS, required=True)
    p.add_argument("--gate", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-core-sha", required=True)
    a = p.parse_args()
    root, stage, out = a.core.resolve(), a.stage.resolve(), a.out.resolve()
    gate = json.loads(a.gate.read_text(encoding="utf-8"))
    if gate.get("status") != "PASS" or gate.get("sector") != a.sector or (
        gate.get("private_sha") != a.expected_core_sha
    ):
        raise ValueError("canary approval artifact invalid/mismatched")
    if not stage.is_relative_to(root / "build") or not (stage / "scripts").is_dir():
        raise ValueError("renderer stage must be isolated under core/build")
    if out == root / "build" or not out.is_relative_to(root / "build") or out.exists():
        raise ValueError("out must be unused under build/")
    if subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                               text=True).strip() != a.expected_core_sha:
        raise ValueError("private source commit mismatch")
    source = root / "preview/kabu/analysis/225_group_all_period" / a.sector
    files = [source / v for v in CSV.values()] + [
        source / "condition_detail_manifest.csv", source / "semantic_status.json",
    ]
    before = {str(f): checksum(f) for f in files}
    manifest = pd.read_csv(source / "condition_detail_manifest.csv", low_memory=False)
    if len(manifest) != 447 or manifest.condition_key.duplicated().any():
        raise AssertionError("immutable condition manifest invalid")
    slugmap = dict(zip(manifest.condition_key, manifest.slug))
    status = json.loads((source / "semantic_status.json").read_text(encoding="utf-8"))
    if status.get("overall_pass") is not True:
        raise AssertionError("source semantic status not PASS")
    sys.path.insert(0, str(stage / "scripts"))
    import refine_p2_report_information_architecture as ui
    out.mkdir(parents=True)
    dest = out / "summaries"
    dest.mkdir()
    ui.SUM = dest
    expected = {}
    for kind in KINDS:
        frame = pd.read_csv(source / CSV[kind], low_memory=False)
        group = frame.groupby("feature" if kind == "single"
                              else [f"feature{i}" for i in range(1, 3 if kind == "pair" else 4)],
                              sort=False, dropna=False)
        generated = ui.group_pages(kind, frame, slugmap)
        if generated != len(group):
            raise AssertionError("renderer generated count differs from candidate groups")
        expected[kind] = generated

    # Postprocessor has no data dependencies and writes only within fresh build.
    import postprocess_p2_accuracy_highlight as highlighter
    highlighter.apply_to_tree(dest)

    inventory = sorted(dest.glob("*.html"))
    expected_total = sum(expected.values()) + 3
    if len(inventory) != expected_total:
        raise AssertionError("staged summary HTML inventory mismatch")
    if gate["url_inventory"]["candidate_total"] != expected_total:
        raise AssertionError("URL gate and staging candidate inventory diverged")
    if gate["url_inventory"]["old_only"] < 1:
        raise AssertionError("stale legacy pages should have been identified")

    # Intra-summary group links must have exactly one on-disk target.
    names = {f.name for f in inventory}
    linked = set()
    for kind in KINDS:
        idx = dest / f"{kind}_features.html"
        for row in js_data(idx.read_text(encoding="utf-8")):
            match = re.search(r'href="([^"]+\.html)"', str(row[0]))
            if not match or match.group(1) not in names:
                raise AssertionError("index target missing from candidate HTML")
            linked.add(match.group(1))
    if linked | {f"{k}_features.html" for k in KINDS} != names:
        raise AssertionError("unlinked or duplicate candidate pages")

    for f in files:
        if checksum(f) != before[str(f)]:
            raise AssertionError("input CSV/JSON was unexpectedly changed")
    if subprocess.check_output(["git", "-C", str(root), "diff", "--name-only"],
                               text=True).strip():
        raise AssertionError("tracked private file modified")
    digest = {f.name: checksum(f) for f in inventory}
    archive = out / f"p2_candidate_summaries_{a.sector}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6) as z:
        for file in inventory:
            z.write(file, arcname=f"{a.sector}/summaries/{file.name}")
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist()) != expected_total or z.testzip() is not None:
            raise AssertionError("corrupt or incomplete archive")
    report = {
        "schema": 1, "status": "PASS_STAGED_REQUIRES_DEPLOY_APPROVAL",
        "sector": a.sector, "core_sha": a.expected_core_sha,
        "generator_groups": expected, "candidate_html_pages": expected_total,
        "sha256_inventory_digest": hashlib.sha256(
            json.dumps(digest, sort_keys=True).encode()).hexdigest(),
        "archive": archive.name, "archive_sha256": checksum(archive),
        "archive_bytes": archive.stat().st_size,
        "legacy_html_copied": False, "stored_sources_unchanged": True,
        "source_signals_recomputed": False, "production_p2_changed": False,
        "deployment_allowed": False,
    }
    (out / "staging_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
