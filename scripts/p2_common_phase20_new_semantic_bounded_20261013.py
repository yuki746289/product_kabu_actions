# Created: 2026-10-13 JST
"""Phase20: bounded actual common semantic computation vs immutable saved CSVs.

Uses the EXACT inner functions called by the new common semantic producer.
Only single/representative/candidate/plateau stages are calculated, in RAM
and a new isolated build directory. Never runs the old successful Actions,
feature extraction, Production P2, full semantic, OR or HTML generators.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

SOURCE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASET="transportation_utilities"
EXPECTED_SOURCE_ROWS=14848
EXPECTED_TICKERS=20
EXPECTED={
    "all_single_categories.csv":2460,
    "representative_single_categories.csv":151,
    "candidate_registry.csv":64,
    "parameter_plateau.csv":97,
}

def check_producer(core:Path, proof:Path, source:Path, original:Path)->dict:
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=SOURCE_SHA:
        raise ValueError("Private source SHA not pinned")
    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import analyze_p2_nikkei_complete_baseline as cb
    import build_p2_225_semantic_bundle as common
    import build_p2_225_canonical_semantic_data as canonical
    import augment_p2_nikkei_complete_daily_rci_groups as augmented
    import finalize_p2_nikkei_complete_baseline as final
    from p2_html_core.p03_common_analysis_plan import PinnedSavedInput,source_preflight,digest

    trusted=json.loads(proof.read_text(encoding="utf-8"))
    if trusted.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
        raise ValueError("Previous independent source identity did not pass")
    record=(trusted.get("groups") or {}).get(DATASET) or {}
    original_hash=digest(source)
    if record.get("csv_sha256")!=original_hash or \
       record.get("row_count")!=EXPECTED_SOURCE_ROWS or \
       record.get("ticker_count")!=EXPECTED_TICKERS or \
       record.get("duplicate_ids") is not False:
        raise ValueError("Original signal SHA and saved population cannot be certified")
    source_preflight(DATASET,PinnedSavedInput(source,original_hash,
                                            EXPECTED_SOURCE_ROWS,EXPECTED_TICKERS))
    prev=json.loads((original/"semantic_status.json").read_text(encoding="utf-8"))
    if (prev.get("overall_pass") is not True or
        prev.get("or_full_universe_pass") is not True or
        prev.get("source_rows")!=EXPECTED_SOURCE_ROWS or
        prev.get("source_tickers")!=EXPECTED_TICKERS):
        raise ValueError("Prior saved semantic/OR status not certified")
    prepared=common.prepare_frame(source)
    if len(prepared)!=EXPECTED_SOURCE_ROWS or \
            prepared["ticker"].astype(str).nunique()!=EXPECTED_TICKERS:
        raise ValueError("New common preprocessing modified saved input population")
    base=cb._baseline_metrics(prepared)
    all_single=canonical._full_single_categories(prepared,base)
    fields, expected_categories=augmented._rep_fields(prepared)
    representatives,_masks=augmented._representative_singles(
        prepared,base,fields,expected_categories)
    candidates=representatives.loc[final._truthy(representatives["candidate"])].copy()
    candidates["condition_type"]="single"
    candidates["small_sample"]=candidates["count"]<30
    candidates["condition_id"]=(
        "S:"+candidates["feature"].astype(str)+"="+
        candidates["category"].astype(str))
    plateau=canonical._parameter_plateau(all_single,representatives)

    new_frames={
        "all_single_categories.csv":all_single,
        "representative_single_categories.csv":representatives,
        "candidate_registry.csv":candidates,
        "parameter_plateau.csv":plateau,
    }
    if {name:len(df) for name,df in new_frames.items()}!=EXPECTED:
        raise ValueError("New semantic rows deviate from already published exact counts")
    if digest(source)!=original_hash:
        raise ValueError("Saved source bytes changed during new computations")
    return {"new_frames":new_frames,"source_sha256":original_hash,
            "source_rows":len(prepared),"source_tickers":EXPECTED_TICKERS,
            "pd":pd,"digest":digest}

def compare_outputs(core:Path,original:Path,proof:Path,
                    staging:Path)->dict:
    if staging.exists():
        raise FileExistsError("Never overwrite an old stage or successful artifact")
    if staging==core or not staging.resolve().is_relative_to((core/"build").resolve()):
        raise ValueError("Phase20 staging must be inside fresh Private core/build")
    source=original/"signal_level_features.csv"
    tested=check_producer(core,proof,source,original)
    pd=tested["pd"]
    errors=[]
    checked={}
    staging.mkdir(parents=True,exist_ok=False)
    for filename,new_frame in tested["new_frames"].items():
        old=original/filename
        if not old.is_file():
            raise FileNotFoundError("Saved reference does not exist: "+filename)
        new=staging/filename
        new_frame.to_csv(new,index=False,encoding="utf-8")
        original_columns=list(pd.read_csv(old,nrows=0).columns)
        new_columns=list(pd.read_csv(new,nrows=0).columns)
        if original_columns!=new_columns:
            errors.append({"file":filename,"kind":"ordered_header_mismatch",
                           "reference_columns":len(original_columns),
                           "new_columns":len(new_columns)})
            continue
        left=pd.read_csv(old,low_memory=False)
        right=pd.read_csv(new,low_memory=False)
        if left.shape!=right.shape:
            errors.append({"file":filename,"kind":"shape_mismatch",
                           "reference_rows":len(left),"new_rows":len(right)})
            continue
        try:
            pd.testing.assert_frame_equal(left,right,check_dtype=False,
                                          check_exact=False,
                                          atol=1e-7,rtol=1e-10,
                                          check_index_type=False)
        except AssertionError:
            # Don't expose private rows on the public audit artifact.
            error_count=0
            first=None
            for column in original_columns:
                a,b=left[column],right[column]
                if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                    import numpy as np
                    aa=pd.to_numeric(a,errors="coerce").to_numpy(float)
                    bb=pd.to_numeric(b,errors="coerce").to_numpy(float)
                    mismatch=~np.isclose(aa,bb,atol=1e-7,rtol=1e-10,equal_nan=True)
                    differences=int(mismatch.sum())
                else:
                    mismatch=~(a.fillna("<NULL>").astype(str)
                               .eq(b.fillna("<NULL>").astype(str)))
                    differences=int(mismatch.sum())
                if differences and first is None:
                    first=column
                error_count+=differences
            errors.append({"file":filename,"kind":"data_mismatch",
                           "different_cells":error_count,
                           "first_differing_column":first})
        checked[filename]={
            "rows":len(left),"columns":len(original_columns),
            "old_sha256":tested["digest"](old),
            "new_sha256":tested["digest"](new),
            "exact_bytes":tested["digest"](old)==tested["digest"](new)
        }
    if tested["digest"](source)!=tested["source_sha256"]:
        raise ValueError("Existing saved original source modified")
    return {
        "schema":1,
        "status":"PASS_PHASE20_NEW_COMMON_SEMANTIC_SUBSET_NUMERIC_PARITY"
                 if not errors and len(checked)==len(EXPECTED)
                 else "FAIL_PHASE20_NEW_COMMON_SEMANTIC_SUBSET_NUMERIC_PARITY",
        "dataset":DATASET,
        "private_code_and_data_sha":SOURCE_SHA,
        "source_sha256":tested["source_sha256"],
        "source_rows":tested["source_rows"],
        "source_tickers":tested["source_tickers"],
        "bounded_new_common_producer_functions_executed":True,
        "previous_successful_artifacts_reexecuted":False,
        "csvs_independently_numeric_equal":len(checked)-len([e for e in errors if e["file"] in checked]),
        "expected_csvs":len(EXPECTED),
        "per_file":checked,
        "mismatches":errors[:12],
        "full_semantic_recomputed":False,
        "or_recomputed":False,
        "p2_signals_recomputed":False,
        "html_generated":False,
        "release_ready":False,
        "production_changed":False,
    }

def selftest()->None:
    assert len(EXPECTED)==4
    assert set(EXPECTED)=={"all_single_categories.csv",
                          "representative_single_categories.csv",
                          "candidate_registry.csv","parameter_plateau.csv"}
    assert SOURCE_SHA=="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
    assert EXPECTED_SOURCE_ROWS==14848 and EXPECTED_TICKERS==20
    print("PASS: new common bounded semantic subset QA scope and reference guards")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--core",type=Path)
    p.add_argument("--reference",type=Path)
    p.add_argument("--proof",type=Path)
    p.add_argument("--staging",type=Path)
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    if args.selftest:
        selftest();return 0
    if not all((args.core,args.reference,args.proof,args.staging,args.report)):
        p.error("--core --reference --proof --staging --report required")
    target=args.report.resolve()
    if target.exists():
        raise FileExistsError("Don't overwrite an earlier audit result")
    report=compare_outputs(args.core.resolve(),args.reference.resolve(),
                           args.proof.resolve(),args.staging.resolve())
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                      encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("per_file","mismatches")},
                     ensure_ascii=False))
    return 0 if report["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
