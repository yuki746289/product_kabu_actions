# Phase43 checkpoint-replay integrating REAL pinned 29 CSV assembler.
# Uses verified old saved data, prior genuine numerical results; NO fresh full producers.
import argparse, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path
SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials","capital_goods_others","transportation_utilities")
EXCLUDE={"exclude_capital_goods_transportation_utilities":"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
"exclude_transportation_utilities":"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"}
DATASETS=GROUPS+tuple(EXCLUDE)
STATUSES=("PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT",
          "PASS_PHASE42_DISAGGREGATED_23_SEMANTIC_EVIDENCE_COVERAGE",
          "PASS_PHASE43_SAVED_SOURCE_PROVENANCE_CHAIN_ONLY",
          "PASS_PHASE43_EIGHT_FRESH_CANONICAL_SEMANTIC_NUMERIC_OUTPUTS",
          "PASS_PHASE43_ACTUAL_ASSEMBLER_FIXTURE_AND_NEGATIVE_GATES")
def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()
def rd(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def write(p,obj):Path(p).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
def audit(core,reference,external,paths,dataset):
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=SHA:
        raise ValueError("Original fixed SHA drift")
    expected=(core/"preview/kabu/analysis"/
              ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/dataset).resolve()
    if reference!=expected or not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Original Private source or policy absent")
    if dataset in GROUPS:source=reference/"signal_level_features.csv"
    else:
        f=list(external.rglob("features.csv"))
        if len(f)!=1 or sha(f[0])!=EXCLUDE[dataset]:raise ValueError("Missing original external exclusion features")
        source=f[0]
    ss=sha(source)
    old,gate,linked,fresh,assembler=map(rd,paths)
    for obj,status in zip((old,gate,linked,fresh,assembler),STATUSES):
        if obj.get("status")!=status or obj.get("dataset")!=dataset or obj.get("source_sha256")!=ss:
            raise ValueError("Prior source-bound result not verified: "+status)
        if obj.get("private_core_sha")!=SHA:raise ValueError("Private SHA mismatch")
    if old["resolved_csv_files"]!=29 or old["mismatches"]!=[] or gate["saved_23_semantic_sha_ledger_keys"]!=23:
        raise ValueError("Source or original 23 semantic evidence missing")
    if fresh["new_semantic_outputs_count"]!=8 or assembler["intentional_negative_gate_test_count"]!=2:
        raise ValueError("Canonical new numeric or assembler rejection controls incomplete")
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p02_semantic_io_contract import CSV_FILES,csv_header
    from p2_html_core.p03_common_analysis_plan import OR_CSVS,SEMANTIC_CSVS,MANIFEST
    from assemble_p2_common_dataset_csv import assemble
    if len(CSV_FILES)!=29 or len(OR_CSVS)!=5 or len(SEMANTIC_CSVS)!=23:
        raise ValueError("Canonical 29 CSV ownership changed")
    root=(core/"build"/"p2_phase43_checkpoint_integration_20261016"/dataset).resolve()
    if root.exists() or not root.is_relative_to((core/"build").resolve()):
        raise ValueError("Fresh ephemeral checkpoint stage only")
    semantic,or_root,shadow,output=(root/n for n in ("semantic","or","original_shadow","normalized"))
    t=time.perf_counter()
    try:
        for p in (semantic,or_root,shadow):p.mkdir(parents=True,exist_ok=False)
        originals={}
        for n in CSV_FILES:
            s=source if n=="signal_level_features.csv" else reference/n
            expected_hash=old["files"][n]["sha256"]
            if not s.is_file() or sha(s)!=expected_hash:
                raise ValueError("Checkpoint input is not SHA-pinned original: "+n)
            (shadow/n).symlink_to(s.resolve())
            if n!=MANIFEST:
                target=(or_root if n in OR_CSVS else semantic)/n
                shutil.copyfile(s,target)
                if sha(target)!=expected_hash:raise ValueError("Checkpoint transport corruption")
            originals[n]=expected_hash
        common={"overall_pass":True,"dataset_id":dataset,"source_sha256":ss,
                "source_rows":old["source_rows"],"source_tickers":old["source_tickers"],
                "provenance":"CHECKPOINT_REPLAY_PRIOR_NUMERIC_PROOF_NOT_FRESH_FULL_PRODUCER",
                "full_new_semantic_executed":False,"full_new_OR_executed":False}
        semhash={n:originals[n] for n in SEMANTIC_CSVS}
        orhash={n:originals[n] for n in OR_CSVS}
        write(semantic/"semantic_status.json",{**common,"stage":"semantic","output_csv_sha256":semhash,
              "phase42_disaggregated_proof":gate["status"],"fresh_8_numeric_proof":fresh["status"]})
        write(or_root/"or_status.json",{**common,"stage":"or","output_csv_sha256":orhash,
              "semantic_single_sha256":semhash["advantage_single_candidates.csv"],
              "previous_OR_numeric_run_ids":[38514178506,38512534788,38518149928,38518904606]})
        copied=assemble(dataset,semantic,or_root,reference/MANIFEST,output,shadow,
                        expected_source_sha256=ss,expected_manifest_sha256=old["manifest_sha256"])
        if copied["status"]!="STAGED_CSV_QA_REQUIRED" or copied["copied_csv_files"]!=29:
            raise ValueError("Actual shared assembler failed")
        if copied["numeric_equivalence"]!="NOT_YET_VERIFIED":
            raise ValueError("Transport may not claim independent numerical parity")
        for n in CSV_FILES:
            if sha(output/n)!=originals[n] or csv_header(output/n)!=csv_header(shadow/n):
                raise ValueError("Checkpoint replay changed stored result: "+n)
        if sha(source)!=ss:raise ValueError("Original feature source mutated")
        return {
          "status":"PASS_PHASE43_SOURCE_BOUND_CHECKPOINT_REAL_29_CSV_ASSEMBLY",
          "dataset":dataset,"private_core_sha":SHA,"source_sha256":ss,
          "original_23_semantic_numeric_evidence_passed":True,
          "original_5_OR_numeric_prior_evidence_success_gated":True,
          "real_canonical_29_csv_assembler_executed":True,
          "physical_output_sha_and_column_parity_files":29,
          "earlier_assembler_tamper_and_lineage_rejection_passed":True,
          "checkpoint_mixed_old_source_reuse":True,
          "fresh_full_semantic_23_producer_executed":False,
          "fresh_full_OR_5_producer_executed":False,
          "fresh_full_29_csv_e2e_numeric_certified":False,
          "phase43_checkpoint_option_passed":True,
          "phase43_strict_fresh_only_passed":False,
          "prior_successful_numeric_computation_repeated":False,
          "private_originals_modified":False,"production_p2_v12_modified":False,
          "release_ready":False,"phase48_started":False,
          "duration_seconds":round(time.perf_counter()-t,3)}
    finally:
        if root.exists():shutil.rmtree(root)
        print("PURGED_EPHEMERAL_CHECKPOINT_29CSV",dataset,flush=True)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dataset",choices=DATASETS,required=True)
    for n in ("core","reference","external","proof38","phase42","phase43","fresh8","assembler","out"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError("No overwrite prior evidence")
    result=audit(a.core.resolve(),a.reference.resolve(),a.external.resolve(),
                 [getattr(a,n).resolve() for n in ("proof38","phase42","phase43","fresh8","assembler")],
                 a.dataset)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    write(a.out,result)
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
