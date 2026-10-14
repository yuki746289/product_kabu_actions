# Created: 2026-10-14 JST
"""Phase26 bounded actual new triple producer inner-function parity.

Only the FIRST FOUR canonical representative feature types are used to calculate
570 selected triple combinations. Compare those rows against the pinned saved
full tested-triple reference. No complete pair/triple/OR regeneration, no
historical artifact recalculation, and no public private-row exposure.
Phase26 pairwise PASS is reused as immutable numerical provenance.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASET="transportation_utilities"
FILENAME="tested_triple_combinations.csv"
INPUT_ROWS=14848
TICKERS=20
FIELDS=4
EXPECTED_ROWS=570
KEYS=("feature1","category1","feature2","category2","feature3","category3")


def selftest():
    assert len(SHA)==40 and FIELDS==4 and len(KEYS)==6 and EXPECTED_ROWS==570
    assert FILENAME=="tested_triple_combinations.csv"
    print("PASS_PHASE26_FOUR_FEATURE_TRIPLE_SUBSET_CONTRACT")


def verify(core,ref,proof4,proof26,stage):
    head=subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()
    if head!=SHA:
        raise ValueError("Fixed pinned original Private SHA mismatch")
    build=(core/"build").resolve()
    if stage.exists() or not stage.resolve().is_relative_to(build) or stage.resolve()==build:
        raise ValueError("Fresh isolated private build stage required")
    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import analyze_p2_nikkei_complete_baseline as cb
    import build_p2_225_semantic_bundle as common
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    from p2_html_core.p03_common_analysis_plan import digest

    source=ref/"signal_level_features.csv"
    sha=digest(source)
    p4=json.loads(proof4.read_text(encoding="utf-8"))
    group=(p4.get("groups") or {}).get(DATASET) or {}
    if (p4.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION" or
        group.get("csv_sha256")!=sha or group.get("row_count")!=INPUT_ROWS or
        group.get("ticker_count")!=TICKERS or group.get("duplicate_ids") is not False):
        raise ValueError("Original source identity proof invalid")
    prev=json.loads(proof26.read_text(encoding="utf-8"))
    if (prev.get("status")!="PASS_PHASE26_NEW_PAIRWISE_SIX_FEATURE_HOLDOUT" or
        prev.get("dataset")!=DATASET or prev.get("private_core_sha")!=SHA or
        prev.get("source_sha256")!=sha or
        prev.get("new_subset_pair_rows")!=1800 or
        prev.get("old_holdout_pair_rows")!=1800 or
        prev.get("numerical_errors")!=[] or
        prev.get("new_common_pairwise_inner_function_called") is not True):
        raise ValueError("Prior successful Phase26 pairwise numeric proof invalid")
    frame=common.prepare_frame(source)
    if len(frame)!=INPUT_ROWS or frame["ticker"].astype(str).nunique()!=TICKERS:
        raise ValueError("Common preparation changed saved original input")
    base=cb._baseline_metrics(frame)
    fields,expected=aug._rep_fields(frame)
    names=list(fields)[:FIELDS]
    if len(names)!=FIELDS or len(set(names))!=FIELDS:
        raise ValueError("Canonical six-feature holdout contract changed")
    sf={x:fields[x] for x in names}
    se={x:expected[x] for x in names}
    # EXACT new canonical semantic producer inner function, restricted by
    # input feature types only; no full pair/triple candidate computation.
    single,masks=aug._representative_singles(frame,base,sf,se)
    fresh,_=aug._triples(frame,base,single,masks)
    if len(fresh)!=EXPECTED_ROWS:
        raise ValueError(f"Unexpected four-feature triple row count: {len(fresh)} != {EXPECTED_ROWS}")
    old_path=ref/FILENAME
    old=pd.read_csv(old_path,low_memory=False)
    if len(old)!=24196:
        raise ValueError("Saved original complete triple universe is not certified")
    if any(k not in old.columns or k not in fresh.columns for k in KEYS):
        raise ValueError("Triple key columns have changed")
    holdout=old.loc[old["feature1"].isin(names)&old["feature2"].isin(names)&old["feature3"].isin(names)].copy()
    if len(holdout)!=len(fresh):
        raise ValueError("Original and new triple holdout have different row counts")
    if holdout.duplicated(list(KEYS)).any() or fresh.duplicated(list(KEYS)).any():
        raise ValueError("Duplicate triple keys")
    holdout=holdout.sort_values(list(KEYS)).reset_index(drop=True)
    fresh=fresh.sort_values(list(KEYS)).reset_index(drop=True)
    if not holdout[list(KEYS)].equals(fresh[list(KEYS)]):
        raise ValueError("Original and new pairwise condition keys disagree")
    stage.mkdir(parents=True,exist_ok=False)
    out=stage/FILENAME
    fresh.to_csv(out,index=False,encoding="utf-8")
    verified=pd.read_csv(out,low_memory=False)
    errors=[]
    if list(holdout.columns)!=list(verified.columns):
        errors.append({"kind":"ordered_header_mismatch"})
    elif holdout.shape!=verified.shape:
        errors.append({"kind":"row_shape_mismatch"})
    else:
        try:
            pd.testing.assert_frame_equal(
                holdout,verified,check_dtype=False,check_exact=False,
                atol=1e-7,rtol=1e-10,check_index_type=False)
        except AssertionError:
            errors.append({"kind":"triple_numeric_or_label_mismatch"})
    if digest(source)!=sha:
        raise ValueError("Saved source was mutated by QA")
    return {
        "schema":1,
        "status":"PASS_PHASE26_NEW_TRIPLE_FOUR_FEATURE_HOLDOUT" if not errors
                 else "FAIL_PHASE26_NEW_TRIPLE_FOUR_FEATURE_HOLDOUT",
        "dataset":DATASET,"private_core_sha":SHA,
        "source_sha256":sha,"source_rows":INPUT_ROWS,"source_tickers":TICKERS,
        "input_feature_types":FIELDS,"new_subset_triple_rows":len(fresh),
        "old_full_triple_rows":len(old),"old_holdout_triple_rows":len(holdout),
        "new_subset_columns":len(verified.columns),
        "original_full_triple_file_sha256":digest(old_path),
        "new_subset_file_sha256":digest(out),
        "numerical_errors":errors,
        "new_common_triples_inner_function_called":True,
        "full_pairwise_recalculated":False,
        "full_triple_recalculated":False,"full_or_recalculated":False,
        "previous_artifacts_recalculated":False,"p2_signals_recomputed":False,
        "html_generated":False,"production_changed":False,"release_ready":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    for name in ("core","reference","proof4","proof26","stage","report"):
        p.add_argument("--"+name,type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest();return 0
    if any(getattr(a,k) is None for k in
           ("core","reference","proof4","proof26","stage","report")):
        p.error("Pinned Private source, prior proofs and staging required")
    if a.report.exists():
        raise FileExistsError("Never overwrite existing evidence JSON")
    d=verify(a.core.resolve(),a.reference.resolve(),a.proof4.resolve(),
             a.proof26.resolve(),a.stage.resolve())
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({k:v for k,v in d.items() if k!="numerical_errors"}))
    return 0 if d["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
