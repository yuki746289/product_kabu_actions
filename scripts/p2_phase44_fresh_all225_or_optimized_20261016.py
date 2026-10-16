"""Actual immutable-source all225 OR5 new producer over new Semantic CSV.

Computes all OR2/OR3 raw combinations via exact ORIGINAL Private
_combo_metrics without retaining 16k x 181318 boolean masks. Then executes
canonical _dedupe, old-original selection/order and canonical _add_stability.
The old 5 OR CSVs are read-only numeric comparators, never producer inputs.
"""
from __future__ import annotations
import argparse
import gc
import itertools
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import p2_phase44_all225_fresh_newproducer_29csv_20261016 as ct
from p2_phase44_optimized_family_20261016 import check_dataframe

def source_guard(core,source,reference):
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=ct.CORE_SHA:
        raise ValueError("Pinned original Private code SHA drift")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Original migration policy missing")
    if subprocess.check_output(["git","-C",str(core),"ls-tree","-r","--name-only","HEAD",".github/workflows"],
                               text=True).strip():
        raise ValueError("Private workflow forbidden")
    original=ct.inspect_source(source)
    ct.validate_old_reference(reference)
    return original

def run(core,source,reference,semantic,output):
    import numpy as np
    import pandas as pd
    import build_p2_225_semantic_bundle as prep
    import analyze_p2_or_combinations as canonical
    import finalize_p2_nikkei_complete_baseline as fin
    from p2_html_core.p03_common_analysis_plan import OR_CSVS
    if output.exists():
        raise FileExistsError("New canonical OR producer output must be fresh")
    src=source_guard(core,source,reference)
    proof=json.loads((semantic/"semantic_status.json").read_text(encoding="utf-8"))
    if (proof.get("dataset_id")!="all_225"
        or proof.get("overall_pass") is not True
        or proof.get("newly_computed_semantic_csv_count")!=23
        or proof.get("newly_computed_not_old_checkpoint_copy") is not True
        or proof.get("source_sha256")!=ct.SOURCE_SHA
        or proof.get("previous_success_artifacts_recomputed") is not False):
        raise ValueError("Actual new canonical semantic producer evidence invalid")
    for name,sha in proof["output_csv_sha256"].items():
        if ct.sha256(semantic/name)!=sha:
            raise ValueError("Newly computed semantic input checksum mismatch")
    frame=prep.prepare_frame(source)
    if len(frame)!=src["rows"]:
        raise ValueError("Immutable all225 source unexpected")
    canonical.OUT=semantic
    start=time.perf_counter()
    masks=fin._feature_masks(frame)
    pool=canonical._component_pool(frame,masks)
    if not pool:raise ValueError("No eligible canonical OR components")
    population={}
    for obj in pool:
        population[obj["feature"]]=population.get(obj["feature"],0)+1
    baseline=canonical._baseline(frame)
    original_sha={name:ct.sha256(reference/name) for name in OR_CSVS}
    output.mkdir(parents=True,exist_ok=False)
    all_data={}
    ledger={}
    for kind,k,name in (
        ("or2",2,"or_pairwise_all.csv"),
        ("or3",3,"or_triple_all.csv"),
    ):
        beginning=time.perf_counter()
        original=pd.read_csv(reference/name,low_memory=False)
        old_columns=original.columns.tolist()
        # Original pair/triple loops source components in deterministic
        # combinations order with only unique feature groups admitted.
        buffer=[]
        count=0
        def flush():
            nonlocal buffer
            if not buffer:return
            batch=canonical._csv_ready(pd.DataFrame(buffer))
            if set(batch.columns)!=set(old_columns):
                raise ValueError("Canonical newly computed raw OR schema differs")
            batch=batch.reindex(columns=old_columns)
            batch.to_csv(
                output/name,index=False,mode="a",header=not (output/name).exists(),
                encoding="utf-8"
            )
            buffer.clear()
        for elements in itertools.combinations(pool,k):
            if len({x["feature"] for x in elements})!=k:continue
            values=canonical._combo_metrics(frame,kind,list(elements),baseline)
            # _mask is a huge private NumPy vector: it must be removed
            # after each independent condition calculation, NOT retained.
            values.pop("_mask",None)
            buffer.append(values)
            count+=1
            if len(buffer)>=150:
                flush()
                if count%1200==0:
                    print("PHASE44_NEW_OR_SOURCE_BOUND_RAW_PROGRESS",kind,count,flush=True)
        flush()
        if not (output/name).is_file() or count!=len(original):
            raise ValueError("Entire canonical raw OR universe not freshly generated")
        newly=pd.read_csv(output/name,low_memory=False)
        if len(newly)!=count:
            raise ValueError("Original full OR source and new rows mismatch")
        check_dataframe(original,newly,name)
        all_data[kind]=newly
        ledger[name]=ct.sha256(output/name)
        print("PASS_PHASE44_FULL_FRESH_OR_RAW_SOURCE_ORIGINAL",kind,count,
              round(time.perf_counter()-beginning,3),flush=True)
        del original,newly
        gc.collect()
    # Canonical deduplication receives NEW raw producer output, never a
    # source checkpoint. For ranking/summary preserve original stable sort.
    unique={}
    for kind,raw_name,unique_name in (
        ("or2","or_pairwise_all.csv","or_pairwise_unique.csv"),
        ("or3","or_triple_all.csv","or_triple_unique.csv"),
    ):
        original=pd.read_csv(reference/unique_name,low_memory=False)
        raw=pd.read_csv(output/raw_name,low_memory=False)
        new=canonical._csv_ready(canonical._dedupe(raw))
        if set(new.columns)!=set(original.columns):
            raise ValueError("New canonical OR unique schema invalid")
        new=new.reindex(columns=original.columns)
        check_dataframe(original,new,unique_name)
        new.to_csv(output/unique_name,index=False,encoding="utf-8")
        check_dataframe(original,pd.read_csv(output/unique_name,low_memory=False),unique_name)
        unique[kind]=new
        ledger[unique_name]=ct.sha256(output/unique_name)
        print("PASS_FRESH_OR_UNIQUE_FROM_NEW_RAW",unique_name,len(new),flush=True)
    combined=pd.concat([unique["or2"],unique["or3"]],ignore_index=True,sort=False)
    balanced=combined[combined["balanced_candidate"]].copy().sort_values(
        ["balance_index","avg_win_pct","count"],ascending=False)
    expansion=combined[combined["expansion_candidate"]].copy().sort_values(
        ["balance_index","incremental_entries_vs_largest"],ascending=False)
    accuracy=combined[combined["high_accuracy_candidate"]].copy().sort_values(
        ["avg_win_pct","count"],ascending=False)
    def restore_masks(selection):
        selection=selection.copy()
        # The original memory-backed _mask is restored ONLY for selected
        # monthly-stability candidates and discarded immediately afterwards.
        mm=[]
        for _,r in selection.iterrows():
            n=2 if r["condition_type"]=="or2" else 3
            factors=[masks[(str(r[f"feature{i}"]),str(r[f"category{i}"]))]
                     for i in range(1,n+1)]
            mm.append(np.logical_or.reduce(factors))
        selection["_mask"]=mm
        return selection
    pieces=[]
    for candidates in (balanced.head(60),expansion.head(60),accuracy.head(60)):
        if candidates.empty:continue
        selected=restore_masks(candidates)
        produced=canonical._add_stability(frame,selected)
        produced=canonical._csv_ready(produced)
        pieces.append(produced)
        del selected
        gc.collect()
    if not pieces:
        raise ValueError("Original canonical OR candidate output unexpectedly empty")
    final=pd.concat(pieces,ignore_index=True,sort=False).drop_duplicates(
        "condition_key",keep="first")
    original=pd.read_csv(reference/"or_candidate_summary.csv",low_memory=False)
    if set(final.columns)!=set(original.columns):
        raise ValueError("New OR candidate ranking or stability schema differs")
    final=final.reindex(columns=original.columns)
    check_dataframe(original,final,"or_candidate_summary.csv")
    final.to_csv(output/"or_candidate_summary.csv",index=False,encoding="utf-8")
    check_dataframe(original,pd.read_csv(output/"or_candidate_summary.csv",low_memory=False),
                    "or_candidate_summary.csv")
    ledger["or_candidate_summary.csv"]=ct.sha256(output/"or_candidate_summary.csv")
    if set(ledger)!=set(OR_CSVS):
        raise ValueError("Fresh original canonical five OR CSVs incomplete")
    for name,sha in original_sha.items():
        if ct.sha256(reference/name)!=sha:
            raise ValueError("Immutable old OR CSV was modified")
    if ct.sha256(source)!=ct.SOURCE_SHA:
        raise ValueError("Original source features SHA drift")
    if subprocess.check_output(["git","-C",str(core),"diff","--name-only"],text=True).strip():
        raise ValueError("Original Private tracked code modified")
    status={
        "stage":"or","overall_pass":True,"dataset_id":"all_225",
        "source_sha256":ct.SOURCE_SHA,
        "source_rows":src["rows"],"source_tickers":src["tickers"],
        "semantic_single_sha256":proof["output_csv_sha256"]["advantage_single_candidates.csv"],
        "newly_calculated_or_csv_count":5,
        "newly_computed_from_new_semantic_csv_input":True,
        "output_csv_sha256":ledger,
        "old_raw_or_recomputed":False,
        "previous_success_artifacts_recomputed":False,
        "elapsed_seconds":round(time.perf_counter()-start,3),
        "peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
    }
    (output/"or_status.json").write_text(
        json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return status

def main():
    p=argparse.ArgumentParser()
    for n in ("core","source","reference","semantic","output"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    sys.path.insert(0,str(a.core.resolve()/"scripts"))
    proof=run(a.core.resolve(),a.source.resolve(),a.reference.resolve(),
              a.semantic.resolve(),a.output.resolve())
    print("PASS_PHASE44_NEW_ALL5_OR_FROM_NEW_SEMANTIC",
          proof["elapsed_seconds"],proof["peak_rss_mib"],flush=True)

if __name__=="__main__":main()
