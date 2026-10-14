# Created: 2026-10-14 JST
"""Phase36: OR candidate ranking/selection parity from certified SAVED unique inputs.

No OR combination calculations, no existing-successful artifact regeneration,
no P2 extraction, no monthly recomputation, no private files modified.
Uses exact canonical selection and ranking code from common OR producer, and
checks ordered condition keys and all NON-monthly candidate columns against
immutable original or_candidate_summary.csv. Phase37 will separately check
NEW monthly stability for all saved ranked candidate rows.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUSIONS=("exclude_capital_goods_transportation_utilities",
            "exclude_transportation_utilities")
DATASETS=GROUPS+EXCLUSIONS
FILES=("or_pairwise_unique.csv","or_triple_unique.csv")
PREVIOUS="PASS_PHASE34_FULL_OR2_OR3_DEDUPE_NUMERIC_PARITY"
ORIGINAL="or_candidate_summary.csv"
SORTS=(
    ("balanced_candidate", ("balance_index","avg_win_pct","count")),
    ("expansion_candidate", ("balance_index","incremental_entries_vs_largest")),
    ("high_accuracy_candidate", ("avg_win_pct","count")),
)


def selftest():
    assert len(DATASETS)==8 and len(FILES)==2 and len(SORTS)==3
    assert sum(1 for x in SORTS if x[0]=="balanced_candidate")==1
    assert len(CORE_SHA)==40
    print("PASS_PHASE36_SAVED_UNIQUE_OR_RANKING_SCOPE")


def verify(core:Path,reference:Path,prior:Path,dataset:str)->dict:
    if dataset not in DATASETS:
        raise ValueError("Unapproved dataset")
    if subprocess.check_output(
          ["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=CORE_SHA:
        raise ValueError("Original Private SHA drift")
    expected=(core/"preview/kabu/analysis"/
       ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
       dataset).resolve()
    if reference!=expected:
        raise ValueError("Dataset reference folder not original")
    p=json.loads(prior.read_text(encoding="utf-8"))
    if (p.get("status")!=PREVIOUS or p.get("dataset")!=dataset
        or p.get("private_core_sha")!=CORE_SHA or p.get("mismatches")!=[]
        or p.get("new_common_dedupe_function_called") is not True
        or p.get("successful_artifacts_recomputed") is not False):
        raise ValueError("Phase34 original unique source-bound proof invalid")

    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import analyze_p2_or_combinations as common_or
    from p2_html_core.p03_common_analysis_plan import digest

    before={f:digest(reference/f) for f in FILES+(ORIGINAL,)}
    for filename in FILES:
        source=p.get("verified",{}).get(filename,{})
        if source.get("original_unique_sha256")!=before[filename]:
            raise ValueError("Saved original unique source changed since Phase34")
    pair, triple = (pd.read_csv(reference/name,low_memory=False) for name in FILES)
    if (pair.empty or triple.empty or
        pair["condition_key"].duplicated().any() or
        triple["condition_key"].duplicated().any()):
        raise ValueError("Original saved unique inputs incomplete or duplicate")
    combined=pd.concat([pair,triple],ignore_index=True,sort=False)
    if combined["condition_key"].duplicated().any():
        raise ValueError("OR2+OR3 unique candidates share keys")

    selections=[]
    selected_sizes={}
    for flag,order in SORTS:
        q=combined[combined[flag]].copy().sort_values(
            list(order),ascending=False).head(60)
        selected_sizes[flag]=len(q)
        selections.append(q)
    candidates=pd.concat(selections,ignore_index=True,sort=False)
    if candidates.empty:
        raise ValueError("Expected nonempty canonical candidate selection")
    candidates=candidates.drop_duplicates("condition_key",keep="first")
    saved=pd.read_csv(reference/ORIGINAL,low_memory=False)
    if saved.empty or saved["condition_key"].duplicated().any():
        raise ValueError("Saved canonical candidate summary empty or duplicate")
    # Compare all columns from old candidate summary that are not generated
    # by _add_stability. Stability starts with total_months.
    cols=list(saved.columns)
    if "total_months" not in cols:
        raise ValueError("Original OR ranking/stability boundary missing")
    rank_cols=cols[:cols.index("total_months")]
    if list(candidates.columns)!=rank_cols:
        raise ValueError("Original non-monthly output columns/order differ from new ranking")
    if saved.shape[0]!=candidates.shape[0]:
        raise ValueError("OR ranked candidate count changed")
    result=candidates.reset_index(drop=True)
    original=saved[rank_cols].reset_index(drop=True)
    failures=[]
    if not original["condition_key"].equals(result["condition_key"]):
        failures.append("ordered_condition_keys")
    if not original["condition_type"].equals(result["condition_type"]):
        failures.append("ordered_OR_kind")
    if not failures:
        try:
            pd.testing.assert_frame_equal(
                original,result,check_exact=False,check_dtype=False,
                atol=1e-7,rtol=1e-10,check_index_type=False)
        except AssertionError:
            failures.append("numeric_rank_label_or_boolean")
    status=json.loads((reference/"semantic_status.json").read_text(encoding="utf-8"))
    if (status.get("overall_pass") is not True or
        status.get("or_full_universe_pass") is not True or
        status.get("or_candidate_summary_rows")!=len(saved)):
        raise ValueError("Original saved OR ranking status not certified")
    if any(digest(reference/name)!=sha for name,sha in before.items()):
        raise ValueError("Original saved reference changed during rank audit")
    return {
        "schema":1,
        "status":("PASS_PHASE36_OR_CANDIDATE_RANK_SELECTION" if not failures
                  else "FAIL_PHASE36_OR_CANDIDATE_RANK_SELECTION"),
        "dataset":dataset,"private_core_sha":CORE_SHA,
        "pinned_source_sha256":p.get("original_source_sha256"),
        "or_unique_source_sha256":{name:before[name] for name in FILES},
        "or_candidate_original_sha256":before[ORIGINAL],
        "ranked_candidates":len(candidates),
        "original_candidate_rows":len(saved),
        "sorted_groups":selected_sizes,
        "rank_columns_checked":len(rank_cols),
        "numeric_or_label_mismatches":failures,
        "used_original_phase34_unique_proofs":True,
        "new_canonical_ranking_executed":True,
        "previous_artifacts_recomputed":False,
        "new_raw_OR_calculated":False,"new_monthly_stability_calculated":False,
        "source_signals_recomputed":False,"original_data_modified":False,
        "full_OR_bundle_generated":False,"html_generated":False,
        "production_changed":False,"release_ready":False,
    }


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    for name in ("core","reference","phase34","report"):
        p.add_argument("--"+name,type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest();return 0
    if any(getattr(a,k) is None for k in ("dataset","core","reference","phase34","report")):
        p.error("Pinned originals, Phase34 proof and fresh report required")
    if a.report.exists():
        raise FileExistsError("Never overwrite prior JSON evidence")
    d=verify(a.core.resolve(),a.reference.resolve(),a.phase34.resolve(),a.dataset)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in d.items() if k not in (
        "or_unique_source_sha256","or_candidate_original_sha256")},
        ensure_ascii=False))
    return 0 if d["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
