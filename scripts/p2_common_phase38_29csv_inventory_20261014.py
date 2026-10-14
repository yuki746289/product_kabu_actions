# Created: 2026-10-14 JST
"""Phase38: 29 saved CSV contract/source SHA inventory for 6 sectors + 2 exclusions.

Read only: no numerical calculation, no copying original data, no semantic/OR
production, no HTML. Verifies exact shared CSV inventory+column order through
the FIXED common p02_semantic_io_contract.audit_dataset and enforces provenance
for the two external saved exclusion signal_level_features.csv inputs.
Outputs only compact JSON metadata (SHA, row/header counts), never private CSV.
Phase37 successful original source-bound numerical proof is required.
"""
from __future__ import annotations
import argparse
import csv
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
PRIOR="PASS_PHASE37_NEW_OR_MONTHLY_STABILITY_SHARD"
FILE_COUNT=29

def selftest()->None:
    assert len(DATASETS)==8 and len(GROUPS)==6 and len(EXCLUSIONS)==2
    assert FILE_COUNT==29 and len(CORE_SHA)==40
    assert all(len(v[2])==64 and v[0]>0 and v[1]>0 for v in EXCLUSIONS.values())
    print("PASS_PHASE38_CANONICAL_READ_ONLY_29_CSV_CONTRACT")

def rows_and_header(path:Path)->tuple[int,tuple[str,...]]:
    with path.open(newline="",encoding="utf-8-sig") as f:
        source=csv.reader(f)
        header=tuple(next(source))
        if not header or len(set(header))!=len(header):
            raise ValueError("Original CSV header missing/duplicate")
        count=0
        for number,record in enumerate(source,2):
            if len(record)!=len(header):
                raise ValueError(f"Malformed original saved CSV at {path.name}:{number}")
            count+=1
    return count,header

def verify(core:Path,dataset:str,root:Path,proof4:Path,proof37:Path,
           saved_sources:Path)->dict:
    if dataset not in DATASETS:
        raise ValueError("Unsupported scoped dataset")
    sha=subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                                 text=True).strip()
    if sha!=CORE_SHA:raise ValueError("Pinned original Private core SHA drift")
    expected_root=(core/"preview/kabu").resolve()
    if root!=expected_root:
        raise ValueError("Canonical site directory mismatch")
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p01_dataset_config import get_dataset
    from p2_html_core.p02_semantic_io_contract import (
        CSV_FILES, ExplicitInput, audit_dataset, baseline_headers,
        file_sha256, csv_header
    )
    if len(CSV_FILES)!=FILE_COUNT:
        raise ValueError("Canonical output contract changed")
    reference=get_dataset(dataset).source_dir(root)
    source=reference/"signal_level_features.csv"
    old4=json.loads(proof4.read_text(encoding="utf-8"))
    if dataset in GROUPS:
        record=(old4.get("groups") or {}).get(dataset) or {}
        rows,tickers=record.get("row_count"),record.get("ticker_count")
        if (old4.get("status")!="PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION" or
            record.get("duplicate_ids") is not False or
            record.get("csv_sha256")!=file_sha256(source) or
            not isinstance(rows,int) or rows<=0 or
            not isinstance(tickers,int) or tickers<=0):
            raise ValueError("Source group full original identity proof invalid")
        external={}
    else:
        found=list(saved_sources.rglob("features.csv"))
        if len(found)!=1:
            raise ValueError("Exactly one certified original exclusion features.csv required")
        source=found[0]
        rows,tickers,saved_sha=EXCLUSIONS[dataset]
        record=old4.get("saved_exclusion") or {}
        if (old4.get("status")!="PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE" or
            old4.get("variant")!=dataset or
            record.get("csv_sha256")!=saved_sha or
            record.get("row_count")!=rows or
            record.get("ticker_count")!=tickers or
            record.get("duplicate_ids") is not False or
            file_sha256(source)!=saved_sha):
            raise ValueError("Pinned exclusion original source mismatch")
        external={"signal_level_features.csv":ExplicitInput(source,saved_sha)}
    prior=json.loads(proof37.read_text(encoding="utf-8"))
    if (prior.get("status")!=PRIOR or prior.get("dataset")!=dataset or
        prior.get("private_core_sha")!=CORE_SHA or
        prior.get("original_source_sha256")!=file_sha256(source) or
        prior.get("candidate_offset")!=0 or
        prior.get("mismatches")!=[] or
        prior.get("previous_artifacts_recomputed") is not False):
        raise ValueError("Previous Phase37 full Run prerequisite proof is invalid")
    canonical_headers=baseline_headers(root)
    scanned=audit_dataset(root,dataset,canonical_headers,external)
    if (scanned["status"]!="PASS_SHARED_IO_CONTRACT" or
        scanned["resolved_csv_files"]!=FILE_COUNT or
        scanned["local_csv_files"]!=(29 if dataset in GROUPS else 28) or
        scanned["problems"]):
        raise ValueError("Saved canonical 29 CSV shared header/inventory mismatch: "+
                         json.dumps(scanned["problems"][:3],ensure_ascii=False))
    report_files={}
    for name in CSV_FILES:
        path=(source if name=="signal_level_features.csv" else reference/name)
        if not path.is_file():
            raise FileNotFoundError("Pinned canonical source missing: "+name)
        # 29 immutable full-file SHA/row counts, not producer recomputation.
        count,header=rows_and_header(path)
        if header!=canonical_headers[name]:
            raise ValueError("29 CSV original column order mismatch: "+name)
        report_files[name]={
            "rows":count,"columns":len(header),
            "sha256":file_sha256(path),
            "external_saved_source":dataset in EXCLUSIONS and name=="signal_level_features.csv",
        }
        if name=="signal_level_features.csv" and count!=rows:
            raise ValueError("Original source count differs from Phase4 proof")
    if len(report_files)!=FILE_COUNT or file_sha256(source)!=prior["original_source_sha256"]:
        raise ValueError("Original SHA/full contract mutated during read-only audit")
    return {
       "schema":1,"status":"PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT",
       "dataset":dataset,"private_core_sha":CORE_SHA,
       "source_sha256":file_sha256(source),"source_rows":rows,
       "source_tickers":tickers,"local_csv_files":scanned["local_csv_files"],
       "external_pinned_csv_files":len(external),
       "resolved_csv_files":len(report_files),
       "manifest_sha256":report_files["condition_detail_manifest.csv"]["sha256"],
       "files":report_files,"mismatches":[],
       "shared_contract_function_called":True,
       "source_signals_recomputed":False,"old_csv_modified":False,
       "new_semantic_producer_executed":False,
       "new_or_producer_executed":False,"normalization_producer_executed":False,
       "old_artifacts_recomputed":False,"html_generated":False,
       "production_changed":False,"release_ready":False,
       "full_new_producer_numerical_certification":False,
    }

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    for name in ("core","site-root","proof4","proof37","saved-sources","report"):
        p.add_argument("--"+name,type=Path)
    a=p.parse_args()
    if a.selftest:selftest();return 0
    if any(getattr(a,n) is None for n in
           ("dataset","core","site_root","proof4","proof37","saved_sources","report")):
        p.error("Pinned canonical dataset, source identity and Phase37 proof required")
    if a.report.exists():
        raise FileExistsError("Do not overwrite previous audit evidence")
    result=verify(a.core.resolve(),a.dataset,a.site_root.resolve(),
        a.proof4.resolve(),a.proof37.resolve(),a.saved_sources.resolve())
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="files"},ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2

if __name__=="__main__":
    raise SystemExit(main())
