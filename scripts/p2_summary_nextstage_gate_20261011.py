# Created: 2026-10-11 18:00 JST
"""Read-only URL inventory and independent saved-signal numeric P2 summary gate.

Only interrogates saved signal_level_features and candidate CSV; no P2 v12
recalculation or edits. A single representative daily RCI state is verified per
sector, independently of the HTML renderer and aggregate candidate outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

SECTORS = (
    "technology", "financials", "consumer_goods", "materials",
    "capital_goods_others", "transportation_utilities",
)
FILES = {
    "single": ("advantage_single_candidates.csv", ["feature"]),
    "pair": ("advantage_pairwise_candidates.csv", ["feature1", "feature2"]),
    "triple": ("advantage_triple_candidates.csv", ["feature1", "feature2", "feature3"]),
}
INPUT_SHA = "0e2d5722d6764102adfe6995b793f533b60b1532"


def names_for(kind: str, frame: pd.DataFrame, cols: list[str]) -> set[str]:
    grouped = frame.groupby(cols[0] if kind == "single" else cols,
                            sort=False, dropna=False)
    names = set()
    for key, _ in grouped:
        vals = (str(key),) if kind == "single" else tuple(str(x) for x in key)
        digest = hashlib.sha1((kind + ":" + "|".join(vals)).encode()).hexdigest()[:14]
        name = f"{kind}-{digest}.html"
        if name in names:
            raise AssertionError("group hash collision")
        names.add(name)
    return names


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def url_inventory(core: Path, source: Path, source_frames: dict[str, pd.DataFrame]) -> dict:
    base = source.relative_to(core).as_posix()
    raw = subprocess.check_output(
        ["git", "-C", str(core), "ls-tree", "-r", "--name-only", "HEAD", "--",
         base + "/summaries/"], text=True
    ).splitlines()
    old = {Path(p).name for p in raw if p.endswith(".html")}
    if len(old) != 712 or len(raw) < 712:
        raise AssertionError("expected 712 unchanged legacy summaries")
    new = set()
    result = {}
    for kind, (_, cols) in FILES.items():
        expected = names_for(kind, source_frames[kind], cols)
        expected.add(f"{kind}_features.html")
        existing = {n for n in old if n.startswith(kind + "-") or
                    n == f"{kind}_features.html"}
        new |= expected
        result[kind] = {
            "old_pages": len(existing), "candidate_pages": len(expected),
            "old_only_count": len(existing - expected),
            "candidate_only_count": len(expected - existing),
            "intersection_count": len(existing & expected),
            "old_only_names": sorted(existing - expected),
            "candidate_only_names": sorted(expected - existing),
        }
    if sum(r["old_pages"] for r in result.values()) != 712:
        raise AssertionError("legacy source categories were not disjoint")
    return {
        "old_total": len(old), "candidate_total": len(new),
        "old_only": len(old - new), "candidate_only": len(new - old),
        "both": len(old & new), "families": result,
        "removed_url_policy": "DO_NOT_PUBLISH_STALE_HTML; final URL routing pending",
    }


def independent_numeric(source: Path, candidates: pd.DataFrame, pop: int) -> dict:
    """Check representative *materialized* daily-RCI state, no mask recalculation.

    Select highest-count canonical-parameter candidates. Compare their 5D,
    10D and 20D win rates and full population share against saved raw signals.
    """
    signals = source / "signal_level_features.csv"
    if not signals.is_file():
        raise FileNotFoundError("saved signal_level_features.csv absent")
    required = ["daily_rci14_state"] + [f"moved_predicted_{h}d" for h in (5, 10, 20)]
    header = pd.read_csv(signals, nrows=0).columns
    if not all(x in header for x in required):
        raise AssertionError("saved signals missing materialized daily RSI/RCI state or win flags")
    rows = candidates[candidates["feature"].astype(str).eq("daily_rci14_state")].copy()
    if "is_representative" not in rows:
        raise AssertionError("single candidates need is_representative")
    rows = rows[rows.is_representative.astype(str).str.casefold().eq("true")]
    rows = rows[rows.params_json.astype(str).str.contains('"direction_delta": 5', regex=False)]
    rows = rows[rows.params_json.astype(str).str.contains('"80/20/-20/-80"', regex=False)]
    rows = rows.sort_values("count", ascending=False).drop_duplicates("category")
    selected = rows.head(3).copy()
    if len(selected) != 3 or selected.category.duplicated().any():
        raise AssertionError("no three distinct canonical daily RCI14 representatives")
    cats = [str(x) for x in selected.category]
    count = {c: 0 for c in cats}
    sumwins = {(c, h): 0.0 for c in cats for h in (5, 10, 20)}
    nwin = {(c, h): 0 for c in cats for h in (5, 10, 20)}
    total = 0
    # Only four columns in memory at once; chunks bound runtime and RAM.
    for block in pd.read_csv(signals, usecols=required, chunksize=25000):
        total += len(block)
        states = block.daily_rci14_state.astype(str)
        for c in cats:
            m = states.eq(c)
            count[c] += int(m.sum())
            for h in (5, 10, 20):
                arr = pd.to_numeric(block.loc[m, f"moved_predicted_{h}d"],
                                    errors="coerce").dropna()
                sumwins[(c, h)] += float(arr.sum())
                nwin[(c, h)] += len(arr)
    if total != pop:
        raise AssertionError(f"signal row count differs from saved status: {total} vs {pop}")
    checks = []
    for _, r in selected.iterrows():
        c = str(r.category)
        if count[c] != int(r["count"]):
            raise AssertionError(f"saved-signal candidate count mismatch for {c}: "
                                 f"{count[c]} vs {r['count']}")
        share = 100 * count[c] / pop
        if abs(share - float(r["retention_pct"])) > 0.0002:
            raise AssertionError(f"population share mismatch for {c}")
        for h in (5, 10, 20):
            if nwin[(c, h)] == 0:
                raise AssertionError("representative group has no evaluable win flags")
            rate = sumwins[(c, h)] / nwin[(c, h)] * 100
            if abs(rate - float(r[f"win_{h}d_pct"])) > 0.02:
                raise AssertionError(f"saved signal numeric mismatch {c} {h}D: "
                                     f"{rate} vs {r[f'win_{h}d_pct']}")
        checks.append({"category": c, "count": count[c],
                       "evaluated_horizons": [5, 10, 20]})
    return {
        "scope": "daily_rci14_state canonical params, first 3 representative categories",
        "independent_signal_rows_scanned": total,
        "representatives": checks, "signal_sha256": digest_file(signals),
        "limit": "This is not a complete revalidation of parameterized candidates.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", type=Path, required=True)
    ap.add_argument("--sector", choices=SECTORS, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--expected-core-sha", default=INPUT_SHA)
    a = ap.parse_args()
    core, out = a.core.resolve(), a.output.resolve()
    if out == core / "build" or not out.is_relative_to(core / "build") or out.exists():
        raise ValueError("output must be an unused subdirectory of core/build")
    if subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"],
                               text=True).strip() != a.expected_core_sha:
        raise ValueError("unexpected source commit")
    source = core / "preview/kabu/analysis/225_group_all_period" / a.sector
    out.mkdir(parents=True)
    try:
        status = json.loads((source / "semantic_status.json").read_text(encoding="utf-8"))
        if status.get("overall_pass") is not True:
            raise AssertionError("saved semantic status not PASS")
        pop = int(status["source_rows"])
        frames = {k: pd.read_csv(source / name, low_memory=False)
                  for k, (name, _) in FILES.items()}
        for k, f in frames.items():
            if f.empty or not set(FILES[k][1]).issubset(f.columns):
                raise AssertionError(f"invalid saved candidate source: {k}")
        report = {
            "schema": 1, "sector": a.sector, "private_sha": a.expected_core_sha,
            "status": "PASS", "population": pop,
            "url_inventory": url_inventory(core, source, frames),
            "numeric_canary": independent_numeric(source, frames["single"], pop),
            "signal_recomputed": False, "source_mutated": False,
            "previous_successful_run_repeated": False, "deployment_allowed": False,
        }
    except Exception as exc:
        report = {
            "schema": 1, "sector": a.sector, "private_sha": a.expected_core_sha,
            "status": "FAIL", "failure_class": type(exc).__name__,
            "failure_reason": str(exc)[:600], "deployment_allowed": False,
        }
    (out / "nextstage_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("url_inventory",)},
                     ensure_ascii=False), flush=True)
    if report["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
