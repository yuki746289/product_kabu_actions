# Created: 2026-10-12T19:19:00+09:00
"""Audit stored P2 cohort partition counts from successful phase2 JSON only.

No raw feature rows are downloaded. Aggregate row/ticker consistency alone is
NOT evidence of per-signal partition identity or computational equivalence.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

PRIVATE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS = ("technology", "financials", "consumer_goods", "materials",
          "capital_goods_others", "transportation_utilities")
EXCLUDED = {
    "exclude_transportation_utilities": ("transportation_utilities",),
    "exclude_capital_goods_transportation_utilities":
        ("capital_goods_others", "transportation_utilities"),
}
REQUIRED_ARTIFACTS = (
    ("p2-225-raw-features-20260930", 36703088996),
    ("p2-225-raw-canonical-mirror-asset-final", 36979444713),
)


def report(reports: dict[str, dict], artifact_responses: dict[int, dict]) -> dict:
    errors = []
    expected_names = set(GROUPS) | set(EXCLUDED)
    if set(reports) != expected_names:
        errors.append("Expected exactly 8 unique cohort reports")
    for name in expected_names & set(reports):
        data = reports[name]
        if data.get("dataset") != name or data.get("source_core_sha") != PRIVATE_SHA:
            errors.append("Invalid pinned source/dataset on " + name)
        if data.get("production_changed") is not False or data.get("release_ready") is not False:
            errors.append("Unsafe release assertion on " + name)
        if data.get("numeric_equivalence_verified") is not False:
            errors.append("Unexpected numerical certification " + name)
        if name in GROUPS:
            if data.get("status") != "PASS_SAVED_SCHEMA_AND_SOURCE_POPULATION":
                errors.append("Group schema not PASS " + name)
            if data.get("ordered_headers_equal") != 29:
                errors.append("Group 29 headers not identical " + name)
            if (data.get("validated_saved_signal_population") or {}).get("unique_identity") is not True:
                errors.append("Group signal uniqueness not verified " + name)
        else:
            if data.get("status") != "PASS_SAVED_SCHEMA_EXCLUSION_SOURCE_UNRESOLVED":
                errors.append("Exclusion source unexpectedly claimed complete " + name)
            if data.get("ordered_headers_equal") != 28:
                errors.append("Exclusion 28 headers not identical " + name)
    if errors:
        return {"status": "FAIL_AGGREGATE_PROVENANCE", "errors": errors,
                "numeric_equivalence_verified": False, "release_ready": False}

    def counts(group: str) -> tuple[int, int]:
        x = reports[group]
        return int(x["semantic_status_rows"]), int(x["semantic_status_tickers"])

    total_rows = sum(counts(group)[0] for group in GROUPS)
    total_tickers = sum(counts(group)[1] for group in GROUPS)
    if (total_rows, total_tickers) != (181318, 225):
        errors.append("Six-group total does not match saved canonical 225 population")
    checks = []
    for variant, exclusions in EXCLUDED.items():
        rows, tickers = counts(variant)
        expected_rows = total_rows - sum(counts(ex)[0] for ex in exclusions)
        expected_tickers = total_tickers - sum(counts(ex)[1] for ex in exclusions)
        is_valid = (rows, tickers) == (expected_rows, expected_tickers)
        if not is_valid:
            errors.append("Aggregate exclusion complement mismatch: " + variant)
        checks.append({"dataset": variant, "status": "PASS_COUNTS" if is_valid else "FAIL",
                       "rows": rows, "tickers": tickers,
                       "expected_rows": expected_rows, "expected_tickers": expected_tickers})
    locators = []
    for name, run_id in REQUIRED_ARTIFACTS:
        root = artifact_responses.get(run_id, {})
        matches = [a for a in root.get("artifacts", [])
                   if a.get("name") == name and not a.get("expired") and
                      int(a.get("size_in_bytes", 0)) > 0]
        if len(matches) != 1:
            errors.append("Missing or expired saved source artifact " + name)
        else:
            item = matches[0]
            locators.append({"run_id": run_id, "artifact_name": name,
                             "artifact_id": item["id"],
                             "zip_size_bytes": item["size_in_bytes"],
                             "file_content_sha256": "NOT_YET_PINNED"})
    return {
        "schema": 1, "status": "PASS_SAVED_POPULATION_AGGREGATES_ONLY" if not errors
                              else "FAIL_AGGREGATE_PROVENANCE",
        "errors": errors, "phase2_core_sha": PRIVATE_SHA, "phase2_data_sets": len(reports),
        "saved_six_sector_total_rows": total_rows,
        "saved_six_sector_total_tickers": total_tickers,
        "expected_canonical_rows": 181318, "expected_canonical_tickers": 225,
        "excluded_complements": checks, "saved_source_artifact_locators": locators,
        "full_saved_signal_partition_identity_checked": False,
        "full_numeric_equivalence_verified": False,
        "all_10_datasets_have_pinned_sources": False,
        "csv_byte_parity_verified": False, "html_qa_verified": False,
        "source_signals_recomputed": False, "production_changed": False,
        "release_ready": False, "deployment_performed": False,
    }


def read_reports(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    paths = sorted(root.glob("p2-common-schema-*/audit.json"))
    if len(paths) != 8:
        raise ValueError(f"Expected eight completed phase2 reports: got {len(paths)}")
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        dataset = data.get("dataset")
        if dataset in out:
            raise ValueError("Duplicate dataset report: " + str(dataset))
        out[dataset] = data
    return out


def selftest():
    group_rows = [48782, 16307, 33330, 39007, 29044, 14848]
    group_tickers = [61, 20, 41, 48, 35, 20]
    assert sum(group_rows) == 181318
    assert sum(group_tickers) == 225
    assert 181318 - 14848 == 166470
    assert 181318 - 14848 - 29044 == 137426
    assert 225 - 20 - 35 == 170
    print("PASS: aggregate invariant selftest")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase2-evidence", type=Path)
    ap.add_argument("--saved-run-metadata", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not all((args.phase2_evidence, args.saved_run_metadata, args.out)):
        ap.error("Pass --phase2-evidence, --saved-run-metadata and --out")
    reports = read_reports(args.phase2_evidence)
    artifact_responses = {
        r: json.loads((args.saved_run_metadata / f"{r}.json").read_text(encoding="utf-8"))
        for _, r in REQUIRED_ARTIFACTS
    }
    result = report(reports, artifact_responses)
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("Audit result cannot overwrite older evidence")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    sys.exit(main())
