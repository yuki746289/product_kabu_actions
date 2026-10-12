# Created: 2026-10-12T19:19:00+09:00
"""Byte-roundtrip compatibility of existing saved 29 CSVs through new assembler.

This does NOT recalculate P2, semantic analysis, OR, or improve its trading
performance. Legacy stage ledgers are constructed solely from read-only,
already approved stored files, marked as audit adapters (not claimed producer
origin). The test proves staged assembly, headers, and SHA equality only.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys

COHORTS = ("technology","financials","consumer_goods","materials",
           "capital_goods_others","transportation_utilities")
SOURCE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"


def run(core: Path, dataset: str, evidence: Path, out_root: Path) -> dict:
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p02_semantic_io_contract import CSV_FILES, file_sha256
    from p2_html_core.p03_common_analysis_plan import OR_CSVS, MANIFEST, SEMANTIC_CSVS
    from assemble_p2_common_dataset_csv import assemble
    from qa_p2_common_saved_csv import compare

    if dataset not in COHORTS:
        raise ValueError("Only six sectors with all 29 published CSVs are supported")
    original = core/"preview/kabu/analysis/225_group_all_period"/dataset
    if out_root.exists() or not out_root.resolve().is_relative_to((core/"build").resolve()):
        raise ValueError("A fresh isolated folder under private core/build is required")
    certified = json.loads(evidence.read_text(encoding="utf-8"))
    if certified.get("status") != "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
        raise ValueError("Independent saved feature source ID audit has not passed")
    group_evidence = certified.get("groups",{}).get(dataset)
    if not group_evidence or certified["source"]["row_count"] != 181318:
        raise ValueError("Missing independently certified saved dataset")
    source_path = original/"signal_level_features.csv"
    source_sha = file_sha256(source_path)
    if source_sha != group_evidence["csv_sha256"]:
        raise ValueError("Saved group input SHA differs from independent phase4 source")

    old_status = json.loads((original/"semantic_status.json").read_text(encoding="utf-8"))
    if old_status.get("overall_pass") is not True or old_status.get("or_full_universe_pass") is not True:
        raise ValueError("Legacy semantic and OR data did not pass earlier QA")

    normalized = out_root/"normalized"
    semantic = out_root/"semantic"
    or_root = out_root/"or"
    semantic.mkdir(parents=True)
    or_root.mkdir()
    for item in CSV_FILES:
        target = semantic/item if item in SEMANTIC_CSVS else (
            or_root/item if item in OR_CSVS else None)
        if target:
            source = original/item
            if not source.is_file():
                raise FileNotFoundError(source)
            shutil.copy2(source,target)

    semantic_hash = {x:file_sha256(semantic/x) for x in SEMANTIC_CSVS}
    or_hash = {x:file_sha256(or_root/x) for x in OR_CSVS}
    if semantic_hash["signal_level_features.csv"] != source_sha:
        raise RuntimeError("Source signal copy changed")

    # These new audit adapter records document exactly what was verified in
    # saved files. They are NOT the original OR producer's historical ledgers.
    base = {"overall_pass":True,"dataset_id":dataset,"source_sha256":source_sha,
            "provenance_type":"READ_ONLY_SAVED_LEGACY_ADAPTER_NOT_ORIGINAL_PRODUCER"}
    (semantic/"semantic_status.json").write_text(
        json.dumps({**base,"output_csv_sha256":semantic_hash})+"\n",encoding="utf-8")
    (or_root/"or_status.json").write_text(
        json.dumps({**base,"output_csv_sha256":or_hash,
                    "semantic_single_sha256":semantic_hash["advantage_single_candidates.csv"]})
        +"\n",encoding="utf-8")

    manifest_sha = file_sha256(original/MANIFEST)
    assembly = assemble(dataset,semantic,or_root,original/MANIFEST,normalized,original,
                        expected_source_sha256=source_sha,
                        expected_manifest_sha256=manifest_sha)
    parity = compare(normalized,original)
    if parity.get("status") != "PASS_SAVED_CSV_BYTE_PARITY" or parity.get("files_identical") != 29:
        raise RuntimeError("Saved CSV 29-file byte roundtrip failed")

    return {"schema":1,"status":"PASS_SAVED_29_CSV_ROUNDTRIP_ONLY",
            "dataset":dataset,"private_core_sha":SOURCE_SHA,
            "input_signal_sha256":source_sha, "condition_manifest_sha256":manifest_sha,
            "source_files":29,"staged_files":assembly["copied_csv_files"],
            "identical_csv_files":parity["files_identical"],
            "original_stage_provenance_reconstructed":True,
            "original_stage_producer_certificate_verified":False,
            "analysis_rerun":False,"source_signals_recomputed":False,
            "semantic_numeric_equivalence_verified":False,
            "html_generated":False,"production_changed":False,
            "release_ready":False}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--core",type=Path,required=True)
    p.add_argument("--dataset",choices=COHORTS,required=True)
    p.add_argument("--identity-evidence",type=Path,required=True)
    p.add_argument("--stage-root",type=Path,required=True)
    p.add_argument("--status-out",type=Path,required=True)
    a=p.parse_args()
    result=run(a.core.resolve(),a.dataset,a.identity_evidence,
               a.stage_root.resolve())
    out=a.status_out.resolve()
    if out.exists():
        raise FileExistsError("Old audit evidence cannot be overwritten")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=="__main__":
    sys.exit(main())
