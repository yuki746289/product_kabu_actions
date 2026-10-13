# Created: 2026-10-13 JST
"""Phase19: full saved OR candidate summary lineage and non-stability metric QA.

Compare every saved OR candidate summary row against the corresponding already
approved unique OR2/OR3 row. Independently pinned Phase17 deduped CSV hashes
make cross-dataset/old-version mixing fail closed. Monthly stability columns
are not covered by this stage. This does NOT re-run OR/semantic or P2.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

import p2_common_phase17_full_saved_or_dedupe_20261013 as prev

SHA = prev.CORE_SHA
DATASETS = prev.DATASETS
KEY_METRICS = ("condition_key","mask_hash","condition_type","condition_label",
               "component_count","count","retention_pct",
               "max_component_count","incremental_entries_vs_largest",
               "entry_expansion_vs_largest_pct","multi_match_count",
               "multi_match_share_of_union_pct","all_match_count",
               "all_match_share_of_union_pct","equivalent_logic_count",
               "avg_win_pct","min_win_pct","accuracy_core_pct",
               "count_confidence_factor","balance_index",
               "avg_uplift_pp","min_uplift_pp",
               "balanced_candidate","expansion_candidate",
               "high_accuracy_candidate","contains_unknown_price")
TIME_HORIZONS = (5,10,20)
FIELDS = KEY_METRICS + tuple(f"{name}_{h}d_{unit}" for h in TIME_HORIZONS for name,unit in (
    ("win","pct"),("return","pct"),("win_uplift","pp"),
    ("best_component_win","pct"),("delta_vs_best_component","pp")))
COMPONENT_FIELDS = tuple(f"{name}{i}" for i in (1,2,3) for name in (
    "feature","category")) + tuple(f"component{i}_count" for i in (1,2,3))
FLAG_FIELDS = {"balanced_candidate","expansion_candidate",
              "high_accuracy_candidate","contains_unknown_price"}
TEXT_FIELDS = {"condition_key","mask_hash","condition_type","condition_label",
               "feature1","category1","feature2","category2",
               "feature3","category3"} | FLAG_FIELDS
NUMBER_FIELDS = set(FIELDS+COMPONENT_FIELDS)-TEXT_FIELDS
IGNORE_EXTRA = {
    "total_months","active_months","active_month_rate_pct",
    "avg_entries_all_months","median_entries_all_months",
    "avg_entries_active_months","median_entries_active_months"
}


def source_rows(path: Path) -> tuple[list[dict[str,str]], set[str]]:
    with path.open(newline="",encoding="utf-8-sig") as handle:
        reader=csv.DictReader(handle)
        header=reader.fieldnames or []
        if len(header)!=len(set(header)) or not {"condition_key","mask_hash","count"}.issubset(header):
            raise ValueError("Invalid saved OR candidate/source CSV header")
        result=[]
        for line,r in enumerate(reader,2):
            if None in r or any(v is None for v in r.values()):
                raise ValueError(f"Malformed saved OR row at line {line}")
            result.append(r)
    return result,set(header)


def same(old:str,new:str,field:str)->bool:
    if field in FLAG_FIELDS:
        return old.strip().lower()==new.strip().lower()
    if field in NUMBER_FIELDS:
        return prev.equal_float(old,new)
    return old==new


def validate_saved(dataset:str, core:Path, folder:Path, phase17:Path)->dict:
    if dataset not in DATASETS:
        raise ValueError("Unknown dataset")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=SHA:
        raise ValueError("Original Private source SHA drift")
    proof=json.loads(phase17.read_text(encoding="utf-8"))
    if proof.get("status")!="PASS_PHASE17_FULL_SAVED_OR_DEDUPE_ONLY" or \
            proof.get("source_core_sha")!=SHA or proof.get("dataset")!=dataset:
        raise ValueError("Independent Phase17 original OR evidence mismatch")
    family_digest={x["family"]:x["unique_csv_sha256"] for x in proof["families"]}
    if set(family_digest)!={"or2","or3"}:
        raise ValueError("Wrong prior saved OR families")
    original={}
    origins={}
    source_headers={}
    for family,filename in (("or2","or_pairwise_unique.csv"),
                            ("or3","or_triple_unique.csv")):
        src=folder/filename
        if prev.hash_file(src)!=family_digest[family]:
            raise ValueError(f"Prior Phase17 {family} original digest mismatch")
        records,headers=source_rows(src)
        source_headers[family]=headers
        for record in records:
            key=record["condition_key"]
            if key in original:
                raise ValueError("Unique OR candidate identities collide")
            original[key]=record
            origins[key]=family
    status_file=folder/("or_status.json" if dataset=="all_225" else "semantic_status.json")
    status=json.loads(status_file.read_text(encoding="utf-8"))
    if status.get("overall_pass") is not True:
        raise ValueError("Saved original OR job did not pass")
    if dataset!="all_225" and status.get("or_full_universe_pass") is not True:
        raise ValueError("Saved source missing original full OR certification")
    summary_file=folder/"or_candidate_summary.csv"
    candidates,candidate_headers=source_rows(summary_file)
    needed={"condition_key","mask_hash","count","component_count","condition_type"}
    if not needed.issubset(candidate_headers):
        raise ValueError("Candidate summary does not have stable identity fields")
    expected=status.get("candidate_summary_rows" if dataset=="all_225"
                        else "or_candidate_summary_rows")
    if type(expected) is not int or len(candidates)!=expected:
        raise ValueError("Saved candidate count differs from completed status")
    issues=[]
    seen=set()
    compared=0
    for index,row in enumerate(candidates,1):
        key=row["condition_key"]
        if key in seen:
            issues.append(f"row{index} duplicate_candidate_key")
            continue
        seen.add(key)
        old=original.get(key)
        if old is None:
            issues.append(f"row{index} no_original_unique_OR_source")
            continue
        if (row["condition_type"]!=origins[key] or
            row["mask_hash"]!=old["mask_hash"]):
            issues.append(f"row{index} original_mask_or_family_mismatch")
        for field in FIELDS+COMPONENT_FIELDS:
            if field not in candidate_headers:
                issues.append(f"row{index} candidate_missing_{field}")
                continue
            if field not in source_headers[origins[key]]:
                # Pair rows have no feature3/category3; accept blank in
                # candidate's UNION result but reject unexpected fake value.
                if field in ("feature3","category3","component3_count"):
                    if row[field] not in ("","nan","NaN"):
                        issues.append(f"row{index} unexpected_third_component")
                    continue
                issues.append(f"row{index} original_source_missing_{field}")
                continue
            if not same(row[field],old[field],field):
                issues.append(f"row{index} {field}_mismatch")
            compared+=1
    return {
        "schema":1,
        "status":"PASS_PHASE19_FULL_SAVED_OR_CANDIDATE_LINEAGE_ONLY"
             if not issues else "FAIL_PHASE19_FULL_SAVED_OR_CANDIDATE_LINEAGE",
        "dataset":dataset,"original_private_sha":SHA,
        "saved_candidate_csv_sha256":prev.hash_file(summary_file),
        "original_unique_or2_sha256":family_digest["or2"],
        "original_unique_or3_sha256":family_digest["or3"],
        "full_saved_candidate_rows":len(candidates),
        "existing_unique_or_rows":len(original),
        "identities_crosslinked":len(seen),
        "shared_source_fields_checked":compared,
        "lineage_mismatches":len(issues),
        "error_kinds_and_indices":issues[:12],
        "monthly_stability_independently_recomputed":False,
        "old_saved_or_recalculated":False,
        "new_common_or_generated":False,
        "production_changed":False,
        "release_ready":False,
    }


def selftest():
    assert len(DATASETS)==9
    assert "condition_key" in FIELDS and "mask_hash" in FIELDS
    assert same("true","True","balanced_candidate")
    assert same("12.000000000001","12.0","balance_index")
    assert not same("12.5","12.0","balance_index")
    assert not same("or2","or3","condition_type")
    print("PASS: saved OR candidate original identity & numeric guard unit tests")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    p.add_argument("--core",type=Path)
    p.add_argument("--reference",type=Path)
    p.add_argument("--phase17",type=Path)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest(); return 0
    if not all((a.dataset,a.core,a.reference,a.phase17,a.out)):
        p.error("dataset/core/reference/phase17/out required")
    dest=a.out.resolve()
    if dest.exists():
        raise FileExistsError("Never overwrite prior immutable proof")
    report=validate_saved(a.dataset,a.core.resolve(),a.reference.resolve(),a.phase17.resolve())
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="error_kinds_and_indices"},ensure_ascii=False))
    return 0 if report["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
