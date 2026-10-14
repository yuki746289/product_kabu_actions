# Created 2026-10-14 JST
"""Independent full semantic -> OR -> 29-CSV numerical audit, isolated staging.

New output is generated ONLY into core/build and deleted. Existing saved CSVs,
successful GitHub artifacts, original signal extraction and Production P2 v12 are
never touched. The proof states which new producer stages actually ran.
Explicitly checks the SHA-pinned Phase38 saved originals and ordered columns,
condition identifiers, all rows, numeric values and manifest provenance.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUSIONS=("exclude_capital_goods_transportation_utilities",
            "exclude_transportation_utilities")
DATASETS=GROUPS+EXCLUSIONS
EXPECTED="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"

def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def git_sha(core:Path)->str:
    return subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()

def read(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path:Path,data:dict):
    if path.exists():raise FileExistsError("Do not overwrite successful audit")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in data.items() if k not in ("files","errors")},ensure_ascii=False),flush=True)

def selftest():
    assert len(DATASETS)==8 and len(GROUPS)==6 and len(CORE_SHA)==40
    assert all(len(x)>3 for x in DATASETS)
    print("PASS_FULL_POSTEXTRACT_29_CSV_DISJOINT_STAGING_CONTRACT")

def verify(core:Path,dataset:str,reference:Path,source:Path,phase38:Path,keep_stage:bool)->dict:
    if dataset not in DATASETS:raise ValueError("Only eight eligible research datasets")
    if git_sha(core)!=CORE_SHA:raise ValueError("Original Private source SHA changed")
    old=(core/"preview/kabu/analysis"/
         ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
         dataset).resolve()
    if reference!=old:raise ValueError("Approved original reference folder mismatch")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Private Actions architecture approval file missing")
    p=read(phase38)
    if p.get("status")!=EXPECTED or p.get("dataset")!=dataset or p.get("private_core_sha")!=CORE_SHA:
        raise ValueError("Prior original fixed 29-CSV audit identity mismatch")
    if p.get("mismatches")!=[] or p.get("resolved_csv_files")!=29:
        raise ValueError("Original approved CSV inventory incomplete")
    source_sha=digest(source)
    if source_sha!=p["source_sha256"]:
        raise ValueError("Exact old input source hash changed")
    expected_rows=int(p["source_rows"]);expected_tickers=int(p["source_tickers"])
    sys.path.insert(0,str(core/"scripts"))
    import pandas as pd
    from p2_html_core.p02_semantic_io_contract import CSV_FILES,csv_header
    from p2_html_core.p03_common_analysis_plan import OR_CSVS,SEMANTIC_CSVS,MANIFEST
    if len(CSV_FILES)!=29 or set(CSV_FILES)!=(set(OR_CSVS)|set(SEMANTIC_CSVS)|{MANIFEST}):
        raise ValueError("Shared authoritative 29-CSV contract changed")
    for filename in CSV_FILES:
        f=source if filename=="signal_level_features.csv" else reference/filename
        if not f.is_file() or digest(f)!=p["files"][filename]["sha256"]:
            raise ValueError("Original fixed reference file hash missing/changed: "+filename)

    stage=(core/"build"/"full_common_newproducer_20261014"/dataset).resolve()
    if stage.exists():raise FileExistsError("Fresh isolated research staging only")
    stage.parent.mkdir(parents=True,exist_ok=True)
    sem=stage/"01_semantic";orc=stage/"02_or";normalized=stage/"03_normalized_csv"
    args=[sys.executable]
    errors=[]
    ledger={}
    stages=[]
    try:
        for name,script,more in [
            ("semantic",core/"scripts/build_p2_225_semantic_bundle.py",
             ["--features",str(source),"--output-dir",str(sem),"--expected-rows",str(expected_rows),
              "--expected-tickers",str(expected_tickers),"--dataset-id",dataset,
              "--source-sha256",source_sha]),
            ("or",core/"scripts/build_p2_225_or_bundle.py",
             ["--features",str(source),"--semantic-dir",str(sem),
              "--dataset-id",dataset,"--source-sha256",source_sha,"--output-dir",str(orc)]),
            ("normalized",core/"scripts/assemble_p2_common_dataset_csv.py",
             ["--dataset",dataset,"--semantic-dir",str(sem),"--or-dir",str(orc),
              "--source-manifest",str(reference/MANIFEST),"--reference-dir",str(reference),
              "--source-sha256",source_sha,"--manifest-sha256",p["manifest_sha256"],
              "--output-dir",str(normalized)]),
        ]:
            print("START_NEW_PRODUCER",dataset,name,flush=True)
            subprocess.run(args+[str(script)]+more,cwd=str(core),check=True)
            stages.append(name)
            print("END_NEW_PRODUCER",dataset,name,flush=True)

        status=read(normalized/"common_io_status.json")
        if (status.get("dataset_id")!=dataset or status.get("copied_csv_files")!=29
            or status.get("source_sha256")!=source_sha or
            status.get("manifest_sha256")!=p["manifest_sha256"] or
            status.get("numeric_equivalence")!="NOT_YET_VERIFIED"):
            raise ValueError("Output provenance stage did not preserve expected producer identities")

        for filename in CSV_FILES:
            fresh=normalized/filename
            if not fresh.is_file():raise ValueError("New normalized CSV missing: "+filename)
            if csv_header(fresh)!=csv_header(source if filename=="signal_level_features.csv"
                                                    else reference/filename):
                raise ValueError("New/old headers or column order differ: "+filename)
            saved=source if filename=="signal_level_features.csv" else reference/filename
            old_df=pd.read_csv(saved,low_memory=False,dtype={"ticker":str})
            new_df=pd.read_csv(fresh,low_memory=False,dtype={"ticker":str})
            if len(old_df)!=len(new_df) or list(old_df.columns)!=list(new_df.columns):
                raise ValueError("New producer row count/order schema changed: "+filename)
            try:
                pd.testing.assert_frame_equal(
                    old_df,new_df,check_dtype=False,check_exact=False,
                    atol=1e-7,rtol=1e-10,check_index_type=False)
            except AssertionError as error:
                raise AssertionError("NEW_PRODUCER_NUMERIC_OR_CONDITION_PARITY: "+
                                    filename+": "+str(error)[:1000]) from error
            ledger[filename]={"rows":len(new_df),"columns":len(new_df.columns),
                              "new_generated_sha256":digest(fresh),
                              "old_original_sha256":p["files"][filename]["sha256"],
                              "numerically_equal":True}
            del new_df,old_df
            print("PASS_NEW_29_CSV",dataset,filename,ledger[filename]["rows"],flush=True)
        if len(ledger)!=29:raise ValueError("29 CSV full new producer incomplete")
        if digest(source)!=source_sha:raise ValueError("Original input mutated during computation")
        for filename in CSV_FILES:
            oldfile=source if filename=="signal_level_features.csv" else reference/filename
            if digest(oldfile)!=p["files"][filename]["sha256"]:
                raise ValueError("Original old CSV mutated during new computation: "+filename)
        if git_sha(core)!=CORE_SHA or subprocess.check_output(
            ["git","-C",str(core),"diff","--name-only"],text=True).strip():
            raise ValueError("Original repository tracked contents changed")
        return {
            "schema":1,"status":"PASS_FULL_29_CSV_NEW_PRODUCER_NUMERIC_PARITY",
            "dataset":dataset,"private_core_sha":CORE_SHA,
            "source_sha256":source_sha,"source_rows":expected_rows,
            "source_tickers":expected_tickers,
            "new_producer_executed":stages,
            "all_29_csv_rows_order_columns_numeric_equal":True,
            "files":ledger,"csv_count":29,"mismatches":[],
            "original_artifact_overwritten":False,
            "original_csv_or_html_modified":False,
            "production_p2_changed":False,"release_ready":False,
        }
    finally:
        if not keep_stage and stage.exists():
            shutil.rmtree(stage)
            print("PURGED_FRESH_NEW_PRODUCER_PRIVATE_CSV_STAGING",dataset,flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--dataset",choices=DATASETS)
    for k in ("core","reference","source","phase38","report"):
        ap.add_argument("--"+k,type=Path)
    ap.add_argument("--keep-stage",action="store_true")
    a=ap.parse_args()
    if a.selftest:selftest();return 0
    if any(getattr(a,k) is None for k in ("dataset","core","reference","source","phase38","report")):
        ap.error("Dataset, fixed original, source, prior proof and new report required")
    if a.report.exists():raise FileExistsError("Refuse previously used report destination")
    result=verify(a.core.resolve(),a.dataset,a.reference.resolve(),
                  a.source.resolve(),a.phase38.resolve(),a.keep_stage)
    save(a.report,result)
    return 0 if result["status"].startswith("PASS_") else 2

if __name__=="__main__":raise SystemExit(main())
