# Created: 2026-10-12T19:19:00+09:00
"""Read-only phase-2 P2 CSV header contract audit using pinned saved source.

One immutable reference schema is generated from the stored technology data.
Each group/exclusion then compares every existing CSV header and validates the
saved 6-group signal population. Exclusions with no published signal CSV are
explicitly marked blocked. No analysis, HTML, migration or deployment.
"""
from __future__ import annotations
import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PRIVATE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASETS = {
    "technology": "225_group_all_period/technology",
    "financials": "225_group_all_period/financials",
    "consumer_goods": "225_group_all_period/consumer_goods",
    "materials": "225_group_all_period/materials",
    "capital_goods_others": "225_group_all_period/capital_goods_others",
    "transportation_utilities": "225_group_all_period/transportation_utilities",
    "exclude_transportation_utilities": "225_exclusion_all_period/exclude_transportation_utilities",
    "exclude_capital_goods_transportation_utilities": "225_exclusion_all_period/exclude_capital_goods_transportation_utilities",
}
CORE_PREFIX = "preview/kabu/analysis/"
SIGNAL = "signal_level_features.csv"


def expected_files(core: Path) -> tuple[str, ...]:
    source = core / "scripts/p2_html_core/p02_semantic_io_contract.py"
    parsed = ast.parse(source.read_text(encoding="utf-8"))
    for node in parsed.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "CSV_FILES" for t in node.targets
        ):
            names = ast.literal_eval(node.value)
            if isinstance(names, tuple) and len(names) == 29 and len(set(names)) == 29:
                return names
    raise RuntimeError("Cannot resolve canonical 29-file literal contract")


def current_sha(core: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
    ).strip()


def saved_folder(core: Path, dataset: str) -> Path:
    return core / CORE_PREFIX / DATASETS[dataset]


def read_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.reader(handle), None)
    if not row or any(not col or col != col.strip() for col in row) or len(row) != len(set(row)):
        raise ValueError("Invalid, empty or duplicated header: " + path.name)
    return tuple(row)


def signed_source_info(core: Path, dataset: str, file: str) -> dict:
    path = CORE_PREFIX + DATASETS[dataset] + "/" + file
    line = subprocess.check_output(
        ["git", "-C", str(core), "ls-tree", "-l", "HEAD", "--", path], text=True
    ).strip()
    if not line:
        raise FileNotFoundError(path)
    # 100644 blob <git_object_sha> <size_bytes> TAB <path>
    metadata = line.split("\t", 1)[0].split()
    if len(metadata) != 4 or metadata[1] != "blob":
        raise ValueError("Not an immutable tracked blob: " + path)
    return {"git_blob_sha": metadata[2], "bytes": int(metadata[3])}


