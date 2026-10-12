# Created: 2026-10-12T13:08:00+09:00
# Revision: v2, no baseline HTML or numeric input touched.
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
PARTITIONS = {"225_exclusion_all_period": 8, "225_indicator_stageb": 6}
# Only direct HTML attributes, including escaped HTML embedded in JavaScript,
# and the common literal JS location assignments are statically resolvable.
JS_LOCATION = re.compile(
    r'\b(?:window\.|document\.)?location(?:\.href)?\s*=\s*(["\x27])([^"\x27]+)\1',
    re.I,
)

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
    full_targets = sorted(p for p in current if relevant(p) and shard_of(p) == args.shard)
    assert_ok(args.partition_count >= 1 and 0 <= args.partition_index < args.partition_count,
              "Invalid partition")
    assert_ok(args.partition_count == PARTITIONS.get(args.shard, 1),
              "Partition count does not match prescribed audit plan")
    targets = [p for i, p in enumerate(full_targets)
               if i % args.partition_count == args.partition_index]
    unknown = sorted(p for p in current if relevant(p) and shard_of(p) == "UNCLASSIFIED")
    assert_ok(not unknown, "Unclassified published files: " + str(unknown[:5]))
    assert_ok(targets, "Shard unexpectedly empty: " + args.shard)
    # Constrain sparse-checkout to the assigned shard; absence fails instead of silently skipping.
    record = {
        "schema": 2, "status": "RUNNING",
        "shard": args.shard if args.partition_count == 1
                 else f"{args.shard}__{args.partition_index:02d}",
        "base_shard": args.shard,
        "partition_index": args.partition_index, "partition_count": args.partition_count,
        "full_shard_total_files": len(full_targets),
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
        # Literal basenames are not URLs. A valid cross-sector file often
        # has the same basename as a retired file in a different sector.
        # Canonicalize each actual hyperlink from its source directory.
        # Unescape one layer of JSON/JS quote escaping to include hyperlinks
        # serialized into inline JS table rows.
        normalized = html.unescape(source.replace(r'\"', '"').replace(r"\'", "'"))
        attrs = [m.group(2) for m in ATTR.finditer(normalized)]
        attrs.extend(m.group(2) for m in JS_LOCATION.finditer(normalized))
        if p.lower().endswith(".xml"):
            attrs.extend(m.group(1) for m in XML_LOC.finditer(normalized))
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
        else "FAIL_REFERENCES_NEED_REVIEW"
    )
    save()
    return record


def final_gate(folder: Path, out: Path):
    """Reuse precisely nine immutable old PASS reports and only rerun unfinished shards."""
    old_pass = {"root", "analysis_root", "conditions", "225_indicators",
                "225_sector_all_period", "details", "or_details", "or_charts",
                "group_globals"}
    remade = {"summaries"} | {"group_" + s for s in SECTORS}
    partitions = {f"{shard}__{index:02d}"
                  for shard, n in PARTITIONS.items() for index in range(n)}
    expected = remade | partitions
    previous_files = list((folder / "old").glob("p2-crosslink-*/cross_links.json"))
    new_files = list((folder / "new").glob("p2-crosslink-v2-*/cross_links.json"))
    old = [json.loads(p.read_text(encoding="utf-8")) for p in previous_files]
    new = [json.loads(p.read_text(encoding="utf-8")) for p in new_files]
    errors = []
    old_by_name = {p["shard"]: p for p in old}
    new_by_name = {p["shard"]: p for p in new}
    if len(old_by_name) != len(old) or len(new_by_name) != len(new):
        errors.append("Duplicate shard artifact names")
    if len(previous_files) != len(SHARDS):
        errors.append(f"Expected 18 legacy checkpoints, found {len(previous_files)}")
    if set(new_by_name) != expected:
        errors.append("Replacement shard set mismatch: " +
                      repr(sorted(expected ^ set(new_by_name))))
    selected = [old_by_name.get(s, {}) for s in sorted(old_pass)] + [
        new_by_name.get(s, {}) for s in sorted(expected)]
    for shard, report in zip(sorted(old_pass) + sorted(expected), selected):
        if report.get("status") != "PASS_CROSS_LINK_AND_NAVIGATION":
            errors.append(shard + ": " + str(report.get("status", "MISSING")))
        if not report.get("expected_files") or report.get("expected_files") != report.get("checked_files"):
            errors.append(shard + ": incomplete")
        if report.get("private_sha") != HEAD or report.get("retired_urls") != 914:
            errors.append(shard + ": immutable source mismatch")
        if report.get("stale_links") or report.get("other_missing_links"):
            errors.append(shard + ": stale or missing links")
        if report.get("source_recomputed") or report.get("deployment_performed"):
            errors.append(shard + ": forbidden operation")
    for shard, n in PARTITIONS.items():
        reports = [new_by_name.get(f"{shard}__{i:02d}", {}) for i in range(n)]
        if sum(int(r.get("checked_files") or 0) for r in reports) != reports[0].get("full_shard_total_files"):
            errors.append(shard + ": partition sum differs from complete inventory")
        if len({r.get("full_shard_total_files") for r in reports}) != 1:
            errors.append(shard + ": inconsistent inventory sizes")
        if any(r.get("partition_count") != n or r.get("partition_index") != i
               for i, r in enumerate(reports)):
            errors.append(shard + ": shard partition metadata mismatch")
    result = {
        "schema": 2,
        "status": "PASS_PREDEPLOY_CROSS_LINKS" if not errors else "FAIL",
        "private_sha": HEAD,
        "saved_audit_run": 38127100421,
        "reused_successful_run": 38198237853,
        "reused_pass_shards": sorted(old_pass),
        "rerun_shards": sorted(expected),
        "shards_expected": len(selected),
        "shards_received": len(selected),
        "checked_files": sum(int(r.get("checked_files") or 0) for r in selected),
        "links_resolved": sum(int(r.get("link_attributes") or 0) for r in selected),
        "stale_links": sum(len(r.get("stale_links", [])) for r in selected),
        "other_missing_links": sum(len(r.get("other_missing_links", [])) for r in selected),
        "errors": errors,
        "deployment_performed": False,
        "source_recomputed": False,
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
    parser.add_argument("--partition-index", type=int, default=0)
    parser.add_argument("--partition-count", type=int, default=1)
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
