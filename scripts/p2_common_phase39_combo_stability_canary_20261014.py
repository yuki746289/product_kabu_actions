# Created: 2026-10-14 JST
"""Phase39 bounded NEW combination-stability inner numeric parity.

Reuses exact saved original Pairwise/Triple CSVs certified by Phase30/31,
source identities and Phase38 29 CSV immutable SHA ledger. Independently calls
canonical _stability_summary only on first three candidate pairs and three
candidate triples, not any previously proven full pair/triple producer.
No full semantic, OR, feature extraction, source rewrite, or HTML generation.
JSON report only, staging never publishes original private data.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUSIONS={
 "exclude_capital_goods_transportation_utilities":
   (137426,170,"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"),
 "exclude_transportation_utilities":
   (166470,205,"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1")
}
DATASETS=GROUPS+tuple(EXCLUSIONS)
STABILITY="combination_stability_summary.csv"
PAIR="all_pairwise_combinations.csv"
TRIPLE="tested_triple_combinations.csv"
SCOPE=3
EXPECTED_STATUS="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"

def selftest():
    assert len(DATASETS)==8 and SCOPE==3 and len(CORE_SHA)==40
    assert len({PAIR,TRIPLE,STABILITY})==3
    print("PASS_PHASE39_NEW_BOUNDED_COMBO_STABILITY_SCOPE")


def verify(core:Path,reference:Path,external:Path,prior:Path,dataset:str)->dict:
    if dataset not in DATASETS:raise ValueError("Unsupported original dataset")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=CORE_SHA:
        raise ValueError("Original private SHA changed")
    expected=(core/"preview/kabu/analysis"/
       ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
       dataset).resolve()
    if reference!=expected:raise ValueError("Reference dataset directory drift")
    if dataset in GROUPS:source=reference/"signal_level_features.csv"
    else:
        matches=list(external.rglob("features.csv"))
        if len(matches)!=1:raise ValueError("Missing exactly one immutable saved exclusion features CSV")
        source=matches[0]
    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    import finalize_p2_nikkei_complete_baseline as calc
    import build_p2_225_semantic_bundle as common
    from p2_html_core.p03_common_analysis_plan import digest

    sha=digest(source)
    p=json.loads(prior.read_text(encoding="utf-8"))
    if (p.get("status")!=EXPECTED_STATUS or p.get("dataset")!=dataset
        or p.get("private_core_sha")!=CORE_SHA
        or p.get("source_sha256")!=sha or p.get("resolved_csv_files")!=29
        or p.get("mismatches")!=[] or
        p.get("full_new_producer_numerical_certification") is not False):
        raise ValueError("Phase38 old full source SHA/metadata certificate invalid")
    for name in (PAIR,TRIPLE,STABILITY):
        if p.get("files",{}).get(name,{}).get("sha256")!=digest(reference/name):
            raise ValueError("Phase38 original old analysis CSV SHA changed: "+name)

    frame=common.prepare_frame(source)
    rows=p["source_rows"]; tickers=p["source_tickers"]
    if len(frame)!=rows or frame["ticker"].astype(str).nunique()!=tickers:
        raise ValueError("Original source shape changed")
    inputs={}
    selected={}
    for kind,name in (("pair",PAIR),("triple",TRIPLE)):
        all_rows=pd.read_csv(reference/name,low_memory=False)
        if "candidate" not in all_rows:
            raise ValueError("Original upstream candidate flag missing")
        candidates=all_rows.loc[calc._truthy(all_rows["candidate"])].copy()
        if len(candidates)<SCOPE:
            raise ValueError("Insufficient new combination stability canary rows")
        part=candidates.head(SCOPE).copy()
        inputs[kind]=part
        selected[kind]=[tuple(str(r[f"feature{i}"])+":"+str(r[f"category{i}"])
             for i in range(1,4 if kind=="triple" else 3))
             for _,r in part.iterrows()]
    masks=calc._feature_masks(frame)
    new=pd.concat(
        [calc._stability_summary(frame,inputs[k],k,masks) for k in ("pair","triple")],
        ignore_index=True,sort=False)
    if len(new)!=2*SCOPE:
        raise ValueError("Canonical producer new stability returned unexpected rows")
    old=pd.read_csv(reference/STABILITY,low_memory=False)
    if list(new.columns)!=list(old.columns):
        raise ValueError("Original/new canonical combination stability columns differ")
    if old.empty or old.duplicated([
          "condition_type","feature1","category1","feature2","category2",
          "feature3","category3"]).any():
        raise ValueError("Original old combination stability keys malformed")
    def mask_for(kind,row):
        selected_mask=old["condition_type"].astype(str).eq(kind)
        for i in range(1,4 if kind=="triple" else 3):
            selected_mask &= old[f"feature{i}"].astype(str).eq(str(row[f"feature{i}"]))
            selected_mask &= old[f"category{i}"].astype(str).eq(str(row[f"category{i}"]))
        return selected_mask
    expected_rows=[]
    for kind in ("pair","triple"):
        for _,r in inputs[kind].iterrows():
            hit=old.loc[mask_for(kind,r)]
            if len(hit)!=1:
                raise ValueError("Old saved stability record not found or duplicate")
            expected_rows.append(hit)
    original=pd.concat(expected_rows,ignore_index=True)
    failures=[]
    try:
        pd.testing.assert_frame_equal(original,new,check_dtype=False,
            check_exact=False,atol=1e-7,rtol=1e-10,check_index_type=False)
    except AssertionError:
        failures.append("ordered_combo_stability_values_or_labels")
    if sha!=digest(source) or any(
        p["files"][n]["sha256"]!=digest(reference/n) for n in (PAIR,TRIPLE,STABILITY)):
        raise ValueError("Private original file mutated during audit")
    return {
      "schema":1,
      "status":"PASS_PHASE39_NEW_BOUNDED_COMBO_STABILITY" if not failures else
               "FAIL_PHASE39_NEW_BOUNDED_COMBO_STABILITY",
      "dataset":dataset,"private_core_sha":CORE_SHA,"source_sha256":sha,
      "old_stability_total":len(old),"original_pair_rows":p["files"][PAIR]["rows"],
      "original_triple_rows":p["files"][TRIPLE]["rows"],
      "new_pair_candidates":SCOPE,"new_triple_candidates":SCOPE,
      "new_subset_rows":len(new),"columns_compared":len(new.columns),
      "mismatches":failures,"canonical_new_stability_inner_called":True,
      "previous_pairwise_producer_recomputed":False,
      "previous_triple_producer_recomputed":False,
      "previous_artifacts_recomputed":False,
      "full_semantic_recomputed":False,"full_or_recomputed":False,
      "original_signals_recomputed":False,"original_csv_modified":False,
      "production_changed":False,"html_generated":False,"release_ready":False
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--dataset",choices=DATASETS)
    for n in ("core","reference","source-root","phase38","report"):
        ap.add_argument("--"+n,type=Path)
    args=ap.parse_args()
    if args.selftest:
        selftest();return 0
    if any(getattr(args,n) is None for n in
           ("dataset","core","reference","source_root","phase38","report")):
        ap.error("Pinned source, original Phase38 proof, fresh report needed")
    if args.report.exists():
        raise FileExistsError("Never overwrite previous success/failure evidence")
    out=verify(args.core.resolve(),args.reference.resolve(),
               args.source_root.resolve(),args.phase38.resolve(),args.dataset)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k!="source_sha256"},ensure_ascii=False))
    return 0 if out["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
