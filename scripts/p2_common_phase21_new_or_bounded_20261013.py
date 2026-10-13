# Created: 2026-10-13 JST
"""Phase21: bounded NEW common OR producer calculation and independent old parity.

This invokes the exact canonical _combo_metrics used by new shared OR producer
for 8 OR2 + 8 OR3 conditions NOT checked in successful Phase15/16 samples.
All source data remains pinned and read-only. Results are computed in-memory
and summarized as metadata ONLY; no full OR, P2, semantic or HTML rerun.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import p2_common_phase15_or2_or3_saved_sample_20261013 as prior
import p2_common_phase9_direct_metric_parity_20261013 as numeric

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASET="transportation_utilities"
ROWS=14848
TICKERS=20
SKIP_PREVIOUS=32
NEW_PER_FAMILY=8
EXPECTED_TOTAL=2*NEW_PER_FAMILY
RAW_FAMILIES=((2,"or_pairwise_all.csv"),(3,"or_triple_all.csv"))


def select_new(original:Path)->list:
    selected=[]
    allowed=set(prior.FEATURES)
    for n,name in RAW_FAMILIES:
        with (original/name).open(newline="",encoding="utf-8-sig") as input_file:
            reader=csv.DictReader(input_file)
            required={"condition_key","condition_type","mask_hash","count"}
            required|={f"{kind}{i}" for i in range(1,n+1)
                      for kind in ("feature","category")}
            if not required.issubset(reader.fieldnames or ()):
                raise ValueError("Old OR rows missing baseline selection columns")
            eligible=[]
            seen=set()
            for old in reader:
                labels=tuple((old[f"feature{i}"],old[f"category{i}"])
                             for i in range(1,n+1))
                if any(feature not in allowed or not category for feature,category in labels):
                    continue
                if labels in seen:
                    raise ValueError("Duplicate original feature/category OR labels")
                seen.add(labels)
                eligible.append((n,labels,old))
        eligible.sort(key=lambda x:hashlib.sha256(
            json.dumps([n,x[1]],separators=(",",":")).encode()).hexdigest())
        if len(eligible)<SKIP_PREVIOUS+NEW_PER_FAMILY:
            raise ValueError("Insufficient new OR reference rows after previously successful audits")
        selected+=eligible[SKIP_PREVIOUS:SKIP_PREVIOUS+NEW_PER_FAMILY]
    if len(selected)!=EXPECTED_TOTAL:
        raise ValueError("Invalid bounded OR new sample shape")
    return selected


def compare_new_with_original(old:dict, generated:dict)->list[str]:
    import numpy as np
    problems=[]
    for column,value in generated.items():
        if column=="_mask":
            continue
        if column not in old:
            problems.append(column+":missing_original_column")
            continue
        expected=old[column]
        if isinstance(value,(bool,np.bool_)):
            ok=str(value).lower()==str(expected).lower()
        elif isinstance(value,(float,int,np.floating,np.integer)):
            try:
                old_num=float(expected)
                new_num=float(value)
                ok=(math.isnan(old_num) and math.isnan(new_num)) or (
                    math.isfinite(old_num) and math.isfinite(new_num) and
                    math.isclose(old_num,new_num,abs_tol=1e-7,rel_tol=1e-10))
            except (TypeError,ValueError):
                ok=False
        else:
            ok=str(value)==str(expected)
        if not ok:
            problems.append(column+":numeric_or_identity_mismatch")
    return problems


def verify(core:Path,original:Path,source_proof:Path,
           phase15_proof:Path,phase20_proof:Path)->dict:
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=CORE_SHA:
        raise ValueError("Private source commit SHA changed")
    src=original/"signal_level_features.csv"
    source_sha=numeric.hash_file(src)
    p4=json.loads(source_proof.read_text(encoding="utf-8"))
    if p4.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
        raise ValueError("Original phase4 independent source identities not certified")
    gp=(p4.get("groups") or {}).get(DATASET) or {}
    if (gp.get("csv_sha256")!=source_sha or gp.get("row_count")!=ROWS or
        gp.get("ticker_count")!=TICKERS or gp.get("duplicate_ids") is not False):
        raise ValueError("Source original SHA, rows, tickers differ")
    p20=json.loads(phase20_proof.read_text(encoding="utf-8"))
    if (p20.get("status")!="PASS_PHASE20_NEW_COMMON_SEMANTIC_SUBSET_NUMERIC_PARITY" or
        p20.get("dataset")!=DATASET or p20.get("source_sha256")!=source_sha or
        p20.get("csvs_independently_numeric_equal")!=4):
        raise ValueError("New common semantic subset checkpoint not PASS")
    p15=json.loads(phase15_proof.read_text(encoding="utf-8"))
    if (p15.get("status")!="PASS_PHASE15_SAVED_OR2_OR3_DIRECT_NUMERIC_SAMPLE" or
        p15.get("dataset")!=DATASET or p15.get("source_sha256")!=source_sha):
        raise ValueError("Original OR SHA/independent direct numeric proof mismatch")
    for n,name in RAW_FAMILIES:
        key=f"or{n}_reference_sha256"
        if p15.get(key)!=numeric.hash_file(original/name):
            raise ValueError("Original saved raw OR reference bytes differ from Phase15")

    sys.path.insert(0,str(core/"scripts"))
    import analyze_p2_or_combinations as canonical_or
    import build_p2_225_or_bundle as new_common_or
    import finalize_p2_nikkei_complete_baseline as fin

    frame=new_common_or.prepare_frame(src)
    if len(frame)!=ROWS or frame.ticker.astype(str).nunique()!=TICKERS:
        raise ValueError("New OR input preprocessing changed original population")
    canonical_or.OUT=original
    masks=fin._feature_masks(frame)
    component_pool=canonical_or._component_pool(frame,masks)
    lookup={(str(c["feature"]),str(c["category"])):c for c in component_pool}
    if len(lookup)!=len(component_pool):
        raise ValueError("New OR producer candidate pool has duplicate identifiers")
    baseline=canonical_or._baseline(frame)
    selected=select_new(original)
    errors=[]
    compared=0
    for index,(n,labels,old) in enumerate(selected,1):
        try:
            components=[lookup[label] for label in labels]
        except KeyError:
            raise ValueError("Saved reference OR components not found in new producer pool")
        record=canonical_or._combo_metrics(frame,
                                           "or2" if n==2 else "or3",
                                           components,baseline)
        failures=compare_new_with_original(old,record)
        compared+=len(record)-1
        for item in failures:
            errors.append({"row":index,"field":item})
    if numeric.hash_file(src)!=source_sha:
        raise ValueError("Original private signal features mutated")
    return {
        "schema":1,
        "status":"PASS_PHASE21_BOUNDED_NEW_OR_PRODUCER_NUMERIC_PARITY_ONLY"
                 if not errors else "FAIL_PHASE21_BOUNDED_NEW_OR_PRODUCER_NUMERIC_PARITY",
        "dataset":DATASET,"pinned_private_core_sha":CORE_SHA,
        "saved_source_sha256":source_sha,
        "producer":"build_p2_225_or_bundle.prepare_frame + analyze_p2_or_combinations._combo_metrics",
        "new_or2_conditions":NEW_PER_FAMILY,"new_or3_conditions":NEW_PER_FAMILY,
        "previous_phase15_16_sample_conditions_reexecuted":False,
        "producer_numeric_identity_fields_checked":compared,
        "mismatched_fields":len(errors),
        "first_errors":errors[:12],
        "actual_common_or_inner_producer_executed":True,
        "full_or_bundle_generated":False,
        "full_semantic_bundle_generated":False,
        "historical_artifacts_recomputed":False,
        "p2_signals_recomputed":False,
        "html_generated":False,
        "release_ready":False,"production_changed":False,
    }


def selftest():
    assert SKIP_PREVIOUS==8+24
    assert NEW_PER_FAMILY==8
    assert EXPECTED_TOTAL==16
    assert "transportation_utilities" in prior.SHAPES
    assert prior.SHAPES[DATASET]==(ROWS,TICKERS)
    print("PASS Phase21 bounded new OR producer disjoint holdout source identity gates")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--core",type=Path)
    p.add_argument("--original",type=Path)
    p.add_argument("--source-proof",type=Path)
    p.add_argument("--phase15",type=Path)
    p.add_argument("--phase20",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest();return 0
    if any(getattr(a,x) is None for x in
           ("core","original","source_proof","phase15","phase20","report")):
        p.error("core, original, source-proof, phase15, phase20 and report required")
    out=a.report.resolve()
    if out.exists():
        raise FileExistsError("Never overwrite previous audit evidence")
    data=verify(a.core.resolve(),a.original.resolve(),a.source_proof.resolve(),
                a.phase15.resolve(),a.phase20.resolve())
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k!="first_errors"},ensure_ascii=False))
    return 0 if data["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
