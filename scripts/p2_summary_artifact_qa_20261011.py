# Created: 2026-10-11 JST
"""Read-only release-smoke QA on retained six-sector HTML ZIP artifacts.

No source rebuilding. Independently validate archive SHA, all HTML page
inventory, embedded summary links, condition targets, and inline JS syntax for
representative pages. HTTP routing and real-browser DOM are separate gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

import pandas as pd


def sha256(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            d.update(b)
    return d.hexdigest()


def embedded_rows(source: str) -> list:
    m = re.search(r",D=(\[[\s\S]*?\]),HI=new Set", source)
    if not m:
        raise AssertionError("canonical embedded D array missing")
    d = json.loads(m.group(1))
    if not isinstance(d, list) or not d:
        raise AssertionError("empty or invalid interactive HTML data")
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", type=Path, required=True)
    ap.add_argument("--sector", required=True)
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expected-sha", required=True)
    a = ap.parse_args()
    root, output = a.core.resolve(), a.out.resolve()
    if output == root / "build" or not output.is_relative_to(root / "build") or output.exists():
        raise ValueError("fresh build subdirectory required")
    output.mkdir(parents=True)
    try:
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                       text=True).strip()
        if head != a.expected_sha:
            raise AssertionError("private checkout SHA mismatch")
        prev = json.loads(a.report.read_text(encoding="utf-8"))
        if prev.get("sector") != a.sector or prev.get("status") != "PASS_STAGED_REQUIRES_DEPLOY_APPROVAL":
            raise AssertionError("staging gate JSON invalid")
        if a.archive.name != prev.get("archive") or sha256(a.archive) != prev["archive_sha256"]:
            raise AssertionError("ZIP SHA256 mismatches archived successful staging")
        src = root / "preview/kabu/analysis/225_group_all_period" / a.sector
        manifest = pd.read_csv(src / "condition_detail_manifest.csv", low_memory=False)
        slugs = set(manifest.slug.astype(str))
        if len(slugs) != 447:
            raise AssertionError("expected 447 canonical condition URLs")
        archive = zipfile.ZipFile(a.archive, "r")
        members = archive.namelist()
        if archive.testzip() is not None or len(members) != prev["candidate_html_pages"]:
            raise AssertionError("corrupted/shortened staged zip")
        relative = {}
        for name in members:
            part = Path(name).parts
            if len(part) != 3 or part[0] != a.sector or part[1] != "summaries" or not part[2].endswith(".html"):
                raise AssertionError("unexpected archive path")
            if part[2] in relative:
                raise AssertionError("duplicate summary URL")
            relative[part[2]] = name
        indexed = set()
        links_checked = 0
        scripts_checked = 0
        with tempfile.TemporaryDirectory(dir=output) as temp:
            td = Path(temp)
            for k in ("single", "pair", "triple"):
                index = f"{k}_features.html"
                raw = archive.read(relative[index]).decode("utf-8")
                for entry in embedded_rows(raw):
                    match = re.search(r'href="([^"]+\.html)"', str(entry[0]))
                    if not match or match.group(1) not in relative:
                        raise AssertionError("summary index contains missing group URL")
                    indexed.add(match.group(1))
                    links_checked += 1
            for filename, name in relative.items():
                source = archive.read(name).decode("utf-8")
                if "<!doctype html>" not in source.lower() or "<title>" not in source:
                    raise AssertionError("malformed HTML header")
                rows = embedded_rows(source)
                if filename.endswith("_features.html"):
                    pass
                else:
                    if filename not in indexed:
                        raise AssertionError("unindexed group HTML")
                    for row in rows:
                        # Linkless candidates legitimately lack an approved 447-condition detail.
                        for href in re.findall(r'href="([^"]+)"', str(row[0])):
                            if href.startswith("../conditions/charts/"):
                                slug = Path(href).stem
                                if slug not in slugs:
                                    raise AssertionError("chart link outside canonical manifest")
                                links_checked += 1
                            elif href.startswith("../conditions/"):
                                slug = Path(href).stem
                                if slug not in slugs:
                                    raise AssertionError("condition link outside canonical manifest")
                                links_checked += 1
                if filename in {f"{k}_features.html" for k in ("single", "pair", "triple")} or filename in {
                    sorted(f for f in relative if f.startswith(k + "-"))[0]
                    for k in ("single", "pair", "triple")
                }:
                    for n, js in enumerate(re.findall(r"<script[^>]*>([\s\S]*?)</script>", source)):
                        path = td / (filename + f".{n}.js")
                        path.write_text(js, encoding="utf-8")
                        result = subprocess.run(["node", "--check", str(path)],
                                                capture_output=True, text=True)
                        if result.returncode:
                            raise AssertionError("inline JS syntax check failed for " + filename)
                        scripts_checked += 1
        if indexed | {f"{k}_features.html" for k in ("single", "pair", "triple")} != set(relative):
            raise AssertionError("archive has orphaned/unknown group HTML")
        if subprocess.check_output(["git", "-C", str(root), "diff", "--name-only"],
                                   text=True).strip():
            raise AssertionError("source directory altered")
        report = {
            "schema": 1, "status": "PASS_STATIC_ARTIFACT_QA", "sector": a.sector,
            "private_sha": head, "pages_verified": len(relative),
            "links_verified": links_checked, "javascript_scripts_checked": scripts_checked,
            "reused_original_staging_artifact": True, "original_zip_sha256": prev["archive_sha256"],
            "original_data_recomputed": False, "production_modified": False,
            "deployment_allowed": False,
            "unverified": ["real-browser DOM and interaction", "external HTTP/Apache old-URL handling"],
        }
    except Exception as e:
        report = {
            "schema": 1, "status": "FAIL", "sector": a.sector,
            "reason_type": type(e).__name__, "reason": str(e)[:400],
            "deployment_allowed": False,
        }
    (output / "artifact_static_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if report["status"] != "PASS_STATIC_ARTIFACT_QA":
        sys.exit(1)


if __name__ == "__main__":
    main()
