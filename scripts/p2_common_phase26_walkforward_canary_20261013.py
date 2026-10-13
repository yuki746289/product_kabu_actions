# Created: 2026-10-13 JST
"""Phase26 second canary: only NEW walkforward_results.csv from existing inner function.

Chain to certified Phase26 monthly + Phase4 original source identity evidence.
Prior successful semantic, OR, CSV or HTML artifacts are not recomputed.
Public artifact is JSON metadata only.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASET = "transportation_utilities"
ROW_COUNT = 14848
TICKERS = 20
NAME = "walkforward_results.csv"

def selftest():
    assert len(CORE_SHA) == 40
    assert NAME == "walkforward_results.csv"
    assert ROW_COUNT == 14848 and TICKERS == 20
    print("PASS_PHASE26_WALKFORWARD_ISOLATED_CONTRACT")

def verify(core, reference, phase4, monthly_cert, stage):
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip() != CORE_SHA:
        raise ValueError("Private source code is not the pinned original")
    if (stage.exists() or not stage.resolve().is_relative_to((core/"build").resolve())
        or stage.resolve() == (core/"build").resolve()):
        raise ValueError("Fresh isolated private build staging required")
    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import build_p2_225_semantic_bundle as common
    import augment_p2_nikkei_complete_daily_rci_groups as producer
    from p2_html_core.p03_common_analysis_plan import digest

    src=reference/"signal_level_features.csv"
    original_sha=digest(src)
    p4=json.loads(phase4.read_text(encoding="utf-8"))
    record=(p4.get("groups") or {}).get(DATASET) or {}
    if p4.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION" or (
        record.get("csv_sha256")!=original_sha or
        record.get("row_count")!=ROW_COUNT or
        record.get("ticker_count")!=TICKERS or
        record.get("duplicate_ids") is not False):
        raise ValueError("Prior immutable original-source identity not certified")
    monthly=json.loads(monthly_cert.read_text(encoding="utf-8"))
    if (monthly.get("status")!="PASS_PHASE26_MONTHLY_THREE_CSV_CANARY" or
        monthly.get("dataset")!=DATASET or
        monthly.get("private_core_sha")!=CORE_SHA or
        monthly.get("original_source_sha256")!=original_sha or
        monthly.get("source_rows")!=ROW_COUNT or
        monthly.get("compared_csvs")!=3 or monthly.get("mismatches") or
        not all(z.get("numerically_equal") is True for z in monthly.get("csv_details",[]))):
        raise ValueError("Previous Phase26 bounded three-file proof unavailable")

    f=common.prepare_frame(src)
    if len(f)!=ROW_COUNT or f["ticker"].astype(str).nunique()!=TICKERS:
        raise ValueError("New common source frame population changed")
    # Exactly the two inner functions called by canonical_semantic_data.build.
    fields,expected=producer._rep_fields(f)
    frame=producer._walkforward(f,fields,expected)
    if len(frame)<30 or len(frame)>100:
        raise ValueError("Bounded walkforward structure unexpectedly changed")
    original=reference/NAME
    if not original.is_file():
        raise FileNotFoundError("Pinned walkforward reference CSV missing")
    stage.mkdir(parents=True,exist_ok=False)
    new=stage/NAME
    frame.to_csv(new,index=False,encoding="utf-8")
    before=pd.read_csv(original,low_memory=False)
    after=pd.read_csv(new,low_memory=False)
    issues=[]
    if list(before.columns)!=list(after.columns) or before.shape!=after.shape:
        issues.append({"file":NAME,"kind":"ordered_schema_or_row_shape"})
    else:
        try:
            pd.testing.assert_frame_equal(before,after,check_dtype=False,
                check_exact=False,atol=1e-7,rtol=1e-10,check_index_type=False)
        except AssertionError:
            issues.append({"file":NAME,"kind":"numeric_or_label_disagreement"})
    if digest(src)!=original_sha:
        raise ValueError("Saved original source bytes changed during QA")
    return {
        "schema":1,
        "status":"PASS_PHASE26_WALKFORWARD_NEW_SEMANTIC_CANARY" if not issues else
                 "FAIL_PHASE26_WALKFORWARD_NEW_SEMANTIC_CANARY",
        "dataset":DATASET,"private_core_sha":CORE_SHA,
        "source_sha256":original_sha,"original_rows":ROW_COUNT,"original_tickers":TICKERS,
        "file":NAME,"computed_rows":len(frame),"reference_rows":len(before),
        "computed_column_count":len(after.columns),
        "saved_original_sha256":digest(original),"new_computed_sha256":digest(new),
        "numeric_parity_mismatches":issues,
        "new_common_inner_walkforward_executed":True,
        "previous_artifacts_recalculated":False,"full_semantic_generated":False,
        "or_generated":False,"signals_recomputed":False,"html_generated":False,
        "production_changed":False,"release_ready":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    for key in ("core","reference","phase4","monthly-cert","stage","report"):
        p.add_argument("--"+key,type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest();return 0
    if any(getattr(a,k) is None for k in
           ("core","reference","phase4","monthly_cert","stage","report")):
        p.error("Pinned source, proofs and isolated output stage required")
    report=a.report.resolve()
    if report.exists():
        raise FileExistsError("Never overwrite previous audit evidence")
    result=verify(a.core.resolve(),a.reference.resolve(),a.phase4.resolve(),
                  a.monthly_cert.resolve(),a.stage.resolve())
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                      encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="numeric_parity_mismatches"}))
    return 0 if result["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
