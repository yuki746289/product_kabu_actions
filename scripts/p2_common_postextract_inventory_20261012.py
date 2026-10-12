# Created: 2026-10-12T18:12:00+09:00
"""Public-runner, read-only P2 dataset inventory and independent readiness summary.

The private core is pinned to a commit and never changed. This script does not
read CSV contents or recompute semantic data; it inspects only Git tree names
and the existing status.json evidence saved in the private release.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

DATASETS = {
    "nikkei_index": "",
    "all_225": "analysis/225_indicator_stageb",
    "technology": "analysis/225_group_all_period/technology",
    "financials": "analysis/225_group_all_period/financials",
    "consumer_goods": "analysis/225_group_all_period/consumer_goods",
    "materials": "analysis/225_group_all_period/materials",
    "capital_goods_others": "analysis/225_group_all_period/capital_goods_others",
    "transportation_utilities": "analysis/225_group_all_period/transportation_utilities",
    "exclude_transportation_utilities":
        "analysis/225_exclusion_all_period/exclude_transportation_utilities",
    "exclude_capital_goods_transportation_utilities":
        "analysis/225_exclusion_all_period/exclude_capital_goods_transportation_utilities",
}
ROOT = "preview/kabu"
EXPECTED_LOCAL_CSV = {
    "nikkei_index": 0, "all_225": 0,
    **{x: 29 for x in ("technology", "financials", "consumer_goods",
                       "materials", "capital_goods_others",
                       "transportation_utilities")},
    "exclude_transportation_utilities": 28,
    "exclude_capital_goods_transportation_utilities": 28,
}


def git(core: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(core), *args], text=True, encoding="utf-8"
    ).strip()


def dataset_dir(dataset: str) -> str:
    sub = DATASETS[dataset]
    return ROOT + ("/" + sub if sub else "")


def direct_csv_tree(core: Path, dataset: str) -> list[str]:
    root = dataset_dir(dataset)
    text = git(core, "ls-tree", "-r", "--name-only", "HEAD", "--", root)
    return sorted(Path(p).name for p in text.splitlines()
                  if Path(p).parent.as_posix() == root and p.endswith(".csv"))


def read_semantic_status(core: Path, dataset: str) -> dict | None:
    if dataset in ("nikkei_index", "all_225"):
        return None
    location = dataset_dir(dataset) + "/semantic_status.json"
    try:
        raw = git(core, "show", "HEAD:" + location)
    except subprocess.CalledProcessError:
        return None
    return json.loads(raw)


def audit(core: Path, source_sha: str, expected_names: list[str]) -> dict:
    if git(core, "rev-parse", "HEAD") != source_sha:
        raise ValueError("Private core SHA differs from pinned expected SHA")
    if len(expected_names) != 29 or len(set(expected_names)) != 29:
        raise ValueError("Canonical CSV file contract not exactly 29 unique names")
    reports = []
    for name in DATASETS:
        names = direct_csv_tree(core, name)
        semantic = read_semantic_status(core, name)
        missing = sorted(set(expected_names) - set(names))
        unexpected = sorted(set(names) - set(expected_names))
        known_expected = EXPECTED_LOCAL_CSV[name]
        structural_pass = (
            len(names) == known_expected and not unexpected and
            (name in ("nikkei_index", "all_225") or
             (name.startswith("exclude_") and missing == ["signal_level_features.csv"]) or
             (name not in ("nikkei_index", "all_225") and not missing))
        )
        existing_evidence_pass = (
            isinstance(semantic, dict) and semantic.get("overall_pass") is True
            and semantic.get("source_rows", 0) > 0
            and semantic.get("source_tickers", 0) > 0
            if semantic is not None else False
        )
        reports.append({
            "dataset": name, "local_csv_count": len(names),
            "expected_local_csv_count": known_expected,
            "schema_filenames_pass": structural_pass,
            "missing_saved_csv": missing,
            "unexpected_saved_csv": unexpected,
            "saved_semantic_status_pass": existing_evidence_pass,
            "existing_rows": semantic.get("source_rows") if semantic else None,
            "existing_tickers": semantic.get("source_tickers") if semantic else None,
            "ready_for_shared_rerender": False,
            "blocker": (
                "resolve_pinned_saved_source" if not names or missing else
                "verify_full_schema_and_numeric_parity"
            ),
        })
    return {
        "schema": 1, "status": "PASS_INVENTORY_ONLY_FURTHER_QA_REQUIRED"
        if all(x["schema_filenames_pass"] for x in reports)
        else "FAIL_UNEXPECTED_DATASET_INVENTORY",
        "private_core_sha": source_sha,
        "checked_dataset_count": len(reports),
        "dataset_results": reports,
        "numeric_equivalence_verified": False,
        "all_29_csv_headers_checked": False,
        "full_html_qa_verified": False,
        "actions_ran_only_in_public": True,
        "source_data_recomputed": False,
        "saved_artifacts_reused": True,
        "production_changed": False,
        "release_ready": False,
        "deployment_performed": False,
    }


def selftest() -> None:
    assert len(DATASETS) == 10
    assert all(EXPECTED_LOCAL_CSV[x] == 29 for x in (
        "technology", "financials", "consumer_goods", "materials",
        "capital_goods_others", "transportation_utilities"))
    assert dataset_dir("nikkei_index") == "preview/kabu"
    assert dataset_dir("financials").endswith("/financials")
    print("PASS: dataset inventory checker selftest")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", type=Path)
    ap.add_argument("--expected-core-sha")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not all((args.core, args.expected_core_sha, args.output)):
        ap.error("--core, --expected-core-sha and --output are required")
    core = args.core.resolve()
    scripts = core / "scripts"
    sys.path.insert(0, str(scripts))
    from p2_html_core.p02_semantic_io_contract import CSV_FILES
    result = audit(core, args.expected_core_sha, list(CSV_FILES))
    out = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise FileExistsError(out)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "datasets": len(result["dataset_results"]),
        "private_core_sha": result["private_core_sha"],
        "release_ready": False,
        "issues": [
            {"dataset": r["dataset"], "missing_saved_csv_count": len(r["missing_saved_csv"]),
             "structure_pass": r["schema_filenames_pass"]}
            for r in result["dataset_results"]
        ],
    }, ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
