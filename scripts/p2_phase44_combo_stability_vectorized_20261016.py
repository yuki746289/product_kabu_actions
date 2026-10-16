"""Fast source-bound P2 combo stability, with strict original numeric parity.

Reduces repeated dataframe-to-numpy conversions and year/month/regime filter
scans by grouped NumPy bincount. Reuses prior saved canonical candidate source
as immutable INPUT, never an output. Verification compares the full computed
row/column set to the independent old complete canonical CSV by unique
combination identity. Only scalar numeric receipts are saved.
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

TOTAL=9812
INPUTS=(("pair","advantage_pairwise_candidates.csv",3025),
        ("triple","advantage_triple_candidates.csv",6787))
TARGET="combination_stability_summary.csv"
IDENTITY=["condition_type","feature1","category1",
          "feature2","category2","feature3","category3"]

def identity_keys(table):
    return list(map(tuple,table.reindex(columns=IDENTITY).astype("string")
                    .fillna("<MISSING>").to_numpy()))

def selftest():
    assert sum(n for _,_,n in INPUTS)==TOTAL
    assert len(set(IDENTITY))==len(IDENTITY)
    print("PASS_P2_COMBO_STABILITY_NUMPY_GROUPED_IDENTITY_PLAN")

def run(core:Path,source:Path,ref:Path,start:int,end:int,compare_canonical:int):
    import pandas as pd
    import numpy as np
    if not 0<=start<end<=TOTAL:raise ValueError("Slice outside canonical 9812 row population")
    if not 0<=compare_canonical<=end-start:
        raise ValueError("Canonical direct-function cross-check scope invalid")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=contract.CORE_SHA:
        raise ValueError("Pinned original core SHA differs")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Private Actions policy missing")
    if subprocess.check_output(["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],text=True).strip():
        raise ValueError("Private workflow found")
    contract.inspect_source(source)
    contract.validate_old_reference(ref)
    sha_before={f:contract.sha256(ref/f) for _,f,_ in INPUTS}
    sha_before[TARGET]=contract.sha256(ref/TARGET)
    sys.path.insert(0,str(core/"scripts"))
    import build_p2_225_semantic_bundle as sem
    import finalize_p2_nikkei_complete_baseline as fin
    t=time.perf_counter()
    f=sem.prepare_frame(source)
    dates=f["as_of"]
    years=dates.dt.year.to_numpy(int)
    months=dates.dt.to_period("M").astype(str).to_numpy()
    regime=f["causal_regime"].astype(str).to_numpy()
    uniques={}
    indices={}
    for key,values in (("year",years),("month",months),("regime",regime)):
        v,i=np.unique(values,return_inverse=True)
        uniques[key]=v
        indices[key]=i
    ys=np.asarray(uniques["year"],dtype=int)
    if len(ys)<5:
        raise ValueError("Insufficient canonical year windows")
    rolling={
        "rolling3":[np.flatnonzero((ys>=y-2)&(ys<=y))
                    for y in ys if y>=int(ys[0])+2],
        "rolling5":[np.flatnonzero((ys>=y-4)&(ys<=y))
                    for y in ys if y>=int(ys[0])+4],
    }
    mid=dates.sort_values().iloc[len(f)//2]
    half=[dates.le(mid).to_numpy(),dates.gt(mid).to_numpy()]
    target_arrays={}
    target_valid={}
    total_sums={}
    total_counts={}
    for horizon in (5,10,20):
        arr=pd.to_numeric(f[f"moved_predicted_{horizon}d"],errors="coerce").to_numpy(float)
        target_arrays[horizon]=arr
        valid=np.isfinite(arr)
        target_valid[horizon]=valid
        total_sums[horizon]={}
        total_counts[horizon]={}
        for key,codes in indices.items():
            groups=len(uniques[key])
            total_sums[horizon][key]=np.bincount(
                codes,weights=np.where(valid,arr,0.0),minlength=groups)
            total_counts[horizon][key]=np.bincount(
                codes,weights=valid.astype(float),minlength=groups)
    masks=fin._feature_masks(f)
    sources={name:pd.read_csv(ref/name,low_memory=False)
             for _,name,_ in INPUTS}
    ranges=[]
    offset=0
    for kind,name,expected_count in INPUTS:
        df=sources[name]
        if len(df)!=expected_count or not fin._truthy(df["candidate"]).all():
            raise ValueError("Canonical complete candidate count/flags differ")
        lo=max(start,offset)-offset
        hi=min(end,offset+len(df))-offset
        if lo<hi:ranges.append((kind,df.iloc[lo:hi]))
        offset+=len(df)
    if sum(len(df) for _,df in ranges)!=end-start:
        raise ValueError("Partial canonical candidate slicing")
    old_all=pd.read_csv(ref/TARGET,low_memory=False)
    if len(old_all)!=TOTAL:raise ValueError("Canonical reference cardinality changed")
    original_keys=identity_keys(old_all)
    if len(set(original_keys))!=TOTAL:
        raise ValueError("Duplicate full canonical combo stability identity")
    locator={k:i for i,k in enumerate(original_keys)}
    def uplift(all_sum,all_count,sums,counts):
        n=np.asarray(counts,float)
        b=np.asarray(all_count,float)
        out=np.full(n.shape,np.nan,dtype=float)
        valid=(n>=2)&(b>0)
        out[valid]=sums[valid]/n[valid]*100.0-all_sum[valid]/b[valid]*100.0
        return out
    def group_values(mask,h,key):
        arr=target_arrays[h]
        good=mask & target_valid[h]
        codes=indices[key]
        n=len(uniques[key])
        sums=np.bincount(codes,weights=np.where(good,arr,0.0),minlength=n)
        counts=np.bincount(codes,weights=good.astype(float),minlength=n)
        return sums,counts
    def period_halves(mask,h):
        arr=target_arrays[h]
        valid=target_valid[h]
        values=[]
        for half_mask in half:
            bv=half_mask&valid
            kv=bv&mask
            if not bv.any() or kv.sum()<2:values.append(float("nan"))
            else:values.append(float(arr[kv].mean()*100.0-arr[bv].mean()*100.0))
        return values
    def mk_row(kind,row):
        mask=fin._condition_mask(row,kind,masks)
        count=int(mask.sum())
        q={"condition_type":kind,"count":count,"small_sample":count<30}
        for i in range(1,4 if kind=="triple" else 3):
            q[f"feature{i}"]=row[f"feature{i}"]
            q[f"category{i}"]=row[f"category{i}"]
        for horizon in (5,10,20):
            candidate={}
            for key in ("year","month","regime"):
                sums,counts=group_values(mask,horizon,key)
                candidate[key]=uplift(
                    total_sums[horizon][key],total_counts[horizon][key],
                    sums,counts)
                if key=="year":
                    candidate["_annual_sums"]=sums
                    candidate["_annual_counts"]=counts
            annual_sums=candidate["_annual_sums"]
            annual_counts=candidate["_annual_counts"]
            base_year_sums=total_sums[horizon]["year"]
            base_year_counts=total_counts[horizon]["year"]
            for rtype,bounds in rolling.items():
                cs=np.array([annual_sums[ix].sum() for ix in bounds],dtype=float)
                cn=np.array([annual_counts[ix].sum() for ix in bounds],dtype=float)
                bs=np.array([base_year_sums[ix].sum() for ix in bounds],dtype=float)
                bn=np.array([base_year_counts[ix].sum() for ix in bounds],dtype=float)
                candidate[rtype]=uplift(bs,bn,cs,cn)
            yr=fin._shares(candidate["year"].tolist())
            mo=fin._shares(candidate["month"].tolist())
            roll3=fin._shares(candidate["rolling3"].tolist())
            roll5=fin._shares(candidate["rolling5"].tolist())
            rg=fin._shares(candidate["regime"].tolist())
            q[f"positive_year_share_{horizon}d_pct"]=yr[0]
            q[f"median_year_uplift_{horizon}d_pp"]=yr[1]
            q[f"worst_year_uplift_{horizon}d_pp"]=yr[2]
            q[f"positive_month_share_{horizon}d_pct"]=mo[0]
            q[f"median_month_uplift_{horizon}d_pp"]=mo[1]
            q[f"worst_month_uplift_{horizon}d_pp"]=mo[2]
            q[f"positive_rolling3y_share_{horizon}d_pct"]=roll3[0]
            q[f"median_rolling3y_uplift_{horizon}d_pp"]=roll3[1]
            q[f"positive_rolling5y_share_{horizon}d_pct"]=roll5[0]
            q[f"median_rolling5y_uplift_{horizon}d_pp"]=roll5[1]
            q[f"positive_regime_share_{horizon}d_pct"]=rg[0]
            q[f"median_regime_uplift_{horizon}d_pp"]=rg[1]
            first_half,second_half=period_halves(mask,horizon)
            q[f"first_half_uplift_{horizon}d_pp"]=first_half
            q[f"second_half_uplift_{horizon}d_pp"]=second_half
        for horizon in (5,10,20):
            for suffix in ("win","win_uplift","return"):
                label=(f"win_{horizon}d_pct" if suffix=="win" else
                       f"win_uplift_{horizon}d_pp" if suffix=="win_uplift" else
                       f"return_{horizon}d_pct")
                q[label]=row.get(label,np.nan)
        if kind=="pair":
            for horizon in (5,10,20):
                q[f"incremental_{horizon}d_pp"]=row.get(
                    f"incremental_vs_best_single_{horizon}d_pp",np.nan)
        stable10=(q["positive_rolling5y_share_10d_pct"]>=60
                  and q["second_half_uplift_10d_pp"]>0
                  and q["positive_year_share_10d_pct"]>=60
                  ) if np.isfinite(q["positive_rolling5y_share_10d_pct"]) else False
        stable20=(q["positive_rolling5y_share_20d_pct"]>=60
                  and q["second_half_uplift_20d_pp"]>0
                  and q["positive_year_share_20d_pct"]>=60
                  ) if np.isfinite(q["positive_rolling5y_share_20d_pct"]) else False
        increment=True
        if kind=="pair":
            increment=bool(
                pd.notna(q["incremental_10d_pp"]) and q["incremental_10d_pp"]>0
                or pd.notna(q["incremental_20d_pp"]) and q["incremental_20d_pp"]>0)
        if count<20:label="SMALL_SAMPLE"
        elif count>=30 and increment and stable10 and stable20:
            label="ROBUST_EDGE_CANDIDATE"
        elif count>=30 and increment and (stable10 or stable20):
            label="PROVISIONAL_EDGE"
        else:label="CANDIDATE_UNSTABLE_OR_LIMITED"
        q["stability_label"]=label
        return q

    # Benchmark and numeric cross-check against untouched Private canonical
    # functions for up to 3 rows BEFORE trusting vectorized outputs.
    checks=[]
    done=[]
    for kind,table in ranges:
        for _,row in table.iterrows():
            result=mk_row(kind,row)
            done.append(result)
            if len(checks)<compare_canonical:
                canon=fin._stability_summary(f,pd.DataFrame([row]),kind,masks)
                computed=pd.DataFrame([result])
                checked=canon.reindex(columns=computed.columns)
                if set(computed.columns)!=set(canon.columns):
                    raise ValueError("Optimized canonical schema differs on direct comparator")
                pd.testing.assert_frame_equal(
                    checked,computed,check_exact=False,check_dtype=False,
                    rtol=contract.REL_TOL,atol=contract.ABS_TOL,
                    check_index_type=False)
                checks.append({"kind":kind,"pass":True})
    actual=pd.DataFrame(done)
    keys=identity_keys(actual)
    if len(set(keys))!=len(keys) or any(k not in locator for k in keys):
        raise ValueError("New stability identity mismatch")
    old=old_all.iloc[[locator[k] for k in keys]].reset_index(drop=True)
    if set(actual.columns)-set(old.columns):
        raise ValueError("New canonical output has extra columns")
    missing=set(old.columns)-set(actual.columns)
    permitted={"feature3","category3","incremental_5d_pp",
               "incremental_10d_pp","incremental_20d_pp"}
    if not missing.issubset(permitted):
        raise ValueError("Optimized canonical output missing required columns")
    for col in missing:
        if not old[col].isna().all():
            raise ValueError("Missing canonical union column has non-NA values")
    actual=actual.reindex(columns=old.columns)
    pd.testing.assert_frame_equal(
        old,actual,check_dtype=False,check_exact=False,
        rtol=contract.REL_TOL,atol=contract.ABS_TOL,
        check_index_type=False)
    for name,sha in sha_before.items():
        if contract.sha256(ref/name)!=sha:raise ValueError("Original old data SHA changed")
    if contract.sha256(source)!=contract.SOURCE_SHA:
        raise ValueError("Original source features SHA changed")
    if subprocess.check_output(["git","-C",str(core),"diff","--name-only"],text=True).strip():
        raise ValueError("Private tracked original source altered")
    return {
        "phase":44,"status":"PASS_PHASE44_ALL225_VECTORIZED_COMBO_STABILITY_SHARD",
        "source_sha256":contract.SOURCE_SHA,"private_core_sha":contract.CORE_SHA,
        "canonical_old_csv_sha256":sha_before[TARGET],
        "start":start,"end":end,"rows_computed":len(actual),
        "numeric_parity_all_rows_columns_and_ids":True,
        "original_function_cross_checks":len(checks),
        "runtime_seconds":round(time.perf_counter()-t,3),
        "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
        "previous_success_artifacts_recomputed":False,
        "full_new_29_e2e_certified":False,"phase44_complete":False,
        "release_ready":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--start",type=int)
    p.add_argument("--end",type=int)
    p.add_argument("--compare-canonical",type=int,default=0)
    for name in ("core","source","reference","report"):
        p.add_argument("--"+name,type=Path)
    a=p.parse_args()
    if a.selftest:selftest();return
    if any(getattr(a,k) is None for k in ("start","end","core","source","reference","report")):
        p.error("Complete pinned source/core/range/report required")
    if a.report.exists():raise FileExistsError("Existing audit cannot be overwritten")
    result=run(a.core.resolve(),a.source.resolve(),a.reference.resolve(),
               a.start,a.end,a.compare_canonical)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS_ALL225_VECTORIZED_STABILITY_SHARD",a.start,a.end,
          result["runtime_seconds"],flush=True)

if __name__=="__main__":main()
