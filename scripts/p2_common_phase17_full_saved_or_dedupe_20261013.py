# Created: 2026-10-13 JST
"""Phase17: independent full saved OR2/OR3 dedupe equivalence QA.

Read-only comparison of entire already-saved original OR raw and unique CSVs.
Do not recalculate signals, OR union masks, new semantic results, HTML, or
successful historical artifacts. Compare mask identities, deterministic
canonical representative choice, equivalent-logic count and key metrics.
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

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASETS=("all_225","technology","financials","consumer_goods","materials",
          "capital_goods_others","transportation_utilities",
          "exclude_transportation_utilities",
          "exclude_capital_goods_transportation_utilities")
FAMILIES=(("or2","or_pairwise_all.csv","or_pairwise_unique.csv"),
          ("or3","or_triple_all.csv","or_triple_unique.csv"))
METRICS=("win_5d_pct","win_10d_pct","win_20d_pct",
         "return_5d_pct","return_10d_pct","return_20d_pct",
         "accuracy_core_pct","balance_index","avg_uplift_pp")


def rows(file:Path)->list[dict[str,str]]:
    with file.open("r",encoding="utf-8-sig",newline="") as stream:
        reader=csv.DictReader(stream)
        fields=reader.fieldnames or []
        required={"mask_hash","condition_key","component_count","count",
                  "avg_win_pct","condition_label"}|set(METRICS)
        if len(fields)!=len(set(fields)) or not required.issubset(fields):
            raise ValueError("Missing, duplicate or invalid original OR header: "+file.name)
        out=[]
        for line,r in enumerate(reader,2):
            if None in r or any(v is None for v in r.values()):
                raise ValueError(f"Malformed saved OR CSV {file.name} line {line}")
            if not r["mask_hash"] or not r["condition_key"]:
                raise ValueError("Original OR row has blank identity fields")
            out.append(r)
    if not out:
        raise ValueError("Original OR file is empty: "+file.name)
    return out


def rank(item:tuple[int,dict])->tuple:
    idx,r=item
    return (int(r["component_count"]),
            -int(r["count"]),
            -float(r["avg_win_pct"]),
            r["condition_label"],
            idx)


def equal_float(old:str,new:str)->bool:
    try:
        x,y=float(old),float(new)
        if math.isnan(x) and math.isnan(y):
            return True
        return math.isfinite(x) and math.isfinite(y) and abs(x-y)<=1e-8
    except (ValueError,TypeError):
        return old==new


def audit_family(folder:Path,kind:str,raw_file:str,unique_file:str)->dict:
    raw=rows(folder/raw_file)
    unique=rows(folder/unique_file)
    buckets={}
    for idx,r in enumerate(raw):
        if int(r["component_count"])!=(2 if kind=="or2" else 3):
            raise ValueError("Wrong original OR component count")
        buckets.setdefault(r["mask_hash"],[]).append((idx,r))
    seen=set()
    matched=0
    original_order=list(buckets)
    if len(unique)!=len(buckets):
        raise ValueError("Saved OR unique row count != number of raw mask hashes")
    if [r["mask_hash"] for r in unique]!=sorted(buckets):
        raise ValueError("Saved OR dedupe output mask order mismatch")
    for u in unique:
        h=u["mask_hash"]
        if h in seen:
            raise ValueError("OR unique output contains duplicate mask hash")
        seen.add(h)
        candidates=buckets[h]
        choice=min(candidates,key=rank)[1]
        # Canonical source uses stable sorting on: mask_hash, component_count,
        # descending count, descending avg_win_pct, condition_label.
        if choice["condition_key"]!=u["condition_key"]:
            raise ValueError("Saved OR selected canonical representative differs")
        if int(u.get("equivalent_logic_count") or -1)!=len(candidates):
            raise ValueError("Saved OR equivalent_logic_count mismatch")
        for field in ("component_count","count")+METRICS:
            if field in ("component_count","count"):
                if int(choice[field])!=int(u[field]):
                    raise ValueError(f"Saved OR integer field changed: {field}")
            elif not equal_float(choice[field],u[field]):
                raise ValueError(f"Saved OR representative numeric mismatch: {field}")
            matched+=1
    return {"family":kind,"raw_rows":len(raw),"unique_rows":len(unique),
            "distinct_masks":len(buckets),"representatives":len(seen),
            "identity_numeric_fields_checked":matched,
            "raw_csv_sha256":hash_file(folder/raw_file),
            "unique_csv_sha256":hash_file(folder/unique_file)}


def hash_file(file:Path)->str:
    digest=hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1048576),b""):
            digest.update(chunk)
    return digest.hexdigest()


def selftest():
    assert rank((0,{"component_count":"2","count":"10","avg_win_pct":"50",
                    "condition_label":"A"})) < rank(
           (1,{"component_count":"2","count":"9","avg_win_pct":"51",
               "condition_label":"Z"}))
    assert equal_float("52.0","52.00000000001")
    assert not equal_float("51","52")
    assert equal_float("nan","nan")
    print("PASS Phase17 dedupe original-row ranking numeric guards")


def audit(dataset:str,core:Path,reference:Path)->dict:
    if dataset not in DATASETS:
        raise ValueError("Unapproved dataset")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=CORE_SHA:
        raise ValueError("Pinned canonical source SHA mismatch")
    state_name="or_status.json" if dataset=="all_225" else "semantic_status.json"
    status=json.loads((reference/state_name).read_text(encoding="utf-8"))
    if status.get("overall_pass") is not True:
        raise ValueError("Original prior analysis not PASS")
    if dataset!="all_225" and status.get("or_full_universe_pass") is not True:
        raise ValueError("Saved full OR universe not certified")
    results=[audit_family(reference,*family) for family in FAMILIES]
    for r in results:
        n=2 if r["family"]=="or2" else 3
        raw_key=f"or{n}_raw" if dataset=="all_225" else f"or{n}_raw_rows"
        uniq_key=f"or{n}_unique" if dataset=="all_225" else f"or{n}_unique_rows"
        if status.get(raw_key)!=r["raw_rows"] or status.get(uniq_key)!=r["unique_rows"]:
            raise ValueError("Status counter differs from independently checked OR file")
    return {"schema":1,"dataset":dataset,"source_core_sha":CORE_SHA,
            "status":"PASS_PHASE17_FULL_SAVED_OR_DEDUPE_ONLY","families":results,
            "total_raw_rows":sum(x["raw_rows"] for x in results),
            "total_unique_rows":sum(x["unique_rows"] for x in results),
            "saved_or_recomputed":False,"saved_signals_recomputed":False,
            "production_p2_v12_changed":False,"html_qa_verified":False,
            "release_ready":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--core",type=Path)
    p.add_argument("--reference",type=Path)
    p.add_argument("--dataset",choices=DATASETS)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not all((a.core,a.reference,a.dataset,a.out)):
        p.error("--core --reference --dataset --out required")
    dest=a.out.resolve()
    if dest.exists():
        raise FileExistsError("Cannot overwrite prior audit evidence")
    result=audit(a.dataset,a.core.resolve(),a.reference.resolve())
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="families"},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
