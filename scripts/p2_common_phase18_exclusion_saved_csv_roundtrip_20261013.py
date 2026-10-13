# Created: 2026-10-13 JST
"""Phase18: saved exclusion CSV contract + common assembler 29-file byte roundtrip.

Read ORIGINAL 28 tracked canonical CSVs and the missing ORIGINAL saved signal
features artifact. Stage 29 files in isolated core/build with an explicit
audit-only legacy ledger. This is NOT a test of regenerated numeric results.
Never computes features, P2, semantic, OR, or HTML.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS = {
    "exclude_transportation_utilities": {
        "relative": "225_exclusion_all_period/exclude_transportation_utilities",
        "sha256": "d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1",
        "rows": 166470,
        "tickers": 205,
        "run_id": 37201518110,
        "artifact_id": 11303406552,
    },
    "exclude_capital_goods_transportation_utilities": {
        "relative": "225_exclusion_all_period/exclude_capital_goods_transportation_utilities",
        "sha256": "cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2",
        "rows": 137426,
        "tickers": 170,
        "run_id": 37201520569,
        "artifact_id": 11302906875,
    },
}
SIGNAL = "signal_level_features.csv"


def sha256(file: Path) -> str:
    h = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def validate(original: Path, external: Path, evidence: dict, baseline: dict,
             dataset: str) -> dict:
    if dataset not in GROUPS:
        raise ValueError("Only two approved previously unassembled exclusions")
    cfg = GROUPS[dataset]
    if evidence.get("status") != "PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE":
        raise ValueError("Independent saved original source proof missing")
    if evidence.get("variant") != dataset:
        raise ValueError("Independent proof belongs to a different exclusion")
    src = evidence.get("saved_exclusion") or {}
    if (src.get("csv_sha256") != cfg["sha256"] or
        src.get("row_count") != cfg["rows"] or
        src.get("ticker_count") != cfg["tickers"] or
        src.get("duplicate_ids") is not False):
        raise ValueError("Original source does not match saved Phase4 identity")
    if sha256(external) != cfg["sha256"]:
        raise ValueError("Original external artifact SHA256 differs")
    if baseline.get("source_core_sha") != CORE_SHA or baseline.get("status") != "PASS_REFERENCE_SCHEMA_ONLY":
        raise ValueError("Canonical Phase2 saved schema proof mismatch")
    from pathlib import Path as _Path
    if len(baseline.get("files", {})) != 29:
        raise ValueError("Phase2 29-file canonical reference missing")
    with external.open("r", newline="", encoding="utf-8-sig") as input_csv:
        columns = next(csv.reader(input_csv))
    if len(set(columns)) != len(columns):
        raise ValueError("Saved external signal input header duplicated")
    fingerprint = hashlib.sha256(json.dumps(
        tuple(columns), ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if fingerprint != baseline["files"][SIGNAL]["header_sha256"]:
        raise ValueError("Saved exclusion signal header differs from canonical 29-file contract")
    status = json.loads((original/"semantic_status.json").read_text(encoding="utf-8"))
    if (status.get("overall_pass") is not True or
        status.get("or_full_universe_pass") is not True or
        status.get("source_rows") != cfg["rows"] or
        status.get("source_tickers") != cfg["tickers"]):
        raise ValueError("Saved exclusion semantic or OR status not PASS")
    return {"external_source_sha256":cfg["sha256"],
            "source_rows":cfg["rows"],"source_tickers":cfg["tickers"],
            "source_run_id":cfg["run_id"],"source_artifact_id":cfg["artifact_id"],
            "canonical_header_sha256":fingerprint}


def run(core: Path, source_root: Path, proof_path: Path, baseline_path: Path,
        dataset: str, out_root: Path) -> dict:
    if dataset not in GROUPS:
        raise ValueError("Unsupported dataset")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],
                               text=True).strip() != CORE_SHA:
        raise ValueError("Immutable Private data SHA mismatch")
    build = (core/"build").resolve()
    output = out_root.resolve()
    if output.exists() or output == build or not output.is_relative_to(build):
        raise ValueError("Output must be a fresh isolated core/build subfolder")
    external_matches = sorted(x for x in source_root.rglob("features.csv") if x.is_file())
    if len(external_matches) != 1:
        raise ValueError("Expected exactly one retained original features.csv")
    external = external_matches[0]
    original = core/"preview/kabu/analysis"/GROUPS[dataset]["relative"]
    if not original.exists():
        raise FileNotFoundError(original)
    evidence = json.loads(proof_path.read_text(encoding="utf-8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    # The shared assembler is the Private existing code under the fixed SHA.
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p02_semantic_io_contract import CSV_FILES, file_sha256, csv_header
    from p2_html_core.p03_common_analysis_plan import OR_CSVS, MANIFEST, SEMANTIC_CSVS
    from assemble_p2_common_dataset_csv import assemble
    from qa_p2_common_saved_csv import compare

    source_record = validate(original,external,evidence,baseline,dataset)
    if len(CSV_FILES)!=29 or len(OR_CSVS)!=5 or len(SEMANTIC_CSVS)!=23:
        raise ValueError("Canonical common 29-file stage contract drift")
    present = {p.name for p in original.glob("*.csv") if p.is_file()}
    expected = set(CSV_FILES)-{SIGNAL}
    if present != expected:
        raise ValueError(f"Saved exclusion CSV filenames differ: missing={sorted(expected-present)} "
                         f"unexpected={sorted(present-expected)}")
    for name in expected:
        with (original/name).open("rb") as f:
            if not f.read(1):
                raise ValueError("Empty original legacy CSV")
        cols = csv_header(original/name)
        hdr = hashlib.sha256(json.dumps(
            cols,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
        if hdr != baseline["files"][name]["header_sha256"]:
            raise ValueError("Saved legacy CSV column contract mismatch: "+name)

    reference=output/"reference"
    semantic=output/"semantic"
    or_folder=output/"or"
    normalized=output/"normalized"
    for p in (reference,semantic,or_folder):
        p.mkdir(parents=True,exist_ok=False)
    for name in sorted(expected):
        shutil.copy2(original/name,reference/name)
    shutil.copy2(external,reference/SIGNAL)
    for name in CSV_FILES:
        folder = semantic if name in SEMANTIC_CSVS else or_folder if name in OR_CSVS else None
        if folder is None:
            continue
        shutil.copy2(external if name==SIGNAL else original/name,folder/name)
    semantic_digests={name:file_sha256(semantic/name) for name in SEMANTIC_CSVS}
    or_digests={name:file_sha256(or_folder/name) for name in OR_CSVS}
    source_sha=source_record["external_source_sha256"]
    if semantic_digests[SIGNAL]!=source_sha or file_sha256(reference/SIGNAL)!=source_sha:
        raise RuntimeError("Pinned external original source changed during copying")
    # Legacy producer metadata is unavailable; these are AUDIT-ONLY ledgers,
    # never mislabel these as original historic producer provenance.
    audit_status={"overall_pass":True,"dataset_id":dataset,
                  "source_sha256":source_sha,
                  "provenance_type":"AUDIT_ONLY_SAVED_LEGACY_SHA_LEDGER_NOT_ORIGINAL_PRODUCER"}
    (semantic/"semantic_status.json").write_text(json.dumps({
        **audit_status,"output_csv_sha256":semantic_digests},sort_keys=True)+"\n",encoding="utf-8")
    (or_folder/"or_status.json").write_text(json.dumps({
        **audit_status,"output_csv_sha256":or_digests,
        "semantic_single_sha256":semantic_digests["advantage_single_candidates.csv"]
    },sort_keys=True)+"\n",encoding="utf-8")

    manifest=original/MANIFEST
    assembled=assemble(dataset,semantic,or_folder,manifest,normalized,reference,
                       expected_source_sha256=source_sha,
                       expected_manifest_sha256=file_sha256(manifest))
    parity=compare(normalized,reference)
    if (parity["status"]!="PASS_SAVED_CSV_BYTE_PARITY" or
        parity["files_identical"]!=29 or assembled["copied_csv_files"]!=29):
        raise RuntimeError("Original-source 29 CSV byte roundtrip failed")
    return {
        "schema":1,"status":"PASS_PHASE18_EXCLUSION_SAVED_29_CSV_ROUNDTRIP_ONLY",
        "dataset":dataset,"core_sha":CORE_SHA,**source_record,
        "saved_original_csv_count":28,
        "external_pinned_original_signal_csv":1,
        "normalized_csv_count":assembled["copied_csv_files"],
        "independently_identical_csv_count":parity["files_identical"],
        "previous_six_sector_roundtrip_reexecuted":False,
        "original_producer_ledger_verified":False,
        "audit_only_ledger_reconstructed":True,
        "source_signals_recomputed":False,
        "semantic_or_recomputed":False,
        "numeric_formula_equivalence_verified":False,
        "html_generated":False,"release_ready":False,"production_changed":False,
    }


def selftest():
    assert len(GROUPS)==2
    assert all(len(x["sha256"])==64 for x in GROUPS.values())
    assert GROUPS["exclude_transportation_utilities"]["rows"]==166470
    assert GROUPS["exclude_capital_goods_transportation_utilities"]["rows"]==137426
    print("PASS: Phase18 saved exclusion original-source, SHA and scope invariants")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=sorted(GROUPS))
    p.add_argument("--core",type=Path)
    p.add_argument("--external-saved-root",type=Path)
    p.add_argument("--proof",type=Path)
    p.add_argument("--baseline",type=Path)
    p.add_argument("--output-root",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    if a.selftest:
        selftest()
        return 0
    if any(getattr(a,x) is None for x in
           ("dataset","core","external_saved_root","proof","baseline","output_root","report")):
        p.error("All dataset, core, source, proof, baseline, output and report arguments required")
    record=a.report.resolve()
    if record.exists():
        raise FileExistsError("Never overwrite old audit result")
    result=run(a.core.resolve(),a.external_saved_root.resolve(),
               a.proof.resolve(),a.baseline.resolve(),a.dataset,a.output_root.resolve())
    record.parent.mkdir(parents=True,exist_ok=True)
    record.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
