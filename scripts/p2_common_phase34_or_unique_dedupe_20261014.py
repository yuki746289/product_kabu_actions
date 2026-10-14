# Created: 2026-10-14 JST
"""Phase34 full canonical OR mask-hash deduplication parity from read-only saved raw.

No OR combination producer rerun, no extraction, no P2, no full OR candidate
recalculation. Recompute only the NEW common _dedupe comparison function
into an isolated QA stage and independently compare persisted unique CSVs.
Phase33 source-bound success proof and original raw SHA are mandatory.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUSIONS=("exclude_capital_goods_transportation_utilities",
            "exclude_transportation_utilities")
DATASETS=GROUPS+EXCLUSIONS
FAMILIES=(("or_pairwise_all.csv","or_pairwise_unique.csv"),
          ("or_triple_all.csv","or_triple_unique.csv"))
PREVIOUS="PASS_PHASE33_NEXT_UNSEEN_OR2_OR3_BOUNDED"


def selftest()->None:
    assert len(DATASETS)==8 and len(FAMILIES)==2 and len(SHA)==40
    assert all(raw!=unique and raw.endswith("_all.csv")
               and unique.endswith("_unique.csv") for raw,unique in FAMILIES)
    print("PASS_PHASE34_SAVED_RAW_TO_NEW_COMMON_DEDUPE_CONTRACT")


def verify(core:Path,reference:Path,proof33:Path,dataset:str,stage:Path)->dict:
    if dataset not in DATASETS:
        raise ValueError("Dataset outside certified Phase33 eight datasets")
    if subprocess.check_output(
            ["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=SHA:
        raise ValueError("Immutable Private core SHA changed")
    build=(core/"build").resolve()
    if (stage.exists() or stage.resolve()==build
        or not stage.resolve().is_relative_to(build)):
        raise ValueError("Fresh isolated Private build stage required")
    expected=(core/"preview/kabu/analysis"/
        ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")
        /dataset).resolve()
    if reference!=expected:
        raise ValueError("Reference directory/dataset binding invalid")
    prev=json.loads(proof33.read_text(encoding="utf-8"))
    if (prev.get("status")!=PREVIOUS or prev.get("dataset")!=dataset
        or prev.get("private_core_sha")!=SHA
        or prev.get("mismatch_count")!=0
        or prev.get("new_or2_conditions")!=8
        or prev.get("new_or3_conditions")!=8
        or prev.get("prior_phase32_new_or_recomputed") is not False
        or len(prev.get("source_sha256",""))!=64):
        raise ValueError("Original Phase33 numerical proof is not certified")

    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import analyze_p2_or_combinations as canonical
    from p2_html_core.p03_common_analysis_plan import digest

    status_path=reference/"semantic_status.json"
    status_sha=digest(status_path)
    status=json.loads(status_path.read_text(encoding="utf-8"))
    if (status.get("overall_pass") is not True
        or status.get("or_full_universe_pass") is not True
        or status.get("source_rows")!=prev.get("source_rows")
        or status.get("source_tickers")!=prev.get("source_tickers")):
        raise ValueError("Immutable saved original OR certification is invalid")

    original_hashes={}
    observed={}
    errors=[]
    stage.mkdir(parents=True,exist_ok=False)
    for raw_name,unique_name in FAMILIES:
        raw_path=reference/raw_name
        unique_path=reference/unique_name
        raw_sha=digest(raw_path)
        unique_sha=digest(unique_path)
        original_hashes[raw_name]=raw_sha
        original_hashes[unique_name]=unique_sha
        prior_key="original_or2_sha256" if raw_name=="or_pairwise_all.csv" else "original_or3_sha256"
        if prev.get(prior_key)!=raw_sha:
            raise ValueError("Original OR raw CSV hash changed since Phase33")
        raw=pd.read_csv(raw_path,low_memory=False)
        old=pd.read_csv(unique_path,low_memory=False)
        if (raw.empty or old.empty or
            "mask_hash" not in raw or
            "condition_key" not in raw or
            raw["condition_key"].duplicated().any() or
            old["mask_hash"].duplicated().any()):
            raise ValueError("Saved canonical OR raw/unique inputs are invalid")
        # EXACT original canonical dedupe function used by the common OR producer.
        fresh=canonical._csv_ready(canonical._dedupe(raw))
        if fresh.empty:
            raise ValueError("Unexpected empty unique OR output")
        generated=stage/unique_name
        fresh.to_csv(generated,index=False,encoding="utf-8")
        after=pd.read_csv(generated,low_memory=False)
        if old.shape!=after.shape or list(old.columns)!=list(after.columns):
            errors.append({"csv":unique_name,"kind":"header_or_shape"})
        else:
            try:
                pd.testing.assert_frame_equal(
                    old,after,check_dtype=False,check_exact=False,
                    atol=1e-7,rtol=1e-10,check_index_type=False)
            except AssertionError:
                errors.append({"csv":unique_name,"kind":"keys_numeric_order_or_flags"})
        if len(after)!=raw["mask_hash"].nunique():
            errors.append({"csv":unique_name,"kind":"unique_mask_cardinality"})
        if "equivalent_logic_count" not in after:
            errors.append({"csv":unique_name,"kind":"missing_equivalent_logic_count"})
        observed[unique_name]={
            "original_raw_rows":int(len(raw)),
            "original_unique_rows":int(len(old)),
            "new_unique_rows":int(len(after)),
            "new_columns":len(after.columns),
            "raw_mask_hash_count":int(raw["mask_hash"].nunique()),
            "original_raw_sha256":raw_sha,
            "original_unique_sha256":unique_sha,
            "new_unique_sha256":digest(generated)
        }
    if digest(status_path)!=status_sha or any(
            digest(reference/name)!=sha for name,sha in original_hashes.items()):
        raise ValueError("Original saved OR inputs mutated during QA")
    return {
        "schema":1,
        "status":("PASS_PHASE34_FULL_OR2_OR3_DEDUPE_NUMERIC_PARITY" if not errors
                  else "FAIL_PHASE34_FULL_OR2_OR3_DEDUPE_NUMERIC_PARITY"),
        "dataset":dataset,"private_core_sha":SHA,
        "original_source_sha256":prev["source_sha256"],
        "verified":observed,"mismatches":errors,
        "new_common_dedupe_function_called":True,
        "previous_certified_raw_or_producers_rerun":False,
        "source_features_recomputed":False,
        "successful_artifacts_recomputed":False,
        "full_or_bundle_generated":False,
        "original_files_modified":False,
        "html_generated":False,"production_changed":False,"release_ready":False,
    }


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    for arg in ("core","reference","proof33","stage","report"):
        p.add_argument("--"+arg,type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest()
        return 0
    if any(getattr(a,v) is None for v in ("dataset","core","reference","proof33","stage","report")):
        p.error("Pinned canonical inputs, certified Phase33, new stage and report required")
    if a.report.exists():
        raise FileExistsError("Previous numerical audit evidence must not be overwritten")
    d=verify(a.core.resolve(),a.reference.resolve(),a.proof33.resolve(),
             a.dataset,a.stage.resolve())
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":d["status"],"dataset":d["dataset"],
                      "verified":d["verified"],"mismatches":d["mismatches"]}))
    return 0 if d["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
