# Created 2026-10-16 JST.
"""Benchmark actual P2 masks, _metrics, and _stability_summary read-only.

Fixed 48,782 saved technology rows, fixed Private source SHA and Phase38 proof.
Compares original exact canonical functions to fully equivalent cached NumPy
and (for masks/metrics) Polars alternatives. Each actual same-pair/triple mask
and all numeric outputs must match BEFORE speed is reported as PASS.
No full semantic/OR or 29CSV producer, no existing artifacts regenerated.
Public artifact contains timings, memory, input digests and parity flags ONLY.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
SOURCE_SHA="ca81bb74c6936be6ee77182396b6549bdfaed0526ac6fd564210f0b4ed92bfb3"
DATASET="technology"
FILES=("all_pairwise_combinations.csv","tested_triple_combinations.csv")
PAIR_N=12
TRIPLE_N=6
STAB_PAIR_N=3
STAB_TRIPLE_N=2
TIMING_REPEATS=3
HORIZONS=(5,10,20)

def sha(path:Path):
    h=hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda:file.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def timed(fn,repeats=TIMING_REPEATS):
    times=[]
    result=None
    for _ in range(repeats):
        t=time.perf_counter()
        result=fn()
        times.append(time.perf_counter()-t)
    return result,{"median_seconds":round(statistics.median(times),6),
                   "individual_seconds":[round(x,6) for x in times]}

def same_number(old,new,name):
    import numpy as np
    if isinstance(old,(bool,str)) or isinstance(new,(bool,str)):
        if old!=new:raise AssertionError("label differs: "+name)
        return
    if not np.isclose(float(old),float(new),atol=1e-7,rtol=1e-10,equal_nan=True):
        raise AssertionError("numeric parity differs: "+name+" ("+str(old)+" vs "+str(new)+")")

def same_records(old,new,label):
    if len(old)!=len(new):
        raise AssertionError(label+" record count differs")
    for i,(a,b) in enumerate(zip(old,new)):
        if set(a)!=set(b):
            raise AssertionError(label+" columns changed at record "+str(i))
        for key in a:
            same_number(a[key],b[key],f"{label}[{i}].{key}")

def make_key(kind,row):
    return tuple((str(row[f"feature{i}"]),str(row[f"category{i}"]))
                  for i in range(1,4 if kind=="triple" else 3))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--core",type=Path,required=True)
    ap.add_argument("--phase38",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    core=args.core.resolve()
    if args.report.exists():raise FileExistsError("Never overwrite previous benchmark")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=CORE_SHA:
        raise ValueError("Private fixed SHA changed")
    p=json.loads(args.phase38.read_text(encoding="utf-8"))
    if not (p.get("status")=="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"
            and p.get("dataset")==DATASET and p.get("private_core_sha")==CORE_SHA
            and p.get("source_sha256")==SOURCE_SHA
            and p.get("source_rows")==48782 and p.get("source_tickers")==61
            and p.get("mismatches")==[]):
        raise ValueError("Original saved Phase38 source identity mismatch")
    ref=core/"preview/kabu/analysis/225_group_all_period/technology"
    source=ref/"signal_level_features.csv"
    if sha(source)!=SOURCE_SHA:raise ValueError("Original source changed")
    for file in FILES:
        if sha(ref/file)!=p["files"][file]["sha256"]:
            raise ValueError("Original saved condition source CSV SHA mismatch")
    import numpy as np
    import pandas as pd
    import polars as pl
    sys.path.insert(0,str(core/"scripts"))
    import build_p2_225_semantic_bundle as sem
    import finalize_p2_nikkei_complete_baseline as fin
    import analyze_p2_nikkei_complete_baseline as cb

    # Input preparation is not included in inner-function timings.
    t0=time.perf_counter()
    frame=sem.prepare_frame(source)
    if len(frame)!=48782:raise ValueError("Technology original full source size changed")
    base=cb._baseline_metrics(frame)
    masks,create_seconds=timed(lambda:fin._feature_masks(frame),repeats=1)
    pairs=pd.read_csv(ref/FILES[0],low_memory=False)
    triples=pd.read_csv(ref/FILES[1],low_memory=False)
    cases=[]
    for kind,table,n in (("pair",pairs,PAIR_N),("triple",triples,TRIPLE_N)):
        selected=table.loc[fin._truthy(table["candidate"])].head(n)
        if len(selected)!=n:raise ValueError("Insufficient real original candidate keys")
        for _,row in selected.iterrows():
            key=make_key(kind,row)
            for k in key:
                if k not in masks:raise ValueError("Original categorical feature mask absent")
            cases.append((kind,row,key))
    inputs_sec=round(time.perf_counter()-t0,6)
    print("SOURCE_READY",len(frame),"masks",len(masks),"cases",len(cases),flush=True)

    # MASK benchmark: Polars and NumPy only intersect canonical PRECOMPUTED
    # feature masks. The original categorical classification is measured separately.
    keys=list(dict.fromkeys(k for _,_,m in cases for k in m))
    mask_cols={key:f"v{i}" for i,key in enumerate(keys)}
    flags=pl.DataFrame({mask_cols[key]:masks[key] for key in keys})
    def original_masks():
        return [fin._condition_mask(row,kind,masks) for kind,row,_ in cases]
    def numpy_masks():
        return [np.logical_and.reduce([masks[k] for k in keys_for])
                for _,_,keys_for in cases]
    def polars_masks():
        return [flags.select(pl.all_horizontal(*(pl.col(mask_cols[k]) for k in keys_for)))
                  .to_series().to_numpy()
                for _,_,keys_for in cases]
    orig_masks,t_orig_mask=timed(original_masks)
    nm,t_num_mask=timed(numpy_masks)
    pm,t_pol_mask=timed(polars_masks)
    for group in (nm,pm):
        for a,b in zip(orig_masks,group):
            if not np.array_equal(a,b):raise AssertionError("Mask True/False differs")
    del nm,pm
    print("PASS_ALL_ORIGINAL_PAIR_TRIPLE_BOOLEAN_MASKS",len(cases),flush=True)

    # CACHE for metrics: all original full arrays, 3 valid outcomes+returns and
    # per-year full baselines; don't reimplement original signal/condition rules.
    years=frame["as_of"].dt.year.to_numpy(int)
    yrs=sorted(set(years))
    year_masks={year:years==year for year in yrs}
    y={h:pd.to_numeric(frame[f"moved_predicted_{h}d"],errors="coerce").to_numpy(float) for h in HORIZONS}
    returns={h:pd.to_numeric(frame[f"directional_return_{h}d_pct"],errors="coerce").to_numpy(float) for h in HORIZONS}
    valid={h:np.isfinite(y[h]) for h in HORIZONS}
    rval={h:np.isfinite(returns[h]) for h in HORIZONS}
    year_baseline={h:{year:(
        int((ym & valid[h]).sum()),
        float(y[h][ym & valid[h]].mean()*100) if (ym & valid[h]).any() else np.nan)
        for year,ym in year_masks.items()} for h in HORIZONS}

    def metrics_numpy(mask):
        mask=np.asarray(mask,dtype=bool)
        n=int(mask.sum())
        result={"count":n,"retention_pct":n/len(frame)*100}
        for h in HORIZONS:
            good=mask & valid[h];good_r=mask & rval[h]
            win=float(y[h][good].mean()*100) if good.any() else np.nan
            ret=float(returns[h][good_r].mean()) if good_r.any() else np.nan
            result[f"win_{h}d_pct"]=win
            result[f"return_{h}d_pct"]=ret
            result[f"win_uplift_{h}d_pp"]=win-base[h][0] if np.isfinite(win) else np.nan
            result[f"return_uplift_{h}d_pct"]=ret-base[h][1] if np.isfinite(ret) else np.nan
            uplifts=[]
            for year in yrs:
                ym=year_masks[year]
                nbase,baseline=year_baseline[h][year]
                km=ym & good
                if nbase<3 or km.sum()<2:continue
                uplifts.append(float(y[h][km].mean()*100 - baseline))
            result[f"evaluable_years_{h}d"]=len(uplifts)
            result[f"positive_year_share_{h}d_pct"]=float((np.asarray(uplifts)>0).mean()*100) if uplifts else np.nan
            result[f"worst_year_uplift_{h}d_pp"]=float(min(uplifts)) if uplifts else np.nan
        return result

    # Polars aggregate with the same exact nonfinite and minimum counts as
    # the canonical pandas/Numpy function; category masks still canonical.
    pldata={"year":years}
    for h in HORIZONS:
        pldata[f"y{h}"]=pl.Series(np.where(valid[h],y[h],np.nan)).fill_nan(None)
        pldata[f"r{h}"]=pl.Series(np.where(rval[h],returns[h],np.nan)).fill_nan(None)
    pldf=pl.DataFrame(pldata)
    def metrics_polars(mask):
        f=pldf.with_columns(pl.Series("selected",mask))
        out={"count":int(mask.sum()),"retention_pct":int(mask.sum())/len(frame)*100}
        for h in HORIZONS:
            ycol=f"y{h}";rcol=f"r{h}"
            stats=f.select(
                pl.col(ycol).filter(pl.col("selected")).mean().alias("win"),
                pl.col(rcol).filter(pl.col("selected")).mean().alias("ret")
            ).row(0,named=True)
            win=float(stats["win"]*100) if stats["win"] is not None else np.nan
            ret=float(stats["ret"]) if stats["ret"] is not None else np.nan
            out[f"win_{h}d_pct"]=win
            out[f"return_{h}d_pct"]=ret
            out[f"win_uplift_{h}d_pp"]=win-base[h][0] if np.isfinite(win) else np.nan
            out[f"return_uplift_{h}d_pct"]=ret-base[h][1] if np.isfinite(ret) else np.nan
            sub=f.group_by("year").agg(
                pl.col(ycol).count().alias("nb"),
                pl.col(ycol).filter(pl.col("selected")).count().alias("nk"),
                pl.col(ycol).mean().alias("bm"),
                pl.col(ycol).filter(pl.col("selected")).mean().alias("km"),
            ).sort("year")
            uplifts=[]
            for r in sub.iter_rows(named=True):
                if r["nb"]<3 or r["nk"]<2:continue
                uplifts.append(float(r["km"]*100-r["bm"]*100))
            out[f"evaluable_years_{h}d"]=len(uplifts)
            out[f"positive_year_share_{h}d_pct"]=float((np.asarray(uplifts)>0).mean()*100) if uplifts else np.nan
            out[f"worst_year_uplift_{h}d_pp"]=float(min(uplifts)) if uplifts else np.nan
        return out

    def original_metrics():
        return [cb._metrics(frame,mask,base) for mask in orig_masks]
    def numpy_metrics():
        return [metrics_numpy(mask) for mask in orig_masks]
    def polars_metrics():
        return [metrics_polars(mask) for mask in orig_masks]
    oldm,t_orig_metrics=timed(original_metrics)
    num,t_num_metrics=timed(numpy_metrics)
    pol,t_pol_metrics=timed(polars_metrics)
    same_records(oldm,num,"NumPy cached _metrics")
    same_records(oldm,pol,"Polars _metrics")
    print("PASS_ALL_METRICS_PARITY",len(cases),"fields",len(oldm[0]),flush=True)

    # STABILITY: original entire producer vs exact same producer with
    # _uplift accelerated solely by cached horizon float arrays. This keeps
    # authoritative row labels, condition IDs, periods, ordering and all
    # numerical calculations except repeated pd.to_numeric conversions.
    stab_parts=[pairs.loc[fin._truthy(pairs["candidate"])].head(STAB_PAIR_N),
                triples.loc[fin._truthy(triples["candidate"])].head(STAB_TRIPLE_N)]
    def stability_once():
        return pd.concat([
            fin._stability_summary(frame,stab_parts[0],"pair",masks),
            fin._stability_summary(frame,stab_parts[1],"triple",masks)
        ],ignore_index=True,sort=False)
    original_uplift=fin._uplift
    old_stab,t_orig_stab=timed(stability_once,repeats=2)
    def cached_uplift(_frame,mask,period_mask,h):
        b=period_mask & valid[h]
        k=b & mask
        if b.sum()==0 or k.sum()<2:return np.nan
        return float(y[h][k].mean()*100.0-y[h][b].mean()*100.0)
    try:
        fin._uplift=cached_uplift
        new_stab,t_cached_stab=timed(stability_once,repeats=2)
    finally:
        fin._uplift=original_uplift
    pd.testing.assert_frame_equal(old_stab,new_stab,check_dtype=False,
                                  check_exact=False,atol=1e-7,rtol=1e-10)
    print("PASS_FULL_STABILITY_ROW_NUMERIC_LABEL_PARITY",len(old_stab),flush=True)

    result={
      "schema":1,
      "status":"PASS_MASK_METRICS_STABILITY_MICROBENCH_PARITY",
      "dataset":DATASET,"private_core_sha":CORE_SHA,"source_sha256":SOURCE_SHA,
      "source_rows":len(frame),"original_candidate_cases":len(cases),
      "original_mask_categories":len(masks),
      "original_mask_setup_seconds":round(create_seconds["median_seconds"],6),
      "input_preparation_seconds":inputs_sec,
      "scopes":{
        "canonical_condition_intersection":{"pair":PAIR_N,"triple":TRIPLE_N,
            "parity":"PASS_ALL_BOOLEAN_ROWS","timings":{
                "original":t_orig_mask,"numpy":t_num_mask,"polars":t_pol_mask}},
        "canonical_metrics":{"conditions":len(cases),"metrics_per_condition":len(oldm[0]),
            "parity":"PASS_ALL_NUMERIC_AND_NULL_FIELDS","timings":{
                "original":t_orig_metrics,"numpy_cached":t_num_metrics,"polars":t_pol_metrics}},
        "canonical_stability_summary":{"candidate_pair":STAB_PAIR_N,
            "candidate_triple":STAB_TRIPLE_N,"rows":len(old_stab),
            "parity":"PASS_ALL_COLUMNS_VALUES_AND_LABELS",
            "comparison_scope":"original identical function with only _uplift float-array caching",
            "timings":{"original":t_orig_stab,"numpy_cached_uplift":t_cached_stab}}
      },
      "rss_mib_max_process":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
      "limitations":[
       "Single runner and one original dataset; cache warm; small candidate sample.",
       "Polars compared for condition intersections and canonical _metrics, not complete stability producer.",
       "Does not quantify entire Semantic/OR/29CSV regeneration speed or deployment quality.",
       "Process RSS is total for three methods, not isolated per-method memory."
      ],
      "canonical_functions_or_private_artifacts_modified":False,
      "full_semantic_or_29csv_producers_executed":False,
      "previous_success_artifacts_recomputed":False,"phase42_change_authorized":False,
      "release_or_deploy":False
    }
    if sha(source)!=SOURCE_SHA or any(sha(ref/f)!=p["files"][f]["sha256"] for f in FILES):
        raise ValueError("Original immutable reference changed during measurement")
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return 0

if __name__=="__main__":raise SystemExit(main())
