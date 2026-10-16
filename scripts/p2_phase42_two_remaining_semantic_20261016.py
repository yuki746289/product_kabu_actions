# Created 2026-10-16 JST
"""Phase42 last targeted NEW semantic functions: monthly candidate stability and plateau.

Read the EXACT SHA-pinned previously saved original source tables. Invoke
canonical monthly._candidate_monthly_summary and semantic._parameter_plateau
fresh for their own output only; skip all certified Phase27-31,40,41,42 files.
Original old CSVs, Production P2 v12, HTML never modified. Only audit metadata.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUSIONS={
 "exclude_capital_goods_transportation_utilities":"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
 "exclude_transportation_utilities":"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"}
DATASETS=GROUPS+tuple(EXCLUSIONS)
INPUTS=("candidate_registry.csv","monthly_stability.csv",
        "all_single_categories.csv","representative_single_categories.csv")
OUTPUTS=("monthly_candidate_stability_summary.csv","parameter_plateau.csv")
OLD38="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"
OLD42="PASS_PHASE42_FIVE_CACHED_SEMANTIC_OUTPUTS"

def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def selftest():
    assert len(DATASETS)==8 and len(INPUTS)==4 and len(OUTPUTS)==2
    assert len(set(INPUTS+OUTPUTS))==6
    print("PASS_PHASE42_UNSEEN_MONTHLY_CANDIDATE_PLATEAU_SCOPE")

def verify(core:Path,ref:Path,external:Path,proof38:Path,proof42:Path,dataset:str):
    if dataset not in DATASETS:raise ValueError("Unknown original dataset")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip()!=CORE_SHA:
        raise ValueError("Pinned original Private SHA mismatch")
    expected=(core/"preview/kabu/analysis"/
              ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
              dataset).resolve()
    if ref!=expected:raise ValueError("Unapproved saved original dataset directory")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Private architecture policy missing")
    if dataset in GROUPS:source=ref/"signal_level_features.csv"
    else:
        matches=list(external.rglob("features.csv"))
        if len(matches)!=1 or digest(matches[0])!=EXCLUSIONS[dataset]:
            raise ValueError("Pinned external saved features mismatch")
        source=matches[0]
    orig=json.loads(proof38.read_text(encoding="utf-8"))
    five=json.loads(proof42.read_text(encoding="utf-8"))
    sha=digest(source)
    if (orig.get("status")!=OLD38 or orig.get("dataset")!=dataset
        or orig.get("private_core_sha")!=CORE_SHA
        or orig.get("source_sha256")!=sha
        or orig.get("resolved_csv_files")!=29 or orig.get("mismatches")!=[]):
        raise ValueError("Phase38 saved 29-CSV original source SHA audit invalid")
    if (five.get("status")!=OLD42 or five.get("dataset")!=dataset
        or five.get("original_private_sha")!=CORE_SHA or five.get("source_sha256")!=sha
        or five.get("file_count")!=5 or len(five.get("files",{}))!=5):
        raise ValueError("Phase42 successful five CSV source proof does not match")
    for name in INPUTS+OUTPUTS:
        if digest(ref/name)!=orig["files"][name]["sha256"]:
            raise ValueError("Pinned original saved input or old output SHA changed: "+name)
    if orig["files"]["monthly_stability.csv"]["sha256"]!=five["files"]["monthly_stability.csv"]["original_sha256"]:
        raise ValueError("Monthly certified semantic upstream source not identical")
    import pandas as pd
    sys.path.insert(0,str(core/"scripts"))
    import append_p2_nikkei_monthly_report as monthly
    import build_p2_225_canonical_semantic_data as semantic
    old_input={name:pd.read_csv(ref/name,low_memory=False) for name in INPUTS}
    result={}
    for out,fn,source_names,key in [
        (OUTPUTS[0],monthly._candidate_monthly_summary,
         (INPUTS[1],INPUTS[0]),("condition_id",)),
        (OUTPUTS[1],semantic._parameter_plateau,
         (INPUTS[2],INPUTS[3]),("feature_family","feature","category"))
    ]:
        t=time.perf_counter()
        new=fn(*(old_input[n] for n in source_names))
        saved=pd.read_csv(ref/out,low_memory=False)
        if list(saved.columns)!=list(new.columns):
            raise ValueError(out+": columns differ from saved original")
        if len(saved)!=len(new):
            raise ValueError(out+": number of rows differs from original")
        # Fail on even one missing, extra or duplicate candidate identity.
        if saved.duplicated(list(key)).any() or new.duplicated(list(key)).any():
            raise ValueError(out+": duplicate canonical condition key")
        keys_old=[tuple(str(v) for v in row)
                  for row in saved[list(key)].itertuples(index=False,name=None)]
        keys_new=[tuple(str(v) for v in row)
                  for row in new[list(key)].itertuples(index=False,name=None)]
        if set(keys_old)!=set(keys_new):
            raise ValueError(out+": original vs new condition key coverage differs")
        aligned=new.set_index(pd.Index(keys_new)).loc[keys_old].reset_index(drop=True)
        for col in key:
            aligned[col]=saved[col].astype(str).to_numpy()
        aligned=aligned[saved.columns]
        try:
            pd.testing.assert_frame_equal(saved,aligned,check_dtype=False,
                check_exact=False,atol=1e-7,rtol=1e-10,check_index_type=False)
        except AssertionError as exc:
            raise AssertionError(out+": same-condition numeric or label mismatch: "+str(exc)[:1000]) from exc
        result[out]={"saved_original_sha256":orig["files"][out]["sha256"],
            "old_rows":len(saved),"new_rows":len(new),
            "column_count":len(new.columns),"key_field_names":list(key),
            "full_unique_key_coverage":True,"all_fields_numeric_parity":True,
            "same_original_row_order":keys_old==keys_new,
            "seconds":round(time.perf_counter()-t,5)}
        print("PASS_PHASE42_UNSEEN_SEMANTIC_CSV",dataset,out,len(new),flush=True)
    for name in INPUTS+OUTPUTS:
        if digest(ref/name)!=orig["files"][name]["sha256"]:
            raise ValueError("Saved source mutated during new audit")
    if digest(source)!=sha:
        raise ValueError("Pinned source features changed during proof")
    return {
      "schema":1,"status":"PASS_PHASE42_TWO_UNSEEN_SEMANTIC_OUTPUTS",
      "dataset":dataset,"private_core_sha":CORE_SHA,"source_sha256":sha,
      "newly_verified_files":result,"newly_verified_count":len(result),
      "existing_phase42_five_recomputed":False,"other_prior_success_recomputed":False,
      "production_p2_v12_modified":False,"old_csv_html_modified":False,
      "all_29_csv_new_producer_certified":False,
      "phase43_full_semantic_or_numeric_certified":False,
      "release_ready":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    for name in ("core","reference","source-root","phase38","phase42","report"):
        p.add_argument("--"+name,type=Path)
    a=p.parse_args()
    if a.selftest:selftest();return
    if any(getattr(a,name) is None for name in
           ("dataset","core","reference","source_root","phase38","phase42","report")):
        p.error("Original pinned inputs and fresh report required")
    if a.report.exists():raise FileExistsError("Never overwrite prior evidence")
    data=verify(a.core.resolve(),a.reference.resolve(),a.source_root.resolve(),
                a.phase38.resolve(),a.phase42.resolve(),a.dataset)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data,ensure_ascii=False))
if __name__=="__main__":main()
