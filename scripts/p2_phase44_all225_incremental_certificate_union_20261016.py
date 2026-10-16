"""Final STRICT source-bound union of Phase44 independently new-calculated CSV proofs.

Phase44 numeric component completeness != end-to-end single fresh canonical
semantic->OR->assembler execution. Fail closed on missing family/column/row,
overlap, SHA mismatch, mismatched 29-file inventory, or false full PASS claims.
All input receipts are public-safe numeric metadata JSON; no private source.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from p2_phase44_all225_fresh_newproducer_29csv_20261016 import (
    CORE_SHA, SOURCE_SHA, EXPECTED_FILES,
)

FAMILIES_12={
    "stability5":5,"single4":4,"baseline3":3
}
FAMILIES_9={
    "dependent4":4,"walkforward1":1,"pair4":4
}
GENERATED=frozenset(EXPECTED_FILES)-{"condition_detail_manifest.csv"}

def verify(metadata:Path)->dict:
    assert len(EXPECTED_FILES)==29 and len(GENERATED)==28
    all_files={}
    documents={}
    errors=[]
    inputs={}
    def receipt(name):
        p=metadata/(name+".json")
        if not p.is_file():
            errors.append("missing required receipt "+name)
            return None
        data=json.loads(p.read_text(encoding="utf-8"))
        documents[name]=data
        return data
    def add(name,rows,cols,tag):
        if name not in GENERATED:
            errors.append("unexpected output "+name)
            return
        if name in all_files:
            errors.append("duplicate independent new output "+name)
            return
        expected=EXPECTED_FILES[name]
        if rows!=expected["rows"] or cols!=expected["cols"]:
            errors.append("fixed schema or row count drift: "+name)
            return
        all_files[name]={"verified_rows":rows,"verified_cols":cols,
                         "original_sha256":expected["sha"],"proof_family":tag}
    for group,parts,statuskey,filekey,countkey,sourcekey in (
        ("prior12",FAMILIES_12,
         "PASS_PHASE44_BOUNDED_NEW_FUNCTION_NUMERIC_PARITY",
         "newly_independently_computed_files","newly_verified_file_count","input_sha256"),
        ("additional9",FAMILIES_9,
         "PASS_PHASE44_BOUNDED_UNSEEN_FRESH_NUMERIC_FUNCTION",
         "newly_computed","newly_computed_file_count","source_sha256"),
    ):
        for fam,n in parts.items():
            label=f"{group}_{fam}"
            d=receipt(label)
            if d is None:continue
            files=d.get(filekey,{})
            if (d.get("status")!=statuskey or d.get("family")!=fam
                or d.get("private_core_sha")!=CORE_SHA
                or d.get(sourcekey)!=SOURCE_SHA
                or d.get(countkey)!=n or len(files)!=n
                or d.get("release_ready") is not False):
                errors.append("bad proof family metadata "+label)
                continue
            if d.get("full_new_semantic_or_29_csv_chain_certified") is True:
                errors.append("prior proof illegally claims new E2E "+label)
            for name,v in files.items():
                if (v.get("all_rows_columns_numeric_equal") is not True
                    or v.get("equivalent") is False):
                    errors.append("numeric mismatch or missing receipt "+name)
                    continue
                add(name,v.get("rows"),v.get("columns"),label)
    d=receipt("or_unique")
    if d is not None:
        if (d.get("status")!="PASS_PHASE44_BOUNDED_OR_UNIQUE_TWO_DIRECT_CANONICAL"
            or d.get("source_sha256")!=SOURCE_SHA
            or d.get("private_core_sha")!=CORE_SHA
            or d.get("new_calculated_unique_count")!=2
            or d.get("old_OR_raw_producer_rerun") is not False):
            errors.append("OR unique provenance invalid")
        for name,v in d.get("calculated",{}).items():
            if v.get("all_rows_columns_numeric_equal") is not True:
                errors.append("OR unique numeric fail "+name)
            else:add(name,v.get("rows"),v.get("columns"),"or_unique")
    d=receipt("walkforward")
    if d is not None:
        if (d.get("status")!="PASS_PHASE44_ALL225_COMBO_WALKFORWARD_84_ROWS_NUMERIC"
            or d.get("source_sha256")!=SOURCE_SHA or d.get("private_core_sha")!=CORE_SHA
            or d.get("canonical_result_rows_verified")!=84
            or len(d.get("shards_passed",[]))!=7
            or d.get("one_more_new_csv_family_pass") is not True):
            errors.append("walkforward complete 7-shard proof invalid")
        else:add("combination_walkforward_results.csv",84,15,"walkforward")
    d=receipt("or_raw")
    if d is not None:
        if (d.get("status")!="PASS_PHASE44_ALL225_FULL_OR_RAW_2_CSV_INDEPENDENT_NUMERIC"
            or d.get("independent_new_raw_or_pair_and_triple_pass") is not True
            or len(d.get("successful_shards",[]))!=16
            or d.get("rows_certified")!={"or2":1127,"or3":15184}):
            errors.append("OR raw direct complete full-universe proof invalid")
        else:
            add("or_pairwise_all.csv",1127,48,"or_raw")
            add("or_triple_all.csv",15184,52,"or_raw")
    d=receipt("or_candidate")
    if d is not None:
        if (d.get("status")!="PASS_PHASE44_OR_CANDIDATE_ALL60_SAVED_NEW_CALCULATION_PROOFS"
            or d.get("verified_rows")!=60
            or d.get("certified_shards")!=list(range(6))
            or d.get("additional_producer_recomputations")!=0
            or d.get("all_60_new_numeric_outputs_independently_evidenced") is not True):
            errors.append("OR candidate full 60-row proof invalid")
        else:add("or_candidate_summary.csv",60,78,"or_candidate")
    d=receipt("stability")
    if d is not None:
        if (d.get("status")!="PASS_PHASE44_ALL225_COMBO_STABILITY_COMPLETE_9812"
            or d.get("canonical_grouped_numpy_numeric_comparison") is not True
            or d.get("all_old_source_rows_verified")!=9812
            or d.get("shards_passed")!=list(range(13))
            or d.get("old_canonical_reference_sha256")!=EXPECTED_FILES["combination_stability_summary.csv"]["sha"]):
            errors.append("combination stability complete shard proof invalid")
        else:add("combination_stability_summary.csv",9812,64,"stability")
    if set(all_files)!=GENERATED:
        errors.append("complete 28 generated-CSV family universe differs: missing="+
                      str(sorted(GENERATED-set(all_files)))+
                      " extra="+str(sorted(set(all_files)-GENERATED)))
    passed=not errors and len(all_files)==28
    return {
      "phase":44,
      "status":("PASS_28_NEW_FUNCTION_CSV_NUMERIC_COMPONENTS_1_IMMUTABLE_MANIFEST"
                if passed else "BLOCKED_PHASE44_NUMERIC_RECEIPT_UNION"),
      "source_sha256":SOURCE_SHA,"original_core_sha":CORE_SHA,
      "complete_staged_csv_contract_count":29,
      "fully_new_computed_and_numerically_evidenced_csv_count":len(all_files),
      "pinned_immutable_legacy_manifest": {
          "name":"condition_detail_manifest.csv",
          "rows":EXPECTED_FILES["condition_detail_manifest.csv"]["rows"],
          "columns":EXPECTED_FILES["condition_detail_manifest.csv"]["cols"],
          "sha256":EXPECTED_FILES["condition_detail_manifest.csv"]["sha"],
          "status":"SOURCE_INPUT_SHA_PINNED_NOT_NEWLY_COMPUTED",
      },
      "output_receipt_ledger":all_files,
      "independent_receipt_count":len(documents),
      "errors":errors,
      "all_new_producer_end_to_end_chain_certified":False,
      "phase44_full_end_to_end_pass":False,
      "phase45_allowed":False,
      "release_ready":False,
      "phase48_authorized":False,
      "prior_success_artifacts_recomputed":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--metadata-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    x=p.parse_args()
    if x.output.exists():raise FileExistsError("Never overwrite old source-bound proof")
    result=verify(x.metadata_dir)
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PHASE44_FINAL_COMPUTED_28_CSV_COMPONENT_VERDICT",
          result["status"],result["fully_new_computed_and_numerically_evidenced_csv_count"])
    if result["errors"]:raise SystemExit(2)

if __name__=="__main__":
    main()
