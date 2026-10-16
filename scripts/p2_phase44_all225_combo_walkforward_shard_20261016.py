"""Bounded original-function independent combination walkforward, all_225 two-year shards.

Each job evaluates *all* old saved pair and triple inputs over one disjoint
two-year test period, recomputes canonical train-selected winning conditions
from pinned original immutable 181318-row features, and independently compares
every old CSV column. No full original producer, prior success artifact, or
Production P2 v12 is rerun or changed. Metadata-only certificates leave worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import p2_phase44_all225_fresh_newproducer_29csv_20261016 as contract

HORIZONS=(5,10,20)
N_SHARDS=7
START_YEAR=2013
N_PER_SHARD=2
FAMILIES={"pair":"all_pairwise_combinations.csv",
          "triple":"tested_triple_combinations.csv"}
REFERENCE="combination_walkforward_results.csv"
PROTECTED=["condition_type","horizon","test_year","train_count","train_uplift_pp",
           "test_count","test_win_pct","test_baseline_win_pct","test_uplift_pp",
           "feature1","category1","feature2","category2","feature3","category3"]

def selftest():
    assert [START_YEAR+N_PER_SHARD*i for i in range(N_SHARDS)]==[2013,2015,2017,2019,2021,2023,2025]
    assert sorted(set(y for i in range(N_SHARDS) for y in range(
        START_YEAR+2*i,START_YEAR+2*i+2)))==list(range(2013,2027))
    assert set(FAMILIES.values()).issubset(contract.EXPECTED_FILES)
    print("PASS_PHASE44_COMBO_WALKFORWARD_7_TWO_YEAR_SHARDS")

def run(core:Path,source:Path,ref:Path,shard:int):
    import pandas as pd
    import numpy as np
    if not 0<=shard<N_SHARDS:
        raise ValueError("Expected shard index 0-6")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=contract.CORE_SHA:
        raise ValueError("Immutable private code SHA mismatch")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Private policy missing")
    if subprocess.check_output(
        ["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],
        text=True).strip():
        raise ValueError("Private Actions forbidden")
    source_meta=contract.inspect_source(source)
    contract.validate_old_reference(ref)
    watched={name:contract.sha256(ref/name)
             for name in tuple(FAMILIES.values())+(REFERENCE,)}
    t=time.perf_counter()
    sys.path.insert(0,str(core/"scripts"))
    import build_p2_225_semantic_bundle as sem
    import finalize_p2_nikkei_complete_baseline as fin
    frame=sem.prepare_frame(source)
    years=frame["as_of"].dt.year.to_numpy(int)
    all_years=sorted(set(years))
    expected=list(range(START_YEAR,START_YEAR+N_SHARDS*N_PER_SHARD))
    if (all_years[0]!=START_YEAR-5 or
        [y for y in all_years if y>=all_years[0]+5]!=expected):
        raise ValueError("Fixed source years changed; cannot reuse shard layout")
    target_years=list(range(START_YEAR+2*shard,START_YEAR+2*shard+2))
    old_total=pd.read_csv(ref/REFERENCE,low_memory=False)
    if list(old_total.columns)!=PROTECTED:
        raise ValueError("Original canonical walkforward CSV column order mismatch")
    old=old_total.loc[old_total["test_year"].isin(target_years)].reset_index(drop=True)
    if len(old)!=12:
        raise ValueError("Incomplete 2-year original walkforward expected exactly 12 rows")
    masks=fin._feature_masks(frame)
    data={k:pd.read_csv(ref/name,low_memory=False) for k,name in FAMILIES.items()}
    new=[]
    for year in target_years:
        train=years<year
        test=years==year
        for kind,table in data.items():
            best={}
            yall={h:pd.to_numeric(frame[f"moved_predicted_{h}d"],errors="coerce").to_numpy(float)
                  for h in HORIZONS}
            bmask={h:train&np.isfinite(yall[h]) for h in HORIZONS}
            bmean={h:float(yall[h][bmask[h]].mean()*100) if bmask[h].any()
                    else float("nan") for h in HORIZONS}
            for _,row in table.iterrows():
                mask=fin._condition_mask(row,kind,masks)
                ntrain=int(np.count_nonzero(train&mask))
                if ntrain<20:
                    continue
                for h in HORIZONS:
                    valid=bmask[h]&mask
                    if valid.sum()<20 or not bmask[h].any():
                        continue
                    uplift=float(yall[h][valid].mean()*100 - bmean[h])
                    cur=best.get(h)
                    if cur is None or (uplift,ntrain)>(cur[0],cur[1]):
                        best[h]=(uplift,ntrain,row,mask)
            for h,(uplift,ntrain,row,mask) in best.items():
                y=yall[h]
                bv=test&np.isfinite(y)
                kv=test&mask&np.isfinite(y)
                rec={
                    "condition_type":kind,"horizon":f"{h}D",
                    "test_year":year,"train_count":ntrain,
                    "train_uplift_pp":uplift,
                    "test_count":int(kv.sum()),
                    "test_win_pct":float(y[kv].mean()*100) if kv.any() else np.nan,
                    "test_baseline_win_pct":float(y[bv].mean()*100) if bv.any() else np.nan,
                    "test_uplift_pp":float(y[kv].mean()*100-y[bv].mean()*100)
                        if kv.any() and bv.any() else np.nan,
                }
                for idx in range(1,4 if kind=="triple" else 3):
                    rec[f"feature{idx}"]=row[f"feature{idx}"]
                    rec[f"category{idx}"]=row[f"category{idx}"]
                new.append(rec)
        print("PASS_NEW_COMPLETE_YEAR_CALCULATION",year,len(new),flush=True)
    actual=pd.DataFrame(new).reindex(columns=PROTECTED)
    if len(actual)!=len(old):
        raise ValueError("New entire-year condition winners count differs")
    keys=["test_year","condition_type","horizon"]
    if old.duplicated(keys).any() or actual.duplicated(keys).any():
        raise ValueError("Duplicate condition/year/horizon key")
    if not set(tuple(v) for v in old[keys].to_numpy())==set(
        tuple(v) for v in actual[keys].to_numpy()):
        raise ValueError("Condition/year/horizon identity mismatch")
    actual=actual.sort_values(keys,kind="stable").reset_index(drop=True)
    old=old.sort_values(keys,kind="stable").reset_index(drop=True)
    pd.testing.assert_frame_equal(
        old,actual,check_dtype=False,check_exact=False,
        rtol=contract.REL_TOL,atol=contract.ABS_TOL,check_index_type=False
    )
    for name,digest in watched.items():
        if contract.sha256(ref/name)!=digest:
            raise ValueError("Original canonical reference unexpectedly changed")
    if contract.sha256(source)!=contract.SOURCE_SHA:
        raise ValueError("Original source SHA drift")
    if subprocess.check_output(["git","-C",str(core),"diff","--name-only"],text=True).strip():
        raise ValueError("Private tracked files modified")
    return {
        "phase":44,"status":"PASS_PHASE44_ALL225_CANONICAL_COMBO_WALKFORWARD_TWO_YEARS",
        "shard":shard,"total_shards":N_SHARDS,
        "dataset":"all_225","years":target_years,
        "old_full_source_sha256":contract.SOURCE_SHA,
        "old_reference_sha256":watched[REFERENCE],
        "private_core_sha":contract.CORE_SHA,
        "full_source_rows":source_meta["rows"],
        "rows_compared":len(old),"compared_cells":len(old)*len(old.columns),
        "all_column_value_and_identity_equal":True,
        "time_seconds":round(time.perf_counter()-t,3),
        "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
        "source_signals_recomputed":False,
        "original_csv_html_modified":False,"prior_success_artifacts_recomputed":False,
        "all_29_full_newproducer_certified":False,
        "phase44_complete":False,"release_ready":False,
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--shard",type=int)
    for arg in ("core","source","reference","report"):
        p.add_argument("--"+arg,type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest()
        return 0
    if any(getattr(a,k) is None for k in ("shard","core","source","reference","report")):
        p.error("Shard/core/source/reference/report required")
    if a.report.exists():
        raise FileExistsError("No overwriting previous bounded proof")
    result=run(a.core.resolve(),a.source.resolve(),a.reference.resolve(),a.shard)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS_PHASE44_COMBO_WALKFORWARD_TWO_YEARS",a.shard,flush=True)

if __name__=="__main__":
    main()
