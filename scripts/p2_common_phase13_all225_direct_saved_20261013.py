# Created: 2026-10-13 JST
"""Phase13: numerical parity for all-225 direct RCI/regime categories from saved artifacts.

Read pre-existing source+semantic-base artifact CSVs only; do not recompute
source signals, semantic bundles, OR, HTML or successful QA artifacts.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

import p2_common_phase9_direct_metric_parity_20261013 as base
from p2_common_phase11_other_sector_direct_metrics_20261013 import (
    FEATURES, EXPECTED_CATEGORY_ROWS, EXPECTED_NUMERIC_PER_CATEGORY,
)

SOURCE_SHA256 = "71fb0dc947a4777610fec2d07e08fac168a7ab1d49ac5028c39ad1b7ec03bdc9"
SOURCE_RUN_ID = 36703088996
SOURCE_ARTIFACT_ID = 11093338366
SEMANTIC_RUN_ID = 36711913770
SEMANTIC_ARTIFACT_ID = 11094611818
EXPECTED_ROWS = 181318
EXPECTED_TICKERS = 225


def only_one(root: Path, basename: str) -> Path:
    found = list(root.rglob(basename))
    if len(found) != 1 or not found[0].is_file():
        raise ValueError(f"Expected one immutable {basename}, got {len(found)}")
    return found[0]


def selftest():
    base.selftest()
    assert len(FEATURES) == 10
    assert EXPECTED_CATEGORY_ROWS == 84
    assert EXPECTED_ROWS == 48782+16307+33330+39007+29044+14848
    assert SOURCE_RUN_ID != SEMANTIC_RUN_ID
    print("PASS: all225 source+semantic-base artifact identity and reducer gates")


def verify(source_root: Path, semantic_root: Path, source_evidence: Path) -> dict:
    source = only_one(source_root, "features.csv")
    ref = only_one(semantic_root, "all_single_categories.csv")
    status_path = only_one(semantic_root, "semantic_base_status.json")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if (status.get("overall_pass") is not True or
        status.get("source_rows") != EXPECTED_ROWS or
        status.get("source_tickers") != EXPECTED_TICKERS or
        status.get("all_single_rows") != 2460):
        raise ValueError("Saved historical semantic-base artifact has wrong certified population")
    original = json.loads(source_evidence.read_text(encoding="utf-8"))
    if original.get("status") != "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
        raise ValueError("Missing independently certified pinned source IDs")
    info = original.get("source") or {}
    observed_source_hash = base.hash_file(source)
    if (observed_source_hash != SOURCE_SHA256 or
        info.get("csv_sha256") != SOURCE_SHA256 or
        info.get("row_count") != EXPECTED_ROWS or
        info.get("ticker_count") != EXPECTED_TICKERS):
        raise ValueError("Source bytes or identity differ from immutable historic artifacts")
    old_selected = base.SELECTED_FEATURES
    try:
        base.SELECTED_FEATURES = FEATURES
        reference = base.load_reference(ref)
        if len(reference) != EXPECTED_CATEGORY_ROWS:
            raise ValueError(f"Expected exactly 84 untested canonical rows, got {len(reference)}")
        full, cats = base.calculate_direct(source, set(reference), EXPECTED_ROWS)
    finally:
        base.SELECTED_FEATURES = old_selected
    issues = base.numeric_failures(full, cats, reference)
    return {
        "schema_version": 1,
        "status": "PASS_PHASE13_ALL225_DIRECT_NUMERIC_PARITY_ONLY"
        if not issues else "FAIL_PHASE13_ALL225_DIRECT_NUMERIC_PARITY",
        "dataset": "all_225",
        "source_run_id": SOURCE_RUN_ID, "source_artifact_id": SOURCE_ARTIFACT_ID,
        "semantic_run_id": SEMANTIC_RUN_ID, "semantic_artifact_id": SEMANTIC_ARTIFACT_ID,
        "source_csv_sha256": observed_source_hash,
        "reference_all_single_csv_sha256": base.hash_file(ref),
        "source_rows": EXPECTED_ROWS,
        "source_tickers": EXPECTED_TICKERS,
        "categories_checked": len(reference),
        "numeric_metrics_checked": len(reference) * EXPECTED_NUMERIC_PER_CATEGORY,
        "numeric_mismatches": len(issues),
        "first_issues": issues[:15],
        "existing_semantic_or_recomputed": False,
        "historical_artifacts_regenerated": False,
        "nikkei_index_data_substituted": False,
        "production_changed": False, "html_qa_verified": False,
        "release_ready": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--source-root", type=Path)
    p.add_argument("--semantic-root", type=Path)
    p.add_argument("--source-evidence", type=Path)
    p.add_argument("--out", type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not all((a.source_root, a.semantic_root, a.source_evidence, a.out)):
        p.error("--source-root, --semantic-root, --source-evidence and --out required")
    output=a.out.resolve()
    if output.exists():
        raise FileExistsError("Fresh isolated QA destination required")
    result=verify(a.source_root.resolve(),a.semantic_root.resolve(),
                  a.source_evidence.resolve())
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="first_issues"},ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
