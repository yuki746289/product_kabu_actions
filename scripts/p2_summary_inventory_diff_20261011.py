# Created: 2026-10-11 JST
"""Read-only forensic inventory audit: saved candidate vs full P2 summary universes.

Never regenerate historical signals or copy old HTML into generated output.
Output only a JSON report in a new, untracked build/ directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import pandas as pd

FILES = {
    "single": ("advantage_single_candidates.csv", "all_single_categories.csv", ["feature"]),
    "pair": ("advantage_pairwise_candidates.csv", "all_pairwise_combinations.csv", ["feature1", "feature2"]),
    "triple": ("advantage_triple_candidates.csv", "tested_triple_combinations.csv", ["feature1", "feature2", "feature3"]),
}
EXPECTED = {"single": 32, "pair": 120, "triple": 557}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalogue(path: Path, kind: str, cols: list[str]) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, low_memory=False)
    if not set(cols).issubset(df.columns):
        raise ValueError(f"{path.name}: required columns {cols}, got {list(df.columns)}")
    # Mirror the canonical UI renderer's default dropna=False group semantics.
    groups = df.groupby(cols[0] if kind == "single" else cols, dropna=False, sort=False)
    names = set()
    for raw_key, _ in groups:
        fields = (str(raw_key),) if kind == "single" else tuple(str(v) for v in raw_key)
        token = kind + ":" + "|".join(fields)
        suffix = hashlib.sha1(token.encode("utf-8")).hexdigest()[:14]
        names.add(f"{kind}-{suffix}.html")
    if len(names) != len(groups):
        raise ValueError(f"hash collision in {kind} {path.name}")
    return {"rows": len(df), "groups": len(names), "sha256": digest(path),
            "bytes": path.stat().st_size, "filenames": sorted(names)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--core", type=Path, required=True)
    ap.add_argument("--dataset", default="technology")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    root = args.core.resolve()
    out = args.out.resolve()
    allowed = (root / "build").resolve()
    if out == allowed or not out.is_relative_to(allowed) or out.exists():
        raise ValueError("Output must be a fresh subdirectory of core/build")
    if args.dataset != "technology":
        raise ValueError("Only technology pilot authorized")
    site = root / "preview/kabu/analysis/225_group_all_period" / args.dataset
    tracked = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r",
                                      "--name-only", "HEAD", "--",
                                      f"preview/kabu/analysis/225_group_all_period/{args.dataset}/summaries"],
                                     text=True).splitlines()
    actual = {Path(p).name for p in tracked if p.endswith(".html")}
    kinds = {}
    for kind, (candidate_file, full_file, cols) in FILES.items():
        existing = {n for n in actual if n.startswith(kind + "-") and n.endswith(".html")}
        index = f"{kind}_features.html"
        if index not in actual or len(existing) != EXPECTED[kind]:
            raise ValueError(f"Canonical inventory changed for {kind}: {len(existing)} vs {EXPECTED[kind]}")
        entries = {}
        for label, name in (("candidate", candidate_file), ("full", full_file)):
            item = catalogue(site / name, kind, cols)
            keys = set(item.pop("filenames"))
            item.update({"missing_from_legacy": sorted(existing - keys),
                         "unexpected_vs_legacy": sorted(keys - existing),
                         "matching_legacy_groups": len(existing & keys),
                         "exact_filename_match": keys == existing})
            entries[label] = item
        kinds[kind] = {"reference_groups": len(existing), **entries}
    report = {"schema": 1, "status": "READ_ONLY_INVENTORY_DIAGNOSIS", "dataset": args.dataset,
              "private_sha": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
              "canonical_summary_pages": len(actual),
              "candidate_pages_computed": 3 + sum(d["candidate"]["groups"] for d in kinds.values()),
              "full_pages_computed": 3 + sum(d["full"]["groups"] for d in kinds.values()),
              "kinds": kinds, "source_signals_recomputed": False,
              "source_html_copied": False, "deployment_allowed": False}
    if len(actual) != 712:
        raise ValueError(f"unexpected reference total: {len(actual)}")
    out.mkdir(parents=True)
    (out / "summary_input_inventory_audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "reference": len(actual),
                      "candidate_pages": report["candidate_pages_computed"],
                      "full_pages": report["full_pages_computed"],
                      "groups": {k: {setname: {"groups": d[setname]["groups"],
                                               "missing": len(d[setname]["missing_from_legacy"]),
                                               "extra": len(d[setname]["unexpected_vs_legacy"])}
                                      for setname in ("candidate", "full")}
                                 for k, d in kinds.items()}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
