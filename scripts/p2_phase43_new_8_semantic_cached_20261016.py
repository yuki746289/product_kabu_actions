# Created 2026-10-16 JST
"""Phase43 real *fresh* optimized canonical 8 core Semantic CSV outputs.

Executes actual pinned Private canonical original semantic functions:
 _full_single_categories, aug._representative_singles, aug._pairwise, aug._triples.
Within THIS ephemeral research process, cb._metrics uses the independently
Phase42-benchmarked cached NumPy aggregation (same canonical numeric outputs).
This DOES NOT rerun previously certified Phase40 combo_stability,
Phase41 combo_walkforward, Phase42 existing five stability or OR raw analysis.

New 8 CSV contents, row identity, all columns and numerics compared against
Phase38 SHA-pinned OLD canonical saved reference. They exist only in an
ephemeral Private core/build dir (deleted), with SHA-linked new producer ledger.
No user sensitive CSV ever uploaded to the public action/artifact.
Full 23 semantic / five OR 29 CSV producer is NOT hereby certified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials","capital_goods_others","transportation_utilities")
EXCLUSIONS={
 "exclude_capital_goods_transportation_utilities":"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
 "exclude_transportation_utilities":"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1",
}
DATASETS=GROUPS+tuple(EXCLUSIONS)
OUTS={
 "all_single_categories.csv":"all_single",
 "representative_single_categories.csv":"representative",
 "all_pairwise_combinations.csv":"pairs",
 "tested_triple_combinations.csv":"triples",
 "candidate_registry.csv":"candidates",
 "advantage_single_candidates.csv":"adv_single",
 "advantage_pairwise_candidates.csv":"adv_pair",
 "advantage_triple_candidates.csv":"adv_triple",
}
HORIZONS=(5,10,20)

def sha(path:Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()
def read(path):return json.loads(path.read_text(encoding="utf-8"))
def write(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def selftest():
    assert len(DATASETS)==8 and len(OUTS)==8 and len(set(OUTS.values()))==8
    print("PASS_PHASE43_FRESH_EIGHT_SEMANTIC_OPTIMIZED_BOUNDARY")

class MetricCache:
    def __init__(self,frame):
        import numpy as np
        import pandas as pd
        self.frame=frame
        self.years=frame["as_of"].dt.year.to_numpy(int)
        self.year_masks={int(yr):self.years==yr for yr in sorted(set(self.years))}
        self.values={h:pd.to_numeric(frame[f"moved_predicted_{h}d"],errors="coerce").to_numpy(float) for h in HORIZONS}
        self.returns={h:pd.to_numeric(frame[f"directional_return_{h}d_pct"],errors="coerce").to_numpy(float) for h in HORIZONS}
        self.valid={h:np.isfinite(self.values[h]) for h in HORIZONS}
        self.rvalid={h:np.isfinite(self.returns[h]) for h in HORIZONS}
        self.baseline_year={
          h:{yr:(int((ym & self.valid[h]).sum()),
            float(self.values[h][ym & self.valid[h]].mean()*100)
            if (ym & self.valid[h]).any() else float("nan"))
            for yr,ym in self.year_masks.items()}
          for h in HORIZONS}
    def metrics(self,frame,mask,base):
        import numpy as np
        if frame is not self.frame:
            raise ValueError("Cached metrics original source frame identity changed")
        mask=np.asarray(mask,dtype=bool)
        count=int(mask.sum())
        ans={"count":count,"retention_pct":count/len(frame)*100}
        for h in HORIZONS:
            good=mask & self.valid[h]
            returns=mask & self.rvalid[h]
            win=float(self.values[h][good].mean()*100) if good.any() else np.nan
            ret=float(self.returns[h][returns].mean()) if returns.any() else np.nan
            ans[f"win_{h}d_pct"]=win
            ans[f"return_{h}d_pct"]=ret
            ans[f"win_uplift_{h}d_pp"]=win-base[h][0] if np.isfinite(win) else np.nan
            ans[f"return_uplift_{h}d_pct"]=ret-base[h][1] if np.isfinite(ret) else np.nan
            uplifts=[]
            for year,ym in self.year_masks.items():
                nbase,baseline=self.baseline_year[h][year]
                selected=ym & good
                if nbase<3 or selected.sum()<2:continue
                uplifts.append(float(self.values[h][selected].mean()*100-baseline))
            ans[f"evaluable_years_{h}d"]=len(uplifts)
            ans[f"positive_year_share_{h}d_pct"]=(
              float((np.asarray(uplifts)>0).mean()*100) if uplifts else np.nan)
            ans[f"worst_year_uplift_{h}d_pp"]=float(min(uplifts)) if uplifts else np.nan
        return ans

def go(core:Path,ref:Path,external:Path,p38path:Path,p43path:Path,dataset:str):
    import numpy as np
    import pandas as pd
    if dataset not in DATASETS:raise ValueError("Unsupported canonical population")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=SHA:
        raise ValueError("Original Private core SHA changed")
    expect=(core/"preview/kabu/analysis"/
            ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
            dataset).resolve()
    if ref!=expect:raise ValueError("Old saved reference path not pinned")
    if dataset in GROUPS:source=ref/"signal_level_features.csv"
    else:
        files=list(external.rglob("features.csv"))
        if len(files)!=1 or sha(files[0])!=EXCLUSIONS[dataset]:
            raise ValueError("External original exclusion features SHA mismatch")
        source=files[0]
    p38,p43=read(p38path),read(p43path)
    digest=sha(source)
    if (p38.get("dataset")!=dataset or p43.get("dataset")!=dataset
        or p38.get("status")!="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"
        or p43.get("status")!="PASS_PHASE43_SAVED_SOURCE_PROVENANCE_CHAIN_ONLY"
        or p38.get("private_core_sha")!=SHA or p43.get("private_core_sha")!=SHA
        or p38.get("source_sha256")!=digest or p43.get("source_sha256")!=digest
        or p38.get("mismatches")!=[]):
        raise ValueError("Exact original SHA-bound source and prior Phase43 verification mismatch")
    for name in OUTS:
        if sha(ref/name)!=p38["files"][name]["sha256"]:
            raise ValueError("Original saved target CSV SHA changed: "+name)
    sys.path.insert(0,str(core/"scripts"))
    import build_p2_225_canonical_semantic_data as original
    import build_p2_225_semantic_bundle as prep
    import analyze_p2_nikkei_complete_baseline as cb
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import finalize_p2_nikkei_complete_baseline as fin
    root=(core/"build"/"phase43_fresh_optimized_semantic_eight_20261016"/dataset).resolve()
    if root.exists() or not root.is_relative_to((core/"build").resolve()):
        raise ValueError("Fresh isolated non-persistent Private stage required")
    root.mkdir(parents=True,exist_ok=False)
    clock=time.perf_counter()
    old_metrics=cb._metrics
    ledger={}
    try:
        frame=prep.prepare_frame(source)
        if len(frame)!=p38["source_rows"] or frame.ticker.astype(str).nunique()!=p38["source_tickers"]:
            raise ValueError("Original feature census/source input mismatch")
        metrics=MetricCache(frame)
        base=cb._baseline_metrics(frame)
        fm=fin._feature_masks(frame)
        # Independent actual canonical legacy _metrics vs cached new array values.
        for i,m in enumerate(list(fm.values())[:12]):
            raw=old_metrics(frame,m,base)
            fast=metrics.metrics(frame,m,base)
            if set(raw)!=set(fast):
                raise AssertionError("Optimized _metrics field set changed")
            for k in raw:
                a,b=raw[k],fast[k]
                if not np.isclose(a,b,atol=1e-7,rtol=1e-10,equal_nan=True):
                    raise AssertionError(f"Cached vs canonical original _metrics mismatch in field {k}, test {i}")
        cb._metrics=metrics.metrics
        all_single=original._full_single_categories(frame,base)
        print("PHASE43_FRESH_CANONICAL_ALL_SINGLE",dataset,len(all_single),flush=True)
        fields,expected=aug._rep_fields(frame)
        representative,masks=aug._representative_singles(frame,base,fields,expected)
        if len(representative)!=151:raise ValueError("Canonical 151 representative single outputs changed")
        print("PHASE43_FRESH_CANONICAL_REPRESENTATIVE",dataset,len(representative),flush=True)
        pairs,_=aug._pairwise(frame,base,fields,expected,representative,masks)
        if len(pairs)!=10476:raise ValueError("Canonical 10476 pairwise output rows changed")
        print("PHASE43_FRESH_CANONICAL_PAIRWISE",dataset,len(pairs),flush=True)
        triples,_=aug._triples(frame,base,representative,masks)
        print("PHASE43_FRESH_CANONICAL_TRIPLE",dataset,len(triples),flush=True)
        single=representative.loc[fin._truthy(representative["candidate"])].copy()
        single["condition_type"]="single"
        single["small_sample"]=single["count"]<30
        single["condition_id"]="S:"+single["feature"]+"="+single["category"]
        adv_single=all_single.loc[fin._truthy(all_single["candidate"])].copy()
        adv_pair=pairs.loc[fin._truthy(pairs["candidate"])].copy()
        adv_triple=triples.loc[fin._truthy(triples["candidate"])].copy()
        for df in (adv_single,adv_pair,adv_triple):
            if "small_sample" not in df.columns:
                df["small_sample"]=pd.to_numeric(df["count"],errors="coerce").fillna(0).lt(30)
        outputs={
          "all_single":all_single,"representative":representative,
          "pairs":pairs,"triples":triples,"candidates":single,
          "adv_single":adv_single,"adv_pair":adv_pair,"adv_triple":adv_triple,
        }
        for filename,label in OUTS.items():
            before=time.perf_counter()
            fresh=outputs[label]
            saved=pd.read_csv(ref/filename,low_memory=False)
            if len(saved)!=len(fresh) or list(saved.columns)!=list(fresh.columns):
                raise ValueError(f"REAL_NEW_SEMANTIC_SCHEMA_OR_ROWS_DIFFERS: {filename}: "
                                 f"{len(saved)} vs {len(fresh)}")
            try:
                pd.testing.assert_frame_equal(saved,fresh.reset_index(drop=True),
                    check_dtype=False,check_exact=False,atol=1e-7,rtol=1e-10,
                    check_index_type=False)
            except AssertionError as exc:
                raise AssertionError(f"FRESH_NEW_SEMANTIC_FULL_ROW_ORDER_NUMERIC_PARITY: "
                                      f"{filename}: {str(exc)[:1100]}") from exc
            path=root/filename
            fresh.to_csv(path,index=False,encoding="utf-8")
            if not path.exists() or path.stat().st_size==0:
                raise ValueError("New actual producer output missing")
            ledger[filename]={
              "producer":"PINNED_ORIGINAL_CANONICAL_FUNCTION_WITH_CACHED_NUMPY_METRICS",
              "original_saved_sha256":p38["files"][filename]["sha256"],
              "new_real_output_sha256":sha(path),
              "new_rows":len(fresh),"new_columns":len(fresh.columns),
              "numeric_and_original_order_parity":True,
              "seconds":round(time.perf_counter()-before,3)
            }
            print("PASS_PHASE43_FRESH_CANONICAL_SEMANTIC_FILE",dataset,filename,len(fresh),flush=True)
        for name in OUTS:
            if sha(ref/name)!=p38["files"][name]["sha256"]:
                raise ValueError("Original saved file modified during independent computation")
        if sha(source)!=digest:raise ValueError("Original input modified during research computation")
        return {"schema":1,
          "status":"PASS_PHASE43_EIGHT_FRESH_CANONICAL_SEMANTIC_NUMERIC_OUTPUTS",
          "dataset":dataset,"private_core_sha":SHA,"source_sha256":digest,
          "eight_original_semantic_producer_functions_executed":True,
          "cached_metrics_versus_original_sample_fields":12,
          "new_semantic_outputs":ledger,"new_semantic_outputs_count":len(ledger),
          "rows_source":len(frame),
          "elapsed_seconds":round(time.perf_counter()-clock,3),
          "private_peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
          "source_artifacts_modified":False,"production_p2_v12_changed":False,
          "phase40_combination_stability_recomputed":False,
          "phase41_combination_walkforward_recomputed":False,
          "phase42_stability_csvs_recomputed":False,
          "semantic_all_23_real_output_complete":False,
          "full_new_OR_five_producer_executed":False,
          "new_29_csv_assembler_executed":False,
          "full_end_to_end_29_numeric_parity_certified":False,
          "release_ready":False,"phase48_executed":False}
    finally:
        cb._metrics=old_metrics
        if root.exists():shutil.rmtree(root)
        print("REMOVED_FRESH_CANONICAL_SEMANTIC_PRIVATE_STAGE",dataset,flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--dataset",choices=DATASETS)
    for name in ("core","reference","external","phase38","phase43","report"):
        ap.add_argument("--"+name,type=Path)
    a=ap.parse_args()
    if a.selftest:
        assert len(DATASETS)==8 and len(OUTS)==8 and len(SHA)==40
        print("PASS_PHASE43_EIGHT_FRESH_CANONICAL_OPTIMIZED_NUMPY_SCOPE")
        return
    if any(getattr(a,x) is None for x in ("dataset","core","reference","external","phase38","phase43","report")):
        ap.error("Original source, pinned previous SHA proofs, isolated fresh report required")
    if a.report.exists():raise FileExistsError("Prior original research certificate must not be overwritten")
    data=go(a.core.resolve(),a.reference.resolve(),a.external.resolve(),
            a.phase38.resolve(),a.phase43.resolve(),a.dataset)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k!="new_semantic_outputs"},
                     ensure_ascii=False),flush=True)
if __name__=="__main__":main()
