# Created: 2026-10-13 JST
"""Phase26 canary: three NEW monthly semantic outputs vs immutable saved CSVs.

Runs only the same three monthly inner functions used by the pinned new
common semantic producer. Does not recompute any Phase20-25 certified file,
legacy artifact, P2 signal, OR bundle, full semantic bundle, or HTML.
The public artifact contains summary JSON only, never private CSV rows.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASET = "transportation_utilities"
ROWS = 14848
TICKERS = 20
FILES = (
    "monthly_baseline_performance.csv",
    "monthly_baseline_stability_summary.csv",
    "month_of_year_baseline_summary.csv",
)


def selftest() -> None:
    assert len(FILES) == len(set(FILES)) == 3
    assert all(x.endswith(".csv") for x in FILES)
    assert len(CORE_SHA) == 40
    assert ROWS == 14848 and TICKERS == 20
    print("PASS_PHASE26_MONTHLY_CANARY_CONTRACT")


def verify(core: Path, reference: Path, phase4: Path, phase20: Path,
           stage: Path) -> dict:
    if subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
    ).strip() != CORE_SHA:
        raise ValueError("Pinned Private core SHA mismatch")

    build = (core / "build").resolve()
    if stage.exists() or not stage.resolve().is_relative_to(build) or stage.resolve() == build:
        raise ValueError("New isolated core/build stage required")

    sys.path.insert(0, str(core / "scripts"))
    import pandas as pd
    import build_p2_225_semantic_bundle as new_common
    import append_p2_nikkei_monthly_report as inner
    from p2_html_core.p03_common_analysis_plan import digest

    source = reference / "signal_level_features.csv"
    source_sha = digest(source)
    group = json.loads(phase4.read_text(encoding="utf-8"))
    original = (group.get("groups") or {}).get(DATASET) or {}
    if group.get("status") != "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
        raise ValueError("Missing previous six-sector immutable source identity PASS")
    if (original.get("csv_sha256") != source_sha or
        original.get("row_count") != ROWS or
        original.get("ticker_count") != TICKERS or
        original.get("duplicate_ids") is not False):
        raise ValueError("Original pinned source identity/hash mismatch")

    proof = json.loads(phase20.read_text(encoding="utf-8"))
    if (proof.get("status") != "PASS_PHASE20_NEW_COMMON_SEMANTIC_SUBSET_NUMERIC_PARITY" or
        proof.get("dataset") != DATASET or
        proof.get("private_code_and_data_sha") != CORE_SHA or
        proof.get("source_sha256") != source_sha or
        proof.get("source_rows") != ROWS or
        proof.get("source_tickers") != TICKERS or
        proof.get("csvs_independently_numeric_equal") != 4 or
        proof.get("mismatches")):
        raise ValueError("Previous four-file computation parity proof not certified")

    frame = new_common.prepare_frame(source)
    if len(frame) != ROWS or frame["ticker"].astype(str).nunique() != TICKERS:
        raise ValueError("New common preprocessing changed saved source population")

    # Call precisely the inner functions invoked by
    # build_p2_225_canonical_semantic_data.build(); no other semantic step.
    monthly = inner._monthly_baseline(frame)
    calculated = {
        FILES[0]: monthly,
        FILES[1]: inner._baseline_stability(monthly),
        FILES[2]: inner._month_of_year(frame),
    }
    if (len(calculated[FILES[0]]) < 100 or
        len(calculated[FILES[1]]) != 9 or
        len(calculated[FILES[2]]) != 12):
        raise ValueError("Unexpected month-count contract")
    stage.mkdir(parents=True, exist_ok=False)
    details = []
    errors = []
    for name in FILES:
        old = reference / name
        if not old.is_file():
            raise FileNotFoundError("Missing pinned original: " + name)
        new = stage / name
        calculated[name].to_csv(new, index=False, encoding="utf-8")
        saved = pd.read_csv(old, low_memory=False)
        actual = pd.read_csv(new, low_memory=False)
        equal = True
        if list(saved.columns) != list(actual.columns):
            errors.append({"file": name, "reason": "header_order"})
            equal = False
        elif saved.shape != actual.shape:
            errors.append({"file": name, "reason": "row_or_column_count"})
            equal = False
        else:
            try:
                pd.testing.assert_frame_equal(
                    saved, actual, check_dtype=False, check_exact=False,
                    atol=1e-7, rtol=1e-10, check_index_type=False,
                )
            except AssertionError:
                errors.append({"file": name, "reason": "numerical_or_label_mismatch"})
                equal = False
        details.append({
            "file": name, "rows": len(saved), "columns": len(saved.columns),
            "saved_original_sha256": digest(old),
            "new_computed_sha256": digest(new),
            "numerically_equal": equal,
        })
    if digest(source) != source_sha:
        raise ValueError("Original saved source mutated")
    passed = not errors and len(details) == len(FILES)
    return {
        "schema": 1,
        "status": "PASS_PHASE26_MONTHLY_THREE_CSV_CANARY"
                  if passed else "FAIL_PHASE26_MONTHLY_THREE_CSV_CANARY",
        "dataset": DATASET,
        "private_core_sha": CORE_SHA,
        "original_source_sha256": source_sha,
        "source_rows": ROWS,
        "source_tickers": TICKERS,
        "new_common_inner_functions_called": [
            "_monthly_baseline", "_baseline_stability", "_month_of_year"],
        "compared_csvs": len(details),
        "csv_details": details,
        "mismatches": errors,
        "previous_certified_four_csvs_recalculated": False,
        "full_semantic_bundle_generated": False,
        "full_or_bundle_generated": False,
        "signals_recomputed": False,
        "html_generated": False,
        "production_changed": False,
        "release_ready": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    for name in ("core", "reference", "phase4", "phase20", "stage", "report"):
        ap.add_argument("--" + name, type=Path)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if any(getattr(a, k) is None for k in
           ("core", "reference", "phase4", "phase20", "stage", "report")):
        ap.error("All saved source, reference and evidence paths required")
    report = a.report.resolve()
    if report.exists():
        raise FileExistsError("Cannot overwrite prior evidence")
    result = verify(a.core.resolve(), a.reference.resolve(),
                    a.phase4.resolve(), a.phase20.resolve(), a.stage.resolve())
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("csv_details", "mismatches")}))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
