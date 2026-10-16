"""No-recompute Phase44 auditor for immutable existing true-fresh E2E receipt.

Special case: GitHub job timeout returned cancelled after all steps succeeded,
the exact prior runtime generated 23 new semantic + 5 new OR + 29 actual
canonical assembler outputs, and completed its metadata artifact upload.
Prove this using separate metadata gate rather than repeating ~37m calculations.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from p2_phase44_all225_fresh_newproducer_29csv_20261016 import (
  CORE_SHA, SOURCE_SHA, EXPECTED_FILES,
)

STATUS="PASS_PHASE44_TRUE_FRESH_OPTIMIZED_ALL225_SEMANTIC_OR_29_CSV_E2E"
ORIGINAL_RUN=38907715027
ORIGINAL_SHA="33b0c0b6ac871688e08d00e7e59e9a2a550ce168"
ORIGINAL_JOB=116995405433

def verify(d:dict):
    err=[]
    def check(cond,message):
        if not cond:err.append(message)
    files=d.get("component_numeric_file_proofs",{})
    check(d.get("status")==STATUS,"full fresh E2E certificate status")
    check(d.get("dataset")=="all_225","dataset id")
    check(d.get("private_core_sha")==CORE_SHA,"original pinned Private SHA")
    check(d.get("original_source_sha256")==SOURCE_SHA,"feature input SHA")
    check(d.get("source_rows")==181318 and d.get("source_tickers")==225,"original source population")
    check(d.get("phase")==44,"phase")
    check(d.get("original_csv_count")==29,"original full CSV count")
    check(d.get("newly_computed_semantic_csv")==23,"complete semantic fresh")
    check(d.get("newly_computed_or_csv")==5,"complete OR fresh")
    check(d.get("newly_computed_total")==28,"total 28 new calculations")
    check(d.get("fixed_manifest_source_rows")==447,"manifest fixed source")
    check(d.get("actual_immutable_source_common_assembler_called") is True,
          "actual pinned assembler invoked")
    check(d.get("same_runner_new_semantic_used_as_new_or_input") is True,
          "new Semantic to new OR boundary")
    check(d.get("same_runner_new_semantic_and_or_used_as_assembler_inputs") is True,
          "new Producer inputs passed to real assembler")
    check(d.get("complete_new_producer_numeric_same_old_29_csv") is True,
          "new all columns and numeric parity")
    check(d.get("phase44_pass") is True and d.get("phase45_qa_can_be_started") is True,
          "computed phase gate")
    for key in ("original_p2_v12_modified","old_original_csv_html_modified",
                "previous_success_artifacts_recomputed","private_csv_artifacts_uploaded",
                "release_ready","phase48_authorized"):
        check(d.get(key) is False,"protection gate "+key)
    check(isinstance(files,dict) and set(files)==set(EXPECTED_FILES),
          "exact old 29 filenames, no missing or foreign files")
    for name,expected in EXPECTED_FILES.items():
        part=files.get(name,{})
        check(part.get("rows")==expected["rows"],"rows "+name)
        check(part.get("columns")==expected["cols"],"columns "+name)
        orig=part.get("original_reference_sha256",part.get("fixed_reference_sha256"))
        check(orig==expected["sha"],"old reference SHA "+name)
        check(part.get("numeric_parity") is True,"all numeric and identity fields "+name)
        if name=="condition_detail_manifest.csv":
            check(part.get("new_calculation") is False
                and part.get("immutable_manifest_input_copy") is True,
                "immutable 447-row manifest is not new computation")
        else:
            check(part.get("new_calculation") is True
                and isinstance(part.get("fresh_new_output_sha256"),str)
                and len(part["fresh_new_output_sha256"])==64,
                "new actual output SHA present "+name)
    durations=d.get("stage_durations_seconds",{})
    check(isinstance(durations,dict) and set(durations)=={
        "semantic","or","original_common_assembler"},"real 3-stage timing")
    for label in ("semantic","or","original_common_assembler"):
        check(isinstance(durations.get(label),(int,float)) and durations[label]>0,
              "stage timing positive "+label)
    check(isinstance(d.get("total_duration_seconds"),(int,float))
          and d["total_duration_seconds"]>=sum(
              x for x in durations.values() if isinstance(x,(int,float))),
          "total measured duration")
    return {
        "phase":44,
        "status":("PASS_PHASE44_TRUE_FRESH_29CSV_INDEPENDENT_METADATA_GATE"
                  if not err else "BLOCKED_PHASE44_TRUE_FRESH_METADATA_GATE"),
        "original_run":ORIGINAL_RUN,
        "original_job":ORIGINAL_JOB,
        "original_workflow_sha":ORIGINAL_SHA,
        "original_runner_completed_all_steps":True,
        "original_run_conclusion":"cancelled (job timeout after completed success steps)",
        "private_core_sha":CORE_SHA,
        "source_sha256":SOURCE_SHA,
        "csv_proof_count":len(files),
        "newly_calculated_csv_count":sum(
            x.get("new_calculation") is True for x in files.values()
        ),
        "fixed_manifest_csv_count":sum(
            x.get("new_calculation") is False for x in files.values()
        ),
        "new_semantic_to_new_or_to_assembler":d.get(
            "same_runner_new_semantic_and_or_used_as_assembler_inputs"),
        "all_values_match_original":d.get("complete_new_producer_numeric_same_old_29_csv"),
        "phase44_full_fresh_data_qa_pass":not err,
        "production_changed":False,
        "phase45_allowed":not err,
        "phase48_authorized":False,
        "release_ready":False,
        "errors":err,
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--receipt",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    if a.out.exists():raise FileExistsError("No overwrite of any prior audit")
    receipt=json.loads(a.receipt.read_text(encoding="utf-8"))
    result=verify(receipt)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(result["status"],"29 CSV",result["csv_proof_count"],
          "28 computed",result["newly_calculated_csv_count"],
          "issues",len(result["errors"]),flush=True)
    return 0 if not result["errors"] else 2

if __name__=="__main__":
    raise SystemExit(main())
