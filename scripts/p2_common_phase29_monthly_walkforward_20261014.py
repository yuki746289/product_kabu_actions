# Created: 2026-10-14T12:00:00+09:00
"""Phase29: independently compare four previously unverified semantic outputs.

Runs only monthly baseline x3 + walkforward x1 against immutable saved
canonical references for 7 datasets (transportation_utilities already PASS).
Requires Phase28 successful source-bound certificate. No prior artifacts rerun.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS = ("technology", "financials", "consumer_goods", "materials", "capital_goods_others")
EXCLUSIONS = {
    "exclude_capital_goods_transportation_utilities":
        (137426, 170, "cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"),
    "exclude_transportation_utilities":
        (166470, 205, "d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"),
}
DATASETS = GROUPS + tuple(EXCLUSIONS)
FILES = ("monthly_baseline_performance.csv",
         "monthly_baseline_stability_summary.csv",
         "month_of_year_baseline_summary.csv",
         "walkforward_results.csv")
EXPECTED_PREV = "PASS_PHASE28_ALL_REMAINING_SINGLES_BOUNDED"


def selftest() -> None:
    assert len(DATASETS) == 7 and len(set(DATASETS)) == 7
    assert len(FILES) == len(set(FILES)) == 4
    assert "transportation_utilities" not in DATASETS
    assert len(CORE_SHA) == 40 and all(x.endswith(".csv") for x in FILES)
    print("PASS_PHASE29_FOUR_CSV_NEW_SEMANTIC_SCOPE")


def verify(core: Path, reference: Path, source_root: Path, proof4: Path,
           proof28: Path, dataset: str, stage: Path) -> dict:
    if dataset not in DATASETS:
        raise ValueError("Disallowed or previously certified dataset")
    private_sha = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip()
    if private_sha != CORE_SHA:
        raise ValueError("Private code SHA drift")
    build = (core / "build").resolve()
    if stage.exists() or stage.resolve() == build or not stage.resolve().is_relative_to(build):
        raise ValueError("Require fresh isolated core/build stage")
    group = dataset in GROUPS
    expected_ref = (core / "preview/kabu/analysis" /
                    ("225_group_all_period" if group else "225_exclusion_all_period") /
                    dataset).resolve()
    if expected_ref != reference:
        raise ValueError("Reference folder not bound to dataset")
    if group:
        source = reference / "signal_level_features.csv"
    else:
        all_sources = list(source_root.rglob("features.csv"))
        if len(all_sources) != 1:
            raise ValueError("Require exactly one immutable original exclusion features.csv")
        source = all_sources[0]
    sys.path.insert(0, str(core / "scripts"))
    import pandas as pd
    import append_p2_nikkei_monthly_report as monthly
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import build_p2_225_semantic_bundle as common
    from p2_html_core.p03_common_analysis_plan import digest

    source_hash = digest(source)
    old = json.loads(proof4.read_text(encoding="utf-8"))
    if group:
        e = (old.get("groups") or {}).get(dataset) or {}
        if old.get("status") != "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
            raise ValueError("Phase4 group source identity proof not certified")
        rows, tickers = e.get("row_count"), e.get("ticker_count")
        if (e.get("csv_sha256") != source_hash or e.get("duplicate_ids") is not False
            or not isinstance(rows, int) or rows <= 0
            or not isinstance(tickers, int) or tickers <= 0):
            raise ValueError("Phase4 group SHA or cardinality changed")
    else:
        rows,tickers,expected_hash = EXCLUSIONS[dataset]
        e = old.get("saved_exclusion") or {}
        if (old.get("status") != "PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE"
            or old.get("variant") != dataset
            or source_hash != expected_hash
            or e.get("csv_sha256") != source_hash
            or e.get("row_count") != rows or e.get("ticker_count") != tickers
            or e.get("duplicate_ids") is not False):
            raise ValueError("Phase4 excluded original source proof mismatch")

    prior = json.loads(proof28.read_text(encoding="utf-8"))
    if (prior.get("status") != EXPECTED_PREV or
        prior.get("dataset") != dataset or
        prior.get("private_core_sha") != CORE_SHA or
        prior.get("source_sha256") != source_hash or
        prior.get("new_candidates") != prior.get("candidate_total", 0) - 9 or
        prior.get("mismatches") != [] or prior.get("release_ready") is not False):
        raise ValueError("Phase28 immutable numerical prior proof invalid")

    frame = common.prepare_frame(source)
    if len(frame) != rows or frame["ticker"].astype(str).nunique() != tickers:
        raise ValueError("Source identity cardinality mismatch")
    baseline = monthly._monthly_baseline(frame)
    fields, cats = aug._rep_fields(frame)
    tables = {
        "monthly_baseline_performance.csv": baseline,
        "monthly_baseline_stability_summary.csv": monthly._baseline_stability(baseline),
        "month_of_year_baseline_summary.csv": monthly._month_of_year(frame),
        "walkforward_results.csv": aug._walkforward(frame, fields, cats),
    }
    if any(t.empty for t in tables.values()):
        raise ValueError("Unexpected empty canonical semantic table")
    stage.mkdir(parents=True, exist_ok=False)
    problems = []
    evidence = {}
    for name in FILES:
        old_path = reference / name
        before = pd.read_csv(old_path, low_memory=False)
        generated = stage / name
        tables[name].to_csv(generated, index=False, encoding="utf-8")
        after = pd.read_csv(generated, low_memory=False)
        if list(before.columns) != list(after.columns) or before.shape != after.shape:
            problems.append({"file": name, "kind": "columns_or_rows"})
        else:
            try:
                pd.testing.assert_frame_equal(before, after, check_dtype=False,
                    check_exact=False, atol=1e-7, rtol=1e-10,
                    check_index_type=False)
            except AssertionError:
                problems.append({"file": name, "kind": "numeric_or_label"})
        evidence[name] = {
            "reference_rows": int(len(before)),
            "new_rows": int(len(after)),
            "columns": int(len(after.columns)),
            "reference_sha256": digest(old_path),
            "new_sha256": digest(generated),
        }
    if digest(source) != source_hash:
        raise ValueError("Original saved features bytes altered")
    return {
        "schema": 1,
        "status": ("PASS_PHASE29_NEW_MONTHLY_WALKFORWARD_FOUR_CSV" if not problems
                   else "FAIL_PHASE29_NEW_MONTHLY_WALKFORWARD_FOUR_CSV"),
        "dataset": dataset,
        "private_core_sha": CORE_SHA, "source_sha256": source_hash,
        "source_rows": rows, "source_tickers": tickers,
        "files": evidence, "mismatches": problems,
        "new_canonical_inner_functions_executed": True,
        "monthly_baseline_recalculated_before": False,
        "previous_artifacts_recalculated": False,
        "source_signals_recomputed": False,
        "full_semantic_or_computed": False,
        "html_generated": False,
        "production_changed": False,
        "release_ready": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dataset", choices=DATASETS)
    for n in ("core", "reference", "source-root", "proof4", "proof28", "stage", "report"):
        ap.add_argument("--" + n, type=Path)
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    needed = ("dataset", "core", "reference", "source_root", "proof4",
              "proof28", "stage", "report")
    if any(getattr(args, n) is None for n in needed):
        ap.error("Immutable source, preceding proofs, dataset, stage and report required")
    if args.report.exists():
        raise FileExistsError("Certified evidence must not be overwritten")
    result = verify(args.core.resolve(), args.reference.resolve(),
                    args.source_root.resolve(), args.proof4.resolve(),
                    args.proof28.resolve(), args.dataset, args.stage.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": result["status"], "dataset": result["dataset"],
        "source_rows": result["source_rows"], "files": result["files"],
        "mismatches": result["mismatches"]}, ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
