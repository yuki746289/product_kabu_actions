# Created: 2026-10-12T12:00:00+09:00
"""Read-only, sharded cross-page legacy-URL / internal-navigation predeploy gate.

Never generates historical signals, CSV or HTML. Scans the *committed* site
at an immutable private SHA, using the saved 38127100421 URL inventories.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

HEAD = "d3b173fb073a5938631d9bccf57edaf0bb6a8c51"
SOURCE = "0e2d5722d6764102adfe6995b793f533b60b1532"
PREFIX = "preview/kabu/"
SECTORS = ("technology", "financials", "consumer_goods", "materials",
           "capital_goods_others", "transportation_utilities")
SHARDS = ("root", "conditions", "details", "summaries", "analysis_root",
          "225_exclusion_all_period", "225_indicator_stageb",
          "225_indicators", "225_sector_all_period", "or_charts",
          "or_details", "group_globals") + tuple("group_" + x for x in SECTORS)
EXT = {".html", ".htm", ".js", ".xml"}
ATTR = re.compile(r'\b(?:href|src|action|data-href|data-url)\s*=\s*(["\x27])(.*?)\1', re.I | re.S)
XML_LOC = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.I | re.S)
NAV_JSON = re.compile(r"(?:^|/)(?:[^/]*(?:nav|menu|manifest|sitemap|links)[^/]*)\.json$", re.I)


def run_git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   text=True, encoding="utf-8").strip()


def assert_ok(value, error: str) -> None:
    if not value:
        raise AssertionError(error)


def shard_of(path: str) -> str:
    assert_ok(path.startswith(PREFIX), "Outside site: " + path)
    bits = path[len(PREFIX):].split("/")
    if len(bits) == 1 or bits[0] in ("_runtime", "_samples"):
        return "root"
    if bits[0] in ("conditions", "details", "summaries"):
        return bits[0]
    if bits[0] != "analysis":
        return "UNCLASSIFIED"
    if len(bits) == 2:
        return "analysis_root"
    if bits[1] == "225_group_all_period":
        if len(bits) >= 4 and bits[2] in SECTORS:
            return "group_" + bits[2]
        return "group_globals"
    if bits[1] in SHARDS:
        return bits[1]
    return "UNCLASSIFIED"


def relevant(path: str) -> bool:
    return Path(path).suffix.lower() in EXT or bool(NAV_JSON.search(path))


def load_manifests(root: Path, core: Path):
    current = set(run_git(core, "ls-tree", "-r", "--name-only", HEAD, "--", PREFIX).splitlines())
    old_urls = set()
    by_filename = {}
    sectors = {}
    for sector in SECTORS:
        f = root / ("p2-nextstage-gate-" + sector) / "nextstage_audit.json"
        obj = json.loads(f.read_text(encoding="utf-8"))
        assert_ok(obj.get("sector") == sector and obj.get("private_sha") == SOURCE
                  and obj.get("status") == "PASS", "Saved URL audit invalid: " + sector)
        inv = obj["url_inventory"]
        assert_ok(inv["old_total"] == 712 and inv["candidate_only"] == 2,
                  "Old manifest totals invalid: " + sector)
        names = set()
        for family in inv["families"].values():
            names.update(family["old_only_names"])
        assert_ok(len(names) == inv["old_only"], "Old name cardinality invalid: " + sector)
        stem = PREFIX + "analysis/225_group_all_period/" + sector + "/summaries/"
        current_count = sum(p.startswith(stem) and p.endswith(".html") for p in current)
        assert_ok(current_count == inv["candidate_total"],
                  "Current released summary count mismatch: " + sector)
        for n in names:
            assert_ok(stem + n not in current, "Retired URL still present: " + sector + "/" + n)
            target = "/kabu/analysis/225_group_all_period/" + sector + "/summaries/" + n
            old_urls.add(target)
            by_filename.setdefault(n, set()).add(target)
        sectors[sector] = {"old_only": len(names), "current": current_count}
    assert_ok(len(old_urls) == 914, "Expected 914 retired paths")
    return current, old_urls, by_filename, sectors


def absolute_local_href(source_path: str, ref: str):
    ref = html.unescape(ref).strip()
    if not ref or ref.startswith(("#", "javascript:", "mailto:", "data:", "tel:", "{{")):
        return None
    page = "http://localhost/" + source_path[len("preview/"):]
    dest = urlsplit(urljoin(page, ref))
    if dest.scheme not in ("http", "https") or dest.netloc.lower() not in ("localhost", "127.0.0.1"):
        return None
    path = posixpath.normpath(unquote(dest.path))
    if path == "/kabu":
        path = "/kabu/"
    if not path.startswith("/kabu/"):
        return None
    return path


def scan(args):
    core = args.core.resolve()
    assert_ok(os.environ.get("GITHUB_REPOSITORY") == "yuki746289/product_kabu_actions",
              "Public Actions only")
    assert_ok(run_git(core, "rev-parse", "HEAD") == HEAD, "Private SHA changed")
    assert_ok((core / "docs/ACTIONS_MIGRATION.md").is_file(), "Migration rule missing")
    assert_ok(not run_git(core, "ls-tree", "-r", "--name-only", HEAD, "--", ".github/workflows"),
              "Private workflows found")
    assert_ok(args.shard in SHARDS, "Unknown shard")
    current, old_urls, names, sectors = load_manifests(args.manifests, core)
    targets = sorted(p for p in current if relevant(p) and shard_of(p) == args.shard)
    unknown = sorted(p for p in current if relevant(p) and shard_of(p) == "UNCLASSIFIED")
    assert_ok(not unknown, "Unclassified published files: " + str(unknown[:5]))
    assert_ok(targets, "Shard unexpectedly empty: " + args.shard)
    # Constrain sparse-checkout to the assigned shard; absence fails instead of silently skipping.
    old_pattern = re.compile("|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)))
    record = {
        "schema": 1, "status": "RUNNING", "shard": args.shard,
        "private_sha": HEAD, "legacy_source_sha": SOURCE,
        "saved_audit_run": 38127100421,
        "retired_urls": len(old_urls), "released_summary_sectors": sectors,
        "expected_files": len(targets), "checked_files": 0, "link_attributes": 0,
        "stale_links": [], "other_missing_links": [], "raw_old_name_mentions": [],
        "source_recomputed": False, "tracked_file_modified": False,
        "deployment_performed": False,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    evidence = args.out / "cross_links.json"

    def save():
        evidence.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    save()
    for index, p in enumerate(targets, 1):
        local = core / p
        assert_ok(local.is_file(), "Sparse checkout missing committed page: " + p)
        source = local.read_text(encoding="utf-8", errors="replace")
        if "\ufffd" in source:
            raise AssertionError("Undecodable text source: " + p)
        for found in set(old_pattern.findall(source)):
            if len(record["raw_old_name_mentions"]) < 200:
                record["raw_old_name_mentions"].append({"source": p, "filename": found,
                       "potential_old_targets": sorted(names[found])})
        attrs = [m.group(2) for m in ATTR.finditer(source)]
        if p.lower().endswith(".xml"):
            attrs.extend(m.group(1) for m in XML_LOC.finditer(source))
        for item in attrs:
            target = absolute_local_href(p, item)
            if target is None:
                continue
            record["link_attributes"] += 1
            if target in old_urls:
                if len(record["stale_links"]) < 200:
                    record["stale_links"].append({"source": p, "url": target})
                continue
            # Verify only explicit file references and directory index routes.
            chk = target
            if chk.endswith("/"):
                chk += "index.html"
            if Path(chk).suffix.lower() not in (".html", ".htm", ".js", ".css", ".xml", ".json"):
                continue
            path_in_git = "preview" + chk
            if path_in_git not in current:
                if len(record["other_missing_links"]) < 200:
                    record["other_missing_links"].append({"source": p, "url": target})
        record["checked_files"] += 1
        if index % 100 == 0:
            save()
            print(args.shard, str(index) + "/" + str(len(targets)), flush=True)
    assert_ok(record["checked_files"] == record["expected_files"], "Shard incomplete")
    assert_ok(run_git(core, "rev-parse", "HEAD") == HEAD, "Private HEAD moved")
    assert_ok(not run_git(core, "diff", "--name-only"), "Tracked source changed")
    record["status"] = (
        "PASS_CROSS_LINK_AND_NAVIGATION"
        if not record["stale_links"] and not record["other_missing_links"]
        and not record["raw_old_name_mentions"] else "FAIL_REFERENCES_NEED_REVIEW"
    )
    save()
    return record


def final_gate(folder: Path, out: Path):
    found = list(folder.glob("p2-crosslink-*/cross_links.json"))
    reports = [json.loads(x.read_text("utf-8")) for x in found]
    by_name = {x.get("shard"): x for x in reports}
    errors = []
    if len(reports) != len(SHARDS) or set(by_name) != set(SHARDS):
        errors.append("Shard count or names incomplete")
    for name in SHARDS:
        r = by_name.get(name, {})
        if r.get("status") != "PASS_CROSS_LINK_AND_NAVIGATION":
            errors.append(name + ": " + str(r.get("status", "MISSING")))
        if not r.get("expected_files") or r.get("expected_files") != r.get("checked_files"):
            errors.append(name + ": incomplete file count")
        if r.get("private_sha") != HEAD or r.get("retired_urls") != 914:
            errors.append(name + ": fixed source/old set mismatch")
    result = {
        "schema": 1, "status": "PASS_PREDEPLOY_CROSS_LINKS" if not errors else "FAIL",
        "private_sha": HEAD, "saved_audit_run": 38127100421,
        "shards_expected": len(SHARDS), "shards_received": len(reports),
        "checked_files": sum(int(r.get("checked_files") or 0) for r in reports),
        "links_resolved": sum(int(r.get("link_attributes") or 0) for r in reports),
        "stale_links": sum(len(r.get("stale_links", [])) for r in reports),
        "other_missing_links": sum(len(r.get("other_missing_links", [])) for r in reports),
        "unresolved_old_name_mentions": sum(len(r.get("raw_old_name_mentions", [])) for r in reports),
        "errors": errors, "deployment_performed": False,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "final_cross_link_gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("scan", "final"), required=True)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--manifests", type=Path)
    parser.add_argument("--shard", choices=SHARDS)
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    try:
        if a.mode == "scan":
            assert_ok(a.core is not None and a.manifests is not None and a.shard,
                      "Scan arguments missing")
            r = scan(a)
        else:
            assert_ok(a.folder is not None, "Final artifact dir missing")
            r = final_gate(a.folder, a.out)
        print(json.dumps({k: r.get(k) for k in ("status", "shard", "checked_files",
              "link_attributes", "stale_links", "other_missing_links",
              "raw_old_name_mentions", "errors")}, ensure_ascii=False)[:2200], flush=True)
        return 0 if r["status"].startswith("PASS_") else 1
    except Exception as exc:
        info = {"status": "FAIL", "shard": a.shard, "type": type(exc).__name__,
                "reason": str(exc)[:1000], "deployment_performed": False}
        a.out.mkdir(parents=True, exist_ok=True)
        target = "cross_links.json" if a.mode == "scan" else "final_cross_link_gate.json"
        (a.out / target).write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
        print(json.dumps(info, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
