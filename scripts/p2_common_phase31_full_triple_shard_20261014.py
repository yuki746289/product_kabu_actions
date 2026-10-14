# Created: 2026-10-14 JST
"""Phase31: disjoint canonical three-feature _triples inner producer parity.

Select each 3-feature combination once by feature1 index interval [start,start+4).
Original inner _triples only receives eligible singles from exactly the target
three features, never a full 16-feature triple universe. Previously certified
transport first-four-feature 570 triple conditions are omitted entirely.
Pinned old saved outputs are read-only. Public artifacts only contain metadata.
"""
from __future__ import annotations
import argparse
import itertools
import json
from pathlib import Path
import subprocess
import sys

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials","capital_goods_others","transportation_utilities")
EXCLUSIONS={
 "exclude_capital_goods_transportation_utilities":
    (137426,170,"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"),
 "exclude_transportation_utilities":
    (166470,205,"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"),
}
DATASETS=GROUPS+tuple(EXCLUSIONS)
STARTS=(0,4,8,12)
NFEATURES=16
CERT_TRANSPORT=570
KEYS=("feature1","category1","feature2","category2","feature3","category3")

def selftest():
    combos=list(itertools.combinations(range(NFEATURES),3))
    for i,j,k in combos:
        assert sum(a<=i<min(a+4,NFEATURES) for a in STARTS)==1
    assert len(combos)==560 and len(DATASETS)==8
    assert len([x for x in combos if max(x)<4])==4
    assert len(CORE_SHA)==40 and len(KEYS)==6
    print("PASS_PHASE31_DISJOINT_TRIPLE_FEATURES_CONTRACT")

def read_json(path:Path)->dict:
    return json.loads(path.read_text(encoding="utf-8"))

