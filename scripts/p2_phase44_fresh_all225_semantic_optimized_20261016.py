"""Phase44 all225: newly compute all canonical Semantic 23 CSV into isolated stage.

Actual immutable Private canonical build() is called, with independently
verified NumPy metrics + grouped stability and memory-bounded pair/triple mask
storage. The saved 29 old CSVs are READ-ONLY comparison inputs only.
Never touches Production P2 v12, old outputs or previously successful artifacts.
"""
from __future__ import annotations
import argparse
import gc
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import p2_phase44_all225_fresh_newproducer_29csv_20261016 as ct
from p2_phase44_optimized_family_20261016 import check_dataframe, FAMILY_KEYS

def source_guard(core,source,reference):
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=ct.CORE_SHA:
        raise ValueError("Original pinned Private code SHA drift")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Original execution rule not found")
    if subprocess.check_output(["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],
                               text=True).strip():
        raise ValueError("Private workflows prohibited")
    src=ct.inspect_source(source)
    old=ct.validate_old_reference(reference)
    return src,old

def optimized_combo_factory(f,fin):
    import numpy as np
    import pandas as pd
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


    def calculate(source,kind):
        # Original canonical function filters candidate=True, retaining
        # original pair/triple source order.
        selected=source.loc[fin._truthy(source["candidate"])]
        output=[]
        for row in selected.itertuples(index=False):
            output.append(mk_row(kind,row._asdict()))
        return pd.DataFrame(output)
    return calculate

def identity_key(df):
    columns=("condition_type","feature1","category1",
             "feature2","category2","feature3","category3")
    return list(map(tuple,df.reindex(columns=columns).astype("string")
                    .fillna("<MISSING>").to_numpy()))

def align(old,fresh,name):
    import pandas as pd
    if name=="combination_stability_summary.csv":
        previous=identity_key(old)
        now=identity_key(fresh)
        if (len(set(previous))!=len(previous) or
            len(set(now))!=len(now) or set(previous)!=set(now)):
            raise ValueError("Original and new complete combo identity mismatches")
        mapping={k:i for i,k in enumerate(now)}
        fresh=fresh.iloc[[mapping[k] for k in previous]].reset_index(drop=True)
        # Pair and triple source calculations contain mutually exclusive fields.
        missing=set(old.columns)-set(fresh.columns)
        if missing:
            if not all(old[x].isna().all() for x in missing):
                raise ValueError("Non-null union fields missing in new combo output")
            fresh=fresh.reindex(columns=old.columns)
    elif name in FAMILY_KEYS:
        keys=FAMILY_KEYS[name]
        if name=="yearly_stability.csv": keys=("condition_id","year")
        def key_series(df):
            return df[list(keys)].astype(str).agg("\x1f".join,axis=1)
        a=key_series(old);b=key_series(fresh)
        if (a.duplicated().any() or b.duplicated().any()
            or set(a)!=set(b)):
            raise ValueError("Canonical stable condition/period identity missing")
        fresh=fresh.set_index(b.to_numpy(),drop=False).loc[a.tolist()]
        fresh=fresh.reset_index(drop=True)[old.columns]
        for col in ("year","window_start","window_end"):
            if col in old:
                fresh[col]=pd.to_numeric(fresh[col],errors="raise")
    elif name in ("monthly_candidate_stability_summary.csv","parameter_plateau.csv"):
        # Saved end-report files use a different stable presentation order
        # from the underlying canonical function. Align by unique condition
        # identity, never by numeric values or by sorted row positions.
        keys=(["condition_id"] if name.startswith("monthly_candidate")
              else ["feature_family","feature","category"])
        def ids(df):
            if not set(keys).issubset(df.columns):
                raise ValueError("Canonical result identity columns missing")
            return df[keys].astype("string").fillna("<MISSING>").agg(
                "\x1f".join,axis=1)
        left=ids(old)
        right=ids(fresh)
        if (left.duplicated().any() or right.duplicated().any()
            or set(left)!=set(right)):
            raise ValueError("Canonical candidate or plateau identities differ")
        fresh=fresh.set_index(right.to_numpy(),drop=False).loc[left.tolist()]
        fresh=fresh.reset_index(drop=True)[old.columns]
    elif name=="signal_level_features.csv":
        # Original saved CSV serializes dates to ISO. The new in-memory
        # producer still has datetime dtype; this is formatting, not a
        # change to source date/data or a numerical tolerance exception.
        if list(old.columns)!=list(fresh.columns):
            raise ValueError("Pinned 112-column feature schema changed")
        if "as_of" not in fresh.columns:
            raise ValueError("Immutable source date field is missing")
        fresh=fresh.copy()
        fresh["as_of"]=pd.to_datetime(fresh["as_of"],errors="raise").dt.strftime("%Y-%m-%d")
    elif name=="combination_walkforward_results.csv":
        keys=["test_year","condition_type","horizon"]
        def tuples(df):return list(map(tuple,df[keys].to_numpy()))
        old_keys=tuples(old);new_keys=tuples(fresh)
        if len(set(old_keys))!=len(old_keys) or set(new_keys)!=set(old_keys):
            raise ValueError("Canonical complete combo walkforward key drift")
        lookup={k:i for i,k in enumerate(new_keys)}
        fresh=fresh.iloc[[lookup[k] for k in old_keys]].reset_index(drop=True)
    return fresh

def run(core,source,reference,output):
    import numpy as np
    import pandas as pd
    import build_p2_225_semantic_bundle as prepare
    import build_p2_225_canonical_semantic_data as canonical
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import analyze_p2_nikkei_complete_baseline as cb
    import finalize_p2_nikkei_complete_baseline as fin
    import p2_phase43_new_8_semantic_cached_20261016 as fast
    from p2_html_core.p03_common_analysis_plan import SEMANTIC_CSVS
    if output.exists():
        raise FileExistsError("Fresh semantic stage must not preexist")
    source_meta,old_meta=source_guard(core,source,reference)
    start=time.perf_counter()
    frame=prepare.prepare_frame(source)
    previous_metrics=cb._metrics
    pair=aug._pairwise
    triple=aug._triples
    cond=aug._condition_sets
    stability=fin._stability_summary
    metrics_cache={}
    counts={"slow_metric_crosschecks":0,"discarded_pair_mask_vectors":0,
            "discarded_triple_mask_vectors":0,"new_combo_stability_rows":0}
    def faster_metrics(f,mask,base):
        identity=id(f)
        if identity not in metrics_cache:
            metrics_cache.clear()
            metrics_cache[identity]=fast.MetricCache(f)
        quick=metrics_cache[identity].metrics(f,mask,base)
        if counts["slow_metric_crosschecks"]<12:
            original=previous_metrics(f,mask,base)
            if set(original)!=set(quick):
                raise ValueError("Cached metrics field names changed")
            for key,val in original.items():
                if not np.isclose(val,quick[key],rtol=1e-10,atol=1e-7,equal_nan=True):
                    raise ValueError("Cached metrics do not match canonical")
            counts["slow_metric_crosschecks"]+=1
        return quick
    def minimal_pair(*args):
        df,buffers=pair(*args)
        counts["discarded_pair_mask_vectors"]=len(buffers)
        buffers.clear()
        gc.collect()
        return df,{}
    def minimal_triple(*args):
        df,buffers=triple(*args)
        counts["discarded_triple_mask_vectors"]=len(buffers)
        buffers.clear()
        gc.collect()
        return df,{}
    def generated_condition_sets(single,masks,pairs,pair_masks,triples,triple_masks):
        if pair_masks or triple_masks:
            raise ValueError("Expected bounded temporary pair/triple masks")
        choices={}
        ss=single.loc[fin._truthy(single["candidate"])]
        for row in ss.itertuples(index=False):
            choices[f"S:{row.feature}={row.category}"]=masks[(row.feature,row.category)]
        for table,kind,prefix,limit in ((pairs,"pair","P",50),(triples,"triple","T",25)):
            selected=table.loc[
                fin._truthy(table["candidate"]) &
                pd.to_numeric(table["count"],errors="coerce").ge(10)
            ].copy()
            selected["score"]=selected[[f"win_uplift_{h}d_pp" for h in (5,10,20)]].mean(axis=1)
            selected=selected.sort_values(["score","count"],ascending=[False,False]).head(limit)
            for _,row in selected.iterrows():
                items=[(str(row[f"feature{i}"]),str(row[f"category{i}"]))
                       for i in range(1,4 if kind=="triple" else 3)]
                key=prefix+":"+"&".join(f"{name}={category}" for name,category in items)
                choices[key]=fin._condition_mask(row,kind,masks)
        return choices
    vector=optimized_combo_factory(frame,fin)
    def fast_stability(f,table,kind,masks):
        if f is not frame:
            # canonical.build uses a copy: prepare selected optimizer
            # lazily for the actual Private in-process canonical input.
            raise ValueError("Canonical copy/frame binding not established")
        out=vector(table,kind)
        counts["new_combo_stability_rows"]+=len(out)
        return out
    output.mkdir(parents=True,exist_ok=False)
    old_hashes={name:ct.sha256(reference/name) for name in SEMANTIC_CSVS}
    try:
        # canonical.build copies the supplied frame. Bind combo optimizer to
        # the actual canonical frame lazily using the first invocation.
        combo_frames={}
        def bound_stability(f,table,kind,masks):
            identity=id(f)
            if identity not in combo_frames:
                combo_frames.clear()
                combo_frames[identity]=optimized_combo_factory(f,fin)
            result=combo_frames[identity](table,kind)
            counts["new_combo_stability_rows"]+=len(result)
            return result
        cb._metrics=faster_metrics
        aug._pairwise=minimal_pair
        aug._triples=minimal_triple
        aug._condition_sets=generated_condition_sets
        fin._stability_summary=bound_stability
        print("BEGIN_FRESH_CANONICAL_SEMANTIC_POSTEXTRACT",flush=True)
        data=canonical.build(frame)
        print("PASS_FRESH_CANONICAL_SEMANTIC_CORE_BUILD",flush=True)
    finally:
        cb._metrics=previous_metrics
        aug._pairwise=pair
        aug._triples=triple
        aug._condition_sets=cond
        fin._stability_summary=stability
    expected=set(SEMANTIC_CSVS)
    new_data={k+".csv":v for k,v in data.items() if isinstance(v,pd.DataFrame)
              and not k.startswith("_")}
    if set(new_data)!=expected:
        raise ValueError("New semantic computed name set differs expected 23 files")
    ledger={}
    for name in SEMANTIC_CSVS:
        original=pd.read_csv(reference/name,low_memory=False)
        fresh=align(original,new_data[name],name)
        check_dataframe(original,fresh,name)
        path=output/name
        fresh.to_csv(path,index=False,encoding="utf-8")
        # The saved newly generated file, not merely the in-memory array, must
        # pass the exact same old reference column/row/numeric contract.
        readback=pd.read_csv(path,low_memory=False)
        check_dataframe(original,readback,name)
        ledger[name]=ct.sha256(path)
        print("PASS_FULL_NEW_SEMANTIC_OUTPUT_CSV",name,len(fresh),flush=True)
        del fresh,original,readback
    if ct.sha256(source)!=ct.SOURCE_SHA:
        raise ValueError("Original 181318 features mutated during fresh semantic")
    for name,sha in old_hashes.items():
        if ct.sha256(reference/name)!=sha:
            raise ValueError("Original saved semantic CSV changed")
    if subprocess.check_output(["git","-C",str(core),"diff","--name-only"],text=True).strip():
        raise ValueError("Private source tracked code changed")
    meta={
        "stage":"semantic","overall_pass":True,
        "dataset_id":"all_225","source_sha256":ct.SOURCE_SHA,
        "source_rows":source_meta["rows"],"source_tickers":source_meta["tickers"],
        "newly_computed_semantic_csv_count":len(ledger),
        "output_csv_sha256":ledger,
        "previous_success_artifacts_recomputed":False,
        "newly_computed_not_old_checkpoint_copy":True,
        "num_cached_crosschecks":counts["slow_metric_crosschecks"],
        "counts":counts,
        "elapsed_seconds":round(time.perf_counter()-start,3),
        "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
    }
    (output/"semantic_status.json").write_text(
        json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return meta

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("core","source","reference","output"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    sys.path.insert(0,str(a.core.resolve()/"scripts"))
    result=run(a.core.resolve(),a.source.resolve(),a.reference.resolve(),a.output.resolve())
    print("PASS_PHASE44_FRESH_ALL23_SEMANTIC_SOURCE_BOUND",result["elapsed_seconds"],
          result["peak_rss_mib"],flush=True)

if __name__=="__main__":
    main()
