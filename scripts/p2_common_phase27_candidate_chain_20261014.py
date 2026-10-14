# Created: 2026-10-14T10:26:00+09:00
"""Phase27: immutable saved-source bounded semantic parity, *new* single candidates.

Scope: two non-overlapping candidate-registry slices after the three previously
certified Phase26 candidate conditions, each checking six canonical semantic
stability/rolling CSVs. Never re-execute the Phase26 certified three conditions.
Only numerical parity metadata is exported; never publish original private rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS = ("technology", "financials", "consumer_goods", "materials",
          "capital_goods_others", "transportation_utilities")
EXCLUSIONS = {
    "exclude_capital_goods_transportation_utilities":
        (137426, 170, "cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"),
    "exclude_transportation_utilities":
        (166470, 205, "d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"),
}
DATASETS = GROUPS + tuple(EXCLUSIONS)
FILES = ("yearly_stability.csv", "monthly_stability.csv", "regime_stability.csv",
         "rolling_3y_stability.csv", "rolling_5y_stability.csv",
         "monthly_candidate_stability_summary.csv")
KEYS = {
    "yearly_stability.csv": ("condition_id", "year"),
    "monthly_stability.csv": ("condition_id", "month"),
    "regime_stability.csv": ("condition_id", "regime"),
    "rolling_3y_stability.csv": ("condition_id", "window_start", "window_end"),
    "rolling_5y_stability.csv": ("condition_id", "window_start", "window_end"),
    "monthly_candidate_stability_summary.csv": ("condition_id",),
}
PREVIOUS_GROUP = "PASS_PHASE26_NEW_ROLLING_CANDIDATE_THREE_CONDITION_HOLDOUT"
PREVIOUS_FIVE = "PASS_PHASE26_NEW_ROLLING_CANDIDATE_FIVE_GROUP_HOLDOUT"
PREVIOUS_EXCLUSION = "PASS_PHASE26_EXCLUSIONS_SIX_CSV_BOUNDED_PARITY"
BATCH_SIZE = 3
ALLOWED_OFFSETS = (3, 6)


def selftest() -> None:
    assert set(DATASETS) == (set(GROUPS) | set(EXCLUSIONS))
    assert len(DATASETS) == 8 and len(FILES) == len(KEYS) == 6
    assert BATCH_SIZE == 3 and ALLOWED_OFFSETS == (3, 6)
    assert len(CORE_SHA) == 40
    assert all("condition_id" in KEYS[name] for name in FILES)
    assert set(range(3, 6)).isdisjoint(range(6, 9))
    print("PASS_PHASE27_NEW_BOUNDED_CANDIDATE_SHARDS_CONTRACT")


def file_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid pinned proof schema")
    return data


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify(core: Path, ref: Path, source_root: Path, proof4: Path, proof26: Path,
           dataset: str, offset: int, stage: Path) -> dict:
    if dataset not in DATASETS or offset not in ALLOWED_OFFSETS:
        raise ValueError("Dataset or novel candidate slice is not authorized")
    if subprocess.check_output(
            ["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip() != CORE_SHA:
        raise ValueError("Immutable Private core SHA mismatch")
    build = (core / "build").resolve()
    if stage.exists() or stage.resolve() == build or not stage.resolve().is_relative_to(build):
        raise ValueError("Fresh, isolated Private core/build stage required")
    ref_expected = (core / "preview/kabu/analysis" /
                    ("225_group_all_period" if dataset in GROUPS
                     else "225_exclusion_all_period") / dataset).resolve()
    if ref != ref_expected:
        raise ValueError("Saved original dataset reference directory mismatch")
    if dataset in GROUPS:
        source = ref / "signal_level_features.csv"
    else:
        sources = list(source_root.rglob("features.csv"))
        if len(sources) != 1:
            raise ValueError("Exactly one original certified exclusion features.csv required")
        source = sources[0]

    sys.path.insert(0, str(core / "scripts"))
    import numpy as np
    import pandas as pd
    import analyze_p2_nikkei_complete_baseline as cb
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import build_p2_225_semantic_bundle as common
    import append_p2_nikkei_monthly_report as monthly
    from p2_html_core.p03_common_analysis_plan import digest

    source_sha = digest(source)
    p4 = file_json(proof4)
    if dataset in GROUPS:
        group = (p4.get("groups") or {}).get(dataset) or {}
        if p4.get("status") != "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
            raise ValueError("Previously certified six-group identity proof missing")
        rows, tickers = group.get("row_count"), group.get("ticker_count")
        if (group.get("csv_sha256") != source_sha or
            group.get("duplicate_ids") is not False or
            not isinstance(rows, int) or rows <= 0 or
            not isinstance(tickers, int) or tickers <= 0):
            raise ValueError("Immutable saved group source identity mismatch")
    else:
        rows, tickers, expected_sha = EXCLUSIONS[dataset]
        original = p4.get("saved_exclusion") or {}
        if (source_sha != expected_sha or
            p4.get("status") != "PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE" or
            p4.get("variant") != dataset or
            original.get("csv_sha256") != source_sha or
            original.get("row_count") != rows or
            original.get("ticker_count") != tickers or
            original.get("duplicate_ids") is not False):
            raise ValueError("Immutable original exclusion identity mismatch")

    prev = file_json(proof26)
    prev_status = (PREVIOUS_GROUP if dataset == "transportation_utilities" else
                   PREVIOUS_FIVE if dataset in GROUPS else PREVIOUS_EXCLUSION)
    if (prev.get("status") != prev_status or prev.get("dataset") != dataset or
        prev.get("private_core_sha") != CORE_SHA or
        prev.get("source_sha256") != source_sha or
        prev.get("selected_candidate_conditions") != 3 or
        prev.get("mismatches") != [] or
        not set(FILES).issuperset(set(prev.get("files", {}))) or
        len(prev.get("files", {})) < 3):
        raise ValueError("Prior Phase26 numerical evidence inconsistent with source")

    frame = common.prepare_frame(source)
    if len(frame) != rows or frame["ticker"].astype(str).nunique() != tickers:
        raise ValueError("Original source cardinality mismatch")
    registry_path = ref / "candidate_registry.csv"
    registry = pd.read_csv(registry_path, low_memory=False)
    if "condition_id" not in registry or registry["condition_id"].duplicated().any():
        raise ValueError("Saved certified candidate registry invalid")
    if len(registry) < offset + BATCH_SIZE:
        raise ValueError("Candidate registry lacks the requested new shard")
    selected = registry.iloc[offset:offset + BATCH_SIZE].copy()
    selected_ids = selected["condition_id"].astype(str).tolist()
    if len(selected_ids) != BATCH_SIZE or len(set(selected_ids)) != BATCH_SIZE:
        raise ValueError("Unexpected selected candidate keys")

    fields, expected = aug._rep_fields(frame)
    conditions = {}
    for r in selected.itertuples(index=False):
        feature, category = str(r.feature), str(r.category)
        cid = f"S:{feature}={category}"
        if (feature not in fields or category not in expected[feature] or
            cid != r.condition_id or cid in conditions or
            int(r.count) <= 0):
            raise ValueError("Unrecognized selected canonical candidate")
        conditions[cid] = np.asarray(fields[feature], dtype=object) == category
        if int(conditions[cid].sum()) != int(r.count):
            raise ValueError("Saved candidate condition count differs from new mask")
    # The old Phase26 certified first three candidate positions [0,3) are
    # not part of any Phase27 calculation or its output.
    if set(selected_ids) & set(registry.iloc[:3]["condition_id"].astype(str)):
        raise ValueError("Attempt to recompute certified Phase26 conditions")

    base = cb._baseline_metrics(frame)
    month = cb._stability_rows(frame, conditions, "month", base)
    computed = {
        "yearly_stability.csv": cb._stability_rows(frame, conditions, "year", base),
        "monthly_stability.csv": month,
        "regime_stability.csv": aug._regime_stability(frame, base, conditions),
        "rolling_3y_stability.csv": cb._rolling_rows(frame, conditions, 3),
        "rolling_5y_stability.csv": cb._rolling_rows(frame, conditions, 5),
        "monthly_candidate_stability_summary.csv":
            monthly._candidate_monthly_summary(month, selected),
    }
    if any(value.empty for value in computed.values()):
        raise ValueError("Empty Phase27 bounded new calculation")
    stage.mkdir(parents=True, exist_ok=False)
    issues = []
    stats = {}
    for name in FILES:
        old_path = ref / name
        old = pd.read_csv(old_path, low_memory=False)
        keys = list(KEYS[name])
        fresh = computed[name]
        if any(k not in old or k not in fresh for k in keys):
            raise ValueError("Missing canonical key for " + name)
        old_subset = old.loc[old["condition_id"].isin(selected_ids)].copy()
        if old_subset.duplicated(keys).any() or fresh.duplicated(keys).any():
            raise ValueError("Duplicate original/new condition-period keys: " + name)
        old_subset = old_subset.sort_values(keys).reset_index(drop=True)
        output = stage / name
        fresh.to_csv(output, index=False, encoding="utf-8")
        checked = pd.read_csv(output, low_memory=False)
        checked = checked.sort_values(keys).reset_index(drop=True)
        if len(old_subset) == 0 or len(old_subset) != len(checked):
            issues.append({"file": name, "type": "row_count"})
        elif list(old_subset.columns) != list(checked.columns):
            issues.append({"file": name, "type": "column_order"})
        elif not old_subset[keys].equals(checked[keys]):
            issues.append({"file": name, "type": "condition_key"})
        else:
            try:
                pd.testing.assert_frame_equal(
                    old_subset, checked, check_dtype=False, check_exact=False,
                    atol=1e-7, rtol=1e-10, check_index_type=False)
            except AssertionError:
                issues.append({"file": name, "type": "value_parity"})
        stats[name] = {
            "original_complete_rows": int(len(old)),
            "old_subset_rows": int(len(old_subset)),
            "new_subset_rows": int(len(checked)),
            "columns": int(len(checked.columns)),
            "original_sha256": digest(old_path),
            "new_subset_sha256": digest(output),
        }
    if digest(source) != source_sha or digest(registry_path) != digest(ref / "candidate_registry.csv"):
        raise ValueError("Original saved source identity changed during audit")
    return {
        "schema": 1,
        "status": "PASS_PHASE27_NEW_UNCERTIFIED_SINGLES_SIX_CSV" if not issues else
                  "FAIL_PHASE27_NEW_UNCERTIFIED_SINGLES_SIX_CSV",
        "dataset": dataset, "private_core_sha": CORE_SHA, "source_sha256": source_sha,
        "original_rows": rows, "original_tickers": tickers,
        "candidate_offset": offset, "candidate_count": BATCH_SIZE,
        "selected_condition_hashes": [sha_text(x) for x in selected_ids],
        "checked_files": stats, "mismatches": issues,
        "canonical_inner_functions_executed": True,
        "previous_certified_conditions_recomputed": False,
        "full_semantic_recalculated": False, "full_or_recalculated": False,
        "successful_artifacts_recalculated": False, "signals_recomputed": False,
        "html_generated": False, "production_changed": False,
        "release_ready": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dataset", choices=DATASETS)
    ap.add_argument("--offset", type=int, choices=ALLOWED_OFFSETS)
    for field in ("core", "reference", "source_root", "proof4", "proof26", "stage", "report"):
        ap.add_argument("--" + field.replace("_", "-"), type=Path)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    required = ("core", "reference", "source_root", "proof4", "proof26",
                "stage", "report", "dataset", "offset")
    if any(getattr(a, x) is None for x in required):
        ap.error("Pinned source, proofs, dataset, offset and output required")
    if a.report.exists():
        raise FileExistsError("Never overwrite certified JSON evidence")
    out = verify(a.core.resolve(), a.reference.resolve(), a.source_root.resolve(),
                 a.proof4.resolve(), a.proof26.resolve(), a.dataset,
                 a.offset, a.stage.resolve())
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"status": out["status"], "dataset": out["dataset"],
                      "offset": out["candidate_offset"], "files": out["checked_files"],
                      "mismatches": out["mismatches"]}, ensure_ascii=False))
    return 0 if out["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