def verify(core:Path,reference:Path,original_source:Path,proof4:Path,
           pair_proofs:Path,transport_proof:Path,dataset:str,
           start:int,stage:Path)->dict:
    if dataset not in DATASETS or start not in STARTS:
        raise ValueError("Disallowed dataset/feature-shard start")
    head=subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                                 text=True).strip()
    if head!=CORE_SHA:
        raise ValueError("Private original SHA mismatch")
    base_build=(core/"build").resolve()
    if stage.exists() or stage.resolve()==base_build or not stage.resolve().is_relative_to(base_build):
        raise ValueError("Fresh isolated private build stage required")
    actual_ref=(core/"preview/kabu/analysis"/
        ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
        dataset).resolve()
    if reference!=actual_ref:
        raise ValueError("Pinned dataset directory not canonical")
    if dataset in GROUPS:
        src=reference/"signal_level_features.csv"
    else:
        matches=list(original_source.rglob("features.csv"))
        if len(matches)!=1:raise ValueError("Exactly one original exclusion source required")
        src=matches[0]
    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import analyze_p2_nikkei_complete_baseline as cb
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import build_p2_225_semantic_bundle as common
    from p2_html_core.p03_common_analysis_plan import digest
    sha=digest(src)
    p4=read_json(proof4)
    if dataset in GROUPS:
        g=(p4.get("groups") or {}).get(dataset) or {}
        rows,tickers=g.get("row_count"),g.get("ticker_count")
        if (p4.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION"
            or g.get("csv_sha256")!=sha or g.get("duplicate_ids") is not False
            or not isinstance(rows,int) or rows<=0
            or not isinstance(tickers,int) or tickers<=0):
            raise ValueError("Phase4 group identity verification failed")
    else:
        rows,tickers,expected=EXCLUSIONS[dataset]
        g=p4.get("saved_exclusion") or {}
        if (p4.get("status")!="PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE"
            or p4.get("variant")!=dataset or sha!=expected
            or g.get("csv_sha256")!=sha or g.get("row_count")!=rows
            or g.get("ticker_count")!=tickers or g.get("duplicate_ids") is not False):
            raise ValueError("Phase4 exclusion source identity mismatch")

    originals=set()
    for s in STARTS:
        path=pair_proofs/str(s)/"audit.json"
        if not path.exists():raise ValueError("Missing Phase30 fixed prior pairwise artifact")
        prev=read_json(path)
        if (prev.get("status")!="PASS_PHASE30_NEW_PAIRWISE_NONOVERLAP_SHARD"
            or prev.get("dataset")!=dataset or prev.get("private_core_sha")!=CORE_SHA
            or prev.get("source_sha256")!=sha or prev.get("feature_first_start")!=s
            or prev.get("saved_full_reference_rows")!=10476
            or prev.get("numerical_errors")!=[]
            or prev.get("previous_artifacts_recalculated") is not False):
            raise ValueError("Phase30 prior pairwise shard proof invalid")
        originals.add(prev.get("original_full_pair_sha256"))
    if len(originals)!=1:
        raise ValueError("Phase30 old canonical pair SHA inconsistent across shards")

    if dataset=="transportation_utilities":
        prior=read_json(transport_proof)
        if (prior.get("status")!="PASS_PHASE26_NEW_TRIPLE_FOUR_FEATURE_HOLDOUT"
            or prior.get("dataset")!=dataset
            or prior.get("private_core_sha")!=CORE_SHA
            or prior.get("source_sha256")!=sha
            or prior.get("new_subset_triple_rows")!=CERT_TRANSPORT
            or prior.get("old_holdout_triple_rows")!=CERT_TRANSPORT
            or prior.get("numerical_errors")!=[]
            or prior.get("new_common_triples_inner_function_called") is not True):
            raise ValueError("Already-certified transport triple proof invalid")

    frame=common.prepare_frame(src)
    if len(frame)!=rows or frame["ticker"].astype(str).nunique()!=tickers:
        raise ValueError("Pinned original input cardinality mismatch")
    base=cb._baseline_metrics(frame)
    fields,expected=aug._rep_fields(frame)
    names=list(fields)
    if len(names)!=NFEATURES or len(set(names))!=NFEATURES:
        raise ValueError("Original 16 canonical feature order changed")
    singles,masks=aug._representative_singles(frame,base,fields,expected)

    wanted=[(i,j,k) for i,j,k in itertools.combinations(range(NFEATURES),3)
            if start<=i<min(start+4,NFEATURES)
            and not(dataset=="transportation_utilities" and k<4)]
    if not wanted:raise ValueError("No unverified triple feature combinations")
    old_path=reference/"tested_triple_combinations.csv"
    old_sha=digest(old_path)
    old=pd.read_csv(old_path,low_memory=False)
    if len(old)<1000 or old.duplicated(list(KEYS)).any():
        raise ValueError("Old canonical full triple reference invalid")
    feature_triplets={(names[i],names[j],names[k]) for i,j,k in wanted}
    raw_keys=list(zip(old["feature1"],old["feature2"],old["feature3"]))
    old_subset=old.loc[[k in feature_triplets for k in raw_keys]].copy()
    # Calculate only exactly three feature types per original canonical _triples call.
    # Every family triple is disjoint from other shards and prior holdout.
    frames=[]
    for i,j,k in wanted:
        fset={names[i],names[j],names[k]}
        part=singles.loc[singles["feature"].isin(fset)].copy()
        generated,_=aug._triples(frame,base,part,masks)
        if not generated.empty:
            if set(zip(generated["feature1"],generated["feature2"],generated["feature3"])) != {
                    (names[i],names[j],names[k])}:
                raise ValueError("Unexpected off-shard canonical triple")
            frames.append(generated)
    if not frames or old_subset.empty:
        raise ValueError("Expected non-empty triple production shard")
    fresh=pd.concat(frames,ignore_index=True,sort=False)
    if len(fresh)!=len(old_subset) or fresh.duplicated(list(KEYS)).any():
        raise ValueError("Full original vs new disjoint triple row cardinality mismatch")
    stage.mkdir(parents=True,exist_ok=False)
    output=stage/"triple_shard.csv"
    fresh.to_csv(output,index=False,encoding="utf-8")
    reloaded=pd.read_csv(output,low_memory=False)
    old_subset=old_subset.sort_values(list(KEYS)).reset_index(drop=True)
    reloaded=reloaded.sort_values(list(KEYS)).reset_index(drop=True)
    problems=[]
    if list(old_subset.columns)!=list(reloaded.columns):
        problems.append("ordered_columns")
    elif not old_subset[list(KEYS)].equals(reloaded[list(KEYS)]):
        problems.append("key_values")
    else:
        try:
            pd.testing.assert_frame_equal(old_subset,reloaded,check_dtype=False,
                check_exact=False,atol=1e-7,rtol=1e-10,check_index_type=False)
        except AssertionError:
            problems.append("numeric_or_label")
    if digest(src)!=sha or digest(old_path)!=old_sha:
        raise ValueError("Saved original feature or reference bytes changed")
    return {
        "schema":1,
        "status":"PASS_PHASE31_NEW_TRIPLE_DISJOINT_SHARD" if not problems else "FAIL_PHASE31_NEW_TRIPLE_DISJOINT_SHARD",
        "dataset":dataset,"private_core_sha":CORE_SHA,"source_sha256":sha,
        "source_rows":rows,"source_tickers":tickers,
        "feature_first_start":start,"feature_first_end":min(start+4,NFEATURES),
        "feature_triples_tested":len(wanted),
        "original_full_triples":len(old),
        "new_triple_rows":len(reloaded),"old_subset_triple_rows":len(old_subset),
        "old_full_triple_sha256":digest(old_path),
        "new_subset_sha256":digest(output),
        "numerical_errors":problems,
        "skipped_previous_transport_570":CERT_TRANSPORT if dataset=="transportation_utilities" else 0,
        "previous_certified_triples_recalculated":False,
        "previous_artifacts_recalculated":False,
        "full_semantic_recalculated":False,"full_or_recalculated":False,
        "saved_signals_recomputed":False,"html_generated":False,
        "production_changed":False,"release_ready":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    p.add_argument("--start",type=int,choices=STARTS)
    for arg in ("core","reference","original-source","proof4",
                "pair-proofs","transport-proof","stage","report"):
        p.add_argument("--"+arg,type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest();return 0
    needed=("dataset","start","core","reference","original_source","proof4",
            "pair_proofs","stage","report")
    if any(getattr(a,k) is None for k in needed):
        p.error("Pinned dataset source, Phase30 proof and output required")
    if a.dataset=="transportation_utilities" and a.transport_proof is None:
        p.error("Prior original transport 570 triple numerical proof required")
    if a.report.exists():
        raise FileExistsError("Never overwrite previous numerical certificate")
    result=verify(a.core.resolve(),a.reference.resolve(),a.original_source.resolve(),
                  a.proof4.resolve(),a.pair_proofs.resolve(),
                  a.transport_proof.resolve() if a.transport_proof else Path("NO_PRIOR_TRANSPORT").resolve(),
                  a.dataset,a.start,a.stage.resolve())
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ("old_full_triple_sha256","new_subset_sha256")},
                     ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
