# Created: 2026-10-12 JST
"""Focused post-pass test of interactive P2 favorites in immutable HTML."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

HEAD = "1fa172fdeac45980f3ed10716e61adc764cebb90"


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--core", type=Path, required=True)
    a.add_argument("--sector", required=True)
    a.add_argument("--out", type=Path, required=True)
    opts = a.parse_args()
    core = opts.core.resolve()
    out = opts.out.resolve()
    if out.exists():
        raise ValueError("new output directory needed")
    out.mkdir(parents=True)
    findings = []
    try:
        sha = subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"],
                                      text=True).strip()
        if sha != HEAD:
            raise AssertionError("immutable checkout does not match expected HEAD")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                context = browser.new_context(locale="ja-JP")
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)[:350]))
                base = core / "preview/kabu/analysis/225_group_all_period" / opts.sector
                toggled = False
                for rel in ("analysis/high_entry_accuracy.html", "conditions/index.html"):
                    file = base / rel
                    if not file.exists():
                        raise AssertionError("missing favorite test input: " + rel)
                    errors.clear()
                    page.goto(file.as_uri(), wait_until="load", timeout=40000)
                    page.wait_for_timeout(400)
                    if errors:
                        raise AssertionError(rel + " JavaScript error: " + errors[0])
                    stars = page.locator("button.p2-favorite-btn:not([disabled])")
                    count = stars.count()
                    entry = {"template": rel, "enabled_stars": count}
                    if count:
                        star = stars.first
                        initial = star.evaluate("(e)=>e.classList.contains('is-favorite')")
                        star.click(timeout=12000)
                        after = star.evaluate("(e)=>e.classList.contains('is-favorite')")
                        if after == initial:
                            raise AssertionError(rel + " favorite click had no effect")
                        star.click(timeout=12000)
                        final = star.evaluate("(e)=>e.classList.contains('is-favorite')")
                        if final != initial:
                            raise AssertionError(rel + " favorite reset failed")
                        entry["toggle_and_restore"] = "PASS"
                        toggled = True
                    findings.append(entry)
                if not toggled:
                    raise AssertionError("no enabled favorite control in either audited template")
                if errors:
                    raise AssertionError("post-favorite JavaScript error: " + errors[0])
            finally:
                browser.close()
        result = {"schema": 1, "status": "PASS_FAVORITE_SMOKE",
                  "sector": opts.sector, "head": HEAD,
                  "pages": findings, "prior_artifacts_reused": True,
                  "production_modified": False}
    except Exception as e:
        result = {"schema": 1, "status": "FAIL", "sector": opts.sector,
                  "findings": findings, "reason_type": type(e).__name__,
                  "reason": str(e)[:600], "production_modified": False}
    (out / "favorites.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if result["status"] != "PASS_FAVORITE_SMOKE":
        sys.exit(1)


if __name__ == "__main__":
    main()
