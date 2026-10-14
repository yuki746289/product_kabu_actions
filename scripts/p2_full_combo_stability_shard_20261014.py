# Created 2026-10-14 JST
"""Timeout-safe exhaustive remaining combination-stability verification.

Never reexecute successful Phase39 (first 3 per kind) and Phase40 (next 20
per kind). For each dataset, split ALL other candidate pair/triple conditions
over eight disjoint deterministic position shards. Recompute ONLY the
canonical _stability_summary for this shard, compare every field/order with
original saved rows, and upload only SHA-bound audit JSON, no Private CSV.
No full 6-hour semantic bundle, P2 feature extraction, OR, HTML, release.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys
from pathlib import Path

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUSIONS={
"exclude_capital_goods_transportation_utilities":"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
"exclude_transportation_utilities":"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"}
DATASETS=GROUPS+tuple(EXCLUSIONS)
PARTS=8
SKIP=23
NAME={"pair":"all_pairwise_combinations.csv","triple":"tested_triple_combinations.csv"}
STABILITY="combination_stability_summary.csv"

def sha(path:Path)->str:
    d=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):d.update(b)
    return d.hexdigest()

def load(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def selftest():
    assert len(DATASETS)==8 and PARTS==8 and SKIP==3+20
    assert all(len(h)==64 for h in EXCLUSIONS.values())
    assert sum(len(range(i,79,PARTS)) for i in range(PARTS))==79
    print("PASS_PHASE40_TIMEOUT_SAFE_DISJOINT_8_SHARDS")

def key_for(kind,record):
    n=3 if kind=="triple" else 2
    return (kind,)+tuple((str(record[f"feature{i}"]),str(record[f"category{i}"]))
                          for i in range(1,n+1))

def verify(core:Path,root:Path,sources:Path,dataset:str,part:int,proof38:Path,proof39:Path,proof40:Path):
    if dataset not in DATASETS or not 0<=part<PARTS:
        raise ValueError("Unapproved dataset/shard")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=CORE_SHA:
        raise ValueError("Original Private SHA changed")
    expected=(core/"preview/kabu/analysis"/
              ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
              dataset).resolve()
    if root!=expected:
        raise ValueError("Unapproved original reference folder")
    if dataset in GROUPS:src=root/"signal_level_features.csv"
    else:
        found=list(sources.rglob("features.csv"))
        if len(found)!=1 or sha(found[0])!=EXCLUSIONS[dataset]:
            raise ValueError("External saved exclusions source identity mismatch")
        src=found[0]
    p38=load(proof38);p39=load(proof39);p40=load(proof40)
    source_sha=sha(src)
    if (p38.get("status")!="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"
        or p38.get("dataset")!=dataset or p38.get("private_core_sha")!=CORE_SHA
        or p38.get("source_sha256")!=source_sha):
        raise ValueError("Phase38 original 29CSV/source sha proof missing")
    if (p39.get("status")!="PASS_PHASE39_NEW_BOUNDED_COMBO_STABILITY"
        or p39.get("dataset")!=dataset or p39.get("source_sha256")!=source_sha
        or p39.get("new_pair_candidates")!=3 or p39.get("new_triple_candidates")!=3
        or p39.get("mismatches")!=[]):
        raise ValueError("Phase39 first 3+3 certified condition proof missing")
    if (p40.get("phase")!="40" or p40.get("status")!="PASS_SCOPED"
        or p40.get("dataset")!=dataset or p40.get("source_sha256")!=source_sha
        or p40.get("private_core_sha")!=CORE_SHA
        or p40.get("details",{}).get("column_and_order_numeric_mismatches")!=0):
        raise ValueError("Phase40 next 20+20 source-bound proof missing")
    for kind in NAME:
        if p40["details"]["kinds"][kind]["previous_phase39_skipped"]!=3 or p40["details"]["kinds"][kind]["new_checked"]!=20:
            raise ValueError("Prior disjoint proven 3+20 scope changed")
    for filename in (*NAME.values(),STABILITY):
        if p38["files"][filename]["sha256"]!=sha(root/filename):
            raise ValueError("Original saved source CSV sha mismatch "+filename)
    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import finalize_p2_nikkei_complete_baseline as fin
    import build_p2_225_semantic_bundle as sem
    frame=sem.prepare_frame(src)
    if len(frame)!=p38["source_rows"] or frame.ticker.astype(str).nunique()!=p38["source_tickers"]:
        raise ValueError("Original saved features source shape changed")
    masks=fin._feature_masks(frame)
    saved=pd.read_csv(root/STABILITY,low_memory=False)
    lookup={}
    for _,row in saved.iterrows():
        key=key_for(str(row["condition_type"]),row)
        if key in lookup:raise ValueError("Duplicate original stability condition tuple")
        lookup[key]=row
    stats={};verified=[];failures=[];columns=list(saved.columns)
    for kind,filename in NAME.items():
        inputs=pd.read_csv(root/filename,low_memory=False)
        candidate=inputs.loc[fin._truthy(inputs["candidate"])].copy()
        prior=SKIP
        if len(candidate)<=prior:
            raise ValueError("No unverified saved stability candidate rows")
        if len(candidate)!=p40["details"]["kinds"][kind]["saved_total"]:
            raise ValueError("Original Phase40 candidate total mismatched")
        portion=candidate.iloc[prior+part::PARTS].copy()
        count=len(portion)
        if not count:
            raise ValueError("Empty disjoint shard")
        new=fin._stability_summary(frame,portion,kind,masks)
        if len(new)!=count:raise ValueError("Canonical newly calculated rows not complete")
        for _,actual in new.iterrows():
            key=key_for(kind,actual)
            old=lookup.get(key)
            if old is None:raise ValueError("New condition key missing from original full stability")
            if key in verified:raise ValueError("Duplicate new condition key in shard")
            verified.append(key)
            # Align columns after adding the original missing pair/triple
            # counterpart columns (pair lacks feature3/category3).
            if not set(new.columns).issubset(set(columns)):
                raise ValueError("Unexpected new stability output field(s)")
            expanded=actual.reindex(columns)
            old_aligned=old.reindex(columns)
            try:
                pd.testing.assert_series_equal(old_aligned,expanded,check_dtype=False,
                    check_exact=False,atol=1e-7,rtol=1e-10,check_index_type=False,
                    check_names=False)
            except AssertionError:
                failures.append({"kind":kind,"key_sha256":hashlib.sha256(repr(key).encode()).hexdigest(),
                    "reason":"old_vs_new_stability_numeric_or_label"})
                if len(failures)>=10:break
        stats[kind]={"saved_candidate_total":len(candidate),
                     "prior_successful_skipped":prior,
                     "full_unverified_total":len(candidate)-prior,
                     "new_rows_checked":count}
        print("PROGRESS_TIMEOUT_SAFE_STABILITY",dataset,kind,part,count,flush=True)
    if sha(src)!=source_sha or any(
      sha(root/f)!=p38["files"][f]["sha256"] for f in (*NAME.values(),STABILITY)):
        raise ValueError("Original saved source changed during analysis")
    return {
        "schema":1,
        "status":"PASS_FULL_REMAINING_COMBO_STABILITY_SHARD" if not failures else "FAIL_NUMERIC_PARITY",
        "dataset":dataset,"shard":part,"shards":PARTS,
        "private_core_sha":CORE_SHA,"source_sha256":source_sha,
        "original_stability_sha256":sha(root/STABILITY),
        "source_rows":len(frame),
        "expected_original_stability_rows":len(saved),
        "kinds":stats,
        "new_condition_digest_list":[hashlib.sha256(repr(key).encode()).hexdigest() for key in verified],
        "new_condition_count":len(verified),
        "new_stability_inner_function_executed":True,
        "previously_certified_conditions_recomputed":False,
        "semantic_full_bundle_generated":False,"historical_success_artifacts_recomputed":False,
        "production_changed":False,"original_csv_html_modified":False,
        "release_ready":False,"failures":failures,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    p.add_argument("--part",type=int)
    for name in ("core","reference","source-root","phase38","phase39","phase40","report"):
        p.add_argument("--"+name,type=Path)
    x=p.parse_args()
    if x.selftest:selftest();return 0
    if any(getattr(x,k) is None for k in (
        "dataset","part","core","reference","source_root","phase38","phase39","phase40","report")):
        p.error("dataset, part, core, source and prior SHA-bound certs required")
    if x.report.exists():raise FileExistsError("Refuse overwrite of successful/failed audit")
    data=verify(x.core.resolve(),x.reference.resolve(),x.source_root.resolve(),
                x.dataset,x.part,x.phase38.resolve(),x.phase39.resolve(),x.phase40.resolve())
    x.report.parent.mkdir(parents=True,exist_ok=True)
    x.report.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k not in ("new_condition_digest_list","failures")},ensure_ascii=False))
    return 0 if data["status"].startswith("PASS_") else 2

if __name__=="__main__":raise SystemExit(main())
