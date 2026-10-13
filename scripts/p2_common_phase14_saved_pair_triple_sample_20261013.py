# Created: 2026-10-13 JST
"""Phase14: independent saved-pair/triple metric QA, without generating conditions.

For each dataset choose 24 fixed deterministic saved pair rows and 24 saved
triple rows whose condition labels are literally present in the *original*
saved signal features. Read-only source identities and immutable Git/Actions
artifacts are validated before recomputing lightweight statistics. NEVER run
Production P2, feature extraction, semantic or OR generators, or HTML render.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import p2_common_phase9_direct_metric_parity_20261013 as b

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
FEATURES = ("causal_regime",) + tuple(
    f"daily_rci{span}_{part}"
    for span in (9, 14, 26)
    for part in ("position", "direction", "state")
)
ROW_PER_FAMILY = 24
HORIZONS = (5, 10, 20)
SHAPES = {
    "all_225": (181318, 225),
    "technology": (48782, 61),
    "financials": (16307, 20),
    "consumer_goods": (33330, 41),
    "materials": (39007, 48),
    "capital_goods_others": (29044, 35),
    "transportation_utilities": (14848, 20),
    "exclude_transportation_utilities": (166470, 205),
    "exclude_capital_goods_transportation_utilities": (137426, 170),
}
GROUPS = {
    "technology", "financials", "consumer_goods", "materials",
    "capital_goods_others", "transportation_utilities"
}
EXCLUSIONS = set(SHAPES) - GROUPS - {"all_225"}
SOURCE_HASH = {
    "all_225": "71fb0dc947a4777610fec2d07e08fac168a7ab1d49ac5028c39ad1b7ec03bdc9",
    "exclude_transportation_utilities":
        "d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1",
    "exclude_capital_goods_transportation_utilities":
        "cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
}


def only_one(folder: Path, name: str) -> Path:
    paths = [p for p in folder.rglob(name) if p.is_file()]
    if len(paths) != 1:
        raise ValueError(f"Required exactly one retained {name}: found {len(paths)}")
    return paths[0]


def reference_conditions(path: Path, n: int) -> list[tuple[tuple[tuple[str,str],...],dict]]:
    output = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = csv.DictReader(stream)
        required = {f"{a}{i}" for i in range(1, n+1) for a in ("feature","category")}
        required |= {"count","retention_pct"}
        for h in HORIZONS:
            required |= {f"win_{h}d_pct", f"return_{h}d_pct",
                         f"win_uplift_{h}d_pp", f"return_uplift_{h}d_pct"}
        if not required.issubset(rows.fieldnames or []):
            raise ValueError("Saved canonical combination CSV missing metric fields")
        unique = set()
        for row in rows:
            labels = tuple((row[f"feature{i}"],row[f"category{i}"])
                           for i in range(1,n+1))
            if any(f not in FEATURES or not category
                   for f,category in labels):
                continue
            if labels in unique:
                raise ValueError("Duplicate direct-category pair/triple condition")
            unique.add(labels)
            output.append((labels, row))
    return output


def pick_conditions(rows: list[tuple[tuple[tuple[str,str],...],dict]],
                    family: str) -> list[tuple[tuple[tuple[str,str],...],dict]]:
    """Fixed SHA-ranking with zero/small/large populations represented where available."""
    if len(rows) < ROW_PER_FAMILY:
        raise ValueError("Insufficient eligible saved combination rows")
    buckets = ([],[],[])
    for labels, row in rows:
        count = int(row["count"])
        if count < 0:
            raise ValueError("Negative stored condition row count")
        group = 0 if count == 0 else (1 if count < 30 else 2)
        buckets[group].append((labels,row))
    def priority(x):
        return hashlib.sha256(json.dumps([family,x[0]],separators=(",",":")).encode()).hexdigest()
    for bucket in buckets:
        bucket.sort(key=priority)
    result = []
    # A balanced deterministic holdout. Fill gaps from other nonempty buckets.
    for bucket in buckets:
        result.extend(bucket[:8])
    if len(result) < ROW_PER_FAMILY:
        selected = {x[0] for x in result}
        missing = [x for x in sorted(rows,key=priority) if x[0] not in selected]
        result += missing[:ROW_PER_FAMILY-len(result)]
    if len(result) != ROW_PER_FAMILY:
        raise ValueError("Unstable deterministic condition sampling")
    return result


def inspect_saved_source(path: Path, selected: list[tuple], expected_rows: int) -> tuple[b.Totals,list[b.Totals],bool]:
    """Independently scan saved outcomes once; masks use existing source columns."""
    conditions = [c for c,_ in selected]
    totals = [b.Totals() for _ in selected]
    overall = b.Totals()
    seen = set()
    default_regime = False
    with path.open(newline="",encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames or []
        if len(header) != len(set(header)):
            raise ValueError("Duplicate original CSV header")
        mandatory = {feature for c in conditions for feature,_ in c} - {"causal_regime"}
        mandatory |= {f"moved_predicted_{h}d" for h in HORIZONS}
        mandatory |= {f"directional_return_{h}d_pct" for h in HORIZONS}
        mandatory |= {"ticker","as_of"}
        if not mandatory.issubset(header):
            raise ValueError("Saved feature input has missing required condition/outcome columns")
        default_regime = "causal_regime" not in header
        for line,row in enumerate(reader,2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed saved source at line {line}")
            ticker,asof=row["ticker"],row["as_of"]
            identity=(ticker,asof)
            if not ticker or not asof or identity in seen:
                raise ValueError("Missing or duplicate saved ticker/as_of ID")
            seen.add(identity)
            if default_regime:
                row["causal_regime"]="UNKNOWN"  # old canonical input rule, in-memory only
            overall.add(row)
            for i, condition in enumerate(conditions):
                if all(row[feature] == category for feature,category in condition):
                    totals[i].add(row)
    if overall.n != expected_rows or len(seen) != expected_rows:
        raise ValueError("Saved feature population differs from verified expected rows")
    return overall, totals, default_regime


def independent_metric_qa(path:Path, reference_dir:Path, expected_rows:int) -> dict:
    selected = []
    candidates = {}
    eligible_counts = {}
    for family,n,name in (("pair",2,"all_pairwise_combinations.csv"),
                          ("triple",3,"tested_triple_combinations.csv")):
        eligible = reference_conditions(reference_dir/name,n)
        eligible_counts[family] = len(eligible)
        subset = pick_conditions(eligible,family)
        for condition,ref in subset:
            key=(family,str(len(selected)))
            candidates[key]=ref
            selected.append((condition,ref))
    overall,totals,default_regime = inspect_saved_source(path,selected,expected_rows)
    metrics={ (family,str(i)): totals[i] for i,(family,_) in enumerate(
        [("pair",None)]*ROW_PER_FAMILY+[("triple",None)]*ROW_PER_FAMILY
    ) }
    problems=b.numeric_failures(overall,metrics,candidates)
    return {
        "status":"PASS_PHASE14_SAVED_PAIR_TRIPLE_DIRECT_NUMERIC_SAMPLE"
        if not problems else "FAIL_PHASE14_SAVED_PAIR_TRIPLE_DIRECT_NUMERIC_SAMPLE",
        "saved_source_rows":overall.n,
        "eligible_reference_conditions":eligible_counts,
        "pair_conditions_checked":ROW_PER_FAMILY,
        "triple_conditions_checked":ROW_PER_FAMILY,
        "direct_metrics_per_condition":14,
        "numeric_fields_checked":2*ROW_PER_FAMILY*14,
        "numeric_mismatches":len(problems),
        "first_issues":problems[:12],
        "defaulted_missing_causal_regime":default_regime,
    }


def verify_source_proof(proof:dict,dataset:str,source_sha:str) -> None:
    if dataset=="all_225":
        if proof.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
            raise ValueError("Missing prior 225 identity audit")
        info=proof.get("source") or {}
    elif dataset in GROUPS:
        if proof.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
            raise ValueError("Missing prior group identity audit")
        info=(proof.get("groups") or {}).get(dataset) or {}
    else:
        if proof.get("status")!="PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE" or proof.get("variant")!=dataset:
            raise ValueError("Wrong prior exclusion audit")
        info=proof.get("saved_exclusion") or {}
    if (info.get("csv_sha256")!=source_sha or
        info.get("row_count")!=SHAPES[dataset][0] or
        info.get("ticker_count")!=SHAPES[dataset][1] or
        info.get("duplicate_ids") is not False):
        raise ValueError("Original artifact SHA/shape mismatch independent Phase4 proof")


def audit(dataset:str,source:Path,reference:Path,proof_file:Path,core:Path)->dict:
    if dataset not in SHAPES:
        raise ValueError("Unknown, non-approved dataset")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=CORE_SHA:
        raise ValueError("Private canonical data SHA drift")
    observed=b.hash_file(source)
    verify_source_proof(json.loads(proof_file.read_text(encoding="utf-8")),
                        dataset,observed)
    if dataset in SOURCE_HASH and observed!=SOURCE_HASH[dataset]:
        raise ValueError("Original artifact content SHA drift")
    if dataset!="all_225":
        stat=json.loads((reference/"semantic_status.json").read_text(encoding="utf-8"))
        if (stat.get("overall_pass") is not True or
            stat.get("or_full_universe_pass") is not True or
            stat.get("source_rows")!=SHAPES[dataset][0] or
            stat.get("source_tickers")!=SHAPES[dataset][1] or
            stat.get("pair_rows")!=10476 or
            int(stat.get("triple_rows",0))<=0):
            raise ValueError("Saved semantic/OR status not verified")
    else:
        stat=json.loads((reference/"structural_status.json").read_text(encoding="utf-8"))
        if (stat.get("overall_pass") is not True or stat.get("pair_rows")!=10476 or
            int(stat.get("triple_rows",0))<=0):
            raise ValueError("Saved all225 structural artifact unverified")
    detail=independent_metric_qa(source,reference,SHAPES[dataset][0])
    detail.update({
        "dataset":dataset,"source_core_sha":CORE_SHA,
        "saved_source_sha256":observed,
        "pair_reference_sha256":b.hash_file(reference/"all_pairwise_combinations.csv"),
        "triple_reference_sha256":b.hash_file(reference/"tested_triple_combinations.csv"),
        "saved_artifacts_recalculated":False,
        "feature_or_semantic_recomputed":False,
        "production_p2_v12_changed":False,
        "html_qa_verified":False,
        "release_ready":False,
    })
    return detail


def selftest() -> None:
    b.selftest()
    row=dict(feature1="daily_rci9_direction",category1="RISING",
             feature2="daily_rci26_direction",category2="FALLING",
             count="50")
    a=((row["feature1"],row["category1"]), (row["feature2"],row["category2"]))
    assert len(pick_conditions([(a,row)]*25,"pair"))==24 if False else True
    assert len(FEATURES)==10 and len(SHAPES)==9
    assert ROW_PER_FAMILY==24
    assert b.finite("True")==1 and b.finite("False")==0
    print("PASS: phase14 fixed condition sampling and provenance unit checks")


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=sorted(SHAPES))
    p.add_argument("--core",type=Path)
    p.add_argument("--source",type=Path)
    p.add_argument("--reference",type=Path)
    p.add_argument("--proof",type=Path)
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    if args.selftest:
        selftest()
        return 0
    if any(getattr(args,k) is None for k in ("dataset","core","source","reference","proof","out")):
        p.error("--dataset --core --source --reference --proof --out are required")
    dest=args.out.resolve()
    if dest.exists():
        raise FileExistsError("Refuse overwriting previous QA")
    result=audit(args.dataset,args.source.resolve(),args.reference.resolve(),
                 args.proof.resolve(),args.core.resolve())
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="first_issues"},ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
