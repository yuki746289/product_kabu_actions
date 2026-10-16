# Created 2026-10-16 JST
"""READ-ONLY microbenchmark for P2 research: Pandas vs Polars vs cached NumPy.

Only original source CSV of ONE representative technology dataset is read, with
SHA256 matching the immutable Phase38 proof. No canonical P2/semantic/OR
producer is run. Never write private source rows or sensitive benchmark groups
to public artifacts; only numeric timings, memory, counts, pass/fail metadata.
Three subprocess modes, repetitions of exactly the same real population,
isolated RSS; benchmark is evidence for choosing an approach, NOT certification
of the entire Phase42 pipeline.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time
import tracemalloc

SOURCE_SHA="ca81bb74c6936be6ee77182396b6549bdfaed0526ac6fd564210f0b4ed92bfb3"
PRIVATE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
RUN38="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"
FEATURE="daily_rci9_position"
TARGETS=("moved_predicted_5d","moved_predicted_10d","moved_predicted_20d")
COLS=("as_of",FEATURE)+TARGETS
REPEATS=12
EXPECTED_DATASET="technology"

def digest(p:Path)->str:
    v=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):v.update(chunk)
    return v.hexdigest()

def verify(source:Path,proof:Path,core:Path)->dict:
    p=json.loads(proof.read_text(encoding="utf-8"))
    if p.get("status")!=RUN38 or p.get("dataset")!=EXPECTED_DATASET or p.get("private_core_sha")!=PRIVATE_SHA:
        raise ValueError("Not immutable Phase38 technology source proof")
    if p.get("source_sha256")!=SOURCE_SHA:
        raise ValueError("Phase38 source identity mismatch")
    if p.get("source_rows")!=48782:raise ValueError("Unexpected full population size")
    if p.get("source_tickers")!=61:raise ValueError("Unexpected original technology ticker count")
    if digest(source)!=SOURCE_SHA:raise ValueError("Original saved source bytes changed")
    actual=subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()
    if actual!=PRIVATE_SHA:raise ValueError("Pinned Private original SHA differs")
    return p

def normalize_number(s):
    import pandas as pd
    if pd.api.types.is_bool_dtype(s):return s.astype(float)
    if pd.api.types.is_numeric_dtype(s):return pd.to_numeric(s,errors="coerce").astype(float)
    text=s.astype("string").str.strip().str.lower()
    return pd.to_numeric(text.replace({"true":"1","false":"0"}),errors="coerce").astype(float)

def create_result(records):
    return {"::".join(k):{"rows":int(d[0]),"totals":[(int(x),round(float(s),8)) for x,s in d[1]]}
            for k,d in sorted(records.items())}

def pandas_groups(frame):
    import pandas as pd
    f=frame.copy()
    f["year"]=f["as_of"].astype(str).str.slice(0,4)
    f["category"]=f[FEATURE].fillna("UNKNOWN").astype(str)
    for name in TARGETS:f[name]=normalize_number(f[name])
    return f

def from_pandas(frame):
    g=frame.groupby(["year","category"],dropna=False,sort=True)
    out={}
    for key,v in g:
        total=len(v)
        sums=[(int(v[t].count()),float(v[t].sum())) for t in TARGETS]
        out[tuple(str(x) for x in key)]=(total,sums)
    return create_result(out)

def from_numpy(frame):
    import numpy as np
    years=frame["year"].to_numpy(dtype=str)
    categories=frame["category"].to_numpy(dtype=str)
    key=np.char.add(np.char.add(years,"|"),categories)
    codes,inv=np.unique(key,return_inverse=True)
    n_groups=len(codes)
    rows=np.bincount(inv,minlength=n_groups)
    ys=[frame[t].to_numpy(float) for t in TARGETS]
    totals=[np.bincount(inv,weights=np.where(np.isfinite(y),y,0),minlength=n_groups)
            for y in ys]
    counts=[np.bincount(inv,weights=np.isfinite(y).astype(int),minlength=n_groups)
            for y in ys]
    out={}
    for i,k in enumerate(codes):
        a,b=k.split("|",1)
        out[(a,b)]=(int(rows[i]),[(int(counts[j][i]),float(totals[j][i]))
                                     for j in range(len(TARGETS))])
    return create_result(out)

def polars_group(source):
    import polars as pl
    f=pl.read_csv(source,columns=list(COLS),infer_schema_length=2000)
    return f

def transform_polars(df):
    import polars as pl
    exprs=[pl.col("as_of").cast(pl.String).str.slice(0,4).alias("year"),
           pl.col(FEATURE).cast(pl.String).fill_null("UNKNOWN").alias("category")]
    for t in TARGETS:
        raw=pl.col(t).cast(pl.String).str.strip_chars().str.to_lowercase()
        y=pl.when(raw=="true").then(pl.lit(1.0)).when(raw=="false").then(pl.lit(0.0)).otherwise(raw.cast(pl.Float64,strict=False))
        exprs.append(y.alias(t))
    return df.with_columns(exprs)

def from_polars(df):
    import polars as pl
    aggs=[pl.len().alias("rows")]
    for t in TARGETS:
        aggs.extend((pl.col(t).count().alias(t+"_count"),
                     pl.col(t).sum().alias(t+"_sum")))
    group=df.group_by(["year","category"]).agg(aggs)
    out={}
    for row in group.iter_rows(named=True):
        key=(str(row["year"]),str(row["category"]))
        out[key]=(int(row["rows"]),[(int(row[t+"_count"]),float(row[t+"_sum"] or 0.0)) for t in TARGETS])
    return create_result(out)

def run_worker(mode:str,source:Path)->dict:
    t0=time.perf_counter()
    if mode=="polars":
        source_frame=polars_group(source)
        t1=time.perf_counter()
        frame=transform_polars(source_frame)
        t2=time.perf_counter()
        calc=from_polars
        nrows=frame.height
    else:
        import pandas as pd
        source_frame=pd.read_csv(source,usecols=list(COLS),low_memory=False)
        t1=time.perf_counter()
        frame=pandas_groups(source_frame)
        t2=time.perf_counter()
        calc=from_numpy if mode=="numpy" else from_pandas
        nrows=len(frame)
    all_times=[];result=None
    for i in range(REPEATS):
        before=time.perf_counter()
        current=calc(frame)
        all_times.append(time.perf_counter()-before)
        if result is None:result=current
        elif current!=result:raise AssertionError("Repeated numeric aggregation changed")
    t3=time.perf_counter()
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
    return {"mode":mode,"population_rows":nrows,
            "group_count":len(result),
            "csv_read_seconds":round(t1-t0,6),
            "prepare_seconds":round(t2-t1,6),
            "aggregation_median_seconds":round(statistics.median(all_times),6),
            "aggregation_p90_seconds":round(sorted(all_times)[int(REPEATS*.9)],6),
            "total_seconds":round(t3-t0,6),
            "peak_rss_mib":round(rss,2),
            "results":result}

def selftest():
    import pandas as pd
    toy=pd.DataFrame({"as_of":["2024-01-05","2024-02-02","2025-03-07","2025-04-08"],
                     FEATURE:["HIGH","HIGH","LOW","LOW"],
                     TARGETS[0]:[True,False,True,False],
                     TARGETS[1]:[1.,0.,1.,float("nan")],
                     TARGETS[2]:[1.,1.,0.,0.]})
    x=pandas_groups(toy)
    a=from_pandas(x);b=from_numpy(x)
    if a!=b:raise AssertionError("numpy grouped exact counts/totals differ from pandas")
    import polars as pl
    c=from_polars(transform_polars(pl.from_pandas(toy)))
    if a!=c:raise AssertionError("polars grouped exact counts/totals differ from pandas")
    print("PASS_REAL_GROUPED_PANDAS_NUMPY_POLARS_SYNTHETIC_PARITY")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--mode",choices=("pandas","numpy","polars"))
    ap.add_argument("--source",type=Path)
    ap.add_argument("--proof",type=Path)
    ap.add_argument("--core",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--worker",action="store_true")
    args=ap.parse_args()
    if args.selftest:selftest();return 0
    if not args.source or not args.mode:ap.error("mode and source required")
    if args.worker:
        result=run_worker(args.mode,args.source)
        print(json.dumps(result,allow_nan=False,ensure_ascii=False,separators=(",",":")))
        return 0
    if not args.proof or not args.core or not args.output:
        ap.error("Pinned core, proof and report required")
    if args.output.exists():raise FileExistsError("Fresh isolated benchmark output required")
    p=verify(args.source,args.proof,args.core)
    timings={};expected=None;issues=[]
    for mode in ("pandas","numpy","polars"):
        proc=subprocess.run([sys.executable,__file__,"--worker","--mode",mode,
                             "--source",str(args.source)],capture_output=True,text=True,check=True)
        data=json.loads(proc.stdout.strip().splitlines()[-1])
        result=data.pop("results")
        if expected is None:expected=result
        elif result!=expected:
            issues.append({"mode":mode,"reason":"group_aggregation_data_or_null_parity"})
        timings[mode]=data
    if digest(args.source)!=SOURCE_SHA:
        issues.append({"reason":"source_hash_changed_during_benchmark"})
    assert all(t["population_rows"]==p["source_rows"] for t in timings.values())
    result={"schema":1,"status":"PASS_BENCHMARK_PARITY" if not issues else "FAIL_BENCHMARK_PARITY",
            "private_core_sha":PRIVATE_SHA,
            "dataset":EXPECTED_DATASET,"input_sha256":SOURCE_SHA,
            "source_rows":int(p["source_rows"]),
            "source_tickers":int(p["source_tickers"]),
            "columns_measured":list(COLS),
            "workload":"CSV selected-column read + per-year per-categorical-label 3 horizon counts/sums",
            "repetitions_per_mode":REPEATS,
            "benchmark_is_full_p2_semantic_producer":False,
            "benchmark_is_old_29csv_recomputation":False,
            "canonical_p2_logic_modified":False,
            "prior_success_artifacts_recomputed":False,
            "benchmark_results_equal":len(issues)==0,
            "issues":issues,"measurements":timings,
            "phase42_optimization_authorized":False,
            "production_or_release_performed":False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if not issues else 2

if __name__=="__main__":raise SystemExit(main())
