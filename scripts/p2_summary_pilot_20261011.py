# Created: 2026-10-11 JST
"""Isolated six-page pilot for canonical six-sector P2 indicator summaries.

The approved 447-condition detail family is NOT a sufficient input for
the 712-page indicator summaries. Use the original three SAVED candidate
CSVs and the pinned canonical UI renderer. No P2 v12 recomputation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

SECTORS = ("technology", "financials", "consumer_goods", "materials",
           "capital_goods_others", "transportation_utilities")
CSVS = {
    "single": "advantage_single_candidates.csv",
    "pair": "advantage_pairwise_candidates.csv",
    "triple": "advantage_triple_candidates.csv",
}
EXPECTED = {"single": 33, "pair": 121, "triple": 558}
PROBES = (
    "single_features.html",
    "single-024fd29f8cb77a.html",
    "pair_features.html",
    "pair-0283227d107664.html",
    "triple_features.html",
    "triple-00093b4b282e31.html",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def first_difference(a: Path, b: Path) -> int | None:
    with a.open("rb") as fa, b.open("rb") as fb:
        pos = 0
        while True:
            aa, bb = fa.read(65536), fb.read(65536)
            if aa != bb:
                return pos + next((i for i, (x, y) in enumerate(zip(aa, bb)) if x != y),
                                  min(len(aa), len(bb)))
            if not aa:
                return None
            pos += len(aa)


def execute(core: Path, stage: Path, dataset: str, out: Path) -> dict:
    import pandas as pd

    core = core.resolve()
    stage = stage.resolve()
    out = out.resolve()
    if dataset not in SECTORS:
        raise ValueError("unknown sector")
    if not stage.is_relative_to(core / "build") or not (stage / "scripts").is_dir():
        raise ValueError("only isolated build/scripts renderer stage allowed")
    if not out.is_relative_to(core / "build") or out.exists():
        raise ValueError("output must be a NEW directory inside core/build")
    source = core / "preview/kabu/analysis/225_group_all_period" / dataset
    before = {}
    source_files = [source / "condition_detail_manifest.csv"] + [source / f for f in CSVS.values()]
    old_paths = [source / "summaries" / f for f in PROBES]
    for p in source_files + old_paths:
        if not p.is_file():
            raise FileNotFoundError(f"source or comparison HTML not checked out: {p}")
        before[str(p)] = sha256(p)
    # Import the fixed-version renderer from build/, never mutate tracked source.
    sys.path.insert(0, str(stage / "scripts"))
    import refine_p2_report_information_architecture as ui
    import postprocess_p2_accuracy_highlight as highlight

    manifest = pd.read_csv(source / "condition_detail_manifest.csv")
    if len(manifest) != 447 or manifest.condition_key.duplicated().any():
        raise ValueError("canonical condition manifest mismatch")
    slugmap = dict(zip(manifest.condition_key, manifest.slug))
    dest = out / "analysis/225_group_all_period" / dataset / "summaries"
    dest.mkdir(parents=True)
    ui.SUM = dest
    observed = {}
    for kind, name in CSVS.items():
        frame = pd.read_csv(source / name, low_memory=False)
        if frame.empty:
            raise ValueError("empty saved candidate data " + name)
        observed[kind] = ui.group_pages(kind, frame, slugmap)
    highlight.apply_to_tree(dest)
    inventory = sorted(p.name for p in dest.glob("*.html"))
    if len(inventory) != 712 or len(set(inventory)) != 712:
        raise ValueError(f"wrong full summary inventory: {len(inventory)} vs 712")
    for kind, expected_count in EXPECTED.items():
        filenames = [n for n in inventory if n.startswith(kind + "-") or n == kind + "_features.html"]
        if len(filenames) != expected_count or observed[kind] != expected_count - 1:
            raise ValueError(f"wrong {kind} summary group count: {observed[kind]} / {len(filenames)}")
    rows = []
    for name in PROBES:
        older = source / "summaries" / name
        newer = dest / name
        if not newer.is_file():
            raise FileNotFoundError(f"generated representative HTML missing: {name}")
        first = first_difference(older, newer)
        rows.append({
            "filename": name, "old_sha256": before[str(older)],
            "new_sha256": sha256(newer), "old_bytes": older.stat().st_size,
            "new_bytes": newer.stat().st_size, "first_difference": first,
            "byte_equal": first is None and before[str(older)] == sha256(newer),
        })
    for p in source_files + old_paths:
        if sha256(p) != before[str(p)]:
            raise RuntimeError("immutable source input was changed: " + str(p))
    outcome = {
        "dataset": dataset, "status": "PASS_BYTES" if all(x["byte_equal"] for x in rows) else "FAIL_BYTES",
        "summary_inventory": len(inventory), "group_counts": observed,
        "checked_representatives": 6, "matched_pages": sum(x["byte_equal"] for x in rows),
        "rows": rows, "source_hashes": {str(p.relative_to(core)): before[str(p)] for p in source_files},
        "input_source": "saved advantage_single/pairwise/triple_candidates CSV (not 447 condition manifest alone)",
        "p2_v12_recomputed": False, "source_html_modified": False,
        "deployment_allowed": False, "promoted": False,
        "scope": "one technology sector, six representative pages; 712 full inventory rendered only in build",
        "limits": ["HTML byte-equivalence is not an independent financial model audit.",
                   "Other sectors and unprobed pages are not certified."]
    }
    (out / "summary_pilot_audit.json").write_text(
        json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in outcome.items() if k != "rows"}, ensure_ascii=False), flush=True)
    if outcome["status"] != "PASS_BYTES":
        raise SystemExit(2)
    return outcome


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--core", type=Path, required=True)
    ap.add_argument("--stage", type=Path, required=True)
    ap.add_argument("--dataset", choices=SECTORS, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    execute(args.core, args.stage, args.dataset, args.out)
