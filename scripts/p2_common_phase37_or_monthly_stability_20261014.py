# Created: 2026-10-14 JST
"""Phase37: bounded OR ranked-candidate monthly stability parity.

Consumes only immutable previously saved ranked candidate rows (Phase36
rank-selection proof) and pinned original signal-level features. Builds
one mask per previously unverified candidate and runs canonical _add_stability
on no more than 10 rows. Never recalculates prior successful OR raw,
unique dedupe, OR ranking, feature extraction, or HTML. JSON evidence only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS = ("technology", "financials", "consumer_goods", "materials",
          "capital_goods_others", "transportation_utilities")
EXCLUSIONS = {
    "exclude_capital_goods_transportation_utilities":
        (137426,170,"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"),
    "exclude_transportation_utilities":
        (166470,205,"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"),
}
DATASETS = GROUPS + tuple(EXCLUSIONS)
TOTALS = {
    "technology":60,"financials":75,"consumer_goods":60,
    "materials":60,"capital_goods_others":60,"transportation_utilities":61,
    "exclude_capital_goods_transportation_utilities":60,
    "exclude_transportation_utilities":60,
}
WIDTH = 10
PRIOR_STATUS = "PASS_PHASE36_OR_CANDIDATE_RANK_SELECTION"


def selftest() -> None:
    assert set(DATASETS)==set(TOTALS) and len(DATASETS)==8
    assert WIDTH==10 and len(SHA)==40
    assert sum(min(WIDTH,75-i) for i in range(0,75,WIDTH))==75
    print("PASS_PHASE37_DISJOINT_RANKED_OR_MONTHLY_SCOPE")


def verify(core:Path, ref:Path, sources:Path, proof4:Path,
           proof36:Path, dataset:str, offset:int)->dict:
    if dataset not in DATASETS or offset<0 or offset%WIDTH or offset>=TOTALS[dataset]:
        raise ValueError("Unauthorized dataset/candidate shard")
    if subprocess.check_output(
        ["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=SHA:
        raise ValueError("Original Private core SHA changed")
    expected=(core/"preview/kabu/analysis"/
        ("225_group_all_period" if dataset in GROUPS
         else "225_exclusion_all_period")/dataset).resolve()
    if ref!=expected:
        raise ValueError("Old reference folder not canonical")
    if dataset in GROUPS:
        src=ref/"signal_level_features.csv"
    else:
        files=list(sources.rglob("features.csv"))
        if len(files)!=1:raise ValueError("Immutable excluded original feature artifact missing")
        src=files[0]

    sys.path.insert(0,str(core/"scripts"))
    import numpy as np
    import pandas as pd
    import analyze_p2_or_combinations as canonical
    import build_p2_225_or_bundle as common
    import finalize_p2_nikkei_complete_baseline as fin
    from p2_html_core.p03_common_analysis_plan import digest

    orig_sha=digest(src)
    p4=json.loads(proof4.read_text(encoding="utf-8"))
    if dataset in GROUPS:
        record=(p4.get("groups") or {}).get(dataset) or {}
        rows,tickers=record.get("row_count"),record.get("ticker_count")
        if (p4.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION"
            or record.get("csv_sha256")!=orig_sha
            or record.get("duplicate_ids") is not False
            or not isinstance(rows,int) or rows<=0
            or not isinstance(tickers,int) or tickers<=0):
            raise ValueError("Immutable old sector source proof invalid")
    else:
        rows,tickers,expected_sha=EXCLUSIONS[dataset]
        record=p4.get("saved_exclusion") or {}
        if (p4.get("status")!="PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE"
            or p4.get("variant")!=dataset or orig_sha!=expected_sha
            or record.get("csv_sha256")!=orig_sha
            or record.get("row_count")!=rows or record.get("ticker_count")!=tickers
            or record.get("duplicate_ids") is not False):
            raise ValueError("Immutable exclusion source proof invalid")
    rank=json.loads(proof36.read_text(encoding="utf-8"))
    if (rank.get("status")!=PRIOR_STATUS or rank.get("dataset")!=dataset
        or rank.get("private_core_sha")!=SHA
        or rank.get("pinned_source_sha256")!=orig_sha
        or rank.get("ranked_candidates")!=TOTALS[dataset]
        or rank.get("original_candidate_rows")!=TOTALS[dataset]
        or rank.get("numeric_or_label_mismatches")!=[]
        or rank.get("new_monthly_stability_calculated") is not False):
        raise ValueError("Pinned prior ranking proof missing or mismatched")

    old_path=ref/"or_candidate_summary.csv"
    old_sha=digest(old_path)
    if old_sha!=rank.get("or_candidate_original_sha256"):
        raise ValueError("Old OR candidate CSV drift after prior ranking proof")
    old=pd.read_csv(old_path,low_memory=False)
    allcols=list(old.columns)
    if len(old)!=TOTALS[dataset] or old["condition_key"].duplicated().any():
        raise ValueError("Old original ranked candidates invalid")
    if "total_months" not in allcols:
        raise ValueError("Original OR stability output boundary missing")
    start=allcols.index("total_months")
    stability=allcols[start:]
    if len(stability)<15:
        raise ValueError("Incomplete original monthly metrics")
    shard=old.iloc[offset:offset+WIDTH].copy()
    if shard.empty:
        raise ValueError("Empty unverified original monthly shard")
    frame=common.prepare_frame(src)
    if len(frame)!=rows or frame["ticker"].astype(str).nunique()!=tickers:
        raise ValueError("Original source rows and tickers changed")
    feature_masks=fin._feature_masks(frame)
    scoped=shard[allcols[:start]].copy()
    unions=[]
    for _,item in scoped.iterrows():
        n=int(item["component_count"])
        if n not in (2,3) or item["condition_type"]!=f"or{n}":
            raise ValueError("Noncanonical selected OR candidate type")
        members=[]
        seen=set()
        for i in range(1,n+1):
            key=(str(item[f"feature{i}"]),str(item[f"category{i}"]))
            if key in seen or key not in feature_masks:
                raise ValueError("Unknown or repeated original candidate feature")
            seen.add(key)
            members.append(np.asarray(feature_masks[key],dtype=bool))
        mask=np.logical_or.reduce(members)
        if canonical._mask_hash(mask)!=str(item["mask_hash"]):
            raise ValueError("Ranked OR union does not match original saved mask hash")
        unions.append(mask)
    scoped["_mask"]=unions
    computed=canonical._csv_ready(canonical._add_stability(frame,scoped))
    if list(computed.columns)!=allcols:
        raise ValueError("Canonical monthly output column order differs")
    actual=computed.reset_index(drop=True)
    expected=shard.reset_index(drop=True)
    failures=[]
    if not actual["condition_key"].equals(expected["condition_key"]):
        failures.append("candidate_keys_or_order")
    if not failures:
        try:
            pd.testing.assert_frame_equal(
                expected[stability],actual[stability],check_dtype=False,
                check_exact=False,atol=1e-7,rtol=1e-10,check_index_type=False)
        except AssertionError:
            failures.append("monthly_or_yearly_stability_numbers")
    if digest(src)!=orig_sha or digest(old_path)!=old_sha:
        raise ValueError("Original source or saved candidate CSV mutated during audit")
    ids=actual["condition_key"].astype(str).tolist()
    return {
        "schema":1,
        "status":("PASS_PHASE37_NEW_OR_MONTHLY_STABILITY_SHARD" if not failures else
                  "FAIL_PHASE37_NEW_OR_MONTHLY_STABILITY_SHARD"),
        "dataset":dataset,"private_core_sha":SHA,
        "original_source_sha256":orig_sha,
        "old_candidate_sha256":old_sha,
        "candidate_offset":offset,"candidate_rows":len(actual),
        "total_candidate_rows":len(old),
        "candidate_key_hashes":[hashlib.sha256(k.encode("utf-8")).hexdigest() for k in ids],
        "monthly_fields_compared":len(stability),
        "mismatches":failures,"canonical_new_stability_called":True,
        "previous_rank_recalculated":False,
        "previous_OR_raw_or_unique_recalculated":False,
        "previous_artifacts_recomputed":False,
        "original_signals_recomputed":False,
        "original_files_modified":False,
        "production_changed":False,"html_generated":False,"release_ready":False,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--dataset",choices=DATASETS)
    ap.add_argument("--offset",type=int)
    for n in ("core","reference","source-root","proof4","proof36","report"):
        ap.add_argument("--"+n,type=Path)
    a=ap.parse_args()
    if a.selftest:
        selftest();return 0
    if any(getattr(a,x) is None for x in
           ("dataset","offset","core","reference","source_root","proof4","proof36","report")):
        ap.error("Pinned original source, proof and output required")
    if a.report.exists():
        raise FileExistsError("Never overwrite successful audit")
    result=verify(a.core.resolve(),a.reference.resolve(),a.source_root.resolve(),
                  a.proof4.resolve(),a.proof36.resolve(),a.dataset,a.offset)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in (
        "candidate_key_hashes","original_source_sha256","old_candidate_sha256")},
        ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
