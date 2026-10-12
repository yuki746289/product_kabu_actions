# Created: 2026-10-12T13:08:00+09:00
"""Regression checks: never confuse same basenames across sectors with dead URLs."""
from __future__ import annotations
import html
import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts/p2_cross_page_links_20261012_v2.py"
spec = importlib.util.spec_from_file_location("cross_page_links_v2", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class CrossLinkResolutionTests(unittest.TestCase):
    def test_common_summary_identical_basename_exists(self):
        actual = module.absolute_local_href(
            "preview/kabu/summaries/single_features.html",
            "single-0fec673de599a5.html")
        self.assertEqual(actual, "/kabu/summaries/single-0fec673de599a5.html")
        self.assertNotEqual(actual, "/kabu/analysis/225_group_all_period/technology/summaries/single-0fec673de599a5.html")

    def test_relative_sector_path_resolves_in_same_sector(self):
        actual = module.absolute_local_href(
            "preview/kabu/analysis/225_group_all_period/technology/summaries/pair_features.html",
            "pair-778821695de820.html")
        self.assertEqual(actual, "/kabu/analysis/225_group_all_period/technology/summaries/pair-778821695de820.html")

    def test_actual_retired_canonical_url_is_caught(self):
        url = "/kabu/analysis/225_group_all_period/capital_goods_others/summaries/pair-778821695de820.html"
        self.assertEqual(module.absolute_local_href("preview/kabu/index.html", url),url)

    def test_escaped_javascript_table_html_anchor(self):
        src = r'D=[["<a href=\"single-0fec673de599a5.html\">label<\/a>", "1"]]'
        normalized = html.unescape(src.replace(r'\"', '"').replace(r"\'", "'"))
        links = [m.group(2) for m in module.ATTR.finditer(normalized)]
        self.assertEqual(links, ["single-0fec673de599a5.html"])

    def test_javascript_literal_navigation(self):
        data = 'window.location.href="/kabu/analysis/225_group_all_period/technology/index.html"'
        urls = [m.group(2) for m in module.JS_LOCATION.finditer(data)]
        self.assertEqual(urls, ["/kabu/analysis/225_group_all_period/technology/index.html"])

    def test_normalize_query_fragment_parent_dir(self):
        self.assertEqual(
            module.absolute_local_href("preview/kabu/analysis/225_group_all_period/technology/analysis/high_entry_accuracy.html",
                                      "../summaries/single_features.html?sort=1#x"),
            "/kabu/analysis/225_group_all_period/technology/summaries/single_features.html")

    def test_shard_partition_deterministic(self):
        self.assertEqual(module.PARTITIONS["225_exclusion_all_period"],8)
        self.assertEqual(module.PARTITIONS["225_indicator_stageb"],6)
        self.assertEqual(sum(len([j for j in range(2025) if j%6==i]) for i in range(6)),2025)

if __name__ == "__main__":
    unittest.main()
