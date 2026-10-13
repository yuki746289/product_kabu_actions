# Created: 2026-10-13 JST
"""Phase23: bounded NEW common OR numeric computation on five other sectors.

Calls EXACT canonical _combo_metrics used by the new common OR producer for
8 OR2 + 8 OR3 never-before-sampled conditions in EACH remaining sector.
Strictly reuses successful Phase15 source, Phase22 common semantic, and Phase4
identity certificates. No source/P2/full OR/semantic/HTML replay.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

import p2_common_phase21_new_or_bounded_20261013 as prev
import p2_common_phase22_new_semantic_five_sectors_20261013 as prior_sem
import p2_common_phase9_direct_metric_parity_20261013 as numeric

DATASETS=prior_sem.MORE_SECTORS
SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"


def selftest()->None:
    prev.selftest()
    prior_sem.selftest()
    assert len(DATASETS)==5 and prev.DATASET not in DATASETS
    assert prev.NEW_PER_FAMILY==8 and prev.SKIP_PREVIOUS==32
    print("PASS: Phase23 five fresh common OR producer holdout source/semantics gates")


def verify(dataset:str,core:Path,original:Path,
           phase4:Path,phase15:Path,phase22:Path)->dict:
    if dataset not in DATASETS:
        raise ValueError("Only previously untested five-sector common OR pilot")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=SHA:
        raise ValueError("Pinned canonical Private SHA changed")
    expected_rows,expected_tickers,_=DATASETS[dataset]
    src=original/"signal_level_features.csv"
    original_sha=numeric.hash_file(src)
    p4=json.loads(phase4.read_text(encoding="utf-8"))
    if p4.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
        raise ValueError("Saved original source population not independently certified")
    saved=(p4.get("groups") or {}).get(dataset) or {}
    if (saved.get("csv_sha256")!=original_sha or
        saved.get("row_count")!=expected_rows or
        saved.get("ticker_count")!=expected_tickers or
        saved.get("duplicate_ids") is not False):
        raise ValueError("Pinned original signal source digest/identity mismatch")
    p22=json.loads(phase22.read_text(encoding="utf-8"))
    if (p22.get("status")!="PASS_PHASE22_NEW_SECTOR_COMMON_SEMANTIC_SUBSET_PARITY" or
        p22.get("dataset")!=dataset or p22.get("source_sha256")!=original_sha or
        p22.get("csvs_independently_numeric_equal")!=4 or
        p22.get("prior_transportation_phase20_reexecuted") is not False):
        raise ValueError("Actual new common semantic subset prior gate not PASS")
    p15=json.loads(phase15.read_text(encoding="utf-8"))
    if (p15.get("status")!="PASS_PHASE15_SAVED_OR2_OR3_DIRECT_NUMERIC_SAMPLE" or
        p15.get("dataset")!=dataset or p15.get("source_sha256")!=original_sha):
        raise ValueError("Original OR independent direct comparison proof differs")
    for n,name in prev.RAW_FAMILIES:
        if p15.get(f"or{n}_reference_sha256")!=numeric.hash_file(original/name):
            raise ValueError("Raw OR saved source differs from earlier Phase15 SHA proof")
    if (json.loads((original/"semantic_status.json").read_text(encoding="utf-8"))
        .get("or_full_universe_pass") is not True):
        raise ValueError("Old OR full-universe status did not PASS")

    sys.path.insert(0,str(core/"scripts"))
    import analyze_p2_or_combinations as or_calculator
    import build_p2_225_or_bundle as common_or
    import finalize_p2_nikkei_complete_baseline as masks_mod

    frame=common_or.prepare_frame(src)
    if len(frame)!=expected_rows or frame.ticker.astype(str).nunique()!=expected_tickers:
        raise ValueError("New OR source preparation changed fixed population")
    or_calculator.OUT=original
    feature_masks=masks_mod._feature_masks(frame)
    candidates=or_calculator._component_pool(frame,feature_masks)
    lookup={(str(x["feature"]),str(x["category"])):x for x in candidates}
    if len(lookup)!=len(candidates):
        raise ValueError("Duplicate new OR component pool identifiers")
    baseline=or_calculator._baseline(frame)
    selected=prev.select_new(original)
    mismatches=[]
    checked_fields=0
    for i,(n,labels,old_row) in enumerate(selected,1):
        components=[]
        for label in labels:
            if label not in lookup:
                raise ValueError("Saved raw OR label not found in original single pool")
            components.append(lookup[label])
        result=or_calculator._combo_metrics(
            frame,"or2" if n==2 else "or3",components,baseline)
        fields=prev.compare_new_with_original(old_row,result)
        checked_fields+=len(result)-1
        mismatches.extend({"row":i,"field":f} for f in fields)
    if numeric.hash_file(src)!=original_sha:
        raise ValueError("Original input modified during bounded common OR computation")
    return {
        "schema":1,
        "status":"PASS_PHASE23_FIVE_SECTOR_NEW_OR_PRODUCER_NUMERIC_PARITY"
                 if not mismatches else "FAIL_PHASE23_FIVE_SECTOR_NEW_OR_PRODUCER_PARITY",
        "dataset":dataset,"original_private_sha":SHA,
        "original_saved_source_sha256":original_sha,
        "original_source_rows":expected_rows,"original_source_tickers":expected_tickers,
        "new_or2_conditions":prev.NEW_PER_FAMILY,
        "new_or3_conditions":prev.NEW_PER_FAMILY,
        "new_producer_numeric_fields_checked":checked_fields,
        "numeric_mismatches":len(mismatches),
        "first_issues":mismatches[:12],
        "reused_phase22_new_semantic_success":True,
        "prior_phase21_transportation_reexecuted":False,
        "prior_phase15_16_OR_conditions_reexecuted":False,
        "actual_common_or_inner_producer_executed":True,
        "full_or_bundle_generated":False,
        "full_semantic_bundle_generated":False,
        "saved_artifacts_recalculated":False,
        "signals_recomputed":False,
        "production_changed":False,"release_ready":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=sorted(DATASETS))
    p.add_argument("--core",type=Path)
    p.add_argument("--original",type=Path)
    p.add_argument("--source-proof",type=Path)
    p.add_argument("--phase15",type=Path)
    p.add_argument("--phase22",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    if a.selftest:selftest();return 0
    if any(getattr(a,x) is None for x in
           ("dataset","core","original","source_proof","phase15","phase22","report")):
        p.error("dataset/core/original/source-proof/phase15/phase22/report required")
    out=a.report.resolve()
    if out.exists():
        raise FileExistsError("Output must be fresh for new common calculation QA")
    audit=verify(a.dataset,a.core.resolve(),a.original.resolve(),
                 a.source_proof.resolve(),a.phase15.resolve(),a.phase22.resolve())
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in audit.items() if k!="first_issues"},ensure_ascii=False))
    return 0 if audit["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
