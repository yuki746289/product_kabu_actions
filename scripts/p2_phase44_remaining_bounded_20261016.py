"""Phase44 bounded incremental new numeric producer functions, all_225 only.

Previously passed 12 CSV family computations are NOT repeated. Existing SHA-bound
reference single/pair/monthly data are inputs to separate canonical functions,
never passed off as outputs of a fresh end-to-end producer.
Output only public-safe scalar proof JSON. No input/raw CSV leave GitHub runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

import p2_phase44_all225_fresh_newproducer_29csv_20261016 as contract
from p2_phase44_optimized_family_20261016 import check_dataframe

CORE_SHA=contract.CORE_SHA
FAMILIES={
    "dependent4": (
        "monthly_candidate_stability_summary.csv",
        "parameter_plateau.csv",
        "signal_level_features.csv", "failures.csv",
    ),
    "walkforward1": ("walkforward_results.csv",),
    "pair4": (
        "all_pairwise_combinations.csv",
        "tested_triple_combinations.csv",
        "advantage_pairwise_candidates.csv",
        "advantage_triple_candidates.csv",
    ),
}
INPUTS={
    "dependent4": (
        "all_single_categories.csv","representative_single_categories.csv",
        "monthly_stability.csv","candidate_registry.csv",
    ),
    "walkforward1": (),
    "pair4": ("representative_single_categories.csv",),
}

def digest(path: Path) -> str:
    return contract.sha256(path)

def selftest() -> None:
    assert set(FAMILIES) == {"dependent4", "walkforward1", "pair4"}
    assert len({f for family in FAMILIES.values() for f in family}) == 9
    for family in FAMILIES:
        assert set(FAMILIES[family]).isdisjoint(INPUTS[family])
        assert all(name in contract.EXPECTED_FILES for name in FAMILIES[family]+INPUTS[family])
    print("PASS_PHASE44_UNSEEN_NINE_CSV_SCOPE_AND_PROVENANCE")

def calculate(family: str, core: Path, source: Path, reference: Path) -> dict:
    import numpy as np
    import pandas as pd
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=CORE_SHA:
        raise ValueError("Pinned original core SHA changed")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Canonical policy missing")
    if subprocess.check_output(
        ["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],
        text=True,
    ).strip():
        raise ValueError("Private workflows found")
    source_meta=contract.inspect_source(source)
    reference_meta=contract.validate_old_reference(reference)
    watched={name:digest(reference/name)
             for name in FAMILIES[family]+INPUTS[family]}
    sys.path.insert(0,str(core/"scripts"))
    import build_p2_225_semantic_bundle as prep
    import build_p2_225_canonical_semantic_data as canonical
    import append_p2_nikkei_monthly_report as monthly
    import analyze_p2_nikkei_complete_baseline as cb
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import finalize_p2_nikkei_complete_baseline as fin
    t=time.perf_counter()
    produced={}
    elapsed={}
    if family=="dependent4":
        start=time.perf_counter()
        all_single=pd.read_csv(reference/"all_single_categories.csv",low_memory=False)
        representative=pd.read_csv(reference/"representative_single_categories.csv",low_memory=False)
        registry=pd.read_csv(reference/"candidate_registry.csv",low_memory=False)
        monthly_stability=pd.read_csv(reference/"monthly_stability.csv",low_memory=False)
        produced["parameter_plateau.csv"]=canonical._parameter_plateau(all_single,representative)
        produced["monthly_candidate_stability_summary.csv"]=monthly._candidate_monthly_summary(
            monthly_stability,registry)
        elapsed["dependent_canonical"]=round(time.perf_counter()-start,4)
        start=time.perf_counter()
        frame=prep.prepare_frame(source)
        normalized=frame.drop(columns=["y5","y10","y20"],errors="ignore").copy()
        normalized["as_of"]=normalized["as_of"].dt.strftime("%Y-%m-%d")
        produced["signal_level_features.csv"]=normalized
        produced["failures.csv"]=pd.DataFrame(columns=["as_of","error"])
        elapsed["features_normalization"]=round(time.perf_counter()-start,4)
    elif family=="walkforward1":
        frame=prep.prepare_frame(source)
        fields,expected=aug._rep_fields(frame)
        start=time.perf_counter()
        produced["walkforward_results.csv"]=aug._walkforward(frame,fields,expected)
        elapsed["canonical_walkforward"]=round(time.perf_counter()-start,4)
    elif family=="pair4":
        import p2_phase43_new_8_semantic_cached_20261016 as fast
        frame=prep.prepare_frame(source)
        t1=time.perf_counter()
        base=cb._baseline_metrics(frame)
        cached=fast.MetricCache(frame)
        fields,expected=aug._rep_fields(frame)
        masks={(feature,category):np.asarray(arr,dtype=object)==category
               for feature,arr in fields.items() for category in expected[feature]}
        single=pd.read_csv(reference/"representative_single_categories.csv",low_memory=False)
        if len(single)!=151 or single[["feature","category"]].duplicated().any():
            raise ValueError("Pinned representative singles incomplete")
        elapsed["prepare_cached_metrics"]=round(time.perf_counter()-t1,4)
        original=cb._metrics
        try:
            # Re-run bounded canonical pair/triple functions with audited cached
            # NumPy _metrics; do NOT redo already certified single4 outputs.
            cb._metrics=cached.metrics
            t1=time.perf_counter()
            pairs,_=aug._pairwise(frame,base,fields,expected,single,masks)
            elapsed["canonical_pairwise"]=round(time.perf_counter()-t1,4)
            print("PAIRWISE_NEW_FULL_ROWS",len(pairs),flush=True)
            t1=time.perf_counter()
            triples,_=aug._triples(frame,base,single,masks)
            elapsed["canonical_triple"]=round(time.perf_counter()-t1,4)
            print("TRIPLES_NEW_FULL_ROWS",len(triples),flush=True)
        finally:
            cb._metrics=original
        produced={
            "all_pairwise_combinations.csv":pairs,
            "tested_triple_combinations.csv":triples,
            "advantage_pairwise_candidates.csv":pairs.loc[fin._truthy(pairs["candidate"])].copy(),
            "advantage_triple_candidates.csv":triples.loc[fin._truthy(triples["candidate"])].copy(),
        }
        for name in ("advantage_pairwise_candidates.csv","advantage_triple_candidates.csv"):
            if "small_sample" not in produced[name]:
                produced[name]["small_sample"]=pd.to_numeric(
                    produced[name]["count"],errors="coerce").fillna(0).lt(30)
    else:
        raise ValueError("Unsupported new family")
    if set(produced)!=set(FAMILIES[family]):
        raise ValueError("New computation did not produce complete family")
    proof={}
    for name in FAMILIES[family]:
        start=time.perf_counter()
        legacy=pd.read_csv(reference/name,low_memory=False)
        new=produced[name]
        result=check_dataframe(legacy,new,name)
        proof[name]={
            **result,
            "legacy_sha256":watched[name],
            "canonical_function_newly_executed":True,
            "comparison_seconds":round(time.perf_counter()-start,4),
        }
        print("PASS_PHASE44_FRESH_UNSEEN_CSV",family,name,result["rows"],flush=True)
        del legacy
    if digest(source)!=contract.SOURCE_SHA:
        raise ValueError("Original saved features changed")
    for name,expected in watched.items():
        if digest(reference/name)!=expected:
            raise ValueError("Original saved CSV was modified")
    if subprocess.check_output(["git","-C",str(core),"diff","--name-only"],text=True).strip():
        raise ValueError("Core tracked files have been changed")
    if subprocess.check_output(["git","-C",str(core),"diff","--cached","--name-only"],text=True).strip():
        raise ValueError("Core index has been changed")
    return {
        "schema":1,
        "phase":44,
        "status":"PASS_PHASE44_BOUNDED_UNSEEN_FRESH_NUMERIC_FUNCTION",
        "dataset":"all_225",
        "family":family,
        "private_core_sha":CORE_SHA,
        "source_sha256":contract.SOURCE_SHA,
        "source_rows":source_meta["rows"],
        "source_tickers":source_meta["tickers"],
        "original_reference_count":reference_meta["csv_count"],
        "newly_computed_file_count":len(proof),
        "newly_computed":proof,
        "per_function_seconds":elapsed,
        "runtime_seconds":round(time.perf_counter()-t,3),
        "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
        "saved_inputs_recomputed":False,
        "prior_success_artifacts_recomputed":False,
        "private_core_modified":False,
        "full_29_e2e_new_producer_parity":False,
        "phase44_complete":False,
        "release_ready":False,
        "phase48_authorized":False,
    }

def main() -> int:
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--selftest",action="store_true")
    a.add_argument("--family",choices=sorted(FAMILIES))
    for name in ("core","source","reference","report"):
        a.add_argument("--"+name,type=Path)
    q=a.parse_args()
    if q.selftest:
        selftest()
        return 0
    if any(getattr(q,name) is None for name in ("family","core","source","reference","report")):
        a.error("All five pinned Phase44 arguments are required")
    if q.report.exists():
        raise FileExistsError("Proof output must not overwrite a previous report")
    proof=calculate(q.family,q.core.resolve(),q.source.resolve(),q.reference.resolve())
    q.report.parent.mkdir(parents=True,exist_ok=True)
    q.report.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS_PHASE44_INDEPENDENT_BOUNDED_NEW_FILE_COUNT",q.family,proof["newly_computed_file_count"],flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
