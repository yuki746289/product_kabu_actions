# Created: 2026-10-13T02:18:00+09:00
"""Phase9 single-dataset independent numerical pilot, read-only and isolated.

Calculate only lightweight direct categorical reductions over already-saved P2
outcomes. NEVER run Production P2, common semantic/OR generators, feature
extraction, or regenerate any previously certified artifact. Compare to the
immutable saved single-category analysis CSV using a separate implementation.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASET = "technology"
RELATIVE = "preview/kabu/analysis/225_group_all_period/technology"
SOURCE_FILE = "signal_level_features.csv"
REFERENCE_FILE = "all_single_categories.csv"
SELECTED_FEATURES = (
    "causal_regime",
    "daily_rci26_direction",
    "daily_rci26_position",
    "daily_rci26_state",
)
HORIZONS = (5, 10, 20)
NUMERIC_TOLERANCE = 1e-7


@dataclass
class Totals:
    n: int = 0
    wins: dict[int, list[float]] = field(default_factory=lambda: {h: [] for h in HORIZONS})
    returns: dict[int, list[float]] = field(default_factory=lambda: {h: [] for h in HORIZONS})

    def add(self, values: dict[str, str]) -> None:
        self.n += 1
        for horizon in HORIZONS:
            y = finite(values[f"moved_predicted_{horizon}d"])
            ret = finite(values[f"directional_return_{horizon}d_pct"])
            if y is not None:
                self.wins[horizon].append(y)
            if ret is not None:
                self.returns[horizon].append(ret)

    def metric(self, horizon: int, kind: str) -> float | None:
        values = self.wins[horizon] if kind == "win" else self.returns[horizon]
        if not values:
            return None
        return math.fsum(values) / len(values) * (100.0 if kind == "win" else 1.0)


def finite(value: str | None) -> float | None:
    """Normalize saved CSV boolean outcome flags before numeric reduction."""
    if value is None:
        return None
    token = value.strip()
    if token.lower() == "true":
        return 1.0
    if token.lower() == "false":
        return 0.0
    try:
        result = float(token)
    except (ValueError, AttributeError):
        return None
    return result if math.isfinite(result) else None


def hash_file(file: Path) -> str:
    h = hashlib.sha256()
    with file.open("rb") as stream:
        for data in iter(lambda: stream.read(1048576), b""):
            h.update(data)
    return h.hexdigest()


def load_reference(file: Path) -> dict[tuple[str, str], dict[str, str]]:
    with file.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        names = set(reader.fieldnames or [])
        expected = {"feature", "category", "count", "retention_pct"} | {
            f"{metric}_{h}d_{suffix}"
            for h in HORIZONS
            for metric, suffix in (("win", "pct"), ("return", "pct"),
                                   ("win_uplift", "pp"), ("return_uplift", "pct"))
        }
        if not expected.issubset(names):
            raise ValueError("Saved canonical reference lacks mandatory numeric metrics")
        output = {}
        for row in reader:
            feature = row["feature"]
            if feature not in SELECTED_FEATURES:
                continue
            key = (feature, row["category"])
            if key in output:
                raise ValueError("Ambiguous duplicate saved direct-category reference")
            output[key] = row
        if not output:
            raise ValueError("No saved direct-category reference rows")
        for feature in SELECTED_FEATURES:
            if not any(key[0] == feature for key in output):
                raise ValueError("Missing required saved feature family: " + feature)
        return output


def calculate_direct(file: Path, keys: set[tuple[str, str]],
                     expected_rows: int) -> tuple[Totals, dict[tuple[str,str],Totals]]:
    by_category = {key: Totals() for key in keys}
    full = Totals()
    with file.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        names = set(reader.fieldnames or [])
        required = set(SELECTED_FEATURES) | {
            f"{kind}_{h}d{tail}" for h in HORIZONS
            for kind, tail in (("moved_predicted", ""), ("directional_return", "_pct"))
        }
        # Outcomes are named moved_predicted_5d and directional_return_5d_pct.
        required = set(SELECTED_FEATURES) | {
            f"moved_predicted_{h}d" for h in HORIZONS
        } | {
            f"directional_return_{h}d_pct" for h in HORIZONS
        }
        if not required.issubset(names):
            raise ValueError("Saved feature input misses directly verifiable columns")
        for index, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"Malformed saved feature record at row {index}")
            full.add(row)
            for feature in SELECTED_FEATURES:
                key = (feature, str(row.get(feature, "nan")))
                if key in by_category:
                    by_category[key].add(row)
        if full.n != expected_rows:
            raise ValueError(f"Saved feature population mismatches metadata: {full.n} != {expected_rows}")
    return full, by_category


def same_numeric(actual: float | None, value: str, *, atol: float = NUMERIC_TOLERANCE) -> bool:
    expected = finite(value)
    if actual is None or expected is None:
        return actual is None and expected is None
    return abs(actual-expected) <= atol


def numeric_failures(full: Totals, categories: dict[tuple[str,str], Totals],
                     references: dict[tuple[str,str],dict[str,str]]) -> list[str]:
    issues = []
    for key, old in references.items():
        found = categories[key]
        if found.n != int(old["count"]):
            issues.append(f"{key} count mismatch")
        if not same_numeric(100.0 * found.n / full.n, old["retention_pct"]):
            issues.append(f"{key} retention mismatch")
        for h in HORIZONS:
            old_win = full.metric(h, "win")
            old_ret = full.metric(h, "return")
            win = found.metric(h, "win")
            ret = found.metric(h, "return")
            uplift_win = win - old_win if win is not None and old_win is not None else None
            uplift_ret = ret - old_ret if ret is not None and old_ret is not None else None
            comparisons = {
                f"win_{h}d_pct": win,
                f"return_{h}d_pct": ret,
                f"win_uplift_{h}d_pp": uplift_win,
                f"return_uplift_{h}d_pct": uplift_ret,
            }
            for column, value in comparisons.items():
                if not same_numeric(value, old[column]):
                    issues.append(f"{key} {column} mismatch")
    return issues


def audit(core: Path, phase4: Path) -> dict:
    actual_sha = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual_sha != CORE_SHA:
        raise ValueError("Private saved source is not pinned to approved SHA")
    folder = core / RELATIVE
    source = folder / SOURCE_FILE
    ref = folder / REFERENCE_FILE
    status = json.loads((folder / "semantic_status.json").read_text(encoding="utf-8"))
    if status.get("overall_pass") is not True or status.get("or_full_universe_pass") is not True:
        raise ValueError("Original analysis status not PASS")
    pin = json.loads(phase4.read_text(encoding="utf-8"))
    if pin.get("status") != "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION":
        raise ValueError("Previous independent source identity evidence missing")
    source_record = pin.get("groups", {}).get(DATASET)
    if source_record is None or source_record.get("csv_sha256") != hash_file(source):
        raise ValueError("Original saved signal SHA256 fails independent Phase4 pin")
    orig_sha = hash_file(ref)
    rows = status.get("source_rows")
    if type(rows) is not int or rows != 48782:
        raise ValueError("Pinned original source row count unexpectedly changed")
    reference = load_reference(ref)
    total, stats = calculate_direct(source, set(reference), rows)
    issues = numeric_failures(total, stats, reference)
    return {
        "schema_version": 1,
        "status": "PASS_PHASE9_DIRECT_SAVED_NUMERIC_PARITY_PILOT_ONLY"
            if not issues else "FAIL_PHASE9_DIRECT_SAVED_NUMERIC_PARITY",
        "dataset": DATASET,
        "source_core_sha": CORE_SHA,
        "source_sha256": source_record["csv_sha256"],
        "reference_csv_sha256": orig_sha,
        "source_rows": total.n,
        "selected_features": list(SELECTED_FEATURES),
        "reference_category_rows_checked": len(reference),
        "numeric_fields_per_category": 2 + 4*len(HORIZONS),
        "mismatched_fields": len(issues),
        "first_errors": issues[:20],
        "new_semantic_bundle_generated": False,
        "new_or_bundle_generated": False,
        "existing_artifacts_recalculated": False,
        "html_qa_complete": False,
        "release_ready": False,
        "production_changed": False,
    }


def selftest() -> None:
    totals = Totals()
    totals.add({**{f"moved_predicted_{h}d": "1" for h in HORIZONS},
                **{f"directional_return_{h}d_pct": "2" for h in HORIZONS}})
    totals.add({**{f"moved_predicted_{h}d": "0" for h in HORIZONS},
                **{f"directional_return_{h}d_pct": "-4" for h in HORIZONS}})
    assert totals.n == 2
    assert totals.metric(5, "win") == 50
    assert totals.metric(20, "return") == -1
    row = {"feature": "causal_regime", "category": "RANGE", "count": "2",
           "retention_pct": "100"}
    for h in HORIZONS:
        row.update({f"win_{h}d_pct":"50",f"return_{h}d_pct":"-1",
                    f"win_uplift_{h}d_pp":"0",f"return_uplift_{h}d_pct":"0"})
    assert numeric_failures(totals, {("causal_regime", "RANGE"): totals},
                            {("causal_regime", "RANGE"): row}) == []
    row["win_5d_pct"] = "55"
    assert any("win_5d_pct" in x for x in numeric_failures(
        totals, {("causal_regime", "RANGE"): totals},
        {("causal_regime", "RANGE"): row}))
    assert not same_numeric(50, "")
    assert same_numeric(None, "NaN")
    assert finite("True") == 1.0 and finite("False") == 0.0
    assert finite(" true ") == 1.0 and finite("FALSE") == 0.0
    assert finite("1") == 1.0 and finite("0") == 0.0
    assert finite("") is None and finite("NaN") is None
    checker = Totals()
    for text in ("True", "False"):
        checker.add({
            **{f"moved_predicted_{h}d": text for h in HORIZONS},
            **{f"directional_return_{h}d_pct": "2.5" for h in HORIZONS},
        })
    for h in HORIZONS:
        assert checker.metric(h, "win") == 50.0
        assert checker.metric(h, "return") == 2.5
    print("PASS: independent direct numerical reducer synthetic guard")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--core", type=Path)
    p.add_argument("--phase4", type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    if a.selftest:
        selftest()
        return 0
    if not (a.core and a.phase4 and a.out):
        p.error("Specify --core --phase4 --out")
    output = a.out.resolve()
    if output.exists():
        raise FileExistsError("Audit evidence must not be overwritten")
    result = audit(a.core.resolve(), a.phase4.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",
                      encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="first_errors"},
                     ensure_ascii=False))
    if result["status"].startswith("FAIL_"):
        print("::error::Saved numeric direct-category parity check failed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
