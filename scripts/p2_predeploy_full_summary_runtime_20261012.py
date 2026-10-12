# Created: 2026-10-12 JST
"""Final one-shot predeploy HTML runtime and exact-release-byte gate.

Uses only immutable successful HTML archives from Run 38127100421 and
saved URL manifest audits. Never regenerates HTML, CSV, signals or P2 logic.
Checks ALL 3,370 released summary URLs, not just a browser sample.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

RELEASE = "1fa172fdeac45980f3ed10716e61adc764cebb90"
SOURCE = "0e2d5722d6764102adfe6995b793f533b60b1532"
SECTORS = ("technology", "financials", "consumer_goods", "materials",
           "capital_goods_others", "transportation_utilities")


def must(test, reason):
    if not test:
        raise AssertionError(reason)


def git(core, *args):
    return subprocess.check_output(["git", "-C", str(core), *args],
                                   text=True).strip()


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(core, archive_dir, gate_file, sector, out):
    must(sector in SECTORS, "Invalid sector")
    must(git(core, "rev-parse", "HEAD") == RELEASE, "Private release SHA differs")
    must((core / "docs/ACTIONS_MIGRATION.md").is_file(),
         "Private public-Action migration rule missing")
    archive = archive_dir / f"p2_candidate_summaries_{sector}.zip"
    original = json.loads((archive_dir / "staging_report.json").read_text("utf-8"))
    must(original["sector"] == sector and original["core_sha"] == SOURCE
         and original["status"] == "PASS_STAGED_REQUIRES_DEPLOY_APPROVAL",
         "Original successful source stage does not match")
    must(sha256(archive) == original["archive_sha256"],
         "Original successful archive SHA256 differs")
    urlgate = json.loads(gate_file.read_text("utf-8"))
    must(urlgate["sector"] == sector and urlgate["private_sha"] == SOURCE
         and urlgate["status"] == "PASS", "Original URL inventory gate mismatched")
    inventory = urlgate["url_inventory"]
    must(inventory["old_total"] == 712, "Expected canonical old 712 paths")
    must(inventory["candidate_total"] == int(original["candidate_html_pages"]),
         "Approved candidate HTML count mismatch")

    base = f"preview/kabu/analysis/225_group_all_period/{sector}/summaries/"
    gitpaths = set(git(core, "ls-tree", "-r", "--name-only",
                       "HEAD", "--", base).splitlines())
    require_names = {p[len(base):] for p in gitpaths if p.endswith(".html")}
    old_only = set()
    new_only = set()
    for kind, entry in inventory["families"].items():
        old_only.update(entry["old_only_names"])
        new_only.update(entry["candidate_only_names"])
    must(len(old_only) == inventory["old_only"] and len(new_only) == inventory["candidate_only"],
         "Retired/new URL inventory files inconsistent")
    must(not (old_only & require_names), "Retired old HTML remains on release tree")
    must(new_only <= require_names, "Candidate-only new URL missing on release tree")

    summary = {
        "schema": 1, "status": "RUNNING", "sector": sector,
        "fixed_private_release_sha": RELEASE, "original_source_sha": SOURCE,
        "successful_stage_run": 38127100421,
        "original_archive_sha256": original["archive_sha256"],
        "release_html_target": int(original["candidate_html_pages"]),
        "old_url_absent": len(old_only), "new_urls_present": len(new_only),
        "passed": 0, "failures": [],
        "source_recomputed": False, "files_modified": False,
        "deployment_performed": False,
    }
    checkpoint = out / "predeploy_final.json"

    def save():
        checkpoint.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    with tempfile.TemporaryDirectory(dir=out, prefix="p2_static_") as temp:
        root = Path(temp)
        with zipfile.ZipFile(archive) as z:
            must(z.testzip() is None, "ZIP CRC validation failure")
            members = z.namelist()
            expected = {f"{sector}/summaries/{name}" for name in require_names}
            must(len(members) == len(expected) and set(members) == expected,
                 "Release file list differs from original successful ZIP")
            for name in members:
                parts = Path(name).parts
                must(len(parts) == 3 and parts[0] == sector and parts[1] == "summaries",
                     "Archive path out of summary directory")
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(name))
                content = dest.read_bytes()
                # Compare exact Git blob SHA, not merely equal filenames.
                gitsha = git(core, "rev-parse", f"HEAD:{base}{parts[2]}")
                # Single python SHA-1 implementation of standard Git blob.
                sha = hashlib.sha1(
                    f"blob {len(content)}\0".encode("ascii") + content
                ).hexdigest()
                must(sha == gitsha,
                     f"Release blob differs from successful stage: {parts[2]}")

        save()
        with sync_playwright() as tool:
            browser = tool.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                ctx = browser.new_context(locale="ja-JP",
                                          viewport={"width": 1365, "height": 860})
                page = ctx.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)[:250]))
                for index, path in enumerate(sorted((root / sector / "summaries").glob("*.html")), 1):
                    errors.clear()
                    try:
                        page.goto(path.as_uri(), wait_until="domcontentloaded", timeout=25000)
                        page.wait_for_function(
                            "() => !!document.querySelector('#bd tr')",
                            timeout=13000)
                        must(page.locator("#bd tr").count() > 0, "Table empty")
                        must(page.locator("h1").count() == 1, "Title not present")
                        must(not errors, "Uncaught JavaScript exception " +
                             "; ".join(errors[:2]))
                        summary["passed"] += 1
                    except Exception as e:
                        summary["status"] = "FAIL"
                        summary["failures"].append({
                            "name": path.name, "type": type(e).__name__,
                            "reason": str(e)[:400]})
                        save()
                        break
                    if index % 50 == 0:
                        save()
                        print(f"{sector} {index}/{len(expected)} PASS", flush=True)
            finally:
                browser.close()

    if not summary["failures"]:
        must(summary["passed"] == len(require_names), "Full browser count incomplete")
        must(git(core, "diff", "--name-only") == "", "Private tracked diff not clean")
        summary["status"] = "PASS_PREDEPLOY_FULL_SUMMARY_RUNTIME"
    save()
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--core", type=Path, required=True)
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--url-gate", type=Path, required=True)
    p.add_argument("--sector", choices=SECTORS, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    if out.exists():
        raise ValueError("Must use new output directory under private build/")
    must(out.is_relative_to((a.core.resolve() / "build")),
         "Output must be confined to private core/build/")
    out.mkdir(parents=True)
    try:
        result = run(a.core.resolve(), a.stage.resolve(), a.url_gate.resolve(), a.sector, out)
    except Exception as e:
        result = {"schema": 1, "sector": a.sector, "status": "FAIL",
                  "reason": str(e)[:600], "type": type(e).__name__,
                  "deployment_performed": False, "source_recomputed": False}
        (out / "predeploy_final.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result.get(k) for k in
          ("sector", "status", "passed", "old_url_absent",
           "new_urls_present", "failures", "reason")}, ensure_ascii=False), flush=True)
    if result["status"] != "PASS_PREDEPLOY_FULL_SUMMARY_RUNTIME":
        sys.exit(1)


if __name__ == "__main__":
    main()
