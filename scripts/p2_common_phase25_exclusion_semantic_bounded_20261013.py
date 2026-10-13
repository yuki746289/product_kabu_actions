# Created: 2026-10-13 JST
"""Phase25: bounded actual NEW common semantic calculation for two exclusions.

Only 4 canonical semantic CSV outputs (all-single, representative-single,
candidate registry, parameter plateau) are computed using the EXACT existing
new shared semantic producer inner functions. Original feature artifacts and
legacy CSVs stay read-only. No Production P2, no full semantic/OR, no HTML.
The smaller double exclusion must PASS before the larger single exclusion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
CONFIG={
 "exclude_capital_goods_transportation_utilities":(
     137426,170,64,
     "cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"
 ),
 "exclude_transportation_utilities":(
     166470,205,55,
     "d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"
 ),
}
FILENAME_ROWS={
 "all_single_categories.csv":2460,
 "representative_single_categories.csv":151,
 "candidate_registry.csv":None,
 "parameter_plateau.csv":97,
}


def only_one(path:Path,filename:str)->Path:
    items=list(path.rglob(filename))
    if len(items)!=1 or not items[0].is_file():
        raise ValueError("Expected exactly one fixed original saved source")
    return items[0]


def selftest()->None:
    assert len(CONFIG)==2
    assert set(FILENAME_ROWS)=={
        "all_single_categories.csv","representative_single_categories.csv",
        "candidate_registry.csv","parameter_plateau.csv"}
    assert FILENAME_ROWS["all_single_categories.csv"]==2460
    for name,(rows,tickers,candidate,sha) in CONFIG.items():
        assert name.startswith("exclude_")
        assert rows>100000 and 0<tickers<225 and candidate in (55,64)
        assert len(sha)==64
    print("PASS: bounded new exclusion common semantic source and 4-file contract")


def verify(dataset:str,core:Path,source_dir:Path,reference:Path,
           p4_file:Path,p12_file:Path,p24_file:Path,stage:Path)->dict:
    if dataset not in CONFIG:
        raise ValueError("Unapproved source group")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=SHA:
        raise ValueError("Pinned original Private source SHA mismatch")
    rows,tickers,candidates,expected_sha=CONFIG[dataset]
    source=only_one(source_dir,"features.csv")
    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import numpy as np
    import analyze_p2_nikkei_complete_baseline as cb
    import build_p2_225_semantic_bundle as common
    import build_p2_225_canonical_semantic_data as producer
    import augment_p2_nikkei_complete_daily_rci_groups as aug
    import finalize_p2_nikkei_complete_baseline as fin
    from p2_html_core.p03_common_analysis_plan import (
        PinnedSavedInput,source_preflight,digest,
    )
    source_sha=digest(source)
    if source_sha!=expected_sha:
        raise ValueError("Saved original exclusion source hash mismatches prior artifact")
    p4=json.loads(p4_file.read_text(encoding="utf-8"))
    if p4.get("status")!="PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE" or p4.get("variant")!=dataset:
        raise ValueError("Phase4 independent saved source identities not certified")
    old=p4.get("saved_exclusion") or {}
    if (old.get("csv_sha256")!=source_sha or old.get("row_count")!=rows or
        old.get("ticker_count")!=tickers or old.get("duplicate_ids") is not False):
        raise ValueError("Saved source population or hash differs from Phase4 proof")
    p12=json.loads(p12_file.read_text(encoding="utf-8"))
    if (p12.get("status")!="PASS_PHASE12_EXCLUSION_DIRECT_NUMERIC_PARITY_ONLY" or
        p12.get("dataset")!=dataset or p12.get("pinned_source_sha256")!=source_sha or
        p12.get("numeric_mismatches")!=0):
        raise ValueError("Phase12 independent original numerical proof missing")
    p24=json.loads(p24_file.read_text(encoding="utf-8"))
    if (p24.get("status")!="PASS_PHASE24_EXCLUSION_BOUNDED_NEW_OR_PRODUCER" or
        p24.get("dataset")!=dataset or p24.get("source_sha256")!=source_sha or
        p24.get("numeric_mismatches")!=0):
        raise ValueError("Recent Phase24 actual new OR inner producer evidence missing")
    saved_status=json.loads((reference/"semantic_status.json").read_text(encoding="utf-8"))
    if (saved_status.get("overall_pass") is not True or
        saved_status.get("or_full_universe_pass") is not True or
        saved_status.get("source_rows")!=rows or
        saved_status.get("source_tickers")!=tickers or
        saved_status.get("candidate_single_rows")!=candidates):
        raise ValueError("Saved reference status counters are not certified")

    source_preflight(dataset,PinnedSavedInput(source,source_sha,rows,tickers))
    if stage.exists() or not stage.resolve().is_relative_to((core/"build").resolve()):
        raise ValueError("Fresh isolated core/build staging required")
    frame=common.prepare_frame(source)
    if len(frame)!=rows or frame["ticker"].astype(str).nunique()!=tickers:
        raise ValueError("Common semantic prepare changed original source identity")
    baseline=cb._baseline_metrics(frame)
    all_single=producer._full_single_categories(frame,baseline)
    field,expected=aug._rep_fields(frame)
    representative,_=aug._representative_singles(frame,baseline,field,expected)
    candidate=representative.loc[fin._truthy(representative["candidate"])].copy()
    candidate["condition_type"]="single"
    candidate["small_sample"]=candidate["count"]<30
    candidate["condition_id"]=(
        "S:"+candidate["feature"].astype(str)+"="+candidate["category"].astype(str))
    plateau=producer._parameter_plateau(all_single,representative)
    new={
        "all_single_categories.csv":all_single,
        "representative_single_categories.csv":representative,
        "candidate_registry.csv":candidate,
        "parameter_plateau.csv":plateau,
    }
    expected_rows={**FILENAME_ROWS,"candidate_registry.csv":candidates}
    if {name:len(value) for name,value in new.items()}!=expected_rows:
        raise ValueError("New semantic source calculated unexpected row shapes")
    stage.mkdir(parents=True,exist_ok=False)
    checked=[]
    problems=[]
    for name,table in new.items():
        original=reference/name
        if not original.is_file():
            raise FileNotFoundError("Original semantic reference missing: "+name)
        generated=stage/name
        table.to_csv(generated,index=False,encoding="utf-8")
        approved=pd.read_csv(original,low_memory=False)
        actual=pd.read_csv(generated,low_memory=False)
        if list(actual.columns)!=list(approved.columns) or actual.shape!=approved.shape:
            problems.append({"file":name,"cause":"saved_header_or_shape_mismatch"})
            continue
        try:
            pd.testing.assert_frame_equal(
                approved,actual,check_dtype=False,check_exact=False,
                atol=1e-7,rtol=1e-10,check_index_type=False,
            )
        except AssertionError:
            # No private row values or feature/condition text in public logs.
            count=0
            for column in approved:
                a,b=approved[column],actual[column]
                if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                    a=pd.to_numeric(a,errors="coerce").to_numpy(float)
                    b=pd.to_numeric(b,errors="coerce").to_numpy(float)
                    count+=int((~np.isclose(a,b,atol=1e-7,rtol=1e-10,equal_nan=True)).sum())
                else:
                    count+=int((~approved[column].fillna("<NULL>").astype(str)
                                .eq(actual[column].fillna("<NULL>").astype(str))).sum())
            problems.append({"file":name,"cause":"numeric_parity_mismatch","cells":count})
        checked.append({
            "file":name,"rows":len(approved),
            "columns":len(approved.columns),
            "approved_original_sha256":digest(original),
            "new_computed_sha256":digest(generated),
        })
    if digest(source)!=source_sha:
        raise ValueError("Saved original features mutated while testing new common functions")
    return {
        "schema":1,
        "status":"PASS_PHASE25_EXCLUSION_NEW_SEMANTIC_4_CSV_NUMERIC_ONLY"
                 if not problems and len(checked)==4
                 else "FAIL_PHASE25_EXCLUSION_NEW_SEMANTIC_4_CSV_NUMERIC",
        "dataset":dataset,"private_core_sha":SHA,"source_sha256":source_sha,
        "original_source_rows":rows,"original_source_tickers":tickers,
        "computed_subset_files":len(new),"independently_compared_files":len(checked),
        "csv_details":checked,
        "numerical_mismatches":problems[:8],
        "actual_new_common_semantic_inner_functions_executed":True,
        "full_semantic_bundle_generated":False,"full_or_bundle_generated":False,
        "prior_successful_artifacts_regenerated":False,
        "signals_recomputed":False,"production_changed":False,
        "release_ready":False,
    }


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=sorted(CONFIG))
    p.add_argument("--core",type=Path)
    p.add_argument("--original-source-root",type=Path)
    p.add_argument("--reference",type=Path)
    p.add_argument("--phase4",type=Path)
    p.add_argument("--phase12",type=Path)
    p.add_argument("--phase24",type=Path)
    p.add_argument("--stage",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    if a.selftest:selftest();return 0
    if any(getattr(a,k) is None for k in
           ("dataset","core","original_source_root","reference","phase4",
            "phase12","phase24","stage","report")):
        p.error("dataset/core/saved_source/reference/phase4/phase12/phase24/stage/report required")
    out=a.report.resolve()
    if out.exists():
        raise FileExistsError("Do not overwrite old audit result")
    data=verify(a.dataset,a.core.resolve(),a.original_source_root.resolve(),
                a.reference.resolve(),a.phase4.resolve(),a.phase12.resolve(),
                a.phase24.resolve(),a.stage.resolve())
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k not in ("csv_details","numerical_mismatches")},
                     ensure_ascii=False))
    return 0 if data["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
