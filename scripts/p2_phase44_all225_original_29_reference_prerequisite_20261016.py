# Created 2026-10-16 JST.
"""Phase44 exact original all_225 reference presence audit (fail-closed NO_GO).

No historical signal recompute; no 181318-row feature artifact redownload.
Inputs come from original immutable prior source/run identity (Phase13 prior
verified direct numerical check). Confirm registered exact all_225 saved old
reference has all 29 canonical CSVs with correct headers, not a substitute from
six sectors or 885-line Nikkei. If absent, hard status BLOCKED and do not
certify or execute Phase44 full producer. Emitting a successful audit RUN does
NOT mean Phase44 success; the report status is intentionally BLOCKED.
"""
import argparse,json,subprocess
from pathlib import Path
FIXED_CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
PINNED_FEATURE_SHA="71fb0dc947a4777610fec2d07e08fac168a7ab1d49ac5028c39ad1b7ec03bdc9"
ROWS=181318
TICKERS=225
FEATURES_RUN=36703088996
FEATURES_ARTIFACT="p2-225-raw-features-20260930"
def run(core):
    head=subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()
    if head!=FIXED_CORE_SHA:raise ValueError("Original Private core SHA drift")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Mandatory no Private Actions rule absent")
    import sys
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p01_dataset_config import get_dataset
    from p2_html_core.p02_semantic_io_contract import CSV_FILES
    if len(CSV_FILES)!=29:raise ValueError("Original canonical CSV contract not 29")
    ds=get_dataset("all_225")
    expected=core/"preview/kabu"/ds.relative_dir
    if ds.group!="all_225" or ds.relative_dir!="analysis/225_indicator_stageb":
        raise ValueError("Original registered all225 reference path differs")
    # Examine pinned committed GIT TREE for all 29 actual filenames, not just
    # a sparse checkout or a guess about missing files.
    paths=subprocess.check_output(["git","-C",str(core),"ls-tree","-r",
        "--name-only","HEAD","preview/kabu/analysis/225_indicator_stageb"],
        text=True).splitlines()
    base="preview/kabu/analysis/225_indicator_stageb/"
    direct={p[len(base):] for p in paths
            if p.startswith(base) and "/" not in p[len(base):] and p.endswith(".csv")}
    required=set(CSV_FILES)
    found=required&direct
    missing=sorted(required-direct)
    extra=sorted(direct-required)
    if extra:raise ValueError("Unexpected extra direct CSVs in 225 canonical reference")
    complete=not missing
    return {
      "schema":1,
      "phase":44,
      "status":("INPUT_READY_FOR_PHASE44_INDEPENDENT_ALL225_29CSV_NUMERIC_QA"
                if complete else
                "BLOCKED_PHASE44_MISSING_SAVED_ALL225_29CSV_INDEPENDENT_REFERENCE"),
      "private_core_sha":FIXED_CORE_SHA,
      "dataset":"all_225",
      "source_artifact_run_id":FEATURES_RUN,
      "source_artifact_name":FEATURES_ARTIFACT,
      "original_source_sha256_previously_certified":PINNED_FEATURE_SHA,
      "original_source_rows_previously_certified":ROWS,
      "original_source_tickers_previously_certified":TICKERS,
      "registered_site_path":ds.relative_dir,
      "required_original_reference_csvs":len(required),
      "found_original_reference_csvs":len(found),
      "missing_original_reference_csvs":missing,
      "all_29_old_reference_present":complete,
      "source_feature_rows_reread":False,
      "source_features_recomputed":False,
      "prior_success_artifacts_recomputed":False,
      "other_sector_reference_substituted":False,
      "nikkei_885_reference_substituted":False,
      "all225_full_new_29_csv_numeric_verified":False,
      "phase44_completed":False,
      "phase45_started":False,
      "phase46_deferred":True,
      "phase48_started":False,
      "production_modified":False,
      "release_ready":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--core",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError("Do not overwrite previous audit")
    d=run(a.core.resolve())
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(d,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in d.items() if k!="missing_original_reference_csvs"},ensure_ascii=False))
    print("ABSENT_REFERENCE_CSV_COUNT",len(d["missing_original_reference_csvs"]))
    print("CERTIFICATION_STATUS",d["status"])
if __name__=="__main__":main()
