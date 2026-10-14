# Created: 2026-10-14T12:30:00+09:00
"""Phase30: canonical new pairwise inner function full parity in disjoint shards.

All feature-pair families belong to exactly one shard based on the index of
feature1. For transport, 1,800 previously certified Phase26 pair rows are
excluded by construction and certified proof is reused. Never rerun previous
artifacts, alter original signals/CSV, calculate triples/OR or generate HTML.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUSIONS={
 "exclude_capital_goods_transportation_utilities":
    (137426,170,"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"),
 "exclude_transportation_utilities":
    (166470,205,"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"),
}
DATASETS=GROUPS+tuple(EXCLUSIONS)
SHARD_STARTS=(0,4,8,12)
FIELD_COUNT=16
OLD_ALL_ROWS=10476
CERTIFIED_TRANSPORT_ROWS=1800
KEYS=("feature1","category1","feature2","category2")


def selftest():
    assert len(DATASETS)==8 and len(SHARD_STARTS)==4
    assert sorted(sum((list(range(i,min(i+4,FIELD_COUNT)))
                       for i in SHARD_STARTS),[]))==list(range(FIELD_COUNT))
    assert len(KEYS)==4 and len(CORE_SHA)==40
    print("PASS_PHASE30_DISJOINT_PAIRWISE_FEATURE_SHARD_CONTRACT")


def verify(core:Path,reference:Path,original_source:Path,proof4:Path,
           previous:Path,dataset:str,start:int,stage:Path)->dict:
    if dataset not in DATASETS or start not in SHARD_STARTS:
        raise ValueError("Dataset or shard not allowed")
    if subprocess.check_output(
        ["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=CORE_SHA:
        raise ValueError("Private immutable core SHA drift")
    root=(core/"build").resolve()
    if stage.exists() or stage.resolve()==root or not stage.resolve().is_relative_to(root):
        raise ValueError("Fresh isolated private/build staging required")
    expected_ref=(core/"preview/kabu/analysis"/
                  ("225_group_all_period" if dataset in GROUPS
                   else "225_exclusion_all_period")/dataset).resolve()
    if expected_ref!=reference:
        raise ValueError("Dataset reference directory mismatch")
    if dataset in GROUPS:
        source=reference/"signal_level_features.csv"
    else:
        found=list(original_source.rglob("features.csv"))
        if len(found)!=1:
            raise ValueError("Exactly one immutable original saved feature CSV required")
        source=found[0]
    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import analyze_p2_nikkei_complete_baseline as cb
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import build_p2_225_semantic_bundle as common
    from p2_html_core.p03_common_analysis_plan import digest

    source_sha=digest(source)
    p4=json.loads(proof4.read_text(encoding="utf-8"))
    if dataset in GROUPS:
        e=(p4.get("groups") or {}).get(dataset) or {}
        rows,tickers=e.get("row_count"),e.get("ticker_count")
        if (p4.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION"
            or e.get("csv_sha256")!=source_sha or e.get("duplicate_ids") is not False
            or not isinstance(rows,int) or rows<=0 or
            not isinstance(tickers,int) or tickers<=0):
            raise ValueError("Phase4 group source contract invalid")
    else:
        rows,tickers,expected_sha=EXCLUSIONS[dataset]
        e=p4.get("saved_exclusion") or {}
        if (p4.get("status")!="PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE"
            or p4.get("variant")!=dataset
            or e.get("csv_sha256")!=source_sha or source_sha!=expected_sha
            or e.get("row_count")!=rows or e.get("ticker_count")!=tickers
            or e.get("duplicate_ids") is not False):
            raise ValueError("Phase4 exclusion source contract invalid")
    prev=json.loads(previous.read_text(encoding="utf-8"))
    if dataset=="transportation_utilities":
        if (prev.get("status")!="PASS_PHASE26_NEW_PAIRWISE_SIX_FEATURE_HOLDOUT"
            or prev.get("dataset")!=dataset or prev.get("private_core_sha")!=CORE_SHA
            or prev.get("source_sha256")!=source_sha
            or prev.get("new_subset_pair_rows")!=CERTIFIED_TRANSPORT_ROWS
            or prev.get("old_holdout_pair_rows")!=CERTIFIED_TRANSPORT_ROWS
            or prev.get("numerical_errors")!=[]
            or prev.get("new_common_pairwise_inner_function_called") is not True):
            raise ValueError("Original already-certified six-feature pairwise proof invalid")
    else:
        if (prev.get("status")!="PASS_PHASE29_NEW_MONTHLY_WALKFORWARD_FOUR_CSV"
            or prev.get("dataset")!=dataset or prev.get("private_core_sha")!=CORE_SHA
            or prev.get("source_sha256")!=source_sha
            or prev.get("mismatches")!=[] or len(prev.get("files",{}))!=4):
            raise ValueError("Pinned Phase29 prior numerical proof invalid")

    f=common.prepare_frame(source)
    if len(f)!=rows or f["ticker"].astype(str).nunique()!=tickers:
        raise ValueError("Saved original source row/cardinality drift")
    base=cb._baseline_metrics(f)
    fields,expected=aug._rep_fields(f)
    names=list(fields)
    if len(names)!=FIELD_COUNT or len(set(names))!=FIELD_COUNT:
        raise ValueError("Canonical representative feature count/order changed")

    wanted={(names[i],names[j]) for i in range(start,min(start+4,FIELD_COUNT))
            for j in range(i+1,FIELD_COUNT)
            if not (dataset=="transportation_utilities" and i<6 and j<6)}
    if not wanted:
        raise ValueError("Unexpected empty untested pair feature shard")
    old_path=reference/"all_pairwise_combinations.csv"
    old=pd.read_csv(old_path,low_memory=False)
    if len(old)!=OLD_ALL_ROWS:
        raise ValueError("Original complete pairwise universe missing or changed")
    if any(k not in old.columns for k in KEYS) or old.duplicated(list(KEYS)).any():
        raise ValueError("Original pairwise keys invalid")
    old_subset=old.loc[
        [(a,b) in wanted for a,b in zip(old["feature1"],old["feature2"]) ]
    ].copy()
    original_feature_pairs=set(zip(old_subset["feature1"],old_subset["feature2"]))
    if wanted!=original_feature_pairs:
        raise ValueError("Saved original feature pair coverage drift")
    calculated=[]
    for a,b in sorted(wanted,key=lambda z:(names.index(z[0]),names.index(z[1]))):
        subset={a:fields[a],b:fields[b]}
        subset_exp={a:expected[a],b:expected[b]}
        singles,masks=aug._representative_singles(f,base,subset,subset_exp)
        frame,_=aug._pairwise(f,base,subset,subset_exp,singles,masks)
        if frame.empty:
            raise ValueError("New canonical pairwise inner producer returned empty shard")
        calculated.append(frame)
    fresh=pd.concat(calculated,ignore_index=True,sort=False)
    sorted_keys=list(KEYS)
    if fresh.duplicated(sorted_keys).any() or len(fresh)!=len(old_subset):
        raise ValueError("New pairwise key cardinality or duplicates mismatch")
    stage.mkdir(parents=True,exist_ok=False)
    output=stage/"new_pairwise_subset.csv"
    fresh.to_csv(output,index=False,encoding="utf-8")
    checked=pd.read_csv(output,low_memory=False)
    old_subset=old_subset.sort_values(sorted_keys).reset_index(drop=True)
    checked=checked.sort_values(sorted_keys).reset_index(drop=True)
    errors=[]
    if list(old_subset.columns)!=list(checked.columns):
        errors.append("ordered_columns")
    elif not old_subset[sorted_keys].equals(checked[sorted_keys]):
        errors.append("condition_keys")
    else:
        try:
            pd.testing.assert_frame_equal(
                old_subset,checked,check_dtype=False,check_exact=False,
                atol=1e-7,rtol=1e-10,check_index_type=False)
        except AssertionError:
            errors.append("numeric_or_label")
    if digest(source)!=source_sha:
        raise ValueError("Original source SHA changed during new pairwise calculation")
    return {
      "schema":1,
      "status":"PASS_PHASE30_NEW_PAIRWISE_NONOVERLAP_SHARD" if not errors else
               "FAIL_PHASE30_NEW_PAIRWISE_NONOVERLAP_SHARD",
      "dataset":dataset,"private_core_sha":CORE_SHA,"source_sha256":source_sha,
      "original_source_rows":rows,"original_source_tickers":tickers,
      "feature_first_start":start,"feature_first_end":min(start+4,FIELD_COUNT),
      "canonical_feature_types":FIELD_COUNT,"tested_feature_pairs":len(wanted),
      "saved_full_reference_rows":len(old),
      "new_subset_pair_rows":len(checked),
      "old_subset_pair_rows":len(old_subset),
      "original_full_pair_sha256":digest(old_path),
      "new_subset_sha256":digest(output),
      "numerical_errors":errors,
      "skipped_prior_transport_pair_rows":CERTIFIED_TRANSPORT_ROWS if dataset=="transportation_utilities" else 0,
      "previous_artifacts_recalculated":False,"certified_prior_pairwise_recomputed":False,
      "full_semantic_recalculated":False,"full_or_recalculated":False,
      "historical_signals_recomputed":False,"html_generated":False,
      "production_changed":False,"release_ready":False
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--selftest",action="store_true")
    parser.add_argument("--dataset",choices=DATASETS)
    parser.add_argument("--start",type=int,choices=SHARD_STARTS)
    for v in ("core","reference","original-source","proof4","previous","stage","report"):
        parser.add_argument("--"+v,type=Path)
    a=parser.parse_args()
    if a.selftest:
        selftest();return 0
    required=("dataset","start","core","reference","original_source",
              "proof4","previous","stage","report")
    if any(getattr(a,k) is None for k in required):
        parser.error("Immutable original source, prior proof and fresh stage required")
    if a.report.exists():
        raise FileExistsError("Do not overwrite old audit report")
    result=verify(a.core.resolve(),a.reference.resolve(),
                  a.original_source.resolve(),a.proof4.resolve(),a.previous.resolve(),
                  a.dataset,a.start,a.stage.resolve())
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ("original_full_pair_sha256","new_subset_sha256")},
                     ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
