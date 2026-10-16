# Created 2026-10-16 JST
"""Phase43 read-only cross-proof of saved original Semantic -> OR -> 29 CSV lineage.

This does NOT rerun already-certified Phase29/35/36/37/40/41/42 computations.
Checks the actual original SHA of all 29 old saved dataset inputs against
Phase38 and cross-links the successful Phase42 5+2 independent numerical
certificates and Phase36 OR ranking/unique SHA certificate.
Honest status CERTIFIED_SAVED_LINEAGE_ONLY; full new-producer pipeline remains
BLOCKED until actual new semantic/OR producer status SHA ledgers are available.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,subprocess,sys
from pathlib import Path
SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUDE={
 "exclude_capital_goods_transportation_utilities":"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
 "exclude_transportation_utilities":"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"}
DATASETS=GROUPS+tuple(EXCLUDE)
OR_UNIQUE=("or_pairwise_unique.csv","or_triple_unique.csv")
OR_RANK="or_candidate_summary.csv"
OLD_PROOF="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT"
FIVE_PROOF="PASS_PHASE42_FIVE_CACHED_SEMANTIC_OUTPUTS"
TWO_PROOF="PASS_PHASE42_TWO_UNSEEN_SEMANTIC_OUTPUTS"
OR_PROOF="PASS_PHASE36_OR_CANDIDATE_RANK_SELECTION"

def h(path:Path):
    v=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1<<20),b""):v.update(block)
    return v.hexdigest()

def read(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def selftest():
    assert len(DATASETS)==8 and len(OR_UNIQUE)==2 and len(SHA)==40
    print("PASS_PHASE43_SAVED_LINEAGE_CROSS_PROOF_LIMITED_SCOPE")

def verify(core,ref,extern,proof38,proof42five,proof42two,proof36,dataset):
    if dataset not in DATASETS:raise ValueError("Unsupported original dataset")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=SHA:
        raise ValueError("Pinned original SHA changed")
    approved=(core/"preview/kabu/analysis"/
             ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
             dataset).resolve()
    if ref!=approved:raise ValueError("Saved reference directory drift")
    if dataset in GROUPS:src=ref/"signal_level_features.csv"
    else:
        sources=list(extern.rglob("features.csv"))
        if len(sources)!=1 or h(sources[0])!=EXCLUDE[dataset]:
            raise ValueError("Saved original external features missing/changed")
        src=sources[0]
    source_hash=h(src)
    p38,p5,p2,por=map(read,(proof38,proof42five,proof42two,proof36))
    if p38.get("status")!=OLD_PROOF or p38.get("dataset")!=dataset or p38.get("private_core_sha")!=SHA:
        raise ValueError("Phase38 original 29 CSV certified source missing")
    if p38.get("source_sha256")!=source_hash or p38.get("resolved_csv_files")!=29 or p38.get("mismatches")!=[]:
        raise ValueError("Phase38 saved reference SHA or source not identical")
    if p5.get("status")!=FIVE_PROOF or p5.get("dataset")!=dataset or p5.get("source_sha256")!=source_hash:
        raise ValueError("Phase42 existing five source proof mismatch")
    if p5.get("original_private_sha")!=SHA or p5.get("file_count")!=5 or len(p5.get("files",{}))!=5:
        raise ValueError("Phase42 five proof incomplete")
    if p2.get("status")!=TWO_PROOF or p2.get("dataset")!=dataset or p2.get("source_sha256")!=source_hash:
        raise ValueError("Phase42 two new source proof mismatch")
    if p2.get("private_core_sha")!=SHA or p2.get("newly_verified_count")!=2 or len(p2.get("newly_verified_files",{}))!=2:
        raise ValueError("Phase42 two proof incomplete")
    if por.get("status")!=OR_PROOF or por.get("dataset")!=dataset or por.get("private_core_sha")!=SHA:
        raise ValueError("Phase36 OR ranking/source proof missing")
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p02_semantic_io_contract import CSV_FILES,csv_header
    from p2_html_core.p03_common_analysis_plan import OR_CSVS,MANIFEST,SEMANTIC_CSVS
    if len(CSV_FILES)!=29 or set(CSV_FILES)!=set(OR_CSVS)|{MANIFEST}|set(SEMANTIC_CSVS):
        raise ValueError("Authoritative shared 29 CSV ownership/drift")
    checked={}
    for filename in CSV_FILES:
        path=src if filename=="signal_level_features.csv" else ref/filename
        source_sha=p38["files"].get(filename,{}).get("sha256")
        if not source_sha or h(path)!=source_sha:
            raise ValueError("Saved SHA proof differs actual bytes: "+filename)
        if len(csv_header(path))!=p38["files"][filename]["columns"]:
            raise ValueError("Original CSV header/column count differs: "+filename)
        checked[filename]=source_sha
    for name,info in p5["files"].items():
        if name not in SEMANTIC_CSVS or info["original_sha256"]!=checked[name] or not info["numeric_and_label_parity"]:
            raise ValueError("Phase42 five numerical proof not SHA-linked: "+name)
    for name,info in p2["newly_verified_files"].items():
        if name not in SEMANTIC_CSVS or info["saved_original_sha256"]!=checked[name] or not info["all_fields_numeric_parity"]:
            raise ValueError("Phase42 two independent output proof not SHA-linked: "+name)
    if set(p2["newly_verified_files"])&set(p5["files"]):
        raise ValueError("Phase42 success scopes unexpectedly overlap")
    for n in OR_UNIQUE:
        if por.get("or_unique_source_sha256",{}).get(n)!=checked[n]:
            raise ValueError("Phase36 saved raw unique OR source SHA differs from current original: "+n)
    if por.get("or_candidate_original_sha256")!=checked[OR_RANK]:
        raise ValueError("Phase36 OR ranking proof source SHA differs")
    # Saved original manifest must share the same SHA used by Phase38.
    if h(ref/MANIFEST)!=p38["manifest_sha256"]:
        raise ValueError("Manifest has changed since Phase38 certification")
    if h(src)!=source_hash:
        raise ValueError("Original features mutated during evidence verification")
    return {
      "schema":1,
      "status":"PASS_PHASE43_SAVED_SOURCE_PROVENANCE_CHAIN_ONLY",
      "dataset":dataset,"private_core_sha":SHA,"source_sha256":source_hash,
      "saved_original_csv_total":29,
      "saved_original_semantic_csv":len(SEMANTIC_CSVS),
      "saved_original_or_csv":len(OR_CSVS),
      "phase42_independent_numerical_csv_sha_linked":len(p5["files"])+len(p2["newly_verified_files"]),
      "phase36_or_unique_and_rank_sha_linked":3,
      "manifest_sha256":p38["manifest_sha256"],
      "source_lineage_cross_proof_passed":True,
      "new_semantic_output_sha_ledger_produced":False,
      "new_or_output_sha_ledger_produced":False,
      "new_29csv_producer_executed":False,
      "full_new_semantic_or_numeric_parity_certified":False,
      "phase43_complete":False,"release_ready":False,
      "old_source_csv_modified":False,"old_artifacts_rerun":False,
      "production_modified":False
    }
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=DATASETS)
    for k in ("core","reference","source-root","phase38","phase42-five","phase42-two","phase36","report"):
        p.add_argument("--"+k,type=Path)
    a=p.parse_args()
    if a.selftest:selftest();return
    required=("dataset","core","reference","source_root","phase38","phase42_five","phase42_two","phase36","report")
    if any(getattr(a,k) is None for k in required):p.error("Missing exact original and independent proof artifacts")
    if a.report.exists():raise FileExistsError("Fresh audit artifact only")
    result=verify(a.core.resolve(),a.reference.resolve(),a.source_root.resolve(),
                  a.phase38.resolve(),a.phase42_five.resolve(),a.phase42_two.resolve(),
                  a.phase36.resolve(),a.dataset)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
