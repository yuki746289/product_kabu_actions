"""Read-only original all225 29-CSV assembler integration after complete component proofs.

Inputs are OLD canonical saved checkpoint CSVs, not freshly produced CSV bytes.
Separately approved new-function numerical equivalence must be certified by
28/28-source-bound proof first. This validates real canonical assemble() for
all_225 and immutable 447-condition manifest; NEVER present this as a fresh
semantic->OR end-to-end producer run.
"""
from __future__ import annotations

import argparse
import json
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

from p2_phase44_all225_fresh_newproducer_29csv_20261016 import (
    SOURCE_SHA, CORE_SHA, EXPECTED_FILES, inspect_source, validate_old_reference,
    sha256,
)

def verify(core:Path,source:Path,reference:Path,meta:Path)->dict:
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=CORE_SHA:
        raise ValueError("Pinned Private source SHA changed")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Private Actions policy missing")
    if subprocess.check_output(
        ["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],
        text=True).strip():
        raise ValueError("Original Private workflows prohibited")
    evidence=json.loads(meta.read_text(encoding="utf-8"))
    if (evidence.get("status")!="PASS_28_NEW_FUNCTION_CSV_NUMERIC_COMPONENTS_1_IMMUTABLE_MANIFEST"
        or evidence.get("fully_new_computed_and_numerically_evidenced_csv_count")!=28
        or evidence.get("source_sha256")!=SOURCE_SHA
        or evidence.get("original_core_sha")!=CORE_SHA
        or evidence.get("all_new_producer_end_to_end_chain_certified") is not False
        or evidence.get("errors")!=[]):
        raise ValueError("Missing verified all28 component numeric evidence")
    if set(evidence["output_receipt_ledger"])!=set(EXPECTED_FILES)-{"condition_detail_manifest.csv"}:
        raise ValueError("Independent computed CSV coverage incomplete")
    input_meta=inspect_source(source)
    reference_meta=validate_old_reference(reference)
    t0=time.perf_counter()
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p02_semantic_io_contract import CSV_FILES
    from p2_html_core.p03_common_analysis_plan import SEMANTIC_CSVS,OR_CSVS,MANIFEST
    from assemble_p2_common_dataset_csv import assemble
    if set(CSV_FILES)!=set(EXPECTED_FILES):
        raise ValueError("Fixed all225 29 CSV source contract unexpected")
    if (len(SEMANTIC_CSVS)!=23 or len(OR_CSVS)!=5
        or MANIFEST!="condition_detail_manifest.csv"):
        raise ValueError("Original canonical Semantic OR manifest partition differs")
    stage=(core/"build/phase44_all225_immutable_checkpoint_assemble_20261016").resolve()
    if stage.exists() or not stage.is_relative_to((core/"build").resolve()):
        raise ValueError("Fresh isolated original-source assembly stage required")
    semantic=stage/"01_semantic"
    orroot=stage/"02_or"
    out=stage/"03_normalized"
    stage.mkdir(parents=True,exist_ok=False)
    try:
        semantic.mkdir()
        orroot.mkdir()
        for dirname,names in ((semantic,SEMANTIC_CSVS),(orroot,OR_CSVS)):
            ledger={}
            for name in names:
                original=reference/name
                staged=dirname/name
                shutil.copy2(original,staged)
                if sha256(staged)!=EXPECTED_FILES[name]["sha"]:
                    raise ValueError("Saved source mismatch before integration")
                ledger[name]=EXPECTED_FILES[name]["sha"]
            record={
                "status":"SAVED_IMMUTABLE_CHECKPOINT_AFTER_INDEPENDENT_NEW_NUMERIC_PROOF",
                "overall_pass":True,
                "dataset_id":"all_225","source_sha256":SOURCE_SHA,
                "output_csv_sha256":ledger,
                "fresh_new_semantic_or_producers_executed":False,
                "numeric_component_receipts_verified":28,
            }
            if dirname==orroot:
                record["semantic_single_sha256"]=EXPECTED_FILES["advantage_single_candidates.csv"]["sha"]
            (dirname/("semantic_status.json" if dirname==semantic else "or_status.json")).write_text(
                json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        status=assemble(
            "all_225",semantic,orroot,reference/MANIFEST,out,reference,
            expected_source_sha256=SOURCE_SHA,
            expected_manifest_sha256=EXPECTED_FILES[MANIFEST]["sha"],
        )
        if (status.get("copied_csv_files")!=29 or status.get("source_signals_recomputed") is not False
            or status.get("analysis_rerun") is not False
            or status.get("numeric_equivalence")!="NOT_YET_VERIFIED"):
            raise ValueError("Real original 29 CSV assembler returned unexpected status")
        ledger={}
        for name,expected in EXPECTED_FILES.items():
            current=out/name
            if sha256(current)!=expected["sha"]:
                raise ValueError("Read-only 29 CSV copy parity differs from original: "+name)
            ledger[name]={
                "original_sha256":expected["sha"],"rows":expected["rows"],
                "columns":expected["cols"],"checkpoint_assembler_byte_equal":True,
            }
        if inspect_source(source)!=input_meta:
            raise ValueError("Original 181318 source modified during assembly")
        validate_old_reference(reference)
        if subprocess.check_output(
            ["git","-C",str(core),"diff","--name-only"],text=True
        ).strip():
            raise ValueError("Private source code unexpectedly modified")
        return {
            "phase":44,
            "status":"PASS_PHASE44_ALL225_REAL_COMMON_ASSEMBLER_FROM_IMMUTABLE_NUMERICALLY_PROVEN_CHECKPOINTS",
            "private_core_sha":CORE_SHA,"source_sha256":SOURCE_SHA,
            "input_rows":input_meta["rows"],"input_tickers":input_meta["tickers"],
            "original_reference_csv_count":reference_meta["csv_count"],
            "source_bound_computed_component_receipts":28,
            "manifest_immutable_source_rows":reference_meta["condition_ids"],
            "actual_canonical_assemble_called":True,
            "assembled_csv_count":len(ledger),"file_ledgers":ledger,
            "legacy_old_input_bytes_reused_for_assembly":True,
            "fresh_semantic_or_producers_executed_in_this_job":False,
            "fresh_end_to_end_29_csv_producer_certified":False,
            "phase44_full_fresh_producer_pass":False,"phase45_allowed":False,
            "release_ready":False,"phase48_authorized":False,
            "runtime_seconds":round(time.perf_counter()-t0,3),
            "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
            "private_original_data_modified":False,
        }
    finally:
        if stage.exists():
            shutil.rmtree(stage)
            print("PURGED_IMMUTABLE_ALL225_ASSEMBLER_CHECKPOINT_STAGE",flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("core","source","reference","component-proof","report"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():raise FileExistsError("Cannot overwrite prior audit")
    result=verify(a.core.resolve(),a.source.resolve(),a.reference.resolve(),a.component_proof.resolve())
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS_29_CSV_REAL_COMMON_ASSEMBLER_CHECKPOINT_ONLY_NO_NEW_E2E",flush=True)

if __name__=="__main__":
    main()
