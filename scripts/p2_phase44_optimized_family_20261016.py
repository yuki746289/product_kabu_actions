"""Bounded all_225 optimized-producer verification; never legacy-copy certification.

Each family regenerates distinct selected outputs from saved immutable features,
using audited NumPy cached metrics or the original isolated canonical routines.
No private CSV leaves the runner; only an allowlisted JSON certificate is saved.
A family PASS never implies a complete 29-CSV end-to-end producer PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import subprocess
import sys
import time
from pathlib import Path

import p2_phase44_all225_fresh_newproducer_29csv_20261016 as contract

CORE_SHA = contract.CORE_SHA
OUTPUTS = {
    "stability5": (
        "yearly_stability.csv", "monthly_stability.csv",
        "rolling_3y_stability.csv", "rolling_5y_stability.csv",
        "regime_stability.csv",
    ),
    "single4": (
        "all_single_categories.csv", "representative_single_categories.csv",
        "candidate_registry.csv", "advantage_single_candidates.csv",
    ),
    "baseline3": (
        "monthly_baseline_performance.csv",
        "monthly_baseline_stability_summary.csv",
        "month_of_year_baseline_summary.csv",
    ),
}
FAMILY_KEYS = {
    "yearly_stability.csv": ("condition_id", "year"),
    "monthly_stability.csv": ("condition_id", "month"),
    "rolling_3y_stability.csv": ("condition_id", "window_start", "window_end"),
    "rolling_5y_stability.csv": ("condition_id", "window_start", "window_end"),
    "regime_stability.csv": ("condition_id", "regime"),
}


def check_dataframe(original, generated, name: str) -> dict:
    import pandas as pd

    if list(original.columns) != list(generated.columns):
        raise ValueError("Column order mismatch in " + name)
    if len(original) != len(generated):
        raise ValueError("Row count mismatch in " + name)
    reindexed = False
    keys = FAMILY_KEYS.get(name)
    if keys:
        for field in keys:
            if field not in original.columns:
                raise ValueError("Required identity key is missing in " + name)
        old_keys = original[list(keys)].astype(str).agg("\x1f".join, axis=1)
        new_keys = generated[list(keys)].astype(str).agg("\x1f".join, axis=1)
        if old_keys.duplicated().any() or new_keys.duplicated().any():
            raise ValueError("Duplicate condition/period keys in " + name)
        if set(old_keys) != set(new_keys):
            raise ValueError("Condition/period coverage does not match in " + name)
        reindexed = old_keys.tolist() != new_keys.tolist()
        if reindexed:
            generated = generated.set_index(new_keys.to_numpy(), drop=False).loc[old_keys.tolist()]
            generated = generated.reset_index(drop=True)[list(original.columns)]
        for field in ("year", "window_start", "window_end"):
            if field in original:
                generated[field] = pd.to_numeric(generated[field], errors="raise")

    # Authoritative numeric comparison uses pandas' complete frame comparison:
    # numeric columns: strict relative 1e-12 and absolute 1e-10;
    # nonnumeric identity and labels: exact match; NaN positions: exact.
    pd.testing.assert_frame_equal(
        original.reset_index(drop=True), generated.reset_index(drop=True),
        check_dtype=False, check_exact=False,
        rtol=contract.REL_TOL, atol=contract.ABS_TOL, check_index_type=False,
    )
    return {
        "rows": len(original),
        "columns": len(original.columns),
        "condition_period_keys_equal": bool(keys),
        "reindexed_by_key": reindexed,
        "all_rows_columns_numeric_equal": True,
    }


def selftest() -> None:
    import pandas as pd
    assert set(OUTPUTS) == {"stability5", "single4", "baseline3"}
    assert sum(map(len, OUTPUTS.values())) == 12
    a = pd.DataFrame({"condition_id": ["s:1", "s:2"], "year": [2020, 2021],
                      "value": [0.5, 0.25], "label": ["x", "y"]})
    b = a.iloc[::-1].reset_index(drop=True)
    assert check_dataframe(a, b, "yearly_stability.csv")["reindexed_by_key"]
    b.loc[0, "label"] = "corrupted"
    try:
        check_dataframe(a, b, "yearly_stability.csv")
    except AssertionError:
        pass
    else:
        raise AssertionError("Identity corruption was incorrectly accepted")
    print("PASS_PHASE44_BOUNDED_OPTIMIZED_COMPARATOR_SELFTEST")


def run(core: Path, source: Path, reference: Path, family: str) -> dict:
    import pandas as pd
    if subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
    ).strip() != CORE_SHA:
        raise ValueError("Immutable Private core SHA mismatch")
    if not (core / "docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Immutable Private Actions policy missing")
    if subprocess.check_output(
        ["git", "-C", str(core), "ls-tree", "-r", "--name-only",
         "HEAD", ".github/workflows"], text=True
    ).strip():
        raise ValueError("Private Actions workflows forbidden")
    source_meta = contract.inspect_source(source)
    reference_meta = contract.validate_old_reference(reference)
    before_source_hash = contract.sha256(source)
    original_file_hashes = {
        name: contract.sha256(reference / name) for name in OUTPUTS[family]
    }

    sys.path.insert(0, str(core / "scripts"))
    import build_p2_225_semantic_bundle as sem
    import finalize_p2_nikkei_complete_baseline as fin
    import analyze_p2_nikkei_complete_baseline as cb
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import build_p2_225_canonical_semantic_data as canonical
    import append_p2_nikkei_monthly_report as monthly

    t0 = time.perf_counter()
    frame = sem.prepare_frame(source)
    if len(frame) != source_meta["rows"]:
        raise ValueError("Input parsed row count changed")
    results = {}
    timings = {}

    if family == "stability5":
        import p2_phase42_numpy_cached_stability_20261016 as fast
        t = time.perf_counter()
        masks = fin._feature_masks(frame)
        conditions = fast.build_selected_conditions(reference, fin, masks)
        cache = fast.Cache(frame)
        timings["prepare_cache"] = round(time.perf_counter() - t, 4)
        if not conditions:
            raise ValueError("Optimized mask set is empty")
        for name in OUTPUTS[family]:
            start = time.perf_counter()
            output = pd.DataFrame(
                fast.make_numeric_outputs(cache, conditions, name, cb.MARKET_CATS)
            )
            legacy = pd.read_csv(reference / name, low_memory=False)
            results[name] = check_dataframe(legacy, output, name)
            timings[name] = round(time.perf_counter() - start, 4)
            print("PASS_NEW_NUMPY_FAMILY_FILE", name, len(output), flush=True)
    elif family == "single4":
        import p2_phase43_new_8_semantic_cached_20261016 as fast
        t = time.perf_counter()
        base = cb._baseline_metrics(frame)
        metrics = fast.MetricCache(frame)
        original_metric = cb._metrics
        try:
            masks = fin._feature_masks(frame)
            import numpy as np
            for i, mask in enumerate(list(masks.values())[:12]):
                old = original_metric(frame, mask, base)
                new = metrics.metrics(frame, mask, base)
                if set(old) != set(new):
                    raise ValueError("Optimized metric field names changed")
                for field in old:
                    if not np.isclose(
                        old[field], new[field], rtol=1e-10, atol=1e-7,
                        equal_nan=True,
                    ):
                        raise ValueError("Cached metrics do not match original")
            cb._metrics = metrics.metrics
            singles = canonical._full_single_categories(frame, base)
            fields, expected = aug._rep_fields(frame)
            representatives, _ = aug._representative_singles(
                frame, base, fields, expected
            )
            if len(representatives) != 151:
                raise ValueError("Representative single count differs")
            registry = representatives.loc[
                fin._truthy(representatives["candidate"])
            ].copy()
            registry["condition_type"] = "single"
            registry["small_sample"] = registry["count"] < 30
            registry["condition_id"] = (
                "S:" + registry["feature"] + "=" + registry["category"]
            )
            adv_single = singles.loc[
                fin._truthy(singles["candidate"])
            ].copy()
            if "small_sample" not in adv_single:
                adv_single["small_sample"] = pd.to_numeric(
                    adv_single["count"], errors="coerce"
                ).fillna(0).lt(30)
        finally:
            cb._metrics = original_metric
        timings["calculation"] = round(time.perf_counter() - t, 4)
        output_map = {
            "all_single_categories.csv": singles,
            "representative_single_categories.csv": representatives,
            "candidate_registry.csv": registry,
            "advantage_single_candidates.csv": adv_single,
        }
        for name, data in output_map.items():
            start = time.perf_counter()
            legacy = pd.read_csv(reference / name, low_memory=False)
            results[name] = check_dataframe(legacy, data, name)
            timings[name] = round(time.perf_counter() - start, 4)
            print("PASS_NEW_NUMPY_SINGLE_FILE", name, len(data), flush=True)
    elif family == "baseline3":
        t = time.perf_counter()
        month_base = monthly._monthly_baseline(frame)
        baseline_stability = monthly._baseline_stability(month_base)
        month_of_year = monthly._month_of_year(frame)
        timings["calculation"] = round(time.perf_counter() - t, 4)
        output_map = {
            "monthly_baseline_performance.csv": month_base,
            "monthly_baseline_stability_summary.csv": baseline_stability,
            "month_of_year_baseline_summary.csv": month_of_year,
        }
        for name, data in output_map.items():
            start = time.perf_counter()
            legacy = pd.read_csv(reference / name, low_memory=False)
            results[name] = check_dataframe(legacy, data, name)
            timings[name] = round(time.perf_counter() - start, 4)
            print("PASS_CANONICAL_BASELINE_FILE", name, len(data), flush=True)
    else:
        raise ValueError("Unsupported optimization family")

    if set(results) != set(OUTPUTS[family]):
        raise ValueError("New generated result coverage is incomplete")
    if contract.sha256(source) != before_source_hash:
        raise ValueError("Original input has changed")
    for name, original_sha in original_file_hashes.items():
        if contract.sha256(reference / name) != original_sha:
            raise ValueError("Legacy immutable CSV has changed")
    if subprocess.check_output(
        ["git", "-C", str(core), "diff", "--name-only"], text=True
    ).strip():
        raise ValueError("Tracked source files were altered")
    if subprocess.check_output(
        ["git", "-C", str(core), "diff", "--cached", "--name-only"], text=True
    ).strip():
        raise ValueError("Tracked staged files were altered")
    return {
        "schema": 1, "phase": 44,
        "status": "PASS_PHASE44_BOUNDED_NEW_FUNCTION_NUMERIC_PARITY",
        "dataset": "all_225",
        "family": family,
        "private_core_sha": CORE_SHA,
        "input_sha256": before_source_hash,
        "source_rows": source_meta["rows"],
        "source_tickers": source_meta["tickers"],
        "old_reference_csv_count": reference_meta["csv_count"],
        "newly_independently_computed_files": results,
        "newly_verified_file_count": len(results),
        "runtime_seconds": round(time.perf_counter() - t0, 4),
        "stage_times_seconds": timings,
        "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, 2),
        "canonical_p2_v12_modified": False,
        "original_inputs_or_html_modified": False,
        "previous_successful_artifacts_recomputed": False,
        "full_new_semantic_or_29_csv_chain_certified": False,
        "release_ready": False,
        "phase48_executed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--family", choices=sorted(OUTPUTS))
    p.add_argument("--core", type=Path)
    p.add_argument("--source", type=Path)
    p.add_argument("--reference", type=Path)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    if args.selftest:
        selftest()
        return 0
    if any(getattr(args, name) is None for name in
           ("family", "core", "source", "reference", "out")):
        p.error("Family, core, source, legacy reference and result required")
    if args.out.exists():
        raise FileExistsError("Do not overwrite any previous certificate")
    report = run(
        args.core.resolve(), args.source.resolve(),
        args.reference.resolve(), args.family
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "PASS_BOUNDED_NEW_COMPUTATION_ONLY",
        report["family"], report["newly_verified_file_count"], flush=True
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
