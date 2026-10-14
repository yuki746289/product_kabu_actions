# Created: 2026-10-14 JST
"""Phase26 bounded rolling and monthly-candidate parity for three single candidate IDs.

Never recompute full semantic/OR bundles, source signals, saved artifacts or HTML.
Only generate three isolated saved-source-derived rolling/candidate holdouts and compare
all original persisted columns/rows with pinned canonical CSVs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASET = "transportation_utilities"
SOURCE_ROWS = 14848
TICKERS = 20
TYPES = 6
CONDITIONS = 3
FILES = ("rolling_3y_stability.csv", "rolling_5y_stability.csv",
         "monthly_candidate_stability_summary.csv")
KEYS = {"rolling_3y_stability.csv": ("condition_id", "window_start", "window_end"),
        "rolling_5y_stability.csv": ("condition_id", "window_start", "window_end"),
        "monthly_candidate_stability_summary.csv": ("condition_id",)}
PREVIOUS = "PASS_PHASE26_NEW_STABILITY_THREE_SINGLE_CANDIDATE_HOLDOUT"


def selftest() -> None:
    assert len(SHA) == 40 and len(FILES) == 3 and set(FILES) == set(KEYS)
    assert CONDITIONS == 3 and TYPES == 6
    assert all("condition_id" in KEYS[f] for f in FILES)
    print("PASS_PHASE26_ROLLING_CANDIDATE_CANARY_CONTRACT")


def verify(core: Path, ref: Path, proof4: Path, proof26: Path, stage: Path) -> dict:
    head = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip()
    if head != SHA:
        raise ValueError("Private core fixed SHA mismatch")
    build = (core / "build").resolve()
    if stage.exists() or not stage.resolve().is_relative_to(build) or stage.resolve() == build:
        raise ValueError("New isolated stage under Private core/build required")

    sys.path.insert(0, str(core / "scripts"))
    import pandas as pd
    import analyze_p2_nikkei_complete_baseline as cb
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import build_p2_225_semantic_bundle as common
    import append_p2_nikkei_monthly_report as monthly
    from p2_html_core.p03_common_analysis_plan import digest

    source = ref / "signal_level_features.csv"
    source_sha = digest(source)
    p4 = json.loads(proof4.read_text(encoding="utf-8"))
    group = (p4.get("groups") or {}).get(DATASET) or {}
    if (p4.get("status") != "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION"
        or group.get("csv_sha256") != source_sha
        or group.get("row_count") != SOURCE_ROWS
        or group.get("ticker_count") != TICKERS
        or group.get("duplicate_ids") is not False):
        raise ValueError("Pinned Phase4 source identity mismatch")
    prev = json.loads(proof26.read_text(encoding="utf-8"))
    if (prev.get("status") != PREVIOUS or prev.get("dataset") != DATASET
        or prev.get("private_core_sha") != SHA
        or prev.get("source_sha256") != source_sha
        or prev.get("selected_candidate_conditions") != CONDITIONS
        or prev.get("mismatches") != []
        or set(prev.get("files", {})) != {"yearly_stability.csv", "monthly_stability.csv",
                                       "regime_stability.csv"}
        or prev.get("canonical_inner_stability_functions_called") is not True):
        raise ValueError("Prior successful Phase26 stability proof invalid")

    frame = common.prepare_frame(source)
    if len(frame) != SOURCE_ROWS or frame["ticker"].astype(str).nunique() != TICKERS:
        raise ValueError("Saved input cardinality changed")
    base = cb._baseline_metrics(frame)
    fields, expected = aug._rep_fields(frame)
    names = list(fields)[:TYPES]
    if len(names) != TYPES or len(set(names)) != TYPES:
        raise ValueError("Canonical representative feature type contract changed")
    reduced_fields = {name: fields[name] for name in names}
    reduced_expected = {name: expected[name] for name in names}
    singles, masks = aug._representative_singles(
        frame, base, reduced_fields, reduced_expected)
    winners = singles.loc[singles["candidate"] & singles["count"].gt(0)].head(CONDITIONS)
    if len(winners) != CONDITIONS:
        raise ValueError("Insufficient bounded source-native candidate singles")

    conditions = {}
    for row in winners.itertuples(index=False):
        condition_id = f"S:{row.feature}={row.category}"
        if condition_id in conditions:
            raise ValueError("Duplicate bounded condition id")
        conditions[condition_id] = masks[(row.feature, row.category)]
    # Invoke the original canonical rolling and monthly-candidate functions
    # using only the three proven original candidate condition masks.
    limited_registry = winners.copy()
    limited_registry["condition_id"] = (
        "S:" + limited_registry["feature"] + "=" + limited_registry["category"]
    )
    limited_monthly = cb._stability_rows(frame, conditions, "month", base)
    new = {
        "rolling_3y_stability.csv": cb._rolling_rows(frame, conditions, 3),
        "rolling_5y_stability.csv": cb._rolling_rows(frame, conditions, 5),
        "monthly_candidate_stability_summary.csv": monthly._candidate_monthly_summary(
            limited_monthly, limited_registry),
    }
    if any(part.empty for part in new.values()):
        raise ValueError("Empty bounded stability calculation")
    stage.mkdir(parents=True, exist_ok=False)
    mismatches = []
    file_stats = {}
    for name in FILES:
        path = ref / name
        old = pd.read_csv(path, low_memory=False)
        key = list(KEYS[name])
        if any(k not in old.columns or k not in new[name].columns for k in key):
            raise ValueError(f"Missing canonical condition keys in {name}")
        select = old.loc[old["condition_id"].isin(conditions)].copy()
        fresh = new[name]
        if select.duplicated(key).any() or fresh.duplicated(key).any():
            raise ValueError(f"Duplicate stability keys in {name}")
        select = select.sort_values(key).reset_index(drop=True)
        fresh = fresh.sort_values(key).reset_index(drop=True)
        # Compare after CSV roundtrip so inferred key types match the
        # persisted canonical CSV (e.g. year integer vs in-memory string).
        out = stage / name
        fresh.to_csv(out, index=False, encoding="utf-8")
        checked = pd.read_csv(out, low_memory=False)
        checked = checked.sort_values(key).reset_index(drop=True)
        if len(select) != len(checked) or len(select) == 0:
            mismatches.append({"file": name, "kind": "row_count"})
        elif list(select.columns) != list(checked.columns):
            mismatches.append({"file": name, "kind": "ordered_columns"})
        elif not select[key].equals(checked[key]):
            mismatches.append({"file": name, "kind": "key_values"})
        else:
            try:
                pd.testing.assert_frame_equal(
                    select, checked, check_dtype=False, check_exact=False,
                    atol=1e-7, rtol=1e-10, check_index_type=False)
            except AssertionError:
                mismatches.append({"file": name, "kind": "numeric_or_label"})
        file_stats[name] = {
            "old_full_rows": int(len(old)),
            "old_selected_rows": int(len(select)),
            "new_selected_rows": int(len(checked)),
            "columns": int(len(checked.columns)),
            "old_sha256": digest(path), "new_subset_sha256": digest(out),
        }
    if digest(source) != source_sha:
        raise ValueError("Saved source mutated")
    return {
        "schema": 1,
        "status": ("PASS_PHASE26_NEW_ROLLING_CANDIDATE_THREE_CONDITION_HOLDOUT"
                   if not mismatches else "FAIL_PHASE26_NEW_ROLLING_CANDIDATE_HOLDOUT"),
        "dataset": DATASET, "private_core_sha": SHA, "source_sha256": source_sha,
        "source_rows": SOURCE_ROWS, "source_tickers": TICKERS,
        "input_feature_types": TYPES, "selected_candidate_conditions": len(conditions),
        "files": file_stats, "mismatches": mismatches,
        "canonical_inner_rolling_candidate_functions_called": True,
        "full_semantic_recalculated": False, "full_or_recalculated": False,
        "previous_artifacts_recalculated": False, "p2_signals_recomputed": False,
        "html_generated": False, "production_changed": False, "release_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    for name in ("core", "reference", "proof4", "proof26", "stage", "report"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if any(getattr(args, x) is None for x in
           ("core", "reference", "proof4", "proof26", "stage", "report")):
        parser.error("Pinned source, immutable proof, fresh stage and report required")
    if args.report.exists():
        raise FileExistsError("Never overwrite report or successful evidence")
    result = verify(args.core.resolve(), args.reference.resolve(),
                    args.proof4.resolve(), args.proof26.resolve(), args.stage.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": result["status"], "files": result["files"],
                      "conditions": result["selected_candidate_conditions"],
                      "mismatches": result["mismatches"]}))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
