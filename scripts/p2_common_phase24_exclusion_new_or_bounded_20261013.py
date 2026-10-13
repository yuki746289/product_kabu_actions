# Created: 2026-10-13 JST
"""Phase24: bounded NEW common OR inner producer parity on the two exclusions.

Both saved feature artifacts and existing OR/semantic CSVs are immutable.
Use the exact new OR producer's prepare_frame/_component_pool/_combo_metrics
functions for 8 new OR2 and 8 new OR3 SHA-ranked holdout conditions PER
exclusion. Previous Phase15/16 32+32 conditions are deliberately skipped.
No P2/signals/feature recalculation; no semantic or full OR artifact generated.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

import p2_common_phase21_new_or_bounded_20261013 as prior
import p2_common_phase9_direct_metric_parity_20261013 as numeric

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
EXCLUSIONS={
    "exclude_transportation_utilities":(
        166470,205,"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"
    ),
    "exclude_capital_goods_transportation_utilities":(
        137426,170,"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"
    ),
}


def only_one(root:Path,name:str)->Path:
    hits=list(root.rglob(name))
    if len(hits)!=1 or not hits[0].is_file():
        raise ValueError(f"Expected exactly one retained {name}: {len(hits)}")
    return hits[0]


def selftest()->None:
    prior.selftest()
    assert len(EXCLUSIONS)==2 and prior.SKIP_PREVIOUS==32
    assert prior.NEW_PER_FAMILY==8 and prior.EXPECTED_TOTAL==16
    for name,(rows,tickers,sha) in EXCLUSIONS.items():
        assert name.startswith("exclude_") and len(sha)==64
        assert rows>100000 and 1<tickers<225
    print("PASS: Phase24 exclusion immutable SHA and disjoint bounded producer gates")


def audit(dataset:str, core:Path, saved_root:Path, reference:Path,
          identity_path:Path, phase12_path:Path, phase15_path:Path)->dict:
    if dataset not in EXCLUSIONS:
        raise ValueError("Only two exclusions approved for Phase24")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=CORE_SHA:
        raise ValueError("Private core SHA drift")
    expected_rows,expected_tickers,expected_sha=EXCLUSIONS[dataset]
    source=only_one(saved_root,"features.csv")
    original_sha=numeric.hash_file(source)
    if original_sha!=expected_sha:
        raise ValueError("Original saved exclusion features SHA mismatch")
    phase4=json.loads(identity_path.read_text(encoding="utf-8"))
    if phase4.get("status")!="PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE" or \
       phase4.get("variant")!=dataset:
        raise ValueError("Independent source identity proof missing/mismatched")
    cert=phase4.get("saved_exclusion") or {}
    if cert.get("csv_sha256")!=expected_sha or \
       cert.get("row_count")!=expected_rows or \
       cert.get("ticker_count")!=expected_tickers or \
       cert.get("duplicate_ids") is not False:
        raise ValueError("Independent Phase4 original saved exclusion certificate differs")
    p12=json.loads(phase12_path.read_text(encoding="utf-8"))
    if (p12.get("status")!="PASS_PHASE12_EXCLUSION_DIRECT_NUMERIC_PARITY_ONLY" or
        p12.get("dataset")!=dataset or
        p12.get("pinned_source_sha256")!=original_sha or
        p12.get("numeric_mismatches")!=0 or
        p12.get("categories_verified")!=84):
        raise ValueError("Phase12 original source direct numeric parity evidence not PASS")
    p15=json.loads(phase15_path.read_text(encoding="utf-8"))
    if (p15.get("status")!="PASS_PHASE15_SAVED_OR2_OR3_DIRECT_NUMERIC_SAMPLE" or
        p15.get("dataset")!=dataset or p15.get("source_sha256")!=original_sha):
        raise ValueError("Previous source-bound OR2/OR3 independent proof missing")
    for n,name in prior.RAW_FAMILIES:
        if p15.get(f"or{n}_reference_sha256")!=numeric.hash_file(reference/name):
            raise ValueError("Phase15 original saved OR CSV SHA mismatch")
    original_status=json.loads((reference/"semantic_status.json").read_text(encoding="utf-8"))
    if (original_status.get("overall_pass") is not True or
        original_status.get("or_full_universe_pass") is not True or
        original_status.get("source_rows")!=expected_rows or
        original_status.get("source_tickers")!=expected_tickers):
        raise ValueError("Prior original OR universe not certified")

    sys.path.insert(0,str(core/"scripts"))
    import analyze_p2_or_combinations as calculator
    import build_p2_225_or_bundle as common
    import finalize_p2_nikkei_complete_baseline as fin

    frame=common.prepare_frame(source)
    if len(frame)!=expected_rows or frame["ticker"].astype(str).nunique()!=expected_tickers:
        raise ValueError("Common OR input preparation changed source population")
    calculator.OUT=reference  # read already saved advantage_single_candidates.csv
    masks=fin._feature_masks(frame)
    pool=calculator._component_pool(frame,masks)
    lookup={(str(a["feature"]),str(a["category"])):a for a in pool}
    if len(lookup)!=len(pool):
        raise ValueError("New OR component pool contains duplicate labels")
    baseline=calculator._baseline(frame)
    selected=prior.select_new(reference)
    if len(selected)!=16:
        raise ValueError("Bounded next 8+8 conditions not selected")
    mismatch=[]
    compared=0
    for i,(n,labels,old) in enumerate(selected,1):
        try:
            components=[lookup[key] for key in labels]
        except KeyError:
            raise ValueError("Original OR component missing in new common pool")
        computed=calculator._combo_metrics(
            frame,"or2" if n==2 else "or3",components,baseline)
        problems=prior.compare_new_with_original(old,computed)
        compared+=len(computed)-1
        mismatch.extend({"index":i,"column":col} for col in problems)
    if numeric.hash_file(source)!=original_sha:
        raise ValueError("Original external saved artifact mutated during computation")
    return {
        "schema":1,
        "status":"PASS_PHASE24_EXCLUSION_BOUNDED_NEW_OR_PRODUCER"
                 if not mismatch else "FAIL_PHASE24_EXCLUSION_BOUNDED_NEW_OR_PRODUCER",
        "dataset":dataset,"source_core_sha":CORE_SHA,
        "source_sha256":original_sha,"source_rows":expected_rows,
        "source_tickers":expected_tickers,
        "or2_conditions_new":8,"or3_conditions_new":8,
        "new_producer_fields_checked":compared,
        "numeric_mismatches":len(mismatch),
        "first_issues":mismatch[:12],
        "reused_independent_phase12_success":True,
        "previous_32_per_kind_OR_conditions_reexecuted":False,
        "actual_new_common_or_inner_producer_executed":True,
        "full_semantic_or_bundle_generated":False,
        "original_artifacts_recomputed":False,
        "signals_recomputed":False,
        "production_p2_changed":False,
        "release_ready":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=sorted(EXCLUSIONS))
    p.add_argument("--core",type=Path)
    p.add_argument("--original-source-root",type=Path)
    p.add_argument("--reference",type=Path)
    p.add_argument("--phase4",type=Path)
    p.add_argument("--phase12",type=Path)
    p.add_argument("--phase15",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    if a.selftest:selftest();return 0
    if any(getattr(a,k) is None for k in
           ("dataset","core","original_source_root","reference","phase4","phase12","phase15","report")):
        p.error("dataset/core/source/reference/phase4/phase12/phase15/report required")
    out=a.report.resolve()
    if out.exists():
        raise FileExistsError("Never overwrite previous source or QA result")
    result=audit(a.dataset,a.core.resolve(),a.original_source_root.resolve(),
                 a.reference.resolve(),a.phase4.resolve(),a.phase12.resolve(),
                 a.phase15.resolve())
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="first_issues"},ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
