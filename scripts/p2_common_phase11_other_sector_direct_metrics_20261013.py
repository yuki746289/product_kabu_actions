# Created: 2026-10-13 JST
"""Phase11: independent, additional five-sector direct single-category numerical QA.

Reuses the fixed Phase9 numeric reducer and the existing Phase4 saved source
identity proof. The already-PASS technology sector is NOT processed again.
Saved CSVs are only read; semantic / OR / HTML generators are never invoked.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
import sys

import p2_common_phase9_direct_metric_parity_20261013 as base

PINNED_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS = {
    "financials": (16307, 20),
    "consumer_goods": (33330, 41),
    "materials": (39007, 48),
    "capital_goods_others": (29044, 35),
    "transportation_utilities": (14848, 20),
}
FEATURES = ("causal_regime",) + tuple(
    f"daily_rci{span}_{suffix}"
    for span in (9, 14, 26)
    for suffix in ("position", "direction", "state")
)
EXPECTED_CATEGORY_ROWS = 84
EXPECTED_NUMERIC_PER_CATEGORY = 14


def selftest() -> None:
    base.selftest()
    assert len(GROUPS) == 5 and "technology" not in GROUPS
    assert len(FEATURES) == 10
    assert len(set(FEATURES)) == 10
    assert base.finite("True") == 1 and base.finite("False") == 0
    assert EXPECTED_CATEGORY_ROWS == 32 + 52
    assert set(base.SELECTED_FEATURES).issubset(FEATURES)
    print("PASS: phase11 incremental source and feature gates")


def audit(core: Path, pin_file: Path, dataset: str) -> dict:
    if dataset not in GROUPS:
        raise ValueError("Dataset is not an unverified sector")
    actual_sha = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip()
    if actual_sha != PINNED_SHA:
        raise ValueError("Saved Private source SHA mismatch")
    evidence = json.loads(pin_file.read_text(encoding="utf-8"))
    if evidence.get("status") != "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
        raise ValueError("Independent Phase4 group identity proof missing")
    expected_rows, expected_tickers = GROUPS[dataset]
    root = core / "preview/kabu/analysis/225_group_all_period" / dataset
    source = root / "signal_level_features.csv"
    ref = root / "all_single_categories.csv"
    status = json.loads((root / "semantic_status.json").read_text(encoding="utf-8"))
    if status.get("overall_pass") is not True or status.get("or_full_universe_pass") is not True:
        raise ValueError("Prior saved canonical analysis was not PASS")
    if status.get("source_rows") != expected_rows or status.get("source_tickers") != expected_tickers:
        raise ValueError("Saved population metadata disagrees with Phase4")
    prev = evidence.get("groups", {}).get(dataset) or {}
    source_digest = base.hash_file(source)
    if (prev.get("csv_sha256") != source_digest or
            prev.get("row_count") != expected_rows or
            prev.get("ticker_count") != expected_tickers or
            prev.get("duplicate_ids") is not False):
        raise ValueError("Saved source sha/shape differs from Phase4 independent proof")
    old_features = base.SELECTED_FEATURES
    try:
        base.SELECTED_FEATURES = FEATURES
        reference = base.load_reference(ref)
        if len(reference) != EXPECTED_CATEGORY_ROWS:
            raise ValueError(f"Expected 84 directly measurable category rows: {len(reference)}")
        full, categories = base.calculate_direct(source, set(reference), expected_rows)
    finally:
        base.SELECTED_FEATURES = old_features
    issues = base.numeric_failures(full, categories, reference)
    return {
        "schema": 1,
        "status": "PASS_PHASE11_DIRECT_CATEGORY_NUMERIC_PARITY_ONLY"
            if not issues else "FAIL_PHASE11_DIRECT_CATEGORY_NUMERIC_PARITY",
        "dataset": dataset, "private_core_sha": PINNED_SHA,
        "source_sha256": source_digest,
        "reference_csv_sha256": base.hash_file(ref),
        "source_rows": expected_rows, "source_tickers": expected_tickers,
        "independently_checked_categories": len(reference),
        "independently_checked_numeric_fields": len(reference) * EXPECTED_NUMERIC_PER_CATEGORY,
        "mismatches": len(issues), "first_errors": issues[:15],
        "technology_previous_success_reexecuted": False,
        "original_saved_artifacts_recomputed": False,
        "new_semantic_or_generated": False,
        "production_modified": False, "html_qa_verified": False,
        "release_ready": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dataset", choices=sorted(GROUPS))
    ap.add_argument("--core", type=Path)
    ap.add_argument("--phase4", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if a.dataset is None or a.core is None or a.phase4 is None or a.out is None:
        ap.error("--dataset --core --phase4 --out are required")
    dest = a.out.resolve()
    if dest.exists():
        raise FileExistsError("Cannot overwrite existing audit output")
    result = audit(a.core.resolve(), a.phase4.resolve(), a.dataset)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "first_errors"},
                     ensure_ascii=False))
    if not result["status"].startswith("PASS_"):
        print("::error::New dataset numerical mismatches", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