def new_manifest(core: Path, source_sha: str) -> dict:
    if current_sha(core) != source_sha or source_sha != PRIVATE_SHA:
        raise ValueError("Pinned private commit mismatch")
    paths = expected_files(core)
    folder = saved_folder(core, "technology")
    records = {}
    for name in paths:
        path = folder / name
        if not path.is_file():
            raise FileNotFoundError("Reference CSV not checked out: " + str(path))
        columns = read_header(path)
        records[name] = {
            "columns": list(columns),
            "column_count": len(columns),
            "header_sha256": hashlib.sha256(
                json.dumps(columns, ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest(),
            **signed_source_info(core, "technology", name),
        }
    return {
        "schema": 1, "status": "PASS_REFERENCE_SCHEMA_ONLY",
        "dataset": "technology", "source_core_sha": source_sha,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": records, "numeric_equivalence_pass": False,
        "production_modified": False, "source_recomputed": False,
    }


def inspect_signals(path: Path, expected_rows: int, expected_tickers: int) -> dict:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        header = next(reader)
        ticker_col = header.index("ticker")
        asof_col = header.index("as_of")
        identities = set()
        tickers = set()
        n = 0
        for row in reader:
            if len(row) != len(header):
                raise ValueError("Malformed signal row number " + str(n + 2))
            ticker, asof = row[ticker_col].strip(), row[asof_col].strip()
            if not ticker or not asof:
                raise ValueError("Empty saved ticker/as_of at " + str(n + 2))
            key = (ticker, asof)
            if key in identities:
                raise ValueError("Duplicate signal ticker/as_of " + str(key))
            identities.add(key)
            tickers.add(ticker)
            n += 1
        if n != expected_rows or len(tickers) != expected_tickers:
            raise ValueError(f"Saved signal population mismatch: {n}/{len(tickers)} "
                             f"expected {expected_rows}/{expected_tickers}")
    return {"rows": n, "tickers": len(tickers), "unique_identity": True}


def inspect_dataset(core: Path, dataset: str, source_sha: str, contract: dict) -> dict:
    if dataset not in DATASETS:
        raise ValueError("Unrecognized dataset")
    if current_sha(core) != source_sha or source_sha != PRIVATE_SHA:
        raise ValueError("Pinned private commit mismatch")
    if contract.get("status") != "PASS_REFERENCE_SCHEMA_ONLY" or contract.get("source_core_sha") != source_sha:
        raise ValueError("Reference manifest not from pinned source")
    files = expected_files(core)
    if set(contract["files"]) != set(files):
        raise ValueError("29-file reference contract corrupted")
    folder = saved_folder(core, dataset)
    expected_set = set(files)
    is_exclusion = dataset.startswith("exclude_")
    expected_local = expected_set - {SIGNAL} if is_exclusion else expected_set
    present = {p.name for p in folder.glob("*.csv") if p.is_file()}
    if present != expected_local:
        raise RuntimeError(f"Tracked CSV inventory mismatch: missing={sorted(expected_local - present)} "
                           f"unexpected={sorted(present - expected_local)}")
    matched = []
    object_hashes = {}
    for name in sorted(expected_local):
        file = folder / name
        columns = read_header(file)
        if list(columns) != contract["files"][name]["columns"]:
            raise RuntimeError(f"Column order/name mismatch: {dataset}/{name}")
        object_hashes[name] = signed_source_info(core, dataset, name)
        matched.append(name)
    status_path = folder / "semantic_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("overall_pass") is not True:
        raise RuntimeError("Existing semantic status was not PASS")
    rows = int(status["source_rows"])
    tickers = int(status["source_tickers"])
    population = (
        inspect_signals(folder / SIGNAL, rows, tickers) if not is_exclusion else None
    )
    return {
        "schema": 1, "dataset": dataset, "source_core_sha": source_sha,
        "status": "PASS_SAVED_SCHEMA_AND_SOURCE_POPULATION" if population else
                  "PASS_SAVED_SCHEMA_EXCLUSION_SOURCE_UNRESOLVED",
        "reference_dataset": "technology",
        "files_expected_local": len(expected_local),
        "ordered_headers_equal": len(matched),
        "all_saved_csv_column_headers_match": len(matched) == len(expected_local),
        "saved_file_git_objects": object_hashes,
        "semantic_status_rows": rows, "semantic_status_tickers": tickers,
        "validated_saved_signal_population": population,
        "source_signals_not_published": is_exclusion,
        "numeric_equivalence_verified": False, "html_qa_verified": False,
        "source_signals_recomputed": False, "production_changed": False,
        "release_ready": False,
    }


def selftest() -> None:
    assert len(DATASETS) == 8
    assert "transportation_utilities" in DATASETS
    assert "exclude_transportation_utilities" in DATASETS
    with __import__("tempfile").TemporaryDirectory() as t:
        file = Path(t) / "signals.csv"
        file.write_text("ticker,as_of\n0001,2026-01-01\n0002,2026-01-02\n")
        assert inspect_signals(file, 2, 2)["unique_identity"]
        try:
            inspect_signals(file, 3, 2)
        except ValueError:
            pass
        else:
            raise AssertionError("Failed to reject invalid saved row count")
    print("PASS: phase2 schema audit selftests")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("selftest", "reference", "dataset"), required=True)
    p.add_argument("--core", type=Path)
    p.add_argument("--dataset", choices=sorted(DATASETS))
    p.add_argument("--reference", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--expected-core-sha", default=PRIVATE_SHA)
    args = p.parse_args()
    if args.mode == "selftest":
        selftest()
        return 0
    if args.core is None or args.output is None:
        p.error("--core and --output are mandatory")
    core, out = args.core.resolve(), args.output.resolve()
    if out.exists():
        raise FileExistsError("Output record already exists")
    if args.mode == "reference":
        result = new_manifest(core, args.expected_core_sha)
    else:
        if args.dataset is None or args.reference is None:
            p.error("--dataset and --reference are mandatory for dataset mode")
        contract = json.loads(args.reference.read_text(encoding="utf-8"))
        result = inspect_dataset(core, args.dataset, args.expected_core_sha, contract)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ("files", "saved_file_git_objects")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
