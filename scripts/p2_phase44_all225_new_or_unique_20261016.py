"""Two canonical OR deduplication functions on immutable saved raw OR inputs.

This is only a source-bound independent new calculation of unique OR outputs:
the original raw OR pair/triple producer is NOT reexecuted or certified here.
"""
from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import p2_phase44_all225_fresh_newproducer_29csv_20261016 as contract
from p2_phase44_optimized_family_20261016 import check_dataframe

OLD_RAW={
    "or_pairwise_unique.csv":"or_pairwise_all.csv",
    "or_triple_unique.csv":"or_triple_all.csv",
}

def selftest() -> None:
    assert len(OLD_RAW)==2 and len(set(OLD_RAW.values()))==2
    assert all(f in contract.EXPECTED_FILES for f in list(OLD_RAW)+list(OLD_RAW.values()))
    print("PASS_OR_UNIQUE_TWO_SHA_BOUND_INPUT_CONTRACT")

def run(core:Path,source:Path,reference:Path) -> dict:
    import pandas as pd
    if subprocess.check_output(
        ["git","-C",str(core),"rev-parse","HEAD"],text=True
    ).strip()!=contract.CORE_SHA:
        raise ValueError("Pinned private core SHA drift")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Private execution migration rule missing")
    if subprocess.check_output(
        ["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],
        text=True
    ).strip():
        raise ValueError("Private workflow found")
    src_meta=contract.inspect_source(source)
    old_meta=contract.validate_old_reference(reference)
    sys.path.insert(0,str(core/"scripts"))
    import analyze_p2_or_combinations as original_or
    before=time.perf_counter()
    receipts={}
    for unique,raw in OLD_RAW.items():
        t=time.perf_counter()
        input_before=contract.sha256(reference/raw)
        output_before=contract.sha256(reference/unique)
        canonical_raw=pd.read_csv(reference/raw,low_memory=False)
        new_unique=original_or._csv_ready(original_or._dedupe(canonical_raw))
        old_unique=pd.read_csv(reference/unique,low_memory=False)
        parity=check_dataframe(old_unique,new_unique,unique)
        if contract.sha256(reference/raw)!=input_before:
            raise ValueError("Old raw OR source changed")
        if contract.sha256(reference/unique)!=output_before:
            raise ValueError("Old OR unique reference changed")
        receipts[unique]={
            **parity,
            "input_raw_sha256":input_before,
            "saved_unique_sha256":output_before,
            "canonical_dedupe_newly_executed":True,
            "old_raw_producer_recomputed":False,
            "seconds":round(time.perf_counter()-t,4),
        }
        print("PASS_PHASE44_NEW_OR_UNIQUE_CANONICAL",unique,len(new_unique),flush=True)
    if contract.sha256(source)!=contract.SOURCE_SHA:
        raise ValueError("Original raw features changed")
    if subprocess.check_output(
        ["git","-C",str(core),"diff","--name-only"],text=True
    ).strip():
        raise ValueError("Original private tracked source altered")
    return {
      "phase":44,"status":"PASS_PHASE44_BOUNDED_OR_UNIQUE_TWO_DIRECT_CANONICAL",
      "dataset":"all_225","source_sha256":contract.SOURCE_SHA,
      "source_rows":src_meta["rows"],"source_tickers":src_meta["tickers"],
      "old_reference_count":old_meta["csv_count"],
      "private_core_sha":contract.CORE_SHA,
      "new_calculated_unique_count":2,
      "calculated":receipts,
      "runtime_seconds":round(time.perf_counter()-before,3),
      "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
      "old_OR_raw_producer_rerun":False,
      "all_29_new_producer_certified":False,"phase44_complete":False,
      "phase45_allowed":False,"release_ready":False,"phase48_authorized":False,
    }

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    for name in ("core","source","reference","report"):
        p.add_argument("--"+name,type=Path)
    x=p.parse_args()
    if x.selftest:
        selftest()
        return 0
    if any(getattr(x,n) is None for n in ("core","source","reference","report")):
        p.error("Private SHA-bound source and reference plus report required")
    if x.report.exists():
        raise FileExistsError("Refuse overwrite of existing result")
    q=run(x.core.resolve(),x.source.resolve(),x.reference.resolve())
    x.report.parent.mkdir(parents=True,exist_ok=True)
    x.report.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS_BOUNDED_FRESH_OR_UNIQUE_TWO",flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
