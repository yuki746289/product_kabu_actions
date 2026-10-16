"""Source-pinned optimized canonical combination stability, disjoint row shards.

The canonical _stability_summary function remains unmodified, but its repeated
_pandas-to-numpy_ conversion in _uplift is replaced temporarily by an exactly
equivalent cached-array implementation. A negative/control sample compares
original and cached uplift values before accepting data. Original source
pair/triple candidate rows are fixed old successful CSV read-only inputs.
No private CSV is published; only status/timings/hashes/counters leave runner.
"""
from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import p2_phase44_all225_fresh_newproducer_29csv_20261016 as contract
from p2_phase44_optimized_family_20261016 import check_dataframe

FIRST=120
N_SHARDS=13
TOTAL=9812
REFERENCE="combination_stability_summary.csv"
SOURCE_CSVS=("advantage_pairwise_candidates.csv",
             "advantage_triple_candidates.csv")
KIND=("pair","triple")

def boundaries(shard:int)->tuple[int,int]:
    if not 0<=shard<N_SHARDS:
        raise ValueError("Shard must be 0 to 12")
    if shard==0:
        return 0,FIRST
    return (
        FIRST+(TOTAL-FIRST)*(shard-1)//(N_SHARDS-1),
        FIRST+(TOTAL-FIRST)*shard//(N_SHARDS-1),
    )

def selftest()->None:
    parts=[boundaries(i) for i in range(N_SHARDS)]
    assert len(parts)==N_SHARDS
    assert parts[0]==(0,FIRST) and parts[-1][1]==TOTAL
    assert all(parts[i][1]==parts[i+1][0] for i in range(N_SHARDS-1))
    assert sum(b-a for a,b in parts)==TOTAL
    print("PASS_PHASE44_COMBO_STABILITY_EXACT_THIRTEEN_DISJOINT_SHARDS")

