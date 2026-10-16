# Phase44 all_225: isolated, source-bound new-producer numerical parity.
# Original P2 v12, successful artifacts, saved HTML, and CSVs are read-only.
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from itertools import zip_longest
from pathlib import Path

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
SOURCE_SHA = "71fb0dc947a4777610fec2d07e08fac168a7ab1d49ac5028c39ad1b7ec03bdc9"
EXPECTED_FILES = {
    "advantage_pairwise_candidates.csv": {
        "rows": 3025,
        "cols": 32,
        "sha": "010ac6bd892b50bc1d3a88fc90df16a2a92a261d133d14ceedd5b06530da907a"
    },
    "advantage_single_candidates.csv": {
        "rows": 977,
        "cols": 30,
        "sha": "403d1bd8e78760aae0d40f1702bc84d5f3b18d136099e87796af1f3e59116560"
    },
    "advantage_triple_candidates.csv": {
        "rows": 6787,
        "cols": 31,
        "sha": "98d284af52a57214b3d8d3c7f417d5d68532456b38a7bc0da4e76422d789c062"
    },
    "all_pairwise_combinations.csv": {
        "rows": 10476,
        "cols": 31,
        "sha": "daaaa911731e28b99380d0293ae075c585028078739e58e081fe735a14c9e5de"
    },
    "all_single_categories.csv": {
        "rows": 2460,
        "cols": 29,
        "sha": "1d601134ec2dc300e496d08bceca19a5273bcea4747f9354995d015690f26be1"
    },
    "candidate_registry.csv": {
        "rows": 56,
        "cols": 29,
        "sha": "bc3ccb82ec63e018a130cc71e94748bdc0a15d1f99843c1762bd5f4c73fc99f4"
    },
    "combination_stability_summary.csv": {
        "rows": 9812,
        "cols": 64,
        "sha": "9dd93ab74b66a45d561fa703b7384b162aff4e9f7eef3d798124479d79e6d87e"
    },
    "combination_walkforward_results.csv": {
        "rows": 84,
        "cols": 15,
        "sha": "c62bbc629aafc8c923642062c951f0b32c5852be775c5462f21c49e19748f886"
    },
    "condition_detail_manifest.csv": {
        "rows": 447,
        "cols": 6,
        "sha": "913af3bf3c7255b29ad26101142dd16a26166b818cc261d0f480e6d75d66d4e0"
    },
    "failures.csv": {
        "rows": 0,
        "cols": 2,
        "sha": "6bef02eb12fa36051cdd9c6d7795e8ac278298d8476030563c44bc3af7608dee"
    },
    "month_of_year_baseline_summary.csv": {
        "rows": 12,
        "cols": 9,
        "sha": "35cb6274c22ce3267f9dbc77ecb0744f2a879ec2082008bf4216004c4c492469"
    },
    "monthly_baseline_performance.csv": {
        "rows": 224,
        "cols": 11,
        "sha": "07c75d32a159bfa332cb900ad28bfed32980be6fbd5f7bb93fc1f5644220339a"
    },
    "monthly_baseline_stability_summary.csv": {
        "rows": 9,
        "cols": 10,
        "sha": "3a321f5c0c3ac85025ff18944f268b4194480ea5b553f13160c2596ee8ab3f58"
    },
    "monthly_candidate_stability_summary.csv": {
        "rows": 56,
        "cols": 26,
        "sha": "610536a061ad3011e6d5945169383cc0874cb1bce8ffe440583dc4130c6326ea"
    },
    "monthly_stability.csv": {
        "rows": 10499,
        "cols": 15,
        "sha": "bcde0b0cd5be0b74191a12a1d65f665378a74124fb814292b6a74110ad4ce692"
    },
    "or_candidate_summary.csv": {
        "rows": 60,
        "cols": 78,
        "sha": "54ede2051ee47fbd67a0ef72f8f7aeb22dff54112f8e7fa39fea233e9533f1c0"
    },
    "or_pairwise_all.csv": {
        "rows": 1127,
        "cols": 48,
        "sha": "c6a1d97a95b364214cb3da15bcbbf5f8a0d4f36414a803f58cc6be1de2c39b64"
    },
    "or_pairwise_unique.csv": {
        "rows": 1111,
        "cols": 49,
        "sha": "7f202b5efbcb88c325b744498e1a288ab5aab6c018273fcf493aa3218fad103f"
    },
    "or_triple_all.csv": {
        "rows": 15184,
        "cols": 52,
        "sha": "2a628e12a8a9284fde38286befd7665f4131f8d4f67f0067f572403cada09520"
    },
    "or_triple_unique.csv": {
        "rows": 14502,
        "cols": 53,
        "sha": "d9a2bf39f1f3fff38bca904eb0335fcf4b99aa73aa375dac9269e2ce2f689053"
    },
    "parameter_plateau.csv": {
        "rows": 97,
        "cols": 17,
        "sha": "ca977b79c4fc8f3fcc7dbca37f93e788804c0674cade6415390b00846d6c8048"
    },
    "regime_stability.csv": {
        "rows": 786,
        "cols": 25,
        "sha": "974579967a54198099aca328ee2f90858bcbfc64e0b9415c82791bc2662c0381"
    },
    "representative_single_categories.csv": {
        "rows": 151,
        "cols": 26,
        "sha": "582d0739c38fe767e0379418f373312054499d263deb541d8fbb0ba74618b432"
    },
    "rolling_3y_stability.csv": {
        "rows": 1712,
        "cols": 13,
        "sha": "2c03448a420871648d8d3a93d19173fdb54180dae7dcc1d167e156329c9ab014"
    },
    "rolling_5y_stability.csv": {
        "rows": 1735,
        "cols": 13,
        "sha": "bd181851553e895cf981f38a8df71c34cf82bd7e0dc8adc010302f23a2318e7a"
    },
    "signal_level_features.csv": {
        "rows": 181318,
        "cols": 112,
        "sha": "d08e6ec0d05472ef559ad605113a5d77a95bd7c21cae861b218d2724cec6a62b"
    },
    "tested_triple_combinations.csv": {
        "rows": 19454,
        "cols": 30,
        "sha": "7d23adb7578cd33df4f74cd8e7f26924a520cf853a8c4953607dee93bd161f3e"
    },
    "walkforward_results.csv": {
        "rows": 45,
        "cols": 8,
        "sha": "de242814ec6354bff8fba51f827a8368e3dba8c906197fc28b9b967eab0b94f3"
    },
    "yearly_stability.csv": {
        "rows": 1355,
        "cols": 15,
        "sha": "e08a61a85b7eab0ac7adf54a35796c1b21c0b3f5fc254af9548fb5f1c6fe45c5"
    }
}
REQUIRED_ROWS = 181318
REQUIRED_TICKERS = 225
EXPECTED_CONDITIONS = 447
REL_TOL = 1e-12
ABS_TOL = 1e-10

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def git(core: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(core), *args], text=True, encoding="utf-8"
    ).strip()

