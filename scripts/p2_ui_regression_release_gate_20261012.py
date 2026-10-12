# Created: 2026-10-12 JST
"""One-shot, fail-closed release UI regression on immutable checked-in HTML.

Reuse successful stage ZIP (Run 38127100421); do not render, recompute or mutate
Production P2, source CSV, old audited pages or successful artifacts.
Each sector writes a standalone checkpoint and optional screenshots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

RELEASE_SHA = "1fa172fdeac45980f3ed10716e61adc764cebb90"
SOURCE_SHA = "0e2d5722d6764102adfe6995b793f533b60b1532"
SECTORS = ("technology", "financials", "consumer_goods", "materials",
           "capital_goods_others", "transportation_utilities")
FAMILIES = ("single", "pair", "triple")


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def require(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def dimensions(page) -> dict:
    return page.evaluate("""() => ({
        viewport: innerWidth,
        bodyScroll: document.documentElement.scrollWidth,
        width: document.body.getBoundingClientRect().width,
        height: document.body.getBoundingClientRect().height,
        tableWrappers: document.querySelectorAll('.table-wrap').length,
        sticky: document.querySelectorAll('.p2-sticky-condition,.p2-sticky-dataset').length,
    })""")


def open_html(page, path: Path, errors: list[str], label: str) -> None:
    require(path.is_file(), "Missing audited HTML: " + str(path))
    errors.clear()
    page.goto(path.as_uri(), wait_until="load", timeout=40000)
    page.wait_for_timeout(250)
    require(page.locator("body").count() == 1, label + " missing body")
    require(len(page.locator("body").inner_text(timeout=10000)) > 60,
            label + " empty visible body")
    require(not errors, label + " JavaScript exception: " + "; ".join(errors[:2]))


def check_summary(page, root: Path, errors: list[str], out: Path) -> list[dict]:
    cases = []
    for kind in FAMILIES:
        index = root / f"{kind}_features.html"
        open_html(page, index, errors, "summary " + kind)
        page.wait_for_function("() => !!document.querySelector('#bd tr')", timeout=15000)
        require(page.locator("h1").is_visible(), "summary heading invisible")
        q = page.locator("#q")
        require(q.is_visible(), "summary search missing")
        q.fill("___NONEXISTENT_P2_20261012___")
        require(page.locator("#bd tr").count() == 0, kind + " search failed")
        q.fill("")
        require(page.locator("#bd tr").count() > 0, kind + " search reset failed")
        page.locator("#ps").select_option("25")
        require(page.locator("#bd tr").count() <= 25, kind + " paging failed")
        headers = page.locator("#hd th")
        require(headers.count() > 0, kind + " sortable header missing")
        headers.first.click()
        require(page.locator("#bd tr").count() > 0, kind + " sorting emptied rows")
        favored = False
        stars = page.locator(".p2-favorite-btn:not([disabled])")
        if stars.count():
            star = stars.first
            star.click(timeout=6000)
            require(star.evaluate("(el) => el.classList.contains('is-favorite')"),
                    kind + " favorite toggle failed")
            favored = True
            star.click(timeout=6000)
        require(not errors, kind + " JS exception: " + "; ".join(errors[:2]))
        snapshot = {}
        for width in (1440, 1024, 768):
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(120)
            d = dimensions(page)
            require(d["height"] > 250 and d["width"] > 0,
                    kind + " empty responsive frame")
            snapshot[str(width)] = d
        if kind == "single":
            page.screenshot(path=str(out / "summary_single_768.png"), full_page=False)
        page.set_viewport_size({"width": 1440, "height": 900})
        group = page.locator("#bd tr td:first-child a").first
        require(group.count() == 1, kind + " detail link missing")
        href = group.get_attribute("href")
        require(bool(re.fullmatch(rf"{kind}-[a-f0-9]{{14}}\.html", href or "")),
                kind + " invalid group href: " + str(href))
        group.click(timeout=10000)
        page.wait_for_function("() => !!document.querySelector('#bd tr')", timeout=15000)
        require(page.url.endswith("/" + href), kind + " group navigation failed")
        require(not errors, kind + " group JS exception: " + "; ".join(errors[:2]))
        cases.append({"family": kind, "search": "PASS", "sort": "PASS",
                      "paging": "PASS", "favorite_tested": favored,
                      "group_link": "PASS", "responsive": snapshot})
    return cases


def check_other_templates(page, core: Path, sector: str, errors: list[str],
                          out: Path) -> list[dict]:
    root = core / "preview/kabu/analysis/225_group_all_period" / sector
    results = []

    high = root / "analysis/high_entry_accuracy.html"
    page.set_viewport_size({"width": 1440, "height": 900})
    open_html(page, high, errors, "high-entry analysis")
    require(page.locator("h1").is_visible(), "high-entry heading missing")
    require(page.locator("table").count() > 0, "high-entry table missing")
    page.screenshot(path=str(out / "high_entry_1440.png"), full_page=False)
    results.append({"template": "high_entry_accuracy", "dom": "PASS"})

    page.set_viewport_size({"width": 1024, "height": 900})
    source = root / "analysis/or_combinations.html"
    open_html(page, source, errors, "OR combinations")
    require(page.locator("#expansion225Head").count() == 1, "OR header missing")
    require(page.locator("#expansion225Body").count() == 1, "OR body missing")
    before = page.locator("#expansion225Body").evaluate("(el)=>el.scrollLeft")
    right = page.locator("#expansion225Right")
    require(right.count() == 1, "OR right-scroll button missing")
    right.click(timeout=9000)
    page.wait_for_timeout(180)
    after = page.locator("#expansion225Body").evaluate("(el)=>el.scrollLeft")
    page.locator("#expansion225Home").click(timeout=9000)
    require(not errors, "OR control JS exception: " + "; ".join(errors[:2]))
    page.screenshot(path=str(out / "or_conditions_1024.png"), full_page=False)
    results.append({"template": "or_combinations", "dom": "PASS",
                    "button_exercised": True, "scroll_before": before,
                    "scroll_after": after})

    source = root / "conditions/charts/p-0060dbcc46a8011f.html"
    page.set_viewport_size({"width": 1440, "height": 900})
    open_html(page, source, errors, "condition chart")
    chart = page.locator("#chart")
    require(chart.count() == 1, "monthly chart canvas missing")
    page.wait_for_function(
        "() => { const c=document.getElementById('chart'); return c&&c.width>0&&c.height>0 }",
        timeout=15000)
    for control, value in (("#horizon", "5"), ("#entryStyle", "line"),
                           ("#winMode", "monthly"), ("#displayRange", "36")):
        select = page.locator(control)
        require(select.count() == 1, "chart control missing: " + control)
        select.select_option(value)
        page.wait_for_timeout(100)
    require(not errors, "chart control JS exception: " + "; ".join(errors[:2]))
    csize = chart.evaluate("(el)=>({w:el.width,h:el.height})")
    require(csize["w"] > 0 and csize["h"] > 0, "chart blank canvas dimension")
    page.screenshot(path=str(out / "chart_1440.png"), full_page=False)
    results.append({"template": "monthly_chart", "dom": "PASS",
                    "controls": "PASS", "canvas": csize})

    source = root / "conditions/s-0c5d25b829768750.html"
    open_html(page, source, errors, "condition detail")
    require(page.locator("table").count() > 0, "condition detail table absent")
    require(not errors, "detail JS exception: " + "; ".join(errors[:2]))
    results.append({"template": "condition_detail", "dom": "PASS"})
    return results


def run(core: Path, stage: Path, sector: str, out: Path) -> dict:
    from playwright.sync_api import sync_playwright

    require(sector in SECTORS, "unknown sector")
    require((core / "docs/ACTIONS_MIGRATION.md").is_file(), "missing architecture policy")
    zip_path = stage / f"p2_candidate_summaries_{sector}.zip"
    report = json.loads((stage / "staging_report.json").read_text(encoding="utf-8"))
    require(report.get("status") == "PASS_STAGED_REQUIRES_DEPLOY_APPROVAL",
            "original stage not PASS")
    require(report.get("core_sha") == SOURCE_SHA and report.get("sector") == sector,
            "original stage SHA/sector mismatch")
    require(report.get("archive_sha256") == digest(zip_path), "staged ZIP SHA mismatch")
    with tempfile.TemporaryDirectory(dir=out, prefix="p2_ui_") as tempdir:
        root = Path(tempdir)
        with zipfile.ZipFile(zip_path) as zipf:
            require(zipf.testzip() is None, "original ZIP invalid")
            members = zipf.namelist()
            require(len(members) == int(report["candidate_html_pages"]),
                    "original ZIP page count mismatch")
            for member in members:
                parts = Path(member).parts
                require(len(parts) == 3 and parts[0] == sector
                        and parts[1] == "summaries"
                        and parts[2].endswith(".html"), "invalid ZIP member")
                dest = root / sector / "summaries" / parts[2]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zipf.read(member))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                context = browser.new_context(locale="ja-JP",
                                              viewport={"width": 1440, "height": 900})
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)[:300]))
                summaries = check_summary(page, root / sector / "summaries", errors, out)
                others = check_other_templates(page, core, sector, errors, out)
                require(not errors, "final JavaScript exception")
            finally:
                browser.close()
    return {
        "schema": 1, "status": "PASS_UI_REGRESSION", "sector": sector,
        "fixed_private_sha": RELEASE_SHA, "source_data_sha": SOURCE_SHA,
        "successful_stage_run": 38127100421,
        "successful_zip_sha256": report["archive_sha256"],
        "candidate_pages_reused": int(report["candidate_html_pages"]),
        "summary_families": summaries, "other_templates": others,
        "browser": "Chromium/Playwright file protocol",
        "source_recomputed": False, "prior_artifact_regenerated": False,
        "production_modified": False, "deployment_performed": False,
        "limits": ["Screenshots sampled, not all-page visual diff",
                   "No Windows local Apache/real user-browser access"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--sector", choices=SECTORS, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise ValueError("fresh output directory required")
    out.mkdir(parents=True)
    try:
        result = run(args.core.resolve(), args.staging.resolve(), args.sector, out)
    except Exception as exc:
        result = {"schema": 1, "status": "FAIL", "sector": args.sector,
                  "reason_type": type(exc).__name__, "reason": str(exc)[:700],
                  "deployment_performed": False}
    (out / "ui_regression.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"sector": args.sector, "status": result["status"],
                      "reason": result.get("reason"),
                      "summary_families": len(result.get("summary_families", [])),
                      "other_templates": len(result.get("other_templates", []))},
                     ensure_ascii=False), flush=True)
    if result["status"] != "PASS_UI_REGRESSION":
        sys.exit(1)


if __name__ == "__main__":
    main()
