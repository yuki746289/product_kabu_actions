"""Run true freshly computed all225 Semantic23 -> OR5 -> common assemble29.

Each stage runs as a separate sub-process in the SAME isolated job workspace:
private inputs/intermediate CSV never transit through public GitHub artifacts,
caches, commits or logs. Pinned original canonical Private code functions are
executed with numeric-equivalent optimized caching. Disjoint stage checkpoints
remain available only within the current runner until final independent QA,
then are deleted. Historical successful original artifacts are READ-ONLY.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

import p2_phase44_all225_fresh_newproducer_29csv_20261016 as ct

SCRIPT_SEMANTIC="p2_phase44_fresh_all225_semantic_optimized_20261016.py"
SCRIPT_OR="p2_phase44_fresh_all225_or_optimized_20261016.py"

def run(core:Path,source:Path,reference:Path,runner_scripts:Path):
    import pandas as pd
    from p2_phase44_optimized_family_20261016 import check_dataframe
    from p2_phase44_fresh_all225_semantic_optimized_20261016 import align
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=ct.CORE_SHA:
        raise ValueError("Pinned original Private SHA differs")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Pinned Private workflow policy missing")
    if subprocess.check_output(
        ["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],
        text=True).strip():
        raise ValueError("Private GitHub workflows forbidden")
    src=ct.inspect_source(source)
    ref=ct.validate_old_reference(reference)
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p03_common_analysis_plan import SEMANTIC_CSVS,OR_CSVS,MANIFEST
    from p2_html_core.p02_semantic_io_contract import CSV_FILES
    from assemble_p2_common_dataset_csv import assemble
    if set(CSV_FILES)!=set(ct.EXPECTED_FILES) or len(SEMANTIC_CSVS)!=23 or len(OR_CSVS)!=5:
        raise ValueError("Private source CSV contract changed")
    stage=(core/"build"/"phase44_true_fresh_optimized_full_pipeline").resolve()
    if stage.exists() or not stage.is_relative_to((core/"build").resolve()):
        raise FileExistsError("Full new end-to-end execution requires a unique fresh stage")
    s1=stage/"01_semantic"
    s2=stage/"02_or"
    s3=stage/"03_assembled"
    start=time.perf_counter()
    steps={}
    cert={}
    stage.mkdir(parents=True,exist_ok=False)
    try:
        for name,script,args in (
            ("semantic",SCRIPT_SEMANTIC,[
                "--core",str(core),"--source",str(source),
                "--reference",str(reference),"--output",str(s1)]),
            ("or",SCRIPT_OR,[
                "--core",str(core),"--source",str(source),
                "--reference",str(reference),"--semantic",str(s1),
                "--output",str(s2)]),
        ):
            print("BEGIN_NEW_FRESH_CANONICAL_PHASE44_STAGE",name,flush=True)
            t=time.perf_counter()
            subprocess.run(
                [sys.executable,str(runner_scripts/script)]+args,
                cwd=str(runner_scripts.parent),check=True,
            )
            steps[name]=round(time.perf_counter()-t,3)
            print("PASS_NEW_FRESH_CANONICAL_PHASE44_STAGE",name,steps[name],flush=True)
        sem=json.loads((s1/"semantic_status.json").read_text(encoding="utf-8"))
        or_status=json.loads((s2/"or_status.json").read_text(encoding="utf-8"))
        if (sem.get("overall_pass") is not True or or_status.get("overall_pass") is not True
            or sem.get("newly_computed_semantic_csv_count")!=23
            or or_status.get("newly_calculated_or_csv_count")!=5
            or sem.get("newly_computed_not_old_checkpoint_copy") is not True
            or or_status.get("newly_computed_from_new_semantic_csv_input") is not True
            or or_status.get("semantic_single_sha256")!=
                sem["output_csv_sha256"].get("advantage_single_candidates.csv")
            or sem.get("source_sha256")!=ct.SOURCE_SHA
            or or_status.get("source_sha256")!=ct.SOURCE_SHA):
            raise ValueError("Full new semantic->OR producer chain provenance invalid")
        t=time.perf_counter()
        assembled=assemble(
            "all_225",s1,s2,reference/MANIFEST,s3,reference,
            expected_source_sha256=ct.SOURCE_SHA,
            expected_manifest_sha256=ct.EXPECTED_FILES[MANIFEST]["sha"],
        )
        steps["original_common_assembler"]=round(time.perf_counter()-t,3)
        if (assembled.get("copied_csv_files")!=29
            or assembled.get("dataset_id")!="all_225"
            or assembled.get("source_sha256")!=ct.SOURCE_SHA
            or assembled.get("numeric_equivalence")!="NOT_YET_VERIFIED"):
            raise ValueError("Canonical actual 29 CSV assembler contract did not pass")
        observed=set(p.name for p in s3.glob("*.csv"))
        if observed!=set(ct.EXPECTED_FILES):
            raise ValueError("Assembled new generated 29 CSV name coverage differs")
        for name,spec in ct.EXPECTED_FILES.items():
            original=reference/name
            actual=s3/name
            if name==MANIFEST:
                if ct.sha256(actual)!=spec["sha"]:
                    raise ValueError("Immutable 447-condition manifest changed")
                cert[name]={
                    "rows":spec["rows"],"columns":spec["cols"],
                    "fixed_reference_sha256":spec["sha"],
                    "new_calculation":False,"immutable_manifest_input_copy":True,
                    "numeric_parity":True,
                }
                continue
            t=time.perf_counter()
            old=pd.read_csv(original,low_memory=False)
            new=pd.read_csv(actual,low_memory=False)
            fresh=align(old,new,name)
            # The fixed new semantic/OR rows must be precisely equatable to
            # historical canonical numeric facts, never merely SHA-copied.
            check_dataframe(old,fresh,name)
            if len(new)!=spec["rows"] or len(new.columns)!=spec["cols"]:
                raise ValueError("Original canonical CSV row/schema differs: "+name)
            cert[name]={
                "rows":len(new),"columns":len(new.columns),
                "original_reference_sha256":spec["sha"],
                "fresh_new_output_sha256":ct.sha256(actual),
                "new_calculation":True,
                "numeric_parity":True,
                "comparison_seconds":round(time.perf_counter()-t,3),
            }
            print("PASS_NEW_FRESH_E2E_ASSEMBLED_CSV_NUMERIC",name,len(new),flush=True)
            del old,new,fresh
        if len(cert)!=29 or sum(x["new_calculation"] for x in cert.values())!=28:
            raise ValueError("28 computed plus one immutable manifest contract incomplete")
        if ct.inspect_source(source)!=src:
            raise ValueError("Pinned original source changed during full E2E")
        ct.validate_old_reference(reference)
        if subprocess.check_output(
            ["git","-C",str(core),"diff","--name-only"],text=True
        ).strip():
            raise ValueError("Tracked Private code unexpectedly modified")
        return {
            "phase":44,
            "status":"PASS_PHASE44_TRUE_FRESH_OPTIMIZED_ALL225_SEMANTIC_OR_29_CSV_E2E",
            "dataset":"all_225",
            "private_core_sha":ct.CORE_SHA,
            "original_source_sha256":ct.SOURCE_SHA,
            "source_rows":src["rows"],"source_tickers":src["tickers"],
            "original_csv_count":ref["csv_count"],
            "newly_computed_semantic_csv":23,"newly_computed_or_csv":5,
            "newly_computed_total":28,"fixed_manifest_source_rows":ref["condition_ids"],
            "actual_immutable_source_common_assembler_called":True,
            "same_runner_new_semantic_used_as_new_or_input":True,
            "same_runner_new_semantic_and_or_used_as_assembler_inputs":True,
            "complete_new_producer_numeric_same_old_29_csv":True,
            "component_numeric_file_proofs":cert,
            "stage_durations_seconds":steps,
            "total_duration_seconds":round(time.perf_counter()-start,3),
            "max_parent_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
            "original_p2_v12_modified":False,
            "old_original_csv_html_modified":False,
            "previous_success_artifacts_recomputed":False,
            "private_csv_artifacts_uploaded":False,
            "phase44_pass":True,
            "phase45_qa_can_be_started":True,
            "release_ready":False,
            "phase48_authorized":False,
        }
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        print("PURGED_FRESH_ALL225_SEMANTIC_OR_29CSV_EPHEMERAL_DATA",flush=True)

def main():
    p=argparse.ArgumentParser()
    for x in ("core","source","reference","report"):
        p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():raise FileExistsError("Never overwrite a previous final phase proof")
    try:
        result=run(
            a.core.resolve(),a.source.resolve(),a.reference.resolve(),
            Path(__file__).resolve().parent
        )
    except BaseException:
        print("BLOCKED_NO_FRESH_E2E_PASS_KEEP_PHASE45_GATE_CLOSED",flush=True)
        raise
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS_PHASE44_TRUE_NEW_PRIVATE_CANONICAL_E2E_ALL225_29_CSV",flush=True)

if __name__=="__main__":
    main()
