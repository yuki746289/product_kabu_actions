# Created: 2026-10-12 JST
"""Read-only, real-browser smoke test on retained successful summary ZIP artifacts.

No source renderer, no candidate CSV, no historical signal recomputation, and no
production write. Tests extracted HTML through local file:// navigation only.
A failure writes a small JSON checkpoint before failing closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import zipfile

KINDS = ("single", "pair", "triple")
SUCCESS = "PASS_BROWSER_SMOKE_FILE_PROTOCOL"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(sector: str, artifact: Path, output: Path) -> dict:
    from playwright.sync_api import sync_playwright

    archive_path = artifact / f"p2_candidate_summaries_{sector}.zip"
    report_path = artifact / "staging_report.json"
    stage = json.loads(report_path.read_text(encoding="utf-8"))
    if stage.get("status") != "PASS_STAGED_REQUIRES_DEPLOY_APPROVAL":
        raise AssertionError("prior staging did not PASS")
    if stage.get("core_sha") != "0e2d5722d6764102adfe6995b793f533b60b1532":
        raise AssertionError("immutable Private input differs")
    if stage.get("sector") != sector or stage.get("archive") != archive_path.name:
        raise AssertionError("staging artifact sector or archive mismatch")
    if checksum(archive_path) != stage["archive_sha256"]:
        raise AssertionError("prior successful ZIP digest mismatch")

    with tempfile.TemporaryDirectory(prefix="p2_browser_", dir=output) as tmpdir:
        root = Path(tmpdir)
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise AssertionError("staged archive failed integrity check")
            members = archive.namelist()
            if len(members) != int(stage["candidate_html_pages"]):
                raise AssertionError("staged summary count mismatch")
            for member in members:
                parts = Path(member).parts
                if len(parts) != 3 or parts[:2] != (sector, "summaries") or not parts[2].endswith(".html"):
                    raise AssertionError("archive member outside immutable sector summary directory")
                dest = root / sector / "summaries" / parts[-1]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.read(member))

        checked = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                context = browser.new_context(locale="ja-JP")
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)[:300]))
                for kind in KINDS:
                    path = root / sector / "summaries" / f"{kind}_features.html"
                    page.goto(path.as_uri(), wait_until="load", timeout=20000)
                    page.wait_for_function(
                        "() => !!document.querySelector('#bd tr')", timeout=15000)
                    if not page.locator("h1").is_visible():
                        raise AssertionError(f"{kind} heading not visible")
                    if not page.locator("#q").is_visible():
                        raise AssertionError(f"{kind} search control not visible")
                    if page.locator("#bd tr").count() < 1:
                        raise AssertionError(f"{kind} table did not render")
                    initial_rows = page.locator("#bd tr").count()
                    if initial_rows > 50:
                        raise AssertionError("default page size unexpectedly over 50")
                    page.locator("#q").fill("___P2_NO_SUCH_GROUP_20261012___")
                    if page.locator("#bd tr").count() != 0:
                        raise AssertionError(f"{kind} client-side search filter failed")
                    page.locator("#q").fill("")
                    if page.locator("#bd tr").count() < 1:
                        raise AssertionError(f"{kind} search reset failed")
                    page.locator("#ps").select_option("25")
                    if page.locator("#bd tr").count() > 25:
                        raise AssertionError(f"{kind} page-size pagination failed")
                    # Follow the first real group link; both pages originate
                    # in the already-validated original immutable artifact.
                    link = page.locator("#bd tr td:first-child a").first
                    href = link.get_attribute("href")
                    if not href or not re.fullmatch(rf"{kind}-[0-9a-f]{{14}}\.html", href):
                        raise AssertionError(f"{kind} group hyperlink is invalid")
                    link.click(timeout=10000)
                    page.wait_for_function(
                        "() => !!document.querySelector('#bd tr')", timeout=15000)
                    if not page.url.endswith("/" + href):
                        raise AssertionError(f"{kind} click did not navigate to group")
                    if not page.locator("h1").is_visible():
                        raise AssertionError(f"{kind} group heading not visible")
                    if page.locator("#bd tr").count() < 1:
                        raise AssertionError(f"{kind} group content not displayed")
                    checked.append({"kind": kind, "index_rendered": True,
                                    "search_pass": True, "paging_pass": True,
                                    "group_navigation_pass": True})
                if errors:
                    raise AssertionError("JavaScript runtime errors: " + "; ".join(errors[:3]))
            finally:
                browser.close()

    return {
        "schema": 1, "status": SUCCESS, "sector": sector,
        "source_run": 38127100421,
        "staged_zip_sha256": stage["archive_sha256"],
        "pages_available_in_archive": int(stage["candidate_html_pages"]),
        "browser": "Playwright Chromium headless / file://",
        "checks": checked,
        "old_html_copied": False, "source_data_recomputed": False,
        "artifact_rebuilt": False, "source_mutated": False,
        "deployment_allowed": False,
        "unverified": [
            "Apache/live HTTP route and old URL status codes",
            "full manual visual regression of all pages",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sector", required=True)
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    dest = args.out.resolve()
    if dest.exists():
        raise ValueError("checkpoint must use an unused directory")
    dest.mkdir(parents=True)
    try:
        result = run(args.sector, args.artifact.resolve(), dest)
    except Exception as exc:
        result = {
            "schema": 1, "status": "FAIL", "sector": args.sector,
            "reason_type": type(exc).__name__, "reason": str(exc)[:600],
            "deployment_allowed": False,
        }
    (dest / "browser_smoke.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if result["status"] != SUCCESS:
        sys.exit(1)


if __name__ == "__main__":
    main()
