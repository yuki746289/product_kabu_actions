# Created: 2026-10-12 JST
"""Read-only full saved-input interface preflight for 9 P2 datasets.

Never generate indicators, P2 signals, or semantic/OR data. Verify the exact
stored rows/tickers/required columns after source sha/artifact ID pinning.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

DATA_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
CODE_SHA = "dbd18e8e6730c8b898057adfd89ec6735fb7b3d4"


def git_sha(dir: Path) -> str:
    return subprocess.check_output(["git", "-C", str(dir), "rev-parse", "HEAD"],text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["group","artifact"],required=True)
    parser.add_argument("--dataset",required=True)
    parser.add_argument("--data-root",type=Path,required=True)
    parser.add_argument("--code-root",type=Path,required=True)
    parser.add_argument("--phase4-evidence",type=Path,required=True)
    parser.add_argument("--artifact-root",type=Path)
    parser.add_argument("--artifact-run-id",type=int)
    parser.add_argument("--artifact-id",type=int)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    if git_sha(a.data_root) != DATA_SHA:
        raise ValueError("Saved source data Git commit mismatch")
    if git_sha(a.code_root) != CODE_SHA:
        raise ValueError("New research adapter code Git commit mismatch")
    sys.path.insert(0,str(a.code_root/"scripts"))
    from p2_html_core.p04_saved_postextract_input_adapter import (
        GROUP_SHAPES, SAVED_ARTIFACT_SOURCES, validated_postextract_input,
    )
    evidence=json.loads(a.phase4_evidence.read_text(encoding="utf-8"))
    if a.mode=="group":
        if a.dataset not in GROUP_SHAPES or a.artifact_root is not None:
            raise ValueError("Unexpected group source parameters")
        status=validated_postextract_input(
            a.dataset,core_root=a.data_root,
            checked_core_sha=DATA_SHA,phase4_evidence=evidence)
    else:
        if a.dataset not in SAVED_ARTIFACT_SOURCES or a.artifact_root is None or (
            a.artifact_run_id is None or a.artifact_id is None):
            raise ValueError("Approved external artifact reference required")
        status=validated_postextract_input(
            a.dataset,saved_artifact_root=a.artifact_root,
            run_id=a.artifact_run_id,artifact_id=a.artifact_id,
            phase4_evidence=evidence)
    pin=status["input_pin"]
    inspected=status["verified_input"]
    if inspected["source_sha256"] != pin.sha256:
        raise RuntimeError("Source inspection digest mismatch")
    if inspected.get("expected_rows") != pin.expected_rows or (
        inspected.get("expected_tickers") != pin.expected_tickers):
        raise RuntimeError("Pinned dataset expected shape mismatch")
    if inspected.get("source_rows_counted") is not True:
        raise RuntimeError("Real saved row count was not read and checked")
    report={
        "schema":1,"status":"PASS_PINNED_POSTEXTRACT_SAVED_INPUT_ONLY",
        "dataset":a.dataset,"kind":a.mode,
        "saved_core_sha":DATA_SHA,"adapter_code_sha":CODE_SHA,
        "source_sha256":pin.sha256,
        "expected_rows":pin.expected_rows,"expected_tickers":pin.expected_tickers,
        "source_checked":True,"columns_checked":True,
        "row_count_checked":True,"ticker_count_checked":True,
        "artifact_run_id":status["origin"].get("run_id"),
        "artifact_id":status["origin"].get("artifact_id"),
        "source_signals_recomputed":False,"semantic_numeric_parity_verified":False,
        "html_generated":False,"production_changed":False,"release_ready":False,
    }
    out=a.out.resolve()
    if out.exists():
        raise FileExistsError("Audit evidence is immutable")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return 0


if __name__=="__main__":
    sys.exit(main())
