# Created 2026-10-16 JST
"""Phase42 optimized independent semantic stability parity (saved original source).

Uses source-bound cached numpy arrays and np.bincount for calendar groups.
Reproduces and verifies FIVE unproven canonical semantic CSVs (year/month,
3-year/5-year rolling, regime), every condition and every row.
Inputs are original saved source/candidate CSVs; Phase40/41 expensive
producers and Production P2 v12 are NEVER rerun/modified. Upload audit JSON
only. This does NOT certify the full 29 CSV new-producer pipeline.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys, time
from pathlib import Path
CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials","capital_goods_others","transportation_utilities")
EXCLUDE={
 "exclude_capital_goods_transportation_utilities":"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
 "exclude_transportation_utilities":"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1",
}
DATASETS=GROUPS+tuple(EXCLUDE)
SOURCES=("representative_single_categories.csv","all_pairwise_combinations.csv","tested_triple_combinations.csv")
OUTPUTS=("yearly_stability.csv","monthly_stability.csv","rolling_3y_stability.csv","rolling_5y_stability.csv","regime_stability.csv")
HORIZONS=(5,10,20)

def digest(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as file:
        for data in iter(lambda:file.read(1<<20),b""):h.update(data)
    return h.hexdigest()

def inspect_proof(core,reference,source,proof,dataset):
    if dataset not in DATASETS:raise ValueError("Dataset outside approved 8")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=CORE_SHA:
        raise ValueError("Private fixed original core SHA differs")
    expected=(core/"preview/kabu/analysis"/
              ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
              dataset).resolve()
    if expected!=reference:raise ValueError("Reference directory drift")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Original read-only policy missing")
    p=json.loads(proof.read_text(encoding="utf-8"))
    ss=digest(source)
    if (p.get("status")!="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"
        or p.get("dataset")!=dataset or p.get("private_core_sha")!=CORE_SHA
        or p.get("source_sha256")!=ss or p.get("resolved_csv_files")!=29
        or p.get("mismatches")!=[]):
        raise ValueError("Prior exact-source 29CSV SHA proof mismatch")
    if dataset in EXCLUDE and ss!=EXCLUDE[dataset]:
        raise ValueError("Exclusion original source SHA mismatch")
    for fname in SOURCES+OUTPUTS:
        if digest(reference/fname)!=p["files"][fname]["sha256"]:
            raise ValueError("Saved original candidate or output sha mismatch: "+fname)
    return p

def build_selected_conditions(reference,fin,masks):
    import pandas as pd
    single=pd.read_csv(reference/SOURCES[0],low_memory=False)
    pair=pd.read_csv(reference/SOURCES[1],low_memory=False)
    triple=pd.read_csv(reference/SOURCES[2],low_memory=False)
    out={}
    for row in single.loc[fin._truthy(single["candidate"])].itertuples(index=False):
        key=(str(row.feature),str(row.category))
        out["S:"+key[0]+"="+key[1]]=masks[key]
    for table,kind,top in ((pair,"P",50),(triple,"T",25)):
        subset=table.loc[fin._truthy(table["candidate"]) &
                   pd.to_numeric(table["count"],errors="coerce").ge(10)].copy()
        subset["score"]=subset[[f"win_uplift_{h}d_pp" for h in HORIZONS]].mean(axis=1)
        subset=subset.sort_values(["score","count"],ascending=[False,False]).head(top)
        for _,row in subset.iterrows():
            fields=[(str(row[f"feature{i}"]),str(row[f"category{i}"]))
                       for i in range(1,3 if kind=="P" else 4)]
            key=kind+":"+"&".join(f+"="+cat for f,cat in fields)
            value=masks[fields[0]].copy()
            for field in fields[1:]:value &= masks[field]
            if key in out:raise ValueError("Duplicate canonical condition selection")
            out[key]=value
    return out

class Cache:
    """All numerical vectors and period aggregation masks loaded ONCE."""
    def __init__(self,frame):
        import numpy as np
        import pandas as pd
        self.frame=frame
        self.n=len(frame)
        self.yr=frame["as_of"].dt.year.to_numpy(int)
        self.month=frame["as_of"].dt.to_period("M").astype(str).to_numpy()
        self.regime=frame["causal_regime"].astype(str).to_numpy()
        self.y={h:pd.to_numeric(frame[f"moved_predicted_{h}d"],errors="coerce").to_numpy(float) for h in HORIZONS}
        self.r={h:pd.to_numeric(frame[f"directional_return_{h}d_pct"],errors="coerce").to_numpy(float) for h in HORIZONS}
        self.v={h:np.isfinite(self.y[h]) for h in HORIZONS}
        self.rv={h:np.isfinite(self.r[h]) for h in HORIZONS}
        self.baseline={h:(float(frame[f"moved_predicted_{h}d"].astype(float).mean()*100),
                           float(frame[f"directional_return_{h}d_pct"].astype(float).mean())) for h in HORIZONS}
        self.year_masks={int(k):self.yr==k for k in sorted(set(self.yr))}
        self.tables={}
        for name,series in (("year",self.yr.astype(str)),("month",self.month)):
            labels,inv=np.unique(series,return_inverse=True)
            self.tables[name]=(labels,inv)
        self.regimes=np.unique(self.regime)

    def stats(self,mask,part):
        """Fast independent period rows with precomputed baseline and bincount."""
        import numpy as np
        label,codes=self.tables[part]
        count=np.bincount(codes[mask],minlength=len(label)).astype(int)
        values={}
        for h in HORIZONS:
            iy=self.y[h];ir=self.r[h]
            good=mask & self.v[h];vgood=self.v[h]
            retgood=mask & self.rv[h]
            total_valid=np.bincount(codes[vgood],minlength=len(label))
            total_y=np.bincount(codes[vgood],weights=iy[vgood],minlength=len(label))
            cond_valid=np.bincount(codes[good],minlength=len(label))
            cond_y=np.bincount(codes[good],weights=iy[good],minlength=len(label))
            ret_valid=np.bincount(codes[retgood],minlength=len(label))
            ret_sums=np.bincount(codes[retgood],weights=ir[retgood],minlength=len(label))
            baseline=np.divide(total_y,total_valid,out=np.full(len(label),np.nan),where=total_valid>0)*100
            win=np.divide(cond_y,cond_valid,out=np.full(len(label),np.nan),where=cond_valid>0)*100
            retval=np.divide(ret_sums,ret_valid,out=np.full(len(label),np.nan),where=ret_valid>0)
            values[h]=(win,baseline,retval)
        return label,count,values

    def rolling(self,mask,length):
        import numpy as np
        lo=min(self.year_masks);hi=max(self.year_masks)
        records=[]
        for end in range(lo+length-1,hi+1):
            begin=end-length+1
            pm=(self.yr>=begin)&(self.yr<=end)
            cm=pm & mask
            if not cm.any():continue
            record={"window_start":begin,"window_end":end,"count":int(cm.sum())}
            for h in HORIZONS:
                b=pm & self.v[h];k=cm & self.v[h]
                base=float(self.y[h][b].mean()*100) if b.any() else float("nan")
                val=float(self.y[h][k].mean()*100) if k.any() else float("nan")
                record.update({f"win_{h}d_pct":val,
                    f"baseline_win_{h}d_pct":base,
                    f"uplift_{h}d_pp":val-base if k.any() and b.any() else float("nan")})
            records.append(record)
        return records

    def metrics(self,mask):
        import numpy as np
        count=int(mask.sum())
        rec={"count":count,"retention_pct":count/self.n*100}
        for h in HORIZONS:
            v=self.v[h]&mask;r=self.rv[h]&mask
            win=float(self.y[h][v].mean()*100) if v.any() else np.nan
            ret=float(self.r[h][r].mean()) if r.any() else np.nan
            rec[f"win_{h}d_pct"]=win;rec[f"return_{h}d_pct"]=ret
            rec[f"win_uplift_{h}d_pp"]=win-self.baseline[h][0] if np.isfinite(win) else np.nan
            rec[f"return_uplift_{h}d_pct"]=ret-self.baseline[h][1] if np.isfinite(ret) else np.nan
            ys=[]
            for _,pm in self.year_masks.items():
                bv=pm & self.v[h];cm=bv & mask
                if bv.sum()<3 or cm.sum()<2:continue
                ys.append(float(self.y[h][cm].mean()*100-self.y[h][bv].mean()*100))
            rec[f"evaluable_years_{h}d"]=len(ys)
            rec[f"positive_year_share_{h}d_pct"]=float((np.asarray(ys)>0).mean()*100) if ys else np.nan
            rec[f"worst_year_uplift_{h}d_pp"]=float(min(ys)) if ys else np.nan
        return rec

def make_numeric_outputs(cache,conditions,part,market_cats):
    import numpy as np
    out=[]
    if part in ("yearly_stability.csv","monthly_stability.csv"):
        period="year" if part.startswith("yearly") else "month"
        for key,mask in conditions.items():
            labels,counts,arr=cache.stats(mask,period)
            for j,period_key in enumerate(labels):
                if not counts[j]:continue
                rec={"condition_id":key,period:str(period_key),"count":int(counts[j])}
                for h in HORIZONS:
                    win,base,ret=arr[h]
                    w=float(win[j]);b=float(base[j])
                    rec.update({f"win_{h}d_pct":w,
                        f"period_baseline_win_{h}d_pct":b,
                        f"uplift_{h}d_pp":w-b if np.isfinite(w) and np.isfinite(b) else np.nan,
                        f"return_{h}d_pct":float(ret[j])})
                out.append(rec)
    elif part in ("rolling_3y_stability.csv","rolling_5y_stability.csv"):
        length=3 if part.startswith("rolling_3") else 5
        # Original canonical iterates window-first, condition-second.
        perkey={key:{(v["window_start"],v["window_end"]):v for v in cache.rolling(mask,length)}
                for key,mask in conditions.items()}
        lo=min(cache.year_masks);hi=max(cache.year_masks)
        for end in range(lo+length-1,hi+1):
            start=end-length+1
            for key in conditions:
                v=perkey[key].get((start,end))
                if v is not None:out.append({"condition_id":key,**v})
    else:
        for key,mask in conditions.items():
            for regime in market_cats:
                specific=mask & (cache.regime==regime)
                out.append({"condition_id":key,"regime":regime,**cache.metrics(specific)})
    return out

def verify(core,reference,source,proof,dataset,output):
    import numpy as np
    import pandas as pd
    sys.path.insert(0,str(core/"scripts"))
    import finalize_p2_nikkei_complete_baseline as fin
    import build_p2_225_semantic_bundle as sem
    import analyze_p2_nikkei_complete_baseline as cb
    phase=inspect_proof(core,reference,source,proof,dataset)
    frame=sem.prepare_frame(source)
    if len(frame)!=phase["source_rows"] or frame["ticker"].astype(str).nunique()!=phase["source_tickers"]:
        raise ValueError("Original pinned input population changed")
    t=time.perf_counter()
    masks=fin._feature_masks(frame)
    cond=build_selected_conditions(reference,fin,masks)
    cache=Cache(frame)
    print("PHASE42_SELECTED_SOURCE_CONDITIONS",dataset,len(cond),flush=True)
    files={}
    for name in OUTPUTS:
        start=time.perf_counter()
        old=pd.read_csv(reference/name,low_memory=False)
        records=make_numeric_outputs(cache,cond,name,cb.MARKET_CATS)
        fresh=pd.DataFrame(records)
        if list(old.columns)!=list(fresh.columns):
            raise ValueError(f"{name} output order/schema differs old={list(old.columns)} fresh={list(fresh.columns)}")
        if len(old)!=len(fresh):
            raise ValueError(f"{name} row count differs old={len(old)} fresh={len(fresh)}")
        try:
            pd.testing.assert_frame_equal(old,fresh,check_dtype=False,
                check_exact=False,atol=1e-7,rtol=1e-10,check_index_type=False)
        except AssertionError as err:
            raise AssertionError(f"{name}: numerical/label/order parity differs: {str(err)[:800]}") from err
        files[name]={"rows":len(fresh),"columns":len(fresh.columns),
                     "original_sha256":phase["files"][name]["sha256"],
                     "numeric_and_label_parity":True,
                     "seconds":round(time.perf_counter()-start,3)}
        print("PASS_PHASE42_CACHED_NUMPY_FULL_FILE",dataset,name,len(fresh),flush=True)
        del old,fresh
    if digest(source)!=phase["source_sha256"]:
        raise ValueError("Original source mutated during research benchmark")
    for f in SOURCES+OUTPUTS:
        if digest(reference/f)!=phase["files"][f]["sha256"]:
            raise ValueError("Original saved CSV modified")
    return {
      "schema":1,"status":"PASS_PHASE42_FIVE_CACHED_SEMANTIC_OUTPUTS",
      "dataset":dataset,"original_private_sha":CORE_SHA,
      "source_sha256":phase["source_sha256"],"source_rows":len(frame),
      "source_tickers":phase["source_tickers"],"condition_count":len(cond),
      "file_count":len(files),"files":files,"total_seconds":round(time.perf_counter()-t,3),
      "full_semantic_producer_rerun":False,
      "phase40_and_41_successful_work_recomputed":False,
      "production_p2_v12_changed":False,"original_csv_html_modified":False,
      "phase42_full_29csv_certified":False,"phase43_full_pipeline_certified":False,
      "release_ready":False
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--dataset",choices=DATASETS)
    for n in ("core","reference","source","phase38","report"):
        ap.add_argument("--"+n,type=Path)
    a=ap.parse_args()
    if a.selftest:
        assert len(DATASETS)==8 and len(OUTPUTS)==5
        assert len(SOURCES)==3
        print("PASS_PHASE42_CACHED_NUMPY_FIVE_CSV_SCHEMA_TEST")
        return 0
    if any(getattr(a,n) is None for n in ("dataset","core","reference","source","phase38","report")):
        ap.error("All fixed source inputs and new JSON report required")
    if a.report.exists():raise FileExistsError("Do not overwrite previous success")
    data=verify(a.core.resolve(),a.reference.resolve(),a.source.resolve(),
                a.phase38.resolve(),a.dataset,a.report)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data,ensure_ascii=False))
    return 0
if __name__=="__main__":raise SystemExit(main())
