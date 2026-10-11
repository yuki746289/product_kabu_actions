# Created: 2026-10-11 JST
"""Candidate-only, fail-closed P2 sector summary audit.

Public runner, immutable private core, build/ output only. No HTML copy, P2
recalculation, source write, workflow chaining, or deploy. Audit JSON deliberately
contains no private source rows or rendered HTML.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import subprocess
import sys

KINDS = {
    "single": ("advantage_single_candidates.csv", ("feature",)),
    "pair": ("advantage_pairwise_candidates.csv", ("feature1", "feature2")),
    "triple": ("advantage_triple_candidates.csv", ("feature1", "feature2", "feature3")),
}
SECTORS = (
    "technology", "financials", "consumer_goods", "materials",
    "capital_goods_others", "transportation_utilities",
)
ORPHAN_CANARY = "triple-018ca598da9630.html"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_data(path: Path) -> list:
    source = path.read_text(encoding="utf-8")
    match = re.search(r",D=(\[[\s\S]*?\]),HI=new Set", source)
    if not match:
        raise AssertionError("embedded canonical table data absent")
    rows = json.loads(match.group(1))
    if not isinstance(rows, list):
        raise AssertionError("embedded data is not an array")
    return rows


def value(x: object) -> float | None:
    s = str(x).replace(",", "").strip()
    if s in ("-", "", "nan", "NaN", "None"):
        return None
    try:
        v = float(s)
    except ValueError as exc:
        raise AssertionError("non numeric table cell") from exc
    return v if math.isfinite(v) else None


def check_close(display: object, expected: object, *, exact: bool = False) -> None:
    got = value(display)
    try:
        want = float(expected)
    except (TypeError, ValueError):
        want = float("nan")
    if not math.isfinite(want):
        if got is not None:
            raise AssertionError("expected missing numeric value")
    elif got is None or abs(got - want) > (0.00001 if exact else 0.021):
        raise AssertionError("displayed saved numeric value mismatch")


def group_filename(kind: str, key: object) -> str:
    fields = (str(key),) if kind == "single" else tuple(str(v) for v in key)
    digest = hashlib.sha1((kind + ":" + "|".join(fields)).encode("utf-8")).hexdigest()[:14]
    return f"{kind}-{digest}.html"


def check_group(rows: list, frame, renderer, kind: str, pop: int) -> int:
    import pandas as pd
    # Rows are emitted by the pinned canonical renderer in this exact sort order.
    f = frame.copy()
    for h in (5, 10, 20):
        f[f"win_{h}d_pct"] = pd.to_numeric(f[f"win_{h}d_pct"], errors="coerce")
    f["avg_win_pct"] = f[[f"win_{h}d_pct" for h in (5, 10, 20)]].mean(axis=1)
    f = f.sort_values(["avg_win_pct", "count"], ascending=False)
    if len(rows) != len(f):
        raise AssertionError("group row count mismatch")
    for displayed, (_, expected) in zip(rows, f.iterrows()):
        if len(displayed) != 10:
            raise AssertionError("unexpected canonical summary column count")
        label = renderer.clabel(renderer.fields(expected, kind))
        shown = html.unescape(re.sub(r"<[^>]*>", "", str(displayed[0])))
        if not shown.startswith(label):
            raise AssertionError("displayed condition label differs from input row")
        count = float(expected["count"])
        check_close(displayed[1], count, exact=True)
        check_close(displayed[2], expected["retention_pct"])
        if count < 0 or count > pop:
            raise AssertionError("candidate count outside sector population")
        if abs(float(expected["retention_pct"]) - count / pop * 100) > 0.025:
            raise AssertionError("candidate retention contradicts saved sector population")
        for pos, name in (
            (3, "win_5d_pct"), (4, "win_10d_pct"), (5, "win_20d_pct"),
            (6, "avg_win_pct"), (7, "win_uplift_5d_pp"),
            (8, "win_uplift_10d_pp"), (9, "win_uplift_20d_pp"),
        ):
            check_close(displayed[pos], expected[name])
    return len(rows)


def audit(core: Path, stage: Path, dataset: str, out: Path, expected_sha: str) -> dict:
    import pandas as pd
    core, stage, out = core.resolve(), stage.resolve(), out.resolve()
    if dataset not in SECTORS:
        raise ValueError("unsupported sector")
    if not stage.is_relative_to(core / "build") or not (stage / "scripts").is_dir():
        raise ValueError("renderer must be isolated in build/scripts")
    if out == core / "build" or not out.is_relative_to(core / "build") or out.exists():
        raise ValueError("output must be a new subdirectory of private core/build")
    head = subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"],
                                   text=True).strip()
    if head != expected_sha:
        raise ValueError("immutable source SHA mismatch")
    source = core / "preview/kabu/analysis/225_group_all_period" / dataset
    inputs = [source / name for name, _ in KINDS.values()]
    inputs += [source / "condition_detail_manifest.csv", source / "semantic_status.json"]
    before = {}
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError("required saved input is absent: " + path.name)
        before[str(path)] = sha256(path)
    status = json.loads((source / "semantic_status.json").read_text(encoding="utf-8"))
    pop = int(status["source_rows"])
    if pop <= 0 or status.get("overall_pass") is not True:
        raise AssertionError("saved semantic bundle is not valid")
    manifest = pd.read_csv(source / "condition_detail_manifest.csv", low_memory=False)
    if len(manifest) != 447 or manifest.condition_key.duplicated().any():
        raise AssertionError("approved manifest is not 447 distinct conditions")
    slugmap = dict(zip(manifest.condition_key, manifest.slug))

    # The production/saved sources are never a Python write destination.
    sys.path.insert(0, str(stage / "scripts"))
    import refine_p2_report_information_architecture as renderer
    destination = out / "summaries"
    destination.mkdir(parents=True)
    renderer.SUM = destination
    groups_checked = {}
    rows_checked = {}
    index_checked = {}
    mismatch = []
    for kind, (csv_file, cols) in KINDS.items():
        frame = pd.read_csv(source / csv_file, low_memory=False)
        if frame.empty or not set(cols).issubset(frame.columns):
            raise AssertionError("required saved candidates missing or invalid")
        series = frame.groupby(cols[0] if kind == "single" else list(cols),
                               dropna=False, sort=False)
        expected = {group_filename(kind, key): g for key, g in series}
        if len(expected) != len(series):
            raise AssertionError("summary group filename collision")
        made = renderer.group_pages(kind, frame, slugmap)
        if made != len(expected):
            raise AssertionError("renderer output group count mismatch")
        actual = {p.name for p in destination.glob(f"{kind}-*.html")}
        if actual != set(expected):
            raise AssertionError("rendered group inventory differs from saved candidates")
        index = destination / f"{kind}_features.html"
        summary_rows = read_data(index)
        if len(summary_rows) != len(expected):
            raise AssertionError("summary index has a different number of groups")
        index_urls = []
        for item in summary_rows:
            if len(item) != 11:
                raise AssertionError("summary index unexpected column count")
            match = re.search(r'href="([^"]+\.html)"', str(item[0]))
            if not match:
                raise AssertionError("summary group hyperlink missing")
            name = match.group(1)
            if name not in expected:
                raise AssertionError("index links to group absent in candidate CSV")
            check_close(item[1], len(expected[name]), exact=True)
            index_urls.append(name)
        if set(index_urls) != actual or len(index_urls) != len(actual):
            raise AssertionError("index group URLs are not a bijection with HTML files")
        index_checked[kind] = len(summary_rows)
        validated = 0
        for name, g in expected.items():
            validated += check_group(read_data(destination / name), g, renderer, kind, pop)
        groups_checked[kind] = len(actual)
        rows_checked[kind] = validated
        print(f"PASS {dataset}/{kind}: groups={made} rows={validated}", flush=True)

    files = {p.name for p in destination.glob("*.html")}
    if len(files) != sum(groups_checked.values()) + 3:
        raise AssertionError("foreign or stale HTML files are present")
    legacy_canary = subprocess.check_output([
        "git", "-C", str(core), "ls-tree", "--name-only", "HEAD", "--",
        f"preview/kabu/analysis/225_group_all_period/{dataset}/summaries/{ORPHAN_CANARY}"
    ], text=True).strip()
    if dataset == "technology":
        if not legacy_canary or ORPHAN_CANARY in files:
            raise AssertionError("orphan canary must remain legacy-only")
    for path in inputs:
        if sha256(path) != before[str(path)]:
            raise AssertionError("original private CSV/JSON changed")
    if subprocess.check_output(["git", "-C", str(core), "diff", "--name-only"],
                               text=True).strip():
        raise AssertionError("private tracked content changed")
    return {
        "schema": 1, "status": "PASS_SAVED_INPUT_POPULATION_AUDIT",
        "sector": dataset, "private_sha": head,
        "candidate_groups": groups_checked, "candidate_rows_checked": rows_checked,
        "index_links_checked": index_checked, "html_pages": len(files),
        "legacy_orphan_canary_excluded": (dataset == "technology"),
        "source_sha256": {Path(path).name: sha for path, sha in before.items()},
        "created_from_candidates_only": True, "old_html_copied": False,
        "signals_recomputed": False, "production_p2_changed": False,
        "source_files_modified": False, "deployment_allowed": False,
        "certification_limit": "Verified HTML vs saved candidates and saved sector population; not a fresh signal-level financial validation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--dataset", choices=SECTORS, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-core-sha", required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    try:
        report = audit(args.core, args.stage, args.dataset, out, args.expected_core_sha)
    except Exception as exc:
        report = {
            "schema": 1, "status": "FAIL",
            "sector": args.dataset, "private_sha": args.expected_core_sha,
            "reason_type": type(exc).__name__,
            "reason": str(exc)[:240], "deployment_allowed": False,
        }
        (out).mkdir(parents=True, exist_ok=True)
        (out / "summary_candidate_audit.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
    (out / "summary_candidate_audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
