# Created: 2026-10-13 JST
"""Phase16: 24 *additional* OR2 and 24 *additional* OR3 saved rows per dataset.

Compares disjoint OR conditions beyond the Phase15 certified eight of each
kind. No P2, semantic, OR generation, HTML regeneration, or new signal data.
Uses the same independent verification functions with a strictly disjoint
deterministic SHA-ordered condition selection.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import p2_common_phase15_or2_or3_saved_sample_20261013 as prior

FIRST_CERTIFIED_PER_KIND=8
ADDITIONAL_PER_KIND=24
N_TOTAL_PER_KIND=FIRST_CERTIFIED_PER_KIND+ADDITIONAL_PER_KIND


def next_conditions(folder:Path)->list:
    old=prior.selected_or_rows(folder)
    if len(old)!=2*FIRST_CERTIFIED_PER_KIND:
        raise ValueError("Phase15 old sample scope cannot be matched")
    results=[]
    for n,name in ((2,"or_pairwise_all.csv"),(3,"or_triple_all.csv")):
        file=folder/name
        with file.open(newline="",encoding="utf-8-sig") as source:
            rows=csv.DictReader(source)
            required={f"{field}{i}" for field in ("feature","category") for i in range(1,n+1)}
            required|={"count","retention_pct","mask_hash","component_count","condition_key"}
            if not required.issubset(rows.fieldnames or ()):
                raise ValueError(f"Source OR{n} schema mismatch")
            eligible=[]
            seen=set()
            for row in rows:
                labels=tuple((row[f"feature{i}"],row[f"category{i}"]) for i in range(1,n+1))
                if any(feature not in prior.FEATURES or not category for feature,category in labels):
                    continue
                if int(row["component_count"])!=n or labels in seen:
                    raise ValueError("Duplicate/inconsistent old OR labels")
                seen.add(labels)
                eligible.append((n,labels,row))
        eligible.sort(key=lambda entry:hashlib.sha256(
            json.dumps([n,entry[1]],separators=(",",":")).encode()).hexdigest())
        if len(eligible)<N_TOTAL_PER_KIND:
            raise ValueError(f"Only {len(eligible)} eligible saved OR{n}; require {N_TOTAL_PER_KIND}")
        old_expected=[labels for _,labels,_ in eligible[:FIRST_CERTIFIED_PER_KIND]]
        old_actual=[labels for kind,labels,record in old if kind==n]
        if old_expected!=old_actual:
            raise ValueError("Prior Phase15 deterministic OR sample order drift")
        addition=eligible[FIRST_CERTIFIED_PER_KIND:N_TOTAL_PER_KIND]
        if any(labels in set(old_expected) for _,labels,_ in addition):
            raise ValueError("Previously certified OR condition would be repeated")
        results.extend(addition)
    if len(results)!=2*ADDITIONAL_PER_KIND:
        raise ValueError("Unexpected incremental OR sample size")
    return results


def selftest()->None:
    prior.selftest()
    assert FIRST_CERTIFIED_PER_KIND==8
    assert ADDITIONAL_PER_KIND==24
    assert N_TOTAL_PER_KIND==32
    assert prior.N_PER_KIND==FIRST_CERTIFIED_PER_KIND
    print("PASS: disjoint SHA sampling scope (old 8 + next 24 for OR2 and OR3)")


def audit(dataset:str,core:Path,source:Path,reference:Path,proof:Path)->dict:
    original=prior.selected_or_rows
    try:
        prior.selected_or_rows=next_conditions
        result=prior.audit(dataset,core,source,reference,proof)
    finally:
        prior.selected_or_rows=original
    if result["or2_rows_checked"]!=prior.N_PER_KIND or result["or3_rows_checked"]!=prior.N_PER_KIND:
        # The base auditor's fixed sample report counter must NOT certify
        # the changed incremental scope without explicit override below.
        raise RuntimeError("Base sample counters no longer match frozen original")
    if result["status"]=="PASS_PHASE15_SAVED_OR2_OR3_DIRECT_NUMERIC_SAMPLE":
        result["status"]="PASS_PHASE16_ADDITIONAL_SAVED_OR2_OR3_NUMERIC_SAMPLE"
    else:
        result["status"]="FAIL_PHASE16_ADDITIONAL_SAVED_OR2_OR3_NUMERIC_SAMPLE"
    result["or2_rows_checked"]=ADDITIONAL_PER_KIND
    result["or3_rows_checked"]=ADDITIONAL_PER_KIND
    result["additional_OR_conditions_checked"]=2*ADDITIONAL_PER_KIND
    result["previously_certified_OR_conditions_reexecuted"]=False
    result["phase15_success_run_id"]=38336668272
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--selftest",action="store_true")
    parser.add_argument("--dataset",choices=sorted(prior.SHAPES))
    parser.add_argument("--core",type=Path)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--reference",type=Path)
    parser.add_argument("--proof",type=Path)
    parser.add_argument("--out",type=Path)
    a=parser.parse_args()
    if a.selftest:
        selftest()
        return 0
    if any(getattr(a,x) is None for x in ("dataset","core","source","reference","proof","out")):
        parser.error("Specify dataset, core, source, reference, proof and out")
    out=a.out.resolve()
    if out.exists():
        raise FileExistsError("Do not overwrite successful or failed previous evidence")
    result=audit(a.dataset,a.core.resolve(),a.source.resolve(),
                 a.reference.resolve(),a.proof.resolve())
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="error_examples"},ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
