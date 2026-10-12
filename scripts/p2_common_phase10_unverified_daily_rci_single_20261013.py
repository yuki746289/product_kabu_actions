# Created: 2026-10-13 JST
"""Phase10 incremental independent numerical QA: ONLY unverified daily RCI9/14 groups.

Reuses the Phase9 *auditor*, but neither its old success artifact nor its old
32-category workload. Checks 52 new saved direct-category rows against the
immutable original technology feature and canonical single-category CSVs.
No production/semantic/OR generation or existing artifact regeneration.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

import p2_common_phase9_direct_metric_parity_20261013 as phase9

NEW_FEATURES = tuple(
    f"daily_rci{span}_{group}"
    for span in (9, 14)
    for group in ("direction", "position", "state")
)
EXPECTED_REFERENCE_ROWS = 52


def selftest() -> None:
    assert len(NEW_FEATURES) == 6 and len(set(NEW_FEATURES)) == 6
    assert all(x not in phase9.SELECTED_FEATURES for x in NEW_FEATURES)
    assert phase9.finite("True") == 1.0 and phase9.finite("False") == 0.0
    assert phase9.finite("NaN") is None
    phase9.selftest()
    print("PASS: additional direct-category features and numeric parsing safeguards")


def verify(core: Path, source_evidence: Path) -> dict:
    # This process is dedicated to one incremental, single-threaded audit.
    # Keep the previous certified Phase9 32-category code/artifact untouched.
    original = phase9.SELECTED_FEATURES
    try:
        phase9.SELECTED_FEATURES = NEW_FEATURES
        result = phase9.audit(core, source_evidence)
    finally:
        phase9.SELECTED_FEATURES = original
    if result["reference_category_rows_checked"] != EXPECTED_REFERENCE_ROWS:
        raise ValueError("Expected exactly 52 new daily-RCI9/14 category rows")
    if result["selected_features"] != list(NEW_FEATURES):
        raise ValueError("Incremental selected features do not match fixed scope")
    if result["new_semantic_bundle_generated"] or result["new_or_bundle_generated"]:
        raise ValueError("Unapproved new computed artifact was produced")
    if result["status"] != "PASS_PHASE9_DIRECT_SAVED_NUMERIC_PARITY_PILOT_ONLY":
        result["status"] = "FAIL_PHASE10_DAILY_RCI9_14_DIRECT_NUMERIC_PARITY"
    else:
        result["status"] = "PASS_PHASE10_DAILY_RCI9_14_DIRECT_NUMERIC_PARITY_ONLY"
    result["original_phase9_32_categories_reexecuted"] = False
    result["expected_incremental_reference_rows"] = EXPECTED_REFERENCE_ROWS
    result["independent_numeric_fields_checked"] = (
        result["reference_category_rows_checked"]
        * result["numeric_fields_per_category"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--core", type=Path)
    parser.add_argument("--phase4", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if args.core is None or args.phase4 is None or args.out is None:
        parser.error("--core --phase4 --out are mandatory")
    target = args.out.resolve()
    if target.exists():
        raise FileExistsError("Never overwrite old QA output")
    audit = verify(args.core.resolve(), args.phase4.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({
        "status": audit["status"],
        "dataset": audit["dataset"],
        "new_categories": audit["reference_category_rows_checked"],
        "numeric_fields_checked": audit["independent_numeric_fields_checked"],
        "mismatches": audit["mismatched_fields"],
        "source_sha256": audit["source_sha256"],
        "release_ready": False,
    }, ensure_ascii=False))
    return 0 if audit["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    sys.exit(main())
