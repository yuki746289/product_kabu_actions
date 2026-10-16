# Created 2026-10-16 JST
"""Phase41 full numerical walkforward parity, disjoint two-year shards.

Reproduces EXACT original _walkforward's one-test-year loop, pair/triple
candidate iteration order, strict train thresholds, uplift tie breaks and
dict insertion order. Each shard owns two original test_years. No successful
Phase29 or Phase40 products are rerun, no original CSV/HTML touched.
Outputs only independently verifiable SHA-bound JSON, no private rows.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUDE={
  "exclude_capital_goods_transportation_utilities":
      "cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
  "exclude_transportation_utilities":
      "d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1",
}
DATASETS=GROUPS+tuple(EXCLUDE)
YEAR_START=2013
YEAR_LAST=2026
PER_SHARD=2
SHARDS=7
HORIZONS=(5,10,20)
FILES={"pair":"all_pairwise_combinations.csv","triple":"tested_triple_combinations.csv"}
REFERENCE="combination_walkforward_results.csv"
PREVIOUS="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"

def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def selftest():
    years=[list(range(YEAR_START+PER_SHARD*p,
                      YEAR_START+PER_SHARD*(p+1))) for p in range(SHARDS)]
    assert years==[[x,x+1] for x in range(2013,2027,2)]
    assert sorted({x for xs in years for x in xs})==list(range(2013,2027))
    assert len(DATASETS)==8
    print("PASS_PHASE41_ORIGINAL_YEAR_SHARD_PARTITION")

def verify(core:Path,ref:Path,sources:Path,proof:Path,dataset:str,shard:int):
    if dataset not in DATASETS or not 0<=shard<SHARDS:
        raise ValueError("Out-of-scope dataset or year shard")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=SHA:
        raise ValueError("Original Private core SHA differs")
    root=(core/"preview/kabu/analysis"/(
       "225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
       dataset).resolve()
    if root!=ref:raise ValueError("Reference folder not pinned original")
    if dataset in GROUPS:source=ref/"signal_level_features.csv"
    else:
        candidates=list(sources.rglob("features.csv"))
        if len(candidates)!=1 or digest(candidates[0])!=EXCLUDE[dataset]:
            raise ValueError("Original excluded feature source missing or changed")
        source=candidates[0]
    p=json.loads(proof.read_text(encoding="utf-8"))
    source_sha=digest(source)
    if (p.get("status")!=PREVIOUS or p.get("dataset")!=dataset
        or p.get("private_core_sha")!=SHA or p.get("source_sha256")!=source_sha
        or p.get("resolved_csv_files")!=29 or p.get("mismatches")!=[]):
        raise ValueError("Missing saved Phase38 independent source identity")
    for f in list(FILES.values())+[REFERENCE]:
        if digest(ref/f)!=p["files"][f]["sha256"]:
            raise ValueError("Original reference source SHA mutated: "+f)
    sys.path.insert(0,str(core/"scripts"))
    import numpy as np
    import pandas as pd
    import finalize_p2_nikkei_complete_baseline as fin
    import build_p2_225_semantic_bundle as semantic
    frame=semantic.prepare_frame(source)
    if len(frame)!=p["source_rows"] or frame["ticker"].astype(str).nunique()!=p["source_tickers"]:
        raise ValueError("Original source census changed")
    years=frame["as_of"].dt.year.to_numpy(int)
    all_years=sorted(set(years))
    required_years=list(range(YEAR_START,YEAR_LAST+1))
    if all_years[0]!=YEAR_START-5 or required_years!=[x for x in all_years if x>=all_years[0]+5]:
        raise ValueError("Saved original data time span different")
    year_group=list(range(YEAR_START+shard*PER_SHARD,YEAR_START+(shard+1)*PER_SHARD))
    targets=pd.read_csv(ref/REFERENCE,low_memory=False)
    if list(targets.columns)!=[
       "condition_type","horizon","test_year","train_count","train_uplift_pp",
       "test_count","test_win_pct","test_baseline_win_pct","test_uplift_pp",
       "feature1","category1","feature2","category2","feature3","category3"]:
        raise ValueError("Saved original walkforward schema/order differs")
    old=targets.loc[targets["test_year"].isin(year_group)].reset_index(drop=True)
    if len(old)!=6*len(year_group):raise ValueError("Expected six old test-year horizon rows per year")
    masks=fin._feature_masks(frame)
    input_by_kind={kind:pd.read_csv(ref/file,low_memory=False)
                    for kind,file in FILES.items()}
    results=[]
    for year in year_group:
        train=years<year
        test=years==year
        for kind,table in input_by_kind.items():
            best={}
            # The authoritative _walkforward uses ALL rows in each original input,
            # NOT only the rows with candidate=True.
            yarr={h:pd.to_numeric(frame[f"moved_predicted_{h}d"],
                      errors="coerce").to_numpy(float) for h in HORIZONS}
            baseline={}
            valid={}
            for h in HORIZONS:
                y=yarr[h]
                b=train & np.isfinite(y)
                valid[h]=b
                baseline[h]=float(y[b].mean()*100) if b.any() else float("nan")
            for _,row in table.iterrows():
                mask=fin._condition_mask(row,kind,masks)
                count=int(np.count_nonzero(train & mask))
                if count<20:continue
                for h in HORIZONS:
                    y=yarr[h];b=valid[h]
                    kv=b & mask
                    if kv.sum()<20 or not b.any():continue
                    uplift=float(y[kv].mean()*100 - baseline[h])
                    cur=best.get(h)
                    if cur is None or (uplift,count)>(cur[0],cur[1]):
                        best[h]=(uplift,count,row,mask)
            for h,(train_u,ntrain,row,mask) in best.items():
                y=yarr[h]
                bv=test & np.isfinite(y)
                kv=test & mask & np.isfinite(y)
                record={
                    "condition_type":kind,"horizon":f"{h}D","test_year":year,
                    "train_count":ntrain,"train_uplift_pp":train_u,
                    "test_count":int(kv.sum()),
                    "test_win_pct":float(y[kv].mean()*100) if kv.any() else np.nan,
                    "test_baseline_win_pct":float(y[bv].mean()*100) if bv.any() else np.nan,
                    "test_uplift_pp":float(y[kv].mean()*100-y[bv].mean()*100) if kv.any() and bv.any() else np.nan,
                }
                for i in range(1,4 if kind=="triple" else 3):
                    record[f"feature{i}"]=row[f"feature{i}"]
                    record[f"category{i}"]=row[f"category{i}"]
                results.append(record)
        print("COMPLETE_NEW_ORIGINAL_WALKFORWARD_YEAR",dataset,year,flush=True)
    now=pd.DataFrame(results).reindex(columns=targets.columns)
    if len(now)!=len(old):raise ValueError("New walkforward candidate row count changed")
    mismatches=[]
    try:
        pd.testing.assert_frame_equal(old,now,check_dtype=False,check_exact=False,
                                     atol=1e-7,rtol=1e-10,check_index_type=False)
    except AssertionError as exc:
        mismatches.append(str(exc)[:1200])
    if digest(source)!=source_sha or digest(ref/REFERENCE)!=p["files"][REFERENCE]["sha256"]:
        raise ValueError("Original saved data changed during full walkforward year audit")
    return {
      "schema":1,
      "status":"PASS_PHASE41_NEW_ORIGINAL_WALKFORWARD_TWO_YEARS" if not mismatches else "FAIL_NUMERIC_WALKFORWARD",
      "dataset":dataset,"shard":shard,"shards":SHARDS,"years":year_group,
      "old_rows":len(old),"new_rows":len(now),
      "numeric_comparison_fields":int(len(now)*len(now.columns)),
      "original_reference_sha256":p["files"][REFERENCE]["sha256"],
      "source_sha256":source_sha,"private_core_sha":SHA,
      "mismatches":mismatches,"actual_new_selection_calculated":True,
      "previous_success_artifacts_recomputed":False,
      "original_signal_recomputed":False,"old_csv_modified":False,
      "production_changed":False,"release_ready":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    p.add_argument("--shard",type=int)
    for name in ("core","reference","source-root","proof38","report"):
        p.add_argument("--"+name,type=Path)
    a=p.parse_args()
    if a.selftest:selftest();return 0
    if any(getattr(a,n) is None for n in ("dataset","shard","core","reference","source_root","proof38","report")):
        p.error("Missing source, immutable reference and prior SHA proof")
    if a.report.exists():raise FileExistsError("Never overwrite old numerical evidence")
    r=verify(a.core.resolve(),a.reference.resolve(),a.source_root.resolve(),
             a.proof38.resolve(),a.dataset,a.shard)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(r,ensure_ascii=False))
    return 0 if r["status"].startswith("PASS_") else 2

if __name__=="__main__":raise SystemExit(main())