def run(core:Path,source:Path,reference:Path,shard:int)->dict:
    import numpy as np
    import pandas as pd
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=contract.CORE_SHA:
        raise ValueError("Source code SHA differs")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Private Actions policy not found")
    if subprocess.check_output(
        ["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],
        text=True).strip():
        raise ValueError("Original Private Actions forbidden")
    source_meta=contract.inspect_source(source)
    contract.validate_old_reference(reference)
    old_hashes={name:contract.sha256(reference/name)
               for name in (REFERENCE,)+SOURCE_CSVS}
    start,end=boundaries(shard)
    sys.path.insert(0,str(core/"scripts"))
    import build_p2_225_semantic_bundle as sem
    import finalize_p2_nikkei_complete_baseline as fin
    t=time.perf_counter()
    frame=sem.prepare_frame(source)
    if len(frame)!=181318:
        raise ValueError("Source rows unexpectedly changed")
    masks=fin._feature_masks(frame)
    candidates={name:pd.read_csv(reference/name,low_memory=False)
                for name in SOURCE_CSVS}
    if [len(candidates[x]) for x in SOURCE_CSVS]!=[3025,6787]:
        raise ValueError("Original canonical selected-pair/triple population differs")
    for name in SOURCE_CSVS:
        a=candidates[name]
        if not bool(fin._truthy(a["candidate"]).all()):
            raise ValueError("Saved selected candidate erroneously includes noncandidate")
    old=pd.read_csv(reference/REFERENCE,low_memory=False)
    if len(old)!=TOTAL:
        raise ValueError("Original candidate stability row count changed")
    # Prepare only the precise slice of old fixed input candidates.
    portions=[]
    offset=0
    for kind,name in zip(KIND,SOURCE_CSVS):
        table=candidates[name]
        lo=max(start,offset)-offset
        hi=min(end,offset+len(table))-offset
        if lo<hi:
            portions.append((kind,table.iloc[lo:hi].copy()))
        offset+=len(table)
    if sum(len(p) for _,p in portions)!=end-start:
        raise ValueError("Candidate slicing is incomplete")
    y={h:pd.to_numeric(frame[f"moved_predicted_{h}d"],errors="coerce").to_numpy(float)
       for h in (5,10,20)}
    finite={h:np.isfinite(v) for h,v in y.items()}
    old_uplift=fin._uplift
    def fast_uplift(data,mask,period,h):
        if data is not frame:
            raise ValueError("Cached array requested for unrelated frame")
        b=period&finite[h]
        k=b&mask
        if b.sum()==0 or k.sum()<2:
            return np.nan
        return float(y[h][k].mean()*100.0 - y[h][b].mean()*100.0)
    # Test the optimized implementation against real original canonical uplift.
    test_masks=list(masks.values())[:6]
    years=frame["as_of"].dt.year.to_numpy(int)
    for m in test_masks:
        for year in (2013,2018,2023):
            period=years==year
            for h in (5,10,20):
                a=old_uplift(frame,m,period,h)
                b=fast_uplift(frame,m,period,h)
                if not np.isclose(a,b,atol=contract.ABS_TOL,
                                  rtol=contract.REL_TOL,equal_nan=True):
                    raise ValueError("Canonical _uplift reference mismatch")
    out=[]
    try:
        fin._uplift=fast_uplift
        for kind,subset in portions:
            before=time.perf_counter()
            part=fin._stability_summary(frame,subset,kind,masks)
            if len(part)!=len(subset):
                raise ValueError("Canonical stability source selection mismatch")
            out.append(part)
            print("PASS_NEW_CANONICAL_STABILITY_CANDIDATE_SEGMENT",shard,kind,
                  len(part),round(time.perf_counter()-before,2),flush=True)
    finally:
        fin._uplift=old_uplift
    fresh=pd.concat(out,ignore_index=True,sort=False)
    expected=old.iloc[start:end].reset_index(drop=True)
    # A bounded pair-only/triple-only shard does not itself contain columns
    # belonging exclusively to the other kind. The original full CSV is a
    # concatenation of both kinds. Only canonical all-NA union columns may be
    # introduced here; never suppress, coerce or reorder mismatched values.
    missing=set(expected.columns)-set(fresh.columns)
    permitted={"feature3","category3","incremental_5d_pp",
               "incremental_10d_pp","incremental_20d_pp"}
    unexpected=set(fresh.columns)-set(expected.columns)
    if unexpected or not missing.issubset(permitted):
        raise ValueError("Unexpected canonical stability union schema difference")
    for col in missing:
        if not expected[col].isna().all():
            raise ValueError("Missing canonical union column has real source values: "+col)
    fresh=fresh.reindex(columns=expected.columns)
    checked=check_dataframe(expected,fresh,REFERENCE)
    for name,old_sha in old_hashes.items():
        if contract.sha256(reference/name)!=old_sha:
            raise ValueError("Original source/stability CSV mutated")
    if contract.sha256(source)!=contract.SOURCE_SHA:
        raise ValueError("Original feature source mutated")
    if subprocess.check_output(["git","-C",str(core),"diff","--name-only"],text=True).strip():
        raise ValueError("Tracked Private original source changed")
    return {
        "phase":44,"status":"PASS_PHASE44_ALL225_COMBO_STABILITY_CANONICAL_SHARD",
        "shard":shard,"total_shards":N_SHARDS,
        "dataset":"all_225","range_start":start,"range_end":end,
        "source_sha256":contract.SOURCE_SHA,
        "original_reference_sha256":old_hashes[REFERENCE],
        "private_core_sha":contract.CORE_SHA,
        "source_rows":source_meta["rows"],
        "calculated_candidates":end-start,
        "verified_rows":checked["rows"],
        "verified_columns":checked["columns"],
        "all_row_column_numeric_parity":checked["all_rows_columns_numeric_equal"],
        "numeric_tolerance":{"relative":contract.REL_TOL,"absolute":contract.ABS_TOL},
        "temporary_array_cache_parity_sample":True,
        "elapsed_seconds":round(time.perf_counter()-t,3),
        "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
        "old_computations_reused_without_rerun":True,
        "previous_success_artifacts_recomputed":False,
        "production_p2_changed":False,"release_ready":False,
        "full_new_29_CSV_certified":False,
    }

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--shard",type=int)
    for arg in ("core","source","reference","report"):
        p.add_argument("--"+arg,type=Path)
    x=p.parse_args()
    if x.selftest:
        selftest()
        return 0
    if any(getattr(x,k) is None for k in ("shard","core","source","reference","report")):
        p.error("Requires shard, source, reference and fixed core")
    if x.report.exists():
        raise FileExistsError("New proof output cannot overwrite previously stored evidence")
    result=run(x.core.resolve(),x.source.resolve(),x.reference.resolve(),x.shard)
    x.report.parent.mkdir(parents=True,exist_ok=True)
    x.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS_PHASE44_COMBO_STABILITY_DISJOINT_SHARD",result["shard"],result["verified_rows"],flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
