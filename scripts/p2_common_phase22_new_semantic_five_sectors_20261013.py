# Created: 2026-10-13 JST
"""Phase22: NEW common semantic bounded real computation on five untested sectors.

The original technology/financial/etc historic successful semantic artifacts
are NEVER rerun. We invoke the same four inner functions used by the NEW
common producer in a fresh build directory per sector. Transportation's
successful Phase20 canary is NOT reexecuted.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

import p2_common_phase20_new_semantic_bounded_20261013 as prev

MORE_SECTORS={
    "technology":(48782,61,54),
    "financials":(16307,20,64),
    "consumer_goods":(33330,41,64),
    "materials":(39007,48,56),
    "capital_goods_others":(29044,35,57),
}


def selftest()->None:
    prev.selftest()
    assert len(MORE_SECTORS)==5
    assert "transportation_utilities" not in MORE_SECTORS
    assert {i[2] for i in MORE_SECTORS.values()}=={54,56,57,64}
    assert all(x>0 and y>0 and z>0 for x,y,z in MORE_SECTORS.values())
    print("PASS: five disjoint pending-sector common semantic source/count guards")


def verify(dataset:str,core:Path,original:Path,source_proof:Path,stage:Path)->dict:
    if dataset not in MORE_SECTORS:
        raise ValueError("Only five as-yet-uncertified sector common computations")
    rows,tickers,candidates=MORE_SECTORS[dataset]
    old=(prev.DATASET,prev.EXPECTED_SOURCE_ROWS,prev.EXPECTED_TICKERS,
         dict(prev.EXPECTED))
    try:
        prev.DATASET=dataset
        prev.EXPECTED_SOURCE_ROWS=rows
        prev.EXPECTED_TICKERS=tickers
        prev.EXPECTED["candidate_registry.csv"]=candidates
        result=prev.compare_outputs(core,original,source_proof,stage)
    finally:
        prev.DATASET,prev.EXPECTED_SOURCE_ROWS,prev.EXPECTED_TICKERS=old[:3]
        prev.EXPECTED.clear()
        prev.EXPECTED.update(old[3])
    if result["dataset"]!=dataset or result["source_rows"]!=rows or result["source_tickers"]!=tickers:
        raise ValueError("New common producer report mutated dataset identity")
    if result["status"]=="PASS_PHASE20_NEW_COMMON_SEMANTIC_SUBSET_NUMERIC_PARITY":
        result["status"]="PASS_PHASE22_NEW_SECTOR_COMMON_SEMANTIC_SUBSET_PARITY"
    else:
        result["status"]="FAIL_PHASE22_NEW_SECTOR_COMMON_SEMANTIC_SUBSET_PARITY"
    result["prior_transportation_phase20_reexecuted"]=False
    result["expected_candidate_rows"]=candidates
    return result


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=sorted(MORE_SECTORS))
    p.add_argument("--core",type=Path)
    p.add_argument("--reference",type=Path)
    p.add_argument("--proof",type=Path)
    p.add_argument("--staging",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest();return 0
    if any(getattr(a,n) is None for n in
           ("dataset","core","reference","proof","staging","report")):
        p.error("dataset/core/reference/proof/staging/report required")
    target=a.report.resolve()
    if target.exists():
        raise FileExistsError("Never overwrite earlier verified audit result")
    data=verify(a.dataset,a.core.resolve(),a.reference.resolve(),
                a.proof.resolve(),a.staging.resolve())
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k not in ("per_file","mismatches")},
                     ensure_ascii=False))
    return 0 if data["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
