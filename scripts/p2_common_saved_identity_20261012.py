# Created: 2026-10-12T19:19:00+09:00
"""Verify saved P2 signal identities without recomputing prices, P2 or stats.

Public Actions obtains the PRE-EXISTING source artifact and the original
filtered cohort artifacts. This reads only ticker/as_of IDs, not feature values.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

SOURCE_ROWS = 181318
SOURCE_TICKERS = 225
GROUPS = {
    "technology": (48782, 61),
    "financials": (16307, 20),
    "consumer_goods": (33330, 41),
    "materials": (39007, 48),
    "capital_goods_others": (29044, 35),
    "transportation_utilities": (14848, 20),
}
EXCLUSION = {
    "exclude_transportation_utilities": {
        "omitted": ("transportation_utilities",),
        "expected_rows": 166470, "expected_tickers": 205,
    },
    "exclude_capital_goods_transportation_utilities": {
        "omitted": ("capital_goods_others", "transportation_utilities"),
        "expected_rows": 137426, "expected_tickers": 170,
    },
}


def find_saved_csv(folder: Path, preferred_name: str) -> Path:
    files = sorted(p for p in folder.rglob(preferred_name) if p.is_file())
    if len(files) != 1:
        raise ValueError(f"Expected exactly one saved {preferred_name} in {folder}: {len(files)}")
    return files[0]


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def saved_ids(path: Path, expected_rows: int, expected_tickers: int) -> tuple[set[tuple[str,str]], dict]:
    ids: set[tuple[str,str]] = set()
    tickers = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.reader(handle)
        columns = next(rows, None)
        if columns is None or "ticker" not in columns or "as_of" not in columns:
            raise ValueError("Saved source missing ticker/as_of: " + str(path))
        ticker_col, asof_col = columns.index("ticker"), columns.index("as_of")
        for number, row in enumerate(rows, start=2):
            if len(row) != len(columns):
                raise ValueError(f"Malformed saved CSV at row {number}: {path}")
            ticker = row[ticker_col].strip()
            asof = row[asof_col].strip()
            if not ticker or not asof:
                raise ValueError(f"Blank saved ticker/as_of at row {number}: {path}")
            key = ticker, asof
            if key in ids:
                raise ValueError(f"Duplicate saved signal ID at row {number}: {path}")
            ids.add(key)
            tickers.add(ticker)
    if len(ids) != expected_rows or len(tickers) != expected_tickers:
        raise ValueError(f"Saved population shape mismatch {path.name}: "
                         f"{len(ids)}/{len(tickers)} vs {expected_rows}/{expected_tickers}")
    return ids, {
        "row_count": len(ids), "ticker_count": len(tickers),
        "csv_sha256": file_hash(path), "duplicate_ids": False,
    }


def group_folder(core: Path, group: str) -> Path:
    return core / "preview/kabu/analysis/225_group_all_period" / group


def audit_group(core: Path, source_csv: Path) -> dict:
    source, source_info = saved_ids(source_csv, SOURCE_ROWS, SOURCE_TICKERS)
    all_ids: set[tuple[str,str]] = set()
    group_info: dict[str,dict] = {}
    for group, (rows, tickers) in GROUPS.items():
        path = group_folder(core, group) / "signal_level_features.csv"
        cohort, info = saved_ids(path, rows, tickers)
        if not cohort <= source:
            raise ValueError("Group contains signals outside pinned canonical source: " + group)
        overlap = all_ids.intersection(cohort)
        if overlap:
            raise ValueError(f"Duplicate signal assigned to multiple groups: {group} ({len(overlap)})")
        all_ids.update(cohort)
        group_info[group] = info
    if all_ids != source:
        raise ValueError("Union of six saved groups differs from saved canonical 225 signal identities")
    return {
        "schema": 1, "status": "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION",
        "source": source_info, "groups": group_info,
        "signal_id_rows_verified": len(source),
        "source_values_checked": False,
        "semantic_numeric_equivalence_verified": False,
        "saved_signals_recomputed": False, "production_changed": False,
        "html_changed": False, "release_ready": False,
    }


def audit_exclusion(core: Path, source_csv: Path, saved_exclusion_csv: Path,
                    variant: str) -> dict:
    option = EXCLUSION[variant]
    source, source_info = saved_ids(source_csv, SOURCE_ROWS, SOURCE_TICKERS)
    omitted: set[tuple[str,str]] = set()
    omission_provenance = {}
    for group in option["omitted"]:
        count, n_tickers = GROUPS[group]
        filtered, info = saved_ids(group_folder(core, group)/"signal_level_features.csv",
                                   count, n_tickers)
        if filtered - source:
            raise ValueError("Excluded group has data not present in source: " + group)
        omitted.update(filtered)
        omission_provenance[group] = info
    result, result_info = saved_ids(saved_exclusion_csv, option["expected_rows"],
                                    option["expected_tickers"])
    expected = source - omitted
    if result != expected:
        raise ValueError("Saved exclusion signal IDs differ from exact canonical difference: " +
                         variant)
    return {
        "schema": 1, "status": "PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE",
        "variant": variant, "source": source_info,
        "excluded_groups": omission_provenance, "saved_exclusion": result_info,
        "matching_signal_ids": len(result),
        "source_values_checked": False,
        "semantic_numeric_equivalence_verified": False,
        "saved_signals_recomputed": False, "production_changed": False,
        "html_changed": False, "release_ready": False,
    }


def selftest() -> None:
    assert sum(rows for rows, _ in GROUPS.values()) == SOURCE_ROWS
    assert sum(tickers for _, tickers in GROUPS.values()) == SOURCE_TICKERS
    for x in EXCLUSION.values():
        rows = SOURCE_ROWS - sum(GROUPS[k][0] for k in x["omitted"])
        tickers = SOURCE_TICKERS - sum(GROUPS[k][1] for k in x["omitted"])
        assert (rows,tickers)==(x["expected_rows"],x["expected_tickers"])
    print("PASS synthetic expected size invariants")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("selftest","groups","exclusion"), required=True)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--saved-exclusion-root", type=Path)
    parser.add_argument("--variant", choices=sorted(EXCLUSION))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.mode == "selftest":
        selftest()
        return 0
    if args.core is None or args.source_root is None or args.out is None:
        parser.error("Provide --core --source-root and --out")
    core = args.core.resolve()
    source_csv = find_saved_csv(args.source_root, "features.csv")
    if args.mode == "groups":
        result = audit_group(core, source_csv)
    else:
        if args.variant is None or args.saved_exclusion_root is None:
            parser.error("Exclusion mode requires --variant and --saved-exclusion-root")
        saved_csv = find_saved_csv(args.saved_exclusion_root, "features.csv")
        result = audit_exclusion(core, source_csv, saved_csv, args.variant)
    destination = args.out.resolve()
    if destination.exists():
        raise FileExistsError("Never overwrite previous audit evidence")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",
                           encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ("groups","excluded_groups")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
