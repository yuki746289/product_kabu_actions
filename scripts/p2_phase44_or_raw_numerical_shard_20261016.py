"""Source-validated, bounded canonical OR raw recomputation, all225.
Original candidate universe generated independently from immutable advantage
singles. Canonical _combo_metrics runs only on disjoint raw rows and every
output field is compared. No private source/result CSV may leave the runner.
"""
from __future__ import annotations
import argparse
import itertools
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import p2_phase44_all225_fresh_newproducer_29csv_20261016 as contract
from p2_phase44_optimized_family_20261016 import check_dataframe

CONFIG={"or2":("or_pairwise_all.csv",4,1127,2),
        "or3":("or_triple_all.csv",12,15184,3)}

def region(kind,shard):
    name,n,rows,k=CONFIG[kind]
    if not 0<=shard<n:raise ValueError("OR raw shard out of bounds")
    return rows*shard//n,rows*(shard+1)//n

def selftest():
    for kind,(_,n,total,_) in CONFIG.items():
        ranges=[region(kind,i) for i in range(n)]
        assert ranges[0][0]==0 and ranges[-1][1]==total
        assert all(ranges[i][1]==ranges[i+1][0] for i in range(n-1))
        assert sum(b-a for a,b in ranges)==total
    print("PASS_COMPLETE_OR_RAW_SHARD_PARTITION")

def run(core,source,reference,kind,shard):
    import pandas as pd
    name,n,total,k=CONFIG[kind]
    lo,hi=region(kind,shard)
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=contract.CORE_SHA:
        raise ValueError("Original core SHA changed")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Required Actions policy missing")
    if subprocess.check_output(["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],text=True).strip():
        raise ValueError("Private workflow not allowed")
    source_meta=contract.inspect_source(source)
    contract.validate_old_reference(reference)
    original_digests={p:contract.sha256(reference/p) for p in
                      (name,"advantage_single_candidates.csv")}
    sys.path.insert(0,str(core/"scripts"))
    import build_p2_225_semantic_bundle as sem
    import analyze_p2_or_combinations as original
    import finalize_p2_nikkei_complete_baseline as fin
    start=time.perf_counter()
    frame=sem.prepare_frame(source)
    original.OUT=reference
    masks=fin._feature_masks(frame)
    pool=original._component_pool(frame,masks)
    baseline=original._baseline(frame)
    original_rows=pd.read_csv(reference/name,low_memory=False)
    if len(original_rows)!=total or original_rows["condition_key"].duplicated().any():
        raise ValueError("Original OR raw population incomplete/duplicated")
    expected_keys=[]
    for group in itertools.combinations(pool,k):
        if len({x["feature"] for x in group})==k:
            expected_keys.append(original._or_key(kind,list(group)))
    if expected_keys!=original_rows["condition_key"].tolist():
        raise ValueError("Canonical full universe/order deviates from source")
    lookup={(p["feature"],p["category"]):p for p in pool}
    if len(lookup)!=len(pool):
        raise ValueError("Duplicate source OR component identifier")
    calculated=[]
    for i in range(lo,hi):
        rec=original_rows.iloc[i]
        elements=[lookup[(str(rec[f"feature{j}"]),str(rec[f"category{j}"]))]
                  for j in range(1,k+1)]
        calculated.append(original._combo_metrics(frame,kind,elements,baseline))
        if (i-lo+1)%100==0:
            print("OR_RAW_CANONICAL_PROGRESS",kind,shard,i-lo+1,hi-lo,flush=True)
    result=original._csv_ready(pd.DataFrame(calculated))
    left=original_rows.iloc[lo:hi].reset_index(drop=True)
    proof=check_dataframe(left,result,name)
    if contract.sha256(source)!=contract.SOURCE_SHA:
        raise ValueError("Source features changed")
    for p,sha in original_digests.items():
        if contract.sha256(reference/p)!=sha:
            raise ValueError("Original OR source/output file changed")
    if subprocess.check_output(["git","-C",str(core),"diff","--name-only"],text=True).strip():
        raise ValueError("Private tracked code unexpectedly modified")
    return {
        "phase":44,"status":"PASS_PHASE44_OR_RAW_DIRECT_METRICS_SHARD",
        "kind":kind,"shard":shard,"total_shards":n,
        "range_start":lo,"range_end":hi,"canonical_universe_rows":total,
        "full_original_key_universe_and_order_match":True,
        "newly_calculated":len(calculated),"rows_compared":proof["rows"],
        "all_numeric_and_identity_fields_equal":proof["all_rows_columns_numeric_equal"],
        "source_sha256":contract.SOURCE_SHA,"source_rows":source_meta["rows"],
        "reference_sha256":original_digests[name],
        "private_core_sha":contract.CORE_SHA,
        "seconds":round(time.perf_counter()-start,3),
        "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
        "original_raw_csv_not_recomputed_or_modified":True,
        "previous_success_artifacts_recomputed":False,
        "production_p2_v12_changed":False,
        "full_29_end_to_end_certified":False,"release_ready":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--kind",choices=sorted(CONFIG))
    p.add_argument("--shard",type=int)
    for name in ("core","source","reference","report"):
        p.add_argument("--"+name,type=Path)
    x=p.parse_args()
    if x.selftest:selftest();return
    if any(getattr(x,n) is None for n in ("kind","shard","core","source","reference","report")):
        p.error("Missing pinned source, output or shard")
    if x.report.exists():raise FileExistsError("Refuse duplicate proof")
    result=run(x.core.resolve(),x.source.resolve(),x.reference.resolve(),x.kind,x.shard)
    x.report.parent.mkdir(parents=True,exist_ok=True)
    x.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS_FULL_CANONICAL_OR_RAW_NUMERIC_SHARD",x.kind,x.shard,flush=True)

if __name__=="__main__":main()
