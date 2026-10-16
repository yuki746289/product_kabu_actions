"""Bounded independent all225 canonical OR candidate summary stability.

Use old SHA-pinned OR-unique inputs as already independently proven checkpoint
and regenerate original ranking, candidate selection and monthly stability
rather than copying OR candidate summary rows. This is NOT fresh raw OR math.
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

N_SHARDS=6
TOTAL=60
FIRST=5
SOURCE_NAMES=("or_pairwise_unique.csv","or_triple_unique.csv")
TARGET="or_candidate_summary.csv"

def region(shard):
    if not 0<=shard<N_SHARDS:raise ValueError("Candidate shard out of bounds")
    if shard==0:return 0,FIRST
    return FIRST+(TOTAL-FIRST)*(shard-1)//(N_SHARDS-1),FIRST+(TOTAL-FIRST)*shard//(N_SHARDS-1)

def selftest():
    seg=[region(i) for i in range(N_SHARDS)]
    assert seg[0]==(0,FIRST) and seg[-1][1]==TOTAL
    assert all(seg[i][1]==seg[i+1][0] for i in range(N_SHARDS-1))
    print("PASS_CANONICAL_OR_CANDIDATE_COVERAGE_6_SHARDS")

def run(core,source,reference,shard):
    import pandas as pd
    import numpy as np
    lo,hi=region(shard)
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=contract.CORE_SHA:
        raise ValueError("Original Private core SHA mismatch")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Missing Actions policy")
    if subprocess.check_output(["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],text=True).strip():
        raise ValueError("Private workflows forbidden")
    contract.inspect_source(source)
    contract.validate_old_reference(reference)
    original_sha={name:contract.sha256(reference/name)
                  for name in SOURCE_NAMES+(TARGET,)}
    sys.path.insert(0,str(core/"scripts"))
    import build_p2_225_semantic_bundle as sem
    import analyze_p2_or_combinations as canonical
    import finalize_p2_nikkei_complete_baseline as fin
    t=time.perf_counter()
    frame=sem.prepare_frame(source)
    unique=pd.concat([pd.read_csv(reference/name,low_memory=False)
                      for name in SOURCE_NAMES],ignore_index=True,sort=False)
    balanced=unique.loc[unique["balanced_candidate"]].copy().sort_values(
        ["balance_index","avg_win_pct","count"],ascending=False)
    expansion=unique.loc[unique["expansion_candidate"]].copy().sort_values(
        ["balance_index","incremental_entries_vs_largest"],ascending=False)
    accuracy=unique.loc[unique["high_accuracy_candidate"]].copy().sort_values(
        ["avg_win_pct","count"],ascending=False)
    pool=pd.concat(
        [balanced.head(60),expansion.head(60),accuracy.head(60)],
        ignore_index=True,sort=False
    ).drop_duplicates("condition_key",keep="first").reset_index(drop=True)
    old=pd.read_csv(reference/TARGET,low_memory=False)
    if (len(old)!=TOTAL or len(pool)!=TOTAL
        or old["condition_key"].duplicated().any()
        or pool["condition_key"].tolist()!=old["condition_key"].tolist()):
        raise ValueError("Canonical OR candidate selection identities/order changed")
    selection=pool.iloc[lo:hi].copy()
    masks=fin._feature_masks(frame)
    masks_by_row=[]
    for _,row in selection.iterrows():
        n=2 if row["condition_type"]=="or2" else 3
        factors=[masks[(str(row[f"feature{i}"]),str(row[f"category{i}"]))]
                 for i in range(1,n+1)]
        masks_by_row.append(np.logical_or.reduce(factors))
    selection["_mask"]=masks_by_row
    # Cached period and target arrays preserve the original calculations.
    months=canonical.r.months(frame)
    pmonth=frame["as_of"].dt.to_period("M")
    month_masks=[pmonth.eq(mon).to_numpy() for mon in months]
    years=sorted(frame["as_of"].dt.year.unique())
    yyears=frame["as_of"].dt.year.to_numpy()
    year_masks=[yyears==year for year in years]
    ys={h:pd.to_numeric(frame[f"moved_predicted_{h}d"],errors="coerce").to_numpy(float)
        for h in (5,10,20)}
    rets={h:pd.to_numeric(frame[f"directional_return_{h}d_pct"],errors="coerce").to_numpy(float)
          for h in (5,10,20)}
    yf={h:np.isfinite(ys[h]) for h in ys}
    rf={h:np.isfinite(rets[h]) for h in rets}
    original_months=canonical._monthly_yearly
    def cached_months(data,mask):
        if data is not frame:
            raise ValueError("Unknown cached source object")
        monthly=[]
        for mon,pm in zip(months,month_masks):
            cm=pm&mask
            record={"month":str(mon),"count":int(cm.sum())}
            for h in (5,10,20):
                bv=pm&yf[h]
                cv=cm&yf[h]
                rv=cm&rf[h]
                record[f"win_{h}d_pct"]=float(ys[h][cv].mean()*100.0) if cv.any() else np.nan
                record[f"baseline_win_{h}d_pct"]=float(ys[h][bv].mean()*100.0) if bv.any() else np.nan
                record[f"uplift_{h}d_pp"]=(
                    record[f"win_{h}d_pct"]-record[f"baseline_win_{h}d_pct"]
                    if cv.any() and bv.any() else np.nan)
                record[f"return_{h}d_pct"]=float(rets[h][rv].mean()) if rv.any() else np.nan
            monthly.append(record)
        yearly=[]
        for yr,py in zip(years,year_masks):
            cy=py&mask
            record={"year":int(yr),"count":int(cy.sum())}
            for h in (5,10,20):
                bv=py&yf[h]
                cv=cy&yf[h]
                record[f"win_{h}d_pct"]=float(ys[h][cv].mean()*100.0) if cv.any() else np.nan
                record[f"baseline_win_{h}d_pct"]=float(ys[h][bv].mean()*100.0) if bv.any() else np.nan
                record[f"uplift_{h}d_pp"]=(
                    record[f"win_{h}d_pct"]-record[f"baseline_win_{h}d_pct"]
                    if cv.any() and bv.any() else np.nan)
            yearly.append(record)
        return pd.DataFrame(monthly),pd.DataFrame(yearly)
    for mask in masks_by_row[:2]:
        reference_month,reference_year=original_months(frame,mask)
        cache_month,cache_year=cached_months(frame,mask)
        check_dataframe(reference_month,cache_month,"monthly_arrays_canary")
        check_dataframe(reference_year,cache_year,"yearly_arrays_canary")
    try:
        canonical._monthly_yearly=cached_months
        result=canonical._csv_ready(canonical._add_stability(frame,selection))
    finally:
        canonical._monthly_yearly=original_months
    if len(result)!=hi-lo:
        raise ValueError("New candidate monthly row count changed")
    old_subset=old.iloc[lo:hi].reset_index(drop=True)
    # This selected bounded batch has exactly the full-source schema since
    # selection originates from the combined OR2+OR3 schema.
    checked=check_dataframe(old_subset,result,TARGET)
    for name,sha in original_sha.items():
        if contract.sha256(reference/name)!=sha:
            raise ValueError("Original candidate reference changed")
    if contract.sha256(source)!=contract.SOURCE_SHA:
        raise ValueError("Input features changed")
    if subprocess.check_output(["git","-C",str(core),"diff","--name-only"],text=True).strip():
        raise ValueError("Tracked Private code changed")
    return {
        "phase":44,"status":"PASS_PHASE44_NEW_OR_CANDIDATE_MONTHLY_SHARD",
        "dataset":"all_225","shard":shard,"total_shards":N_SHARDS,
        "start":lo,"end":hi,"canonical_total_candidates":TOTAL,
        "rows_newly_calculated":hi-lo,"numeric_value_and_identity_parity":True,
        "entire_candidate_key_selection_coverage":True,
        "source_sha256":contract.SOURCE_SHA,"private_core_sha":contract.CORE_SHA,
        "original_target_sha256":original_sha[TARGET],
        "canonical_monthly_arrays_vs_original_sample":True,
        "seconds":round(time.perf_counter()-t,3),
        "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
        "old_raw_or_recomputed":False,
        "prior_success_artifacts_recomputed":False,
        "phase44_complete":False,"release_ready":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--shard",type=int)
    for name in ("core","source","reference","report"):
        p.add_argument("--"+name,type=Path)
    a=p.parse_args()
    if a.selftest:selftest();return
    if any(getattr(a,n) is None for n in ("shard","core","source","reference","report")):
        p.error("Missing source, reference, shard or report")
    if a.report.exists():raise FileExistsError("Refuse to overwrite prior proof")
    result=run(a.core.resolve(),a.source.resolve(),a.reference.resolve(),a.shard)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS_PHASE44_NEW_OR_CANDIDATE_SHARD",a.shard,result["rows_newly_calculated"],flush=True)

if __name__=="__main__":main()
