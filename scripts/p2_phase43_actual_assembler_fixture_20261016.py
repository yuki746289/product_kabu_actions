# Created 2026-10-16 JST
"""Phase43 REAL private-core assemble() interface test on immutable original fixture bytes.

This executes the actual original fixed-SHA assemble_p2_common_dataset_csv.assemble
function, in a fresh ephemeral Private core/build directory, using status-ledgers
specifically MARKED SYNTHETIC_FIXTURE assembled from Phase38 SHA-pinned SAVED files.

Validates:
- all exact 29 output bytes match their immutable fixture source SHA
- cross-stage SHA source/dataset/semantic_single ledger binding enforced
- deliberate tampering of one staged OR CSV rejected before copying
- deliberate corrupted semantic->OR linkage rejected before copying
- no source signals or prior success artifact re-execution
- no false claim of a fresh semantic or OR numerical producer
- no saved Private data or Production P2 code changes and no deployment
The fixture is deleted in finally, and only SHA/status metadata exported.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials","capital_goods_others","transportation_utilities")
EXCLUSIONS={
 "exclude_capital_goods_transportation_utilities":"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
 "exclude_transportation_utilities":"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"}
DATASETS=GROUPS+tuple(EXCLUSIONS)
OLD_38="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"
OLD_43="PASS_PHASE43_SAVED_SOURCE_PROVENANCE_CHAIN_ONLY"

def h(path:Path):
    s=hashlib.sha256()
    with path.open("rb") as file:
        for b in iter(lambda:file.read(1<<20),b""):s.update(b)
    return s.hexdigest()

def load(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path:Path,x):
    path.write_text(json.dumps(x,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

def selftest():
    assert len(DATASETS)==8 and len(CORE_SHA)==40 and len(EXCLUSIONS)==2
    print("PASS_PHASE43_REAL_ASSEMBLER_FIXTURE_BOUNDARY_SELFTEST")

def go(core:Path,reference:Path,external:Path,p38path:Path,p43path:Path,dataset:str):
    if dataset not in DATASETS:raise ValueError("Dataset not approved")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=CORE_SHA:
        raise ValueError("Original Private fixed SHA drift")
    source_dir=(core/"preview/kabu/analysis"/
         ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
         dataset).resolve()
    if reference!=source_dir:raise ValueError("Original reference folder differs")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Private architecture policy absent")
    if dataset in GROUPS:
        source=reference/"signal_level_features.csv"
    else:
        matches=list(external.rglob("features.csv"))
        if len(matches)!=1 or h(matches[0])!=EXCLUSIONS[dataset]:
            raise ValueError("Original exclusion feature source mismatch")
        source=matches[0]
    source_sha=h(source)
    p38,p43=load(p38path),load(p43path)
    if (p38.get("status")!=OLD_38 or p43.get("status")!=OLD_43 or
        p38.get("dataset")!=dataset or p43.get("dataset")!=dataset or
        p38.get("private_core_sha")!=CORE_SHA or p43.get("private_core_sha")!=CORE_SHA or
        p38.get("source_sha256")!=source_sha or p43.get("source_sha256")!=source_sha or
        p38.get("resolved_csv_files")!=29 or p38.get("mismatches")!=[] or
        not p43.get("source_lineage_cross_proof_passed") or
        p43.get("full_new_semantic_or_numeric_parity_certified") is not False):
        raise ValueError("Prior immutable original source/lineage certificates absent")
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p02_semantic_io_contract import CSV_FILES,csv_header
    from p2_html_core.p03_common_analysis_plan import OR_CSVS,SEMANTIC_CSVS,MANIFEST
    from assemble_p2_common_dataset_csv import assemble
    if len(CSV_FILES)!=29 or len(SEMANTIC_CSVS)!=23 or len(OR_CSVS)!=5:
        raise ValueError("Common original ownership ledger drift")
    if set(CSV_FILES)!=(set(OR_CSVS)|set(SEMANTIC_CSVS)|{MANIFEST}):
        raise ValueError("Unrecognized 29-CSV output ownership")
    for name in CSV_FILES:
        old=source if name=="signal_level_features.csv" else reference/name
        if not old.is_file() or h(old)!=p38["files"][name]["sha256"]:
            raise ValueError("Source original SHA identity invalid: "+name)
    if h(reference/MANIFEST)!=p38["manifest_sha256"]:
        raise ValueError("Pinned original manifest identity changed")
    build=(core/"build").resolve()
    root=(build/"phase43_assembler_fixture_original_sha_20261016"/dataset).resolve()
    if root.exists() or not root.is_relative_to(build):
        raise ValueError("Fresh isolated test stage required")
    semantic=root/"01_synthetic_saved_semantic_fixture"
    OR=root/"02_synthetic_saved_OR_fixture"
    output=root/"03_real_assembler_output"
    # Excluded-population signal features only exist in the exact prior pinned
    # archive, not in the original per-dataset CSV directory. The assembler
    # requires a complete reference header folder, so make a throwaway symlink
    # shadow of ORIGINAL exact saved sources, never change original files.
    reference_for_contract=reference
    t=time.perf_counter()
    try:
        semantic.mkdir(parents=True,exist_ok=False)
        OR.mkdir(parents=True,exist_ok=False)
        if dataset in EXCLUSIONS:
            reference_for_contract=root/"00_exact_saved_reference_header_shadow"
            reference_for_contract.mkdir(parents=True,exist_ok=False)
            for item in CSV_FILES:
                origin=source if item=="signal_level_features.csv" else reference/item
                if not origin.is_file() or h(origin)!=p38["files"][item]["sha256"]:
                    raise ValueError("Missing/mutated old reference for exclusion shadow: "+item)
                (reference_for_contract/item).symlink_to(origin.resolve())
            print("EXCLUSION_ORIGINAL_HEADER_SHADOW_ISOLATED",dataset,flush=True)
        fixtures={}
        for name in CSV_FILES:
            if name==MANIFEST:continue
            src=source if name=="signal_level_features.csv" else reference/name
            dest=(OR if name in OR_CSVS else semantic)/name
            shutil.copyfile(src,dest)
            if h(dest)!=p38["files"][name]["sha256"]:
                raise ValueError("Fixture copy digest differs from original: "+name)
            fixtures[name]=p38["files"][name]["sha256"]

        common={"overall_pass":True,"dataset_id":dataset,
                "source_sha256":source_sha,"source_rows":int(p38["source_rows"]),
                "source_tickers":int(p38["source_tickers"]),
                "fixture_provenance":"SYNTHETIC_FROM_IMMUTABLE_SAVED_ORIGINAL",
                "new_numerical_producer_executed":False}
        semantic_ledger={name:fixtures[name] for name in SEMANTIC_CSVS}
        OR_ledger={name:fixtures[name] for name in OR_CSVS}
        save(semantic/"semantic_status.json",{**common,"stage":"semantic",
              "output_csv_sha256":semantic_ledger})
        save(OR/"or_status.json",{**common,"stage":"or",
              "output_csv_sha256":OR_ledger,
              "semantic_single_sha256":semantic_ledger["advantage_single_candidates.csv"]})
        status=assemble(dataset,semantic,OR,reference/MANIFEST,output,reference_for_contract,
                 expected_source_sha256=source_sha,
                 expected_manifest_sha256=p38["manifest_sha256"])
        if status["status"]!="STAGED_CSV_QA_REQUIRED":
            raise ValueError("Original assembler must not claim numerical certification")
        if status["copied_csv_files"]!=29 or status["expected_csv_files"]!=29:
            raise ValueError("Original assembler did not stage exactly 29 files")
        if status["numeric_equivalence"]!="NOT_YET_VERIFIED":
            raise ValueError("Original assembler silently claimed numeric parity")
        for name in CSV_FILES:
            if h(output/name)!=p38["files"][name]["sha256"]:
                raise ValueError("Actual original assembler copied unexpected bytes: "+name)
            if status["file_inventory"][name]["sha256"]!=p38["files"][name]["sha256"]:
                raise ValueError("Actual original assembler provenance SHA wrong: "+name)
            old=source if name=="signal_level_features.csv" else reference/name
            if csv_header(old)!=csv_header(output/name):
                raise ValueError("Original assembler output changed column order: "+name)
        if h(source)!=source_sha:
            raise ValueError("Source changed during positive transport proof")
        pass_checks=["pinned_29_original_sha_readonly","real_original_assemble_called",
                "29_exact_bytes_shas","29_exact_column_orders",
                "cross_stage_source_and_single_SHA","no_numerical_certification"]

        # Deliberately tamper ONLY the throwaway OR fixture, never the source.
        test_csv=OR/"or_candidate_summary.csv"
        with test_csv.open("ab") as file:file.write(b"\n#tampered-fixture\n")
        if h(test_csv)==OR_ledger["or_candidate_summary.csv"]:
            raise ValueError("Tamper injection ineffective")
        try:
            assemble(dataset,semantic,OR,reference/MANIFEST,
                     root/"04_should_reject_tampered_output",reference_for_contract,
                     expected_source_sha256=source_sha,
                     expected_manifest_sha256=p38["manifest_sha256"])
        except RuntimeError as err:
            if "producer CSV SHA256 mismatch" not in str(err):
                raise
            pass_checks.append("tampered_OR_intermediate_rejected")
        else:
            raise AssertionError("Assembler accepted tampered OR fixture")

        # Restore saved fixture bytes, then simulate false semantic->OR lineage.
        shutil.copyfile(reference/"or_candidate_summary.csv",test_csv)
        orstatus=load(OR/"or_status.json")
        orstatus["semantic_single_sha256"]="0"*64
        save(OR/"or_status.json",orstatus)
        try:
            assemble(dataset,semantic,OR,reference/MANIFEST,
                     root/"05_should_reject_wrong_source_link",reference_for_contract,
                     expected_source_sha256=source_sha,
                     expected_manifest_sha256=p38["manifest_sha256"])
        except RuntimeError as err:
            if "OR source semantic CSV pin differs" not in str(err):
                raise
            pass_checks.append("wrong_OR_semantic_lineage_rejected")
        else:
            raise AssertionError("Assembler accepted untrue semantic->OR upstream SHA")

        return {
          "schema":1,"status":"PASS_PHASE43_ACTUAL_ASSEMBLER_FIXTURE_AND_NEGATIVE_GATES",
          "dataset":dataset,"private_core_sha":CORE_SHA,
          "source_sha256":source_sha,"saved_reference_manifest_sha256":p38["manifest_sha256"],
          "actual_private_assemble_function_called":True,
          "sha_bound_old_original_fixture_files":29,
          "assembler_copied_and_SHA_verified_outputs":29,
          "pass_checks":pass_checks,
          "intentional_negative_gate_test_count":2,
          "actual_new_semantic_numeric_producer_run":False,
          "actual_new_or_numeric_producer_run":False,
          "semantic_status_is_original_producer_generated":False,
          "or_status_is_original_producer_generated":False,
          "full_new_producer_29_csv_numerical_parity_certified":False,
          "phase43_full_complete":False,
          "previous_successful_producer_outputs_recomputed":False,
          "original_saved_source_files_modified":False,
          "production_p2_v12_changed":False,
          "phase48_merge_or_deploy":False,
          "release_ready":False,"run_seconds":round(time.perf_counter()-t,3)
        }
    finally:
        if root.exists():
            shutil.rmtree(root)
            print("TEMPORARY_PRIVATE_SOURCE_FIXTURE_PURGED",dataset,flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--dataset",choices=DATASETS)
    for n in ("core","reference","external","proof38","proof43","report"):
        ap.add_argument("--"+n,type=Path)
    a=ap.parse_args()
    if a.selftest:selftest();return
    if any(getattr(a,n) is None for n in
         ("dataset","core","reference","external","proof38","proof43","report")):
        ap.error("Pinned original fixture SHA evidence and report path mandatory")
    if a.report.exists():raise FileExistsError("Do not overwrite previous proof")
    out=go(a.core.resolve(),a.reference.resolve(),a.external.resolve(),
           a.proof38.resolve(),a.proof43.resolve(),a.dataset)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    save(a.report,out)
    print(json.dumps(out,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
