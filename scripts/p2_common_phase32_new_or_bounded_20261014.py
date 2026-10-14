# Created: 2026-10-14 JST
"""Phase32 bounded NEW common OR producer numeric parity for all eight datasets.

Only OR2/OR3 rows with at least one component feature OUTSIDE the fixed
Phase14/15/21/23/24 audited feature set are eligible. Disjoint selection
avoids recalc of prior successful saved OR conditions. New canonical
_combo_metrics is applied to four OR2 and four OR3 saved rows; no _build_all,
no full OR/semantic/HTML/production output and no raw row publication.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUSIONS={
 "exclude_capital_goods_transportation_utilities":
    (137426,170,"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"),
 "exclude_transportation_utilities":
    (166470,205,"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"),
}
DATASETS=GROUPS+tuple(EXCLUSIONS)
PREV_FEATURES={"causal_regime"}|{
    f"daily_rci{span}_{part}" for span in (9,14,26)
    for part in ("position","direction","state")
}
FAMILIES=((2,"or_pairwise_all.csv"),(3,"or_triple_all.csv"))
PER_KIND=4
P31_STATUS="PASS_PHASE31_NEW_TRIPLE_DISJOINT_SHARD"


def selftest():
    assert len(DATASETS)==8 and len(PREV_FEATURES)==10
    assert FAMILIES==((2,"or_pairwise_all.csv"),(3,"or_triple_all.csv"))
    assert PER_KIND==4
    assert "fan" not in PREV_FEATURES and "weekly_rci9" not in PREV_FEATURES
    print("PASS_PHASE32_NEW_UNCERTIFIED_OR_COMPONENT_SCOPE")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def choose_rows(reference, eligible_labels):
    chosen=[]
    for n,filename in FAMILIES:
        with (reference/filename).open(encoding="utf-8-sig",newline="") as h:
            reader=csv.DictReader(h)
            required={"condition_key","condition_type","count","mask_hash"}|{
                f"{k}{i}" for i in range(1,n+1)
                for k in ("feature","category")
            }
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("Original OR CSV header incomplete")
            possible=[]
            seen=set()
            for row in reader:
                labels=tuple((row[f"feature{i}"],row[f"category{i}"])
                             for i in range(1,n+1))
                if labels in seen:
                    raise ValueError("Duplicate OR condition labels in original")
                seen.add(labels)
                if not all(pair in eligible_labels for pair in labels):
                    continue
                if all(feature in PREV_FEATURES for feature,_ in labels):
                    continue
                if row["condition_type"] != f"or{n}":
                    raise ValueError("Mismatched saved OR category kind")
                possible.append((n,labels,row))
        possible.sort(key=lambda x:hashlib.sha256(
            json.dumps([x[0],x[1]],separators=(",",":"),
                       ensure_ascii=False).encode("utf-8")).hexdigest())
        if len(possible)<PER_KIND:
            raise ValueError("Insufficient unseen canonical new OR component combinations")
        chosen.extend(possible[:PER_KIND])
    if len(chosen)!=2*PER_KIND:
        raise ValueError("Unexpected OR canary selection count")
    return chosen


def verify(core,reference,source_dir,proof4,phase31,dataset):
    if dataset not in DATASETS:
        raise ValueError("Dataset not approved for scoped OR audit")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=CORE_SHA:
        raise ValueError("Wrong pinned Private core SHA")
    expected_dir=(core/"preview/kabu/analysis"/
        ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
        dataset).resolve()
    if reference!=expected_dir:
        raise ValueError("Unapproved reference directory")
    if dataset in GROUPS:
        source=reference/"signal_level_features.csv"
    else:
        sources=list(source_dir.rglob("features.csv"))
        if len(sources)!=1:
            raise ValueError("Missing exactly one original exclusion feature artifact")
        source=sources[0]
    sys.path.insert(0,str(core/"scripts"))
    import analyze_p2_or_combinations as canonical
    import build_p2_225_or_bundle as common
    import finalize_p2_nikkei_complete_baseline as fin
    from p2_html_core.p03_common_analysis_plan import digest
    import p2_common_phase21_new_or_bounded_20261013 as comparison

    sha=digest(source)
    p4=read_json(proof4)
    if dataset in GROUPS:
        info=(p4.get("groups") or {}).get(dataset) or {}
        rows,tickers=info.get("row_count"),info.get("ticker_count")
        if (p4.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION"
            or info.get("csv_sha256")!=sha or info.get("duplicate_ids") is not False
            or not isinstance(rows,int) or not isinstance(tickers,int)
            or rows<=0 or tickers<=0):
            raise ValueError("Saved group Phase4 source identity mismatch")
    else:
        rows,tickers,old_sha=EXCLUSIONS[dataset]
        info=p4.get("saved_exclusion") or {}
        if (p4.get("status")!="PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE"
            or p4.get("variant")!=dataset or sha!=old_sha
            or info.get("csv_sha256")!=sha or info.get("row_count")!=rows
            or info.get("ticker_count")!=tickers or info.get("duplicate_ids") is not False):
            raise ValueError("Saved exclusion Phase4 identity mismatch")

    passed=read_json(phase31)
    if (passed.get("status")!=P31_STATUS or passed.get("dataset")!=dataset
        or passed.get("source_sha256")!=sha
        or passed.get("private_core_sha")!=CORE_SHA
        or passed.get("feature_first_start")!=0
        or passed.get("numerical_errors")!=[]
        or passed.get("previous_artifacts_recalculated") is not False):
        raise ValueError("Required Phase31 source-bound triple certification missing")

    original_status=read_json(reference/"semantic_status.json")
    if (original_status.get("overall_pass") is not True
        or original_status.get("or_full_universe_pass") is not True
        or original_status.get("source_rows")!=rows
        or original_status.get("source_tickers")!=tickers):
        raise ValueError("Immutable original OR reference status not certified")

    raw_hashes={name:digest(reference/name) for _,name in FAMILIES}
    saved_single_hash=digest(reference/"advantage_single_candidates.csv")
    original_status_hash=digest(reference/"semantic_status.json")
    f=common.prepare_frame(source)
    if len(f)!=rows or f["ticker"].astype(str).nunique()!=tickers:
        raise ValueError("Original saved source population changed")
    canonical.OUT=reference
    masks=fin._feature_masks(f)
    pool=canonical._component_pool(f,masks)
    lookup={(str(x["feature"]),str(x["category"])):x for x in pool}
    if len(lookup)!=len(pool):
        raise ValueError("Duplicate new canonical OR pool components")
    selected=choose_rows(reference,set(lookup))
    baseline=canonical._baseline(f)
    failures=[]
    checked_fields=0
    for index,(n,labels,old) in enumerate(selected):
        new=canonical._combo_metrics(f,f"or{n}",[lookup[x] for x in labels],baseline)
        errors=comparison.compare_new_with_original(old,new)
        checked_fields+=len(new)-1
        failures.extend({"index":index,"field":s} for s in errors)
    if (digest(source)!=sha or
        digest(reference/"advantage_single_candidates.csv")!=saved_single_hash or
        digest(reference/"semantic_status.json")!=original_status_hash or
        any(digest(reference/name)!=old_hash for name,old_hash in raw_hashes.items())):
        raise ValueError("Immutable original OR source or reference modified")
    return {
        "schema":1,
        "status":"PASS_PHASE32_NEW_UNSEEN_OR2_OR3_BOUNDED" if not failures else
                 "FAIL_PHASE32_NEW_UNSEEN_OR2_OR3_BOUNDED",
        "dataset":dataset,"source_sha256":sha,"private_core_sha":CORE_SHA,
        "source_rows":rows,"source_tickers":tickers,
        "new_or2_conditions":PER_KIND,"new_or3_conditions":PER_KIND,
        "numeric_fields_checked":checked_fields,"mismatch_count":len(failures),
        "first_errors":failures[:8],
        "original_or2_sha256":raw_hashes[FAMILIES[0][1]],
        "original_or3_sha256":raw_hashes[FAMILIES[1][1]],
        "new_canonical_combo_metrics_called":True,
        "already_certified_prior_or_conditions_recomputed":False,
        "previous_artifacts_recomputed":False,
        "full_or_bundle_generated":False,"full_semantic_bundle_generated":False,
        "historical_signals_recomputed":False,"html_generated":False,
        "production_changed":False,"release_ready":False
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    for name in ("core","reference","source-root","proof4","phase31","report"):
        p.add_argument("--"+name,type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest();return 0
    required=("dataset","core","reference","source_root","proof4","phase31","report")
    if any(getattr(a,z) is None for z in required):
        p.error("Pinned source, Phase4/31 evidence and new output report required")
    if a.report.exists():
        raise FileExistsError("Never overwrite old audit")
    d=verify(a.core.resolve(),a.reference.resolve(),a.source_root.resolve(),
             a.proof4.resolve(),a.phase31.resolve(),a.dataset)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in d.items() if k!="first_errors"},ensure_ascii=False))
    return 0 if d["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