def inspect_source(source: Path) -> dict:
    if sha256(source) != SOURCE_SHA:
        raise ValueError("Pinned 181318-row input SHA256 mismatch")
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        records = csv.reader(stream)
        header = next(records)
        if "ticker" not in header or "as_of" not in header:
            raise ValueError("Original input identifiers missing")
        idx = header.index("ticker")
        symbols = set()
        total = 0
        for record in records:
            if len(record) != len(header) or not record[idx]:
                raise ValueError("Malformed original source input")
            symbols.add(record[idx])
            total += 1
    if total != REQUIRED_ROWS or len(symbols) != REQUIRED_TICKERS:
        raise ValueError("Original source population mismatch")
    return {"rows": total, "tickers": len(symbols), "sha256": SOURCE_SHA}

def validate_old_reference(reference: Path) -> dict:
    present = {p.name for p in reference.glob("*.csv") if p.is_file()}
    if present != set(EXPECTED_FILES):
        raise ValueError("Original old 29-CSV reference name set changed")
    for name, expected in EXPECTED_FILES.items():
        path = reference / name
        if sha256(path) != expected["sha"]:
            raise ValueError("Original old reference SHA mismatch: " + name)
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream))
        if len(header) != expected["cols"] or len(set(header)) != len(header):
            raise ValueError("Original old reference column contract mismatch: " + name)
    keys = []
    slugs = []
    with (reference / "condition_detail_manifest.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            keys.append(row["condition_key"])
            slugs.append(row["slug"])
    if (len(keys) != EXPECTED_CONDITIONS
            or len(set(keys)) != len(keys)
            or len(set(slugs)) != len(slugs)):
        raise ValueError("Legacy condition identities are not complete or unique")
    return {"csv_count": 29, "condition_ids": len(keys)}

def identity_column(name: str) -> bool:
    lowered = name.lower()
    protected = (
        "ticker", "as_of", "slug", "condition", "feature", "category",
        "name", "label", "pattern", "params", "direction", "regime",
        "identifier", "source", "period_type", "group", "code", "month_key"
    )
    return any(piece in lowered for piece in protected) or lowered.endswith("_id")

def compare_csv(original: Path, produced: Path, expected: dict) -> dict:
    with original.open("r", encoding="utf-8-sig", newline="") as old, produced.open(
        "r", encoding="utf-8-sig", newline=""
    ) as new:
        lhs = csv.reader(old)
        rhs = csv.reader(new)
        a_head = next(lhs, None)
        b_head = next(rhs, None)
        if a_head != b_head or not a_head or len(a_head) != expected["cols"]:
            raise ValueError("New producer header/order mismatch: " + original.name)
        n = 0
        compared_cells = 0
        numeric_rounding_only = 0
        for left, right in zip_longest(lhs, rhs):
            if left is None or right is None or len(left) != len(a_head) or len(right) != len(a_head):
                raise ValueError("New producer length/row schema mismatch: " + original.name)
            n += 1
            compared_cells += len(left)
            for col, (v_old, v_new) in enumerate(zip(left, right)):
                if v_old == v_new:
                    continue
                if identity_column(a_head[col]):
                    raise ValueError("New producer nonnumeric/ID difference: " + original.name)
                try:
                    x, y = float(v_old), float(v_new)
                except (ValueError, OverflowError):
                    raise ValueError("New producer nonnumeric difference: " + original.name) from None
                if not (math.isfinite(x) and math.isfinite(y)
                        and math.isclose(x, y, rel_tol=REL_TOL, abs_tol=ABS_TOL)):
                    raise ValueError("New producer numeric difference: " + original.name)
                numeric_rounding_only += 1
        if n != expected["rows"]:
            raise ValueError("New producer row count mismatch: " + original.name)
        return {
            "rows": n, "columns": len(a_head), "compared_cells": compared_cells,
            "numeric_rounding_only_cells": numeric_rounding_only,
            "legacy_sha256": expected["sha"], "new_output_sha256": sha256(produced),
            "equivalent": True
        }

def verify(core: Path, source: Path, reference: Path) -> dict:
    if git(core, "rev-parse", "HEAD") != CORE_SHA:
        raise ValueError("Private core SHA drift")
    if not (core / "docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Required migration policy absent")
    if git(core, "ls-tree", "-r", "--name-only", "HEAD", ".github/workflows"):
        raise ValueError("Private workflow found")
    sys.path.insert(0, str(core / "scripts"))
    from p2_html_core.p02_semantic_io_contract import CSV_FILES
    from p2_html_core.p03_common_analysis_plan import MANIFEST, OR_CSVS, SEMANTIC_CSVS
    if (set(CSV_FILES) != set(EXPECTED_FILES) or len(SEMANTIC_CSVS) != 23
            or len(OR_CSVS) != 5 or MANIFEST != "condition_detail_manifest.csv"):
        raise ValueError("Source contract changed")
    source_meta = inspect_source(source)
    reference_meta = validate_old_reference(reference)
    stage = (core / "build/phase44_newproducer_20261016").resolve()
    root = (core / "build").resolve()
    if (stage.exists() or not stage.is_relative_to(root) or
            source.is_relative_to(stage) or reference.is_relative_to(stage)):
        raise ValueError("Isolated fresh producer stage required")
    sem = stage / "01_semantic"
    ort = stage / "02_or"
    normalized = stage / "03_normalized_csv"
    started = []
    results = {}
    stage.parent.mkdir(parents=True, exist_ok=True)
    try:
        commands = [
            ("semantic", "build_p2_225_semantic_bundle.py", [
                "--features", str(source), "--output-dir", str(sem),
                "--dataset-id", "all_225", "--source-sha256", SOURCE_SHA,
                "--expected-rows", str(REQUIRED_ROWS), "--expected-tickers", str(REQUIRED_TICKERS)
            ]),
            ("or", "build_p2_225_or_bundle.py", [
                "--features", str(source), "--semantic-dir", str(sem),
                "--dataset-id", "all_225", "--source-sha256", SOURCE_SHA,
                "--output-dir", str(ort)
            ]),
            ("normalized", "assemble_p2_common_dataset_csv.py", [
                "--dataset", "all_225", "--semantic-dir", str(sem),
                "--or-dir", str(ort), "--source-manifest", str(reference / MANIFEST),
                "--reference-dir", str(reference), "--source-sha256", SOURCE_SHA,
                "--manifest-sha256", EXPECTED_FILES[MANIFEST]["sha"],
                "--output-dir", str(normalized)
            ])
        ]
        for stage_name, script, arguments in commands:
            print("BEGIN_PHASE44_ISOLATED_STAGE", stage_name, flush=True)
            subprocess.run(
                [sys.executable, str(core / "scripts" / script)] + arguments,
                check=True, cwd=str(core)
            )
            started.append(stage_name)
            print("PASS_PHASE44_ISOLATED_STAGE", stage_name, flush=True)
        meta = json.loads((normalized / "common_io_status.json").read_text(encoding="utf-8"))
        if (meta.get("copied_csv_files") != 29
                or meta.get("dataset_id") != "all_225"
                or meta.get("numeric_equivalence") != "NOT_YET_VERIFIED"):
            raise ValueError("New assembler metadata does not meet contract")
        for name, expected in EXPECTED_FILES.items():
            print("CHECK_PHASE44_NEW_CSV", name, flush=True)
            results[name] = compare_csv(reference / name, normalized / name, expected)
        if inspect_source(source) != source_meta:
            raise ValueError("Pinned source changed after producer run")
        validate_old_reference(reference)
        if git(core, "diff", "--name-only") or git(core, "diff", "--cached", "--name-only"):
            raise ValueError("Original tracked source files were changed")
        if len(results) != 29 or started != ["semantic", "or", "normalized"]:
            raise ValueError("End-to-end 29 CSV proof incomplete")
        return {
            "schema": 1, "phase": 44,
            "status": "PASS_PHASE44_ALL225_FRESH_NEWPRODUCER_29CSV_NUMERIC_PARITY",
            "dataset": "all_225", "private_core_sha": CORE_SHA,
            "input": source_meta, "old_reference": reference_meta,
            "new_producer_executed": started, "files": results,
            "csv_count": len(results),
            "total_compared_cells": sum(x["compared_cells"] for x in results.values()),
            "numeric_tolerance": {"relative": REL_TOL, "absolute": ABS_TOL},
            "old_signals_recomputed": False, "old_csv_html_modified": False,
            "prior_success_artifacts_recomputed": False,
            "phase45_started": False, "release_ready": False,
            "phase48_authorized": False
        }
    finally:
        if stage.exists():
            shutil.rmtree(stage)
            print("PURGED_PHASE44_NEWPRODUCER_EPHEMERAL_STAGES", flush=True)

def selftest() -> None:
    assert len(EXPECTED_FILES) == 29
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "a.csv").write_text("condition_key,mean\nabc,1.0\n", encoding="utf-8")
        (d / "b.csv").write_text("condition_key,mean\nabc,1.000000000000001\n", encoding="utf-8")
        check = compare_csv(d / "a.csv", d / "b.csv", {"rows": 1, "cols": 2, "sha": sha256(d / "a.csv")})
        assert check["equivalent"] and check["numeric_rounding_only_cells"] == 1
        (d / "b.csv").write_text("condition_key,mean\nxyz,1.0\n", encoding="utf-8")
        try:
            compare_csv(d / "a.csv", d / "b.csv", {"rows": 1, "cols": 2, "sha": sha256(d / "a.csv")})
        except ValueError:
            pass
        else:
            raise AssertionError("Identity corruption was not rejected")
    print("PASS_PHASE44_COMPARATOR_SELFTEST", flush=True)

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--core", type=Path)
    p.add_argument("--source", type=Path)
    p.add_argument("--reference", type=Path)
    p.add_argument("--report", type=Path)
    a = p.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not all([a.core, a.source, a.reference, a.report]):
        p.error("Pinned core, saved source, saved old reference, and output JSON are required")
    if a.report.exists():
        raise FileExistsError("Refuse to overwrite previous proof")
    report = verify(a.core.resolve(), a.source.resolve(), a.reference.resolve())
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS_PHASE44_INDEPENDENT_NEW_PRODUCER_29CSV", report["csv_count"], flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
