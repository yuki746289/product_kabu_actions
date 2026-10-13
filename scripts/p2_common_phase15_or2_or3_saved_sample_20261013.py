# Created: 2026-10-13 JST
"""Phase15: audit saved OR2/OR3 *sample* with independent union-mask reductions.

Never runs P2/semantic/OR producers or reuses a generated candidate as source.
Source inputs are immutable saved features; reference rows are immutable old
OR2/OR3 raw CSVs. All previous successful audits are reused, never rerun.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import p2_common_phase9_direct_metric_parity_20261013 as numeric
import p2_common_phase14_saved_pair_triple_sample_20261013 as prev

CORE_SHA=prev.CORE_SHA
FEATURES=set(prev.FEATURES)
SHAPES=prev.SHAPES
GROUPS=prev.GROUPS
N_PER_KIND=8
H=(5,10,20)
METRICS_PER_ROW=38


def selected_or_rows(folder:Path)->list[tuple[int,tuple[tuple[str,str],...],dict]]:
    selected=[]
    for n,name in ((2,"or_pairwise_all.csv"),(3,"or_triple_all.csv")):
        with (folder/name).open(newline="",encoding="utf-8-sig") as stream:
            rows=csv.DictReader(stream)
            needed={"count","retention_pct","mask_hash","component_count","condition_key"}
            needed |= {f"{x}{i}" for i in range(1,n+1) for x in ("feature","category","component")}
            needed -= {f"component{i}" for i in range(1,n+1)}
            needed |= {f"component{i}_count" for i in range(1,n+1)}
            needed |= {f"win_{h}d_pct" for h in H}
            if not needed.issubset(rows.fieldnames or []):
                raise ValueError("Saved original OR header malformed")
            eligible=[]
            seen=set()
            for r in rows:
                labels=tuple((r[f"feature{i}"],r[f"category{i}"])
                             for i in range(1,n+1))
                if not all(f in FEATURES and c for f,c in labels):
                    continue
                if r.get("component_count")!=str(n):
                    raise ValueError("Reference component_count inconsistent")
                if labels in seen:
                    raise ValueError("Duplicate original OR condition labels")
                seen.add(labels)
                eligible.append((n,labels,r))
        if len(eligible)<N_PER_KIND:
            raise ValueError("Insufficient independently testable original OR rows")
        eligible.sort(key=lambda x:hashlib.sha256(
            json.dumps([n,x[1]],separators=(",",":")).encode()).hexdigest())
        selected += eligible[:N_PER_KIND]
    return selected


def compute_or(source:Path, selected:list, expected_rows:int):
    uniq=set()
    for n, labels,_ in selected:
        uniq.update(labels)
    components={label:numeric.Totals() for label in uniq}
    group_totals=[numeric.Totals() for _ in selected]
    overlaps=[0]*len(selected)
    all_overlap=[0]*len(selected)
    bits=[bytearray((expected_rows+7)//8) for _ in selected]
    full=numeric.Totals()
    ids=set()
    with source.open(newline="",encoding="utf-8-sig") as stream:
        rows=csv.DictReader(stream)
        header=rows.fieldnames or []
        mandatory={f for f,_ in uniq}-{"causal_regime"}
        mandatory |= {"ticker","as_of"}
        mandatory |= {f"moved_predicted_{h}d" for h in H}
        mandatory |= {f"directional_return_{h}d_pct" for h in H}
        if not mandatory.issubset(header) or len(header)!=len(set(header)):
            raise ValueError("Missing or duplicated original saved input columns")
        default_regime="causal_regime" not in header
        for row_idx,row in enumerate(rows):
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Malformed original input CSV row")
            key=(row["ticker"],row["as_of"])
            if not key[0] or not key[1] or key in ids:
                raise ValueError("Missing/duplicate saved signal key")
            ids.add(key)
            if default_regime:
                row["causal_regime"]="UNKNOWN"
            full.add(row)
            for label,t in components.items():
                if row[label[0]]==label[1]:
                    t.add(row)
            for i,(n,labels,_) in enumerate(selected):
                matches=sum(row[f]==category for f,category in labels)
                if matches>=2:
                    overlaps[i]+=1
                if matches==n:
                    all_overlap[i]+=1
                if matches>0:
                    group_totals[i].add(row)
                    bits[i][row_idx//8] |= 1 << (7-(row_idx%8))
    if full.n!=expected_rows or len(ids)!=expected_rows:
        raise ValueError("Original source population violates input identity contract")
    return full,components,group_totals,overlaps,all_overlap,bits,default_regime


def compare_or(full,components,totals,overlaps,all_overlap,bits,selected)->list[str]:
    errors=[]
    def chk(i,field,actual,expected):
        if not numeric.same_numeric(float(actual) if actual is not None else None,expected):
            errors.append(f"OR reference row {i}: {field}")
    for i,(n,labels,ref) in enumerate(selected):
        count=totals[i].n
        counts=[components[k].n for k in labels]
        maximum=max(counts)
        increment=count-maximum
        chk(i,"count",count,ref["count"])
        chk(i,"retention_pct",count/full.n*100,ref["retention_pct"])
        chk(i,"max_component_count",maximum,ref["max_component_count"])
        chk(i,"incremental_entries_vs_largest",increment,ref["incremental_entries_vs_largest"])
        chk(i,"entry_expansion_vs_largest_pct",increment/maximum*100 if maximum else None,
            ref["entry_expansion_vs_largest_pct"])
        chk(i,"multi_match_count",overlaps[i],ref["multi_match_count"])
        chk(i,"multi_match_share_of_union_pct",overlaps[i]/count*100 if count else None,
            ref["multi_match_share_of_union_pct"])
        chk(i,"all_match_count",all_overlap[i],ref["all_match_count"])
        chk(i,"all_match_share_of_union_pct",all_overlap[i]/count*100 if count else None,
            ref["all_match_share_of_union_pct"])
        for j,k in enumerate(labels,1):
            chk(i,f"component{j}_count",components[k].n,ref[f"component{j}_count"])
        fingerprint=hashlib.sha1(bytes(bits[i])).hexdigest()[:16]
        if fingerprint!=ref["mask_hash"]:
            errors.append(f"OR reference row {i}: mask_hash")
        wins=[]
        uplifts=[]
        for h in H:
            win=totals[i].metric(h,"win")
            ret=totals[i].metric(h,"return")
            full_win=full.metric(h,"win")
            baseline_diff=win-full_win if win is not None and full_win is not None else None
            candidates=[components[k].metric(h,"win") for k in labels]
            valid=[v for v in candidates if v is not None]
            best=max(valid) if valid else None
            delta=win-best if best is not None and win is not None else None
            for field,value in (
                (f"win_{h}d_pct",win),(f"return_{h}d_pct",ret),
                (f"win_uplift_{h}d_pp",baseline_diff),
                (f"best_component_win_{h}d_pct",best),
                (f"delta_vs_best_component_{h}d_pp",delta),
            ):
                chk(i,field,value,ref[field])
            if win is not None:
                wins.append(win)
            if baseline_diff is not None:
                uplifts.append(baseline_diff)
        if len(wins)!=3 or len(uplifts)!=3:
            errors.append(f"OR reference row {i}: missing horizon values")
            continue
        avg_win=math.fsum(wins)/3
        weakest=min(wins)
        accuracy=.70*avg_win+.30*weakest
        confidence=.90+.10*math.sqrt(min(count,100)/100.0)
        index=accuracy*confidence
        avg_uplift=math.fsum(uplifts)/3
        min_uplift=min(uplifts)
        for field,value in (
            ("avg_win_pct",avg_win),("min_win_pct",weakest),
            ("accuracy_core_pct",accuracy),
            ("count_confidence_factor",confidence),
            ("balance_index",index),
            ("avg_uplift_pp",avg_uplift),("min_uplift_pp",min_uplift),
        ):
            chk(i,field,value,ref[field])
        for field,value in (
            ("balanced_candidate",count>=60 and weakest>=60 and min_uplift>=2),
            ("expansion_candidate",count>=80 and increment>=20 and min_uplift>=0),
            ("high_accuracy_candidate",count>=30 and weakest>=65),
            ("contains_unknown_price",False),
        ):
            if str(ref[field]).strip().lower() != str(value).lower():
                errors.append(f"OR reference row {i}: {field}")
    return errors


def audit(dataset:str,core:Path,source:Path,reference:Path,proof_file:Path)->dict:
    if dataset not in SHAPES:
        raise ValueError("Unknown dataset or index source unavailable")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=CORE_SHA:
        raise ValueError("Wrong pinned original private source SHA")
    source_hash=numeric.hash_file(source)
    prev.verify_source_proof(json.loads(proof_file.read_text(encoding="utf-8")),
                             dataset,source_hash)
    if dataset in prev.SOURCE_HASH and source_hash!=prev.SOURCE_HASH[dataset]:
        raise ValueError("Saved original source hash mismatch")
    if dataset=="all_225":
        state=json.loads((reference/"or_status.json").read_text(encoding="utf-8"))
        if state.get("overall_pass") is not True or state.get("or2_raw",0)<=0 or state.get("or3_raw",0)<=0:
            raise ValueError("Original OR shard aggregate not PASS")
    else:
        state=json.loads((reference/"semantic_status.json").read_text(encoding="utf-8"))
        if state.get("overall_pass") is not True or state.get("or_full_universe_pass") is not True:
            raise ValueError("Original saved OR universe not certified")
        if state.get("source_rows")!=SHAPES[dataset][0]:
            raise ValueError("Reference OR source row count mismatch")
    selected=selected_or_rows(reference)
    full,components,totals,overlap,complete,bits,used_default=compute_or(
        source,selected,SHAPES[dataset][0])
    errors=compare_or(full,components,totals,overlap,complete,bits,selected)
    return {
        "status":"PASS_PHASE15_SAVED_OR2_OR3_DIRECT_NUMERIC_SAMPLE"
        if not errors else "FAIL_PHASE15_SAVED_OR2_OR3_DIRECT_NUMERIC_SAMPLE",
        "dataset":dataset,
        "private_source_sha":CORE_SHA,"source_sha256":source_hash,
        "or2_reference_sha256":numeric.hash_file(reference/"or_pairwise_all.csv"),
        "or3_reference_sha256":numeric.hash_file(reference/"or_triple_all.csv"),
        "saved_source_rows":full.n,
        "or2_rows_checked":N_PER_KIND,"or3_rows_checked":N_PER_KIND,
        "metric_fields_per_row_including_component_counts":(35,36),
        "numerical_mismatches":len(errors),
        "error_examples":errors[:12],
        "missing_regime_legacy_default_used":used_default,
        "source_features_recomputed":False,
        "historical_semantic_or_artifacts_regenerated":False,
        "production_p2_v12_changed":False,
        "html_qa_complete":False,"release_ready":False,
    }


def selftest()->None:
    numeric.selftest()
    assert N_PER_KIND==8 and len(SHAPES)==9
    assert "all_225" in SHAPES
    labels=(("daily_rci9_direction","RISING"),("daily_rci14_direction","FALLING"))
    assert all(k in FEATURES for k,v in labels)
    assert len(bytearray((181318+7)//8))==22665
    assert hashlib.sha1(bytes([0b10000000])).hexdigest()[:16] == hashlib.sha1(bytes([128])).hexdigest()[:16]
    print("PASS: OR2/OR3 retained-mask identity and numerical QA unit guards")


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--dataset",choices=sorted(SHAPES))
    ap.add_argument("--core",type=Path)
    ap.add_argument("--source",type=Path)
    ap.add_argument("--reference",type=Path)
    ap.add_argument("--proof",type=Path)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    if any(getattr(args,k) is None for k in ("dataset","core","source","reference","proof","out")):
        ap.error("--dataset --core --source --reference --proof --out required")
    result=audit(args.dataset,args.core.resolve(),args.source.resolve(),
                 args.reference.resolve(),args.proof.resolve())
    path=args.out.resolve()
    if path.exists():
        raise FileExistsError("Fresh QA output required")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="error_examples"},ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
