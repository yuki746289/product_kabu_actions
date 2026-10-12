# Created: 2026-10-13 JST
"""Phase12: independent direct single-category numeric QA for TWO exclusions.

Only saved filtered feature artifacts and immutable private approved reference
CSV are read; zero Production, feature extraction, semantic/OR regeneration.
The already-PASS six sectors and their QA artifacts are never rerun.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
import sys

import p2_common_phase9_direct_metric_parity_20261013 as base
from p2_common_phase11_other_sector_direct_metrics_20261013 import (
    FEATURES, EXPECTED_CATEGORY_ROWS, EXPECTED_NUMERIC_PER_CATEGORY,
)

PRIVATE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
EXCLUSIONS = {
    "exclude_transportation_utilities": {
        "rows": 166470, "tickers": 205,
        "sha256": "d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1",
        "run_id": 37201518110, "artifact_id": 11303406552,
        "name": "p2-225-exclusion-no-transport-features",
    },
    "exclude_capital_goods_transportation_utilities": {
        "rows": 137426, "tickers": 170,
        "sha256": "cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
        "run_id": 37201520569, "artifact_id": 11302906875,
        "name": "p2-225-exclusion-no-capital-transport-features",
    },
}


def selftest() -> None:
    base.selftest()
    assert len(EXCLUSIONS) == 2
    assert len(FEATURES) == 10
    assert EXPECTED_CATEGORY_ROWS == 84
    for x in EXCLUSIONS.values():
        assert x["rows"] > 100000 and x["tickers"] > 0
        assert len(x["sha256"]) == 64 and x["artifact_id"] > 0
    print("PASS: phase12 exclusion provenance and independent reducer safeguards")


def verify(core: Path, saved_root: Path, proof_file: Path, dataset: str) -> dict:
    if dataset not in EXCLUSIONS:
        raise ValueError("Unverified exclusion dataset only")
    if subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"],
                               text=True).strip() != PRIVATE_SHA:
        raise ValueError("Private reference SHA changed")
    config = EXCLUSIONS[dataset]
    saved = list(saved_root.rglob("features.csv"))
    if len(saved) != 1:
        raise ValueError(f"Exactly one saved filtered features.csv required: {len(saved)}")
    source = saved[0]
    source_sha = base.hash_file(source)
    if source_sha != config["sha256"]:
        raise ValueError("Saved exclusion source differs from pinned original SHA256")
    proof = json.loads(proof_file.read_text(encoding="utf-8"))
    if proof.get("status") != "PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE":
        raise ValueError("Previous independent exclusion identity evidence did not PASS")
    if proof.get("variant") != dataset:
        raise ValueError("Wrong prior exclusion dataset proof")
    seen = proof.get("saved_exclusion") or {}
    if (seen.get("csv_sha256") != source_sha or
            seen.get("row_count") != config["rows"] or
            seen.get("ticker_count") != config["tickers"]):
        raise ValueError("Stored source SHA, rows or tickers mismatch Phase4 proof")
    directory = ("preview/kabu/analysis/225_exclusion_all_period/" + dataset)
    folder = core / directory
    original = folder / "all_single_categories.csv"
    status = json.loads((folder / "semantic_status.json").read_text(encoding="utf-8"))
    if (status.get("overall_pass") is not True or
            status.get("or_full_universe_pass") is not True or
            status.get("source_rows") != config["rows"] or
            status.get("source_tickers") != config["tickers"]):
        raise ValueError("Saved status is not independently certified")
    before = base.SELECTED_FEATURES
    try:
        base.SELECTED_FEATURES = FEATURES
        reference = base.load_reference(original)
        if len(reference) != EXPECTED_CATEGORY_ROWS:
            raise ValueError(f"Expected precisely 84 saved direct-category rows: {len(reference)}")
        full, cats = base.calculate_direct(source, set(reference), config["rows"])
    finally:
        base.SELECTED_FEATURES = before
    mismatches = base.numeric_failures(full, cats, reference)
    return {
        "schema": 1,
        "status": "PASS_PHASE12_EXCLUSION_DIRECT_NUMERIC_PARITY_ONLY"
            if not mismatches else "FAIL_PHASE12_EXCLUSION_DIRECT_NUMERIC_PARITY",
        "dataset": dataset,
        "pinned_source_sha256": source_sha,
        "private_reference_sha": PRIVATE_SHA,
        "reference_csv_sha256": base.hash_file(original),
        "source_run_id": config["run_id"],
        "source_artifact_id": config["artifact_id"],
        "source_rows": full.n,
        "source_tickers": config["tickers"],
        "categories_verified": len(reference),
        "numeric_fields_verified": len(reference)*EXPECTED_NUMERIC_PER_CATEGORY,
        "numeric_mismatches": len(mismatches),
        "error_examples": mismatches[:12],
        "all_prior_successes_reused": True,
        "feature_extraction_performed": False,
        "semantic_or_recomputed": False,
        "saved_artifacts_recomputed": False,
        "html_qa_verified": False,
        "production_changed": False,
        "release_ready": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dataset", choices=sorted(EXCLUSIONS))
    ap.add_argument("--core", type=Path)
    ap.add_argument("--saved-root", type=Path)
    ap.add_argument("--proof", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not all((args.core, args.saved_root, args.proof, args.out, args.dataset)):
        ap.error("--core --saved-root --proof --dataset --out required")
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("Cannot overwrite previous QA output")
    data = verify(args.core.resolve(), args.saved_root.resolve(),
                  args.proof.resolve(), args.dataset)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k != "error_examples"},ensure_ascii=False))
    return 0 if data["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    sys.exit(main())
