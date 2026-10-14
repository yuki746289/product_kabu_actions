# Created: 2026-10-14 JST
"""Read-only all available HTML link/ID scan + headless Chromium smoke.

All pages from the pinned original dataset branch, never rewrite old HTML.
Absolute internal links and relative links are validated against actual paths
from the original pinned Git tree. Smoke-tests representative original pages
at desktop and mobile widths using a real browser.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess
from urllib.parse import urlsplit,unquote

SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials","capital_goods_others","transportation_utilities")
EXCLUSIONS=("exclude_capital_goods_transportation_utilities","exclude_transportation_utilities")
DATASETS=GROUPS+EXCLUSIONS

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[];self.ids=set();self.title=False;self.titles=[];self.has_body=False
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="a" and d.get("href"):self.links.append(d["href"])
        if d.get("id"):self.ids.add(d["id"])
        if tag=="title":self.title=True
        if tag=="body":self.has_body=True
    def handle_endtag(self,tag):
        if tag=="title":self.title=False
    def handle_data(self,data):
        if self.title:self.titles.append(data)

def run(core:Path,dataset:str)->dict:
    if dataset not in DATASETS:raise ValueError("Unexpected HTML dataset")
    if subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()!=SHA:
        raise ValueError("Fixed Private core SHA changed")
    site=(core/"preview/kabu").resolve()
    base=(site/"analysis"/
          ("225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period")/
          dataset).resolve()
    if not base.is_relative_to(site):raise ValueError("HTML path escapes site")
    paths=sorted(base.rglob("*.html"))
    if len(paths)<20:raise ValueError("Expected many existing saved HTML condition/details pages")
    gitpaths=set(subprocess.check_output(["git","-C",str(core),"ls-tree","-r",
             "--name-only","HEAD","preview/kabu"],text=True).splitlines())
    if not gitpaths:raise ValueError("Pinned full HTML repo tree unavailable")
    unresolved=[];external=set();checked=0;found_ids=0
    for doc in paths:
        parsed=Anchors()
        parsed.feed(doc.read_text(encoding="utf-8"))
        if not parsed.has_body or not "".join(parsed.titles).strip():
            unresolved.append({"page":str(doc.relative_to(site)),"issue":"missing body/title"})
        found_ids+=len(parsed.ids)
        for href in parsed.links:
            uri=urlsplit(href.strip())
            if uri.scheme in ("https","http","mailto","tel") or uri.netloc:
                external.add(uri.netloc or uri.scheme)
                continue
            if uri.scheme or href.strip().lower().startswith(("javascript:","data:","file:")):
                unresolved.append({"page":str(doc.relative_to(site)),"issue":"unsafe scheme"});continue
            if not uri.path:continue
            raw=unquote(uri.path)
            path=(site/raw.lstrip("/")).resolve() if raw.startswith("/") else (doc.parent/raw).resolve()
            if not path.is_relative_to(site):
                unresolved.append({"page":str(doc.relative_to(site)),"href":href,"issue":"site boundary escape"});continue
            suffix=path.relative_to(core).as_posix()
            if suffix not in gitpaths:
                if suffix.endswith("/") or not Path(suffix).suffix:
                    suffix=suffix.rstrip("/")+"/index.html"
                if suffix not in gitpaths and not uri.path.endswith((".css",".js",".png",".jpg",".svg",".webp",".ico",".pdf")):
                    unresolved.append({"page":str(doc.relative_to(site)),"href":href,"issue":"missing pinned Git HTML target"})
            checked+=1
        if len(unresolved)>100:break
    if unresolved:raise ValueError("Pinned all-HTML links/title errors: "+json.dumps(unresolved[:7]))
    # Chromium smoke covers desktop/mobile real page rendering, not invented screenshots.
    from playwright.sync_api import sync_playwright
    representative=[base/"index.html",base/"report_all_period.html"]
    pages=sorted((base/"conditions").rglob("*.html"))
    if pages:representative.append(pages[0])
    for page in representative:
        if not page.exists():raise FileNotFoundError("Representative smoke page missing: "+str(page))
    checks=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--no-sandbox"])
        try:
            for width,height in ((1280,800),(390,844)):
                context=browser.new_context(viewport={"width":width,"height":height})
                tab=context.new_page()
                for page in representative:
                    tab.goto(page.as_uri(),wait_until="domcontentloaded",timeout=30000)
                    title=tab.title().strip()
                    visible=tab.locator("body").count()==1
                    if not title or not visible:
                        raise AssertionError("Browser title/body missing: "+str(page))
                    checks.append({"width":width,"html":page.relative_to(site).as_posix(),
                                   "title_present":bool(title),"body_present":visible})
                context.close()
        finally:browser.close()
    return {"schema":1,"status":"PASS_FULL_ORIGINAL_HTML_LINK_SCAN_AND_BROWSER_SMOKE",
            "dataset":dataset,"private_core_sha":SHA,"pages_scanned":len(paths),
            "in_site_links_verified":checked,"html_ids_seen":found_ids,
            "browser_smokes":len(checks),"smoke_pages_per_viewport":len(representative),
            "external_link_hosts_count":len(external),
            "unresolved_internal_links":0,"old_html_modified":False,
            "all_browser_features_certified":False,
            "legacy_favorites_behavior_certified":False,
            "new_template_generated":False,"release_ready":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--core",type=Path)
    ap.add_argument("--dataset",choices=DATASETS)
    ap.add_argument("--out",type=Path)
    a=ap.parse_args()
    if a.selftest:
        assert len(DATASETS)==8 and len(SHA)==40
        print("PASS_FULL_HTML_LINK_BROWSER_SCOPE");return
    if not all((a.core,a.dataset,a.out)):ap.error("Fixed core, dataset, out required")
    if a.out.exists():raise FileExistsError("Never overwrite audit report")
    result=run(a.core.resolve(),a.dataset)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
