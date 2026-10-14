# Created 2026-10-14 JST
"""Phase40-47 single-run, fail-closed pre-release R&D verification.

This is a BOUNDED and HONEST consolidation runner, not a fake release gate.
40: actual next common stability candidates, new computation (skip Phase39 3+3).
41: original saved walkforward integrity; full new walkforward still unverified.
42-43: source-linked 29 CSV and manifest/source interface audit, not full producer.
44: pinned all225 original source adapter input gate, not full semantic generation.
45: read-only representative HTML structure/URLs, not browser suite.
46: Nikkei exact 890-row source locator, fail closed if missing.
47: aggregate independent evidence, mark NO_GO for uncertified requirements.
No original Private CSV/HTML/P2 code modifications, no prior success rerun,
no main, release, production deployment or public sensitive raw datasets.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, os, sys, subprocess
from pathlib import Path

CORE_SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS=("technology","financials","consumer_goods","materials",
        "capital_goods_others","transportation_utilities")
EXCLUSIONS={
 "exclude_capital_goods_transportation_utilities":(137426,170,"cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"),
 "exclude_transportation_utilities":(166470,205,"d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1")
}
DATASETS=GROUPS+tuple(EXCLUSIONS)
SRC225="71fb0dc947a4777610fec2d07e08fac168a7ab1d49ac5028c39ad1b7ec03bdc9"
RESULT_KINDS=("40","41","42_43","44","45","46")
STATUS_OK="PASS_SCOPED"
STATUS_HOLD="HOLD_NOT_CERTIFIED"

def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as inp:
        for p in iter(lambda:inp.read(1024*1024),b""): h.update(p)
    return h.hexdigest()

def read(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def write(path:Path,out:dict)->int:
    if path.exists():raise FileExistsError("Fresh separate audit output required")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k not in ("file_shas","source_sha256")},ensure_ascii=False))
    return 0 if not out.get("errors") else 2

def verify_core(core:Path):
    actual=subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()
    if actual!=CORE_SHA:raise ValueError("Original Private core SHA drift")
    if not (core/"docs/ACTIONS_MIGRATION.md").is_file():
        raise ValueError("Private architecture policy absent")
    if any((core/".github/workflows").glob("*.yml")) or any((core/".github/workflows").glob("*.yaml")):
        raise ValueError("Private workflow forbidden")

def ref_for(core:Path,dataset:str)->Path:
    if dataset not in DATASETS:raise ValueError("Disallowed dataset")
    label="225_group_all_period" if dataset in GROUPS else "225_exclusion_all_period"
    return core/"preview/kabu/analysis"/label/dataset

def source_for(ref:Path,dataset:str,saved:Path)->Path:
    if dataset in GROUPS:return ref/"signal_level_features.csv"
    candidates=list(saved.rglob("features.csv"))
    if len(candidates)!=1:raise ValueError("Expected pinned excluded features artifact")
    if sha(candidates[0])!=EXCLUSIONS[dataset][2]:
        raise ValueError("Original exclusion SHA differs")
    return candidates[0]

def original_proof(core:Path,dataset:str,ref:Path,saved:Path,phase38:Path):
    verify_core(core)
    p=read(phase38)
    src=source_for(ref,dataset,saved)
    ssha=sha(src)
    if (p.get("status")!="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT" or
        p.get("dataset")!=dataset or p.get("private_core_sha")!=CORE_SHA or
        p.get("source_sha256")!=ssha or p.get("resolved_csv_files")!=29 or
        len(p.get("files",{}))!=29 or p.get("mismatches")!=[]):
        raise ValueError("Original 29 CSV immutable source proof missing")
    return src, p

def common_status(phase,dataset,source,p38,details,*,certified=False,errors=None):
    return {
      "schema":1,"phase":phase,"dataset":dataset,
      "status":STATUS_OK if not errors else "FAIL_SCOPE",
      "full_producer_certified":certified,
      "private_core_sha":CORE_SHA,"source_sha256":sha(source),
      "phase38_source_sha_matched":p38["source_sha256"]==sha(source),
      "details":details,"errors":errors or [],
      "original_signals_modified":False,"previous_success_recomputed":False,
      "production_p2_v12_changed":False,"old_csv_html_modified":False,
      "main_merged":False,"release_created":False,"deployed":False,
    }

def phase40(core,ref,src,p38,p39,dataset):
    import pandas as pd
    sys.path.insert(0,str(core/"scripts"))
    import finalize_p2_nikkei_complete_baseline as fin
    import build_p2_225_semantic_bundle as semantic
    prev=read(p39)
    if (prev.get("status")!="PASS_PHASE39_NEW_BOUNDED_COMBO_STABILITY" or
        prev.get("dataset")!=dataset or prev.get("private_core_sha")!=CORE_SHA or
        prev.get("source_sha256")!=sha(src) or prev.get("mismatches")!=[] or
        prev.get("new_pair_candidates")!=3 or prev.get("new_triple_candidates")!=3):
        raise ValueError("Phase39 success proof missing or mismatched")
    frame=semantic.prepare_frame(src)
    if len(frame)!=p38["source_rows"]:
        raise ValueError("Source rows differ from immutable census")
    masks=fin._feature_masks(frame)
    old_path=ref/"combination_stability_summary.csv"
    if sha(old_path)!=p38["files"]["combination_stability_summary.csv"]["sha256"]:
        raise ValueError("Saved original stability CSV changed")
    old=pd.read_csv(old_path,low_memory=False)
    if old.empty:raise ValueError("Saved original combination stability empty")
    new_parts=[]; by_kind={}
    for kind,filename in (("pair","all_pairwise_combinations.csv"),
                          ("triple","tested_triple_combinations.csv")):
        if sha(ref/filename)!=p38["files"][filename]["sha256"]:
            raise ValueError("Original saved pair/triple inputs modified")
        candidates=pd.read_csv(ref/filename,low_memory=False)
        eligible=candidates[fin._truthy(candidates["candidate"])]
        if len(eligible)<6:raise ValueError("At least 6 candidate source rows needed")
        chunk=eligible.iloc[3:23].copy()  # skip successfully certified original 3
        fresh=fin._stability_summary(frame,chunk,kind,masks)
        if len(fresh)!=len(chunk):raise ValueError("Unexpected new producer count")
        new_parts.append((kind,fresh))
        by_kind[kind]={"saved_total":int(len(eligible)),"new_checked":int(len(chunk)),
                       "previous_phase39_skipped":3,
                       "remaining_new_producer_unverified":int(len(eligible)-3-len(chunk))}
    if any(v["remaining_new_producer_unverified"]<0 for v in by_kind.values()):
        raise ValueError("Candidate accounting underflow")
    keys=["condition_type","feature1","category1","feature2","category2"]
    errors=[]
    for kind,fresh in new_parts:
        filt=old[old["condition_type"].eq(kind)]
        select_cols=keys+(["feature3","category3"] if kind=="triple" else [])
        old_map=filt.copy()
        for i in range(len(fresh)):
            row=fresh.iloc[i]
            selected=old_map
            for key in select_cols:
                if key.startswith("category3") or key.startswith("feature3"):
                    # pair CSV stores NaN on these columns; triple has values
                    pass
                selected=selected[selected[key].astype(str)==str(row.get(key))]
            if len(selected)!=1:raise ValueError("Expected one original saved candidate stability row")
            if list(fresh.columns)!=list(old.columns):
                raise ValueError("New/old combination stability column order differs")
            a=selected.iloc[0:1].reset_index(drop=True)
            b=fresh.iloc[i:i+1].reset_index(drop=True)
            try:
                pd.testing.assert_frame_equal(a,b,check_dtype=False,check_exact=False,
                    atol=1e-7,rtol=1e-10,check_index_type=False)
            except AssertionError:
                errors.append({"kind":kind,"selected_index":i,"issue":"numeric_or_label"})
                if len(errors)>8:break
    details={"scope":"next unverified 20 candidate rows per pair/triple, not full",
      "kinds":by_kind,"reference_sha256":sha(old_path),
      "column_and_order_numeric_mismatches":len(errors),
      "all_stability_rows":int(len(old)),
      "full_stability_certified":all(v["remaining_new_producer_unverified"]==0 for v in by_kind.values())}
    return common_status("40",dataset,src,p38,details,certified=details["full_stability_certified"],errors=errors)

def phase41(core,ref,src,p38,dataset):
    path=ref/"combination_walkforward_results.csv"
    if sha(path)!=p38["files"]["combination_walkforward_results.csv"]["sha256"]:
        raise ValueError("Original walkforward reference SHA drift")
    with path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        necessary={"condition_type","horizon","test_year","train_count","test_count"}
        if not necessary.issubset(reader.fieldnames or []):
            raise ValueError("Saved walkforward schema incomplete")
        keys=set();count=0
        for row in reader:
            key=(row["condition_type"],row["horizon"],row["test_year"])
            if key in keys: raise ValueError("Duplicate original walkforward group/year/horizon")
            keys.add(key);count+=1
    return common_status("41",dataset,src,p38,{
       "saved_walkforward_rows":count,
       "saved_sha256":sha(path),"duplicate_keys":0,
       "full_new_walkforward_producer_executed":False,
       "blocker":"Original new full walkforward scans large certified pair/triple universes; bounded algorithm needed"},
       certified=False)

def phase42_43(core,ref,src,p38,dataset):
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p02_semantic_io_contract import CSV_FILES,csv_header
    from p2_html_core.p03_common_analysis_plan import SEMANTIC_CSVS,OR_CSVS,MANIFEST
    required=set(SEMANTIC_CSVS)|set(OR_CSVS)|{MANIFEST}
    if len(CSV_FILES)!=29 or set(CSV_FILES)!=required:
        raise ValueError("Unexpected semantic/OR/manifest CSV ownership plan")
    problems=[]
    ledger={}
    for filename in CSV_FILES:
        item=p38["files"].get(filename)
        if not item:raise ValueError("Phase38 missing original saved "+filename)
        source=src if filename=="signal_level_features.csv" else ref/filename
        digest=sha(source)
        if digest!=item["sha256"]:
            raise ValueError("Original saved byte SHA changed: "+filename)
        if len(csv_header(source))!=item["columns"]:
            problems.append(filename+":columns")
        ledger[filename]=digest
    manifest=ref/MANIFEST
    with manifest.open(encoding="utf-8-sig",newline="") as f:
        rdr=csv.DictReader(f)
        manifest_columns=rdr.fieldnames or []
        count=0
        for row in rdr:
            if any(v is None for v in row.values()):
                problems.append("malformed_manifest_row")
            count+=1
    return common_status("42_43",dataset,src,p38,{
       "immutable_29_csvs_verified":len(ledger),
       "semantic_csv_count":len(SEMANTIC_CSVS),
       "or_csv_count":len(OR_CSVS),
       "manifest_header":manifest_columns,"manifest_rows":count,
       "old_manifest_sha256":sha(manifest),
       "new_semantic_producer_all_29_numeric_certified":False,
       "end_to_end_producer_ledger_certified":False,
       "missing_evidence":"New producer stage-wise SHA ledgers and normalization verification"},
       certified=False,errors=problems)

def all225(core,source_root):
    verify_core(core)
    files=list(source_root.rglob("features.csv"))
    if len(files)!=1:raise ValueError("Exactly one original all225 feature source required")
    source=files[0]
    actual=sha(source)
    if actual!=SRC225:raise ValueError("Pinned all225 original source SHA drift")
    sys.path.insert(0,str(core/"scripts"))
    from p2_html_core.p03_common_analysis_plan import PinnedSavedInput,source_preflight
    data=source_preflight("all_225",PinnedSavedInput(source,actual,181318,225))
    return {"schema":1,"phase":"44","status":STATUS_OK,"dataset":"all_225",
      "source_sha256":actual,"private_core_sha":CORE_SHA,
      "original_input_rows":data["actual_rows"],"original_input_tickers":data["actual_tickers"],
      "new_adapter_preflight_pass":True,
      "full_29csv_new_225_producer_certified":False,
      "full_producer_certified":False,
      "errors":[],"original_signals_modified":False,"previous_success_recomputed":False,
      "main_merged":False,"deployed":False}

def html_source(core,dataset):
    verify_core(core)
    ref=ref_for(core,dataset)
    from html.parser import HTMLParser
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True);self.links=[];self.title=False;self.title_text=""
        def handle_starttag(self,tag,attrs):
            if tag=="a":
                d=dict(attrs)
                if "href" in d:self.links.append(d["href"])
            if tag=="title":self.title=True
        def handle_data(self,data):
            if self.title:self.title_text+=data
        def handle_endtag(self,tag):
            if tag=="title":self.title=False
    result=[]
    invalid=[]
    for filename in ("index.html","report_all_period.html"):
        page=ref/filename
        if not page.exists(): invalid.append("missing:"+filename);continue
        original=sha(page)
        parser=Parser();parser.feed(page.read_text(encoding="utf-8"))
        if not parser.title_text.strip():invalid.append("no-title:"+filename)
        for link in parser.links:
            low=link.lower().strip()
            if low.startswith(("javascript:","data:","file:")):
                invalid.append("unsafe-uri")
            if ".." in low.split("?")[0].split("#")[0].split("/"):
                invalid.append("traversal-url")
        if sha(page)!=original:invalid.append("page-sha-modified")
        result.append({"file":filename,"bytes":page.stat().st_size,
                       "sha256":original,"links_checked":len(parser.links)})
    return {"schema":1,"phase":"45","dataset":dataset,"private_core_sha":CORE_SHA,
      "status":STATUS_OK if not invalid else "FAIL_SCOPE",
      "saved_html_pages_checked":len(result),"pages":result,
      "errors":invalid,"browser_regression_executed":False,
      "full_html_link_existence_certified":False,
      "full_producer_certified":False,"original_html_modified":False,"deployed":False}

def nikkei_source(core):
    verify_core(core)
    target=core/"data/diagnostics/p2_stage_b/nikkei_complete_baseline_20260915/signal_level_features.csv"
    if target.exists():
        with target.open(encoding="utf-8-sig",newline="") as f:
            rows=sum(1 for _ in f)-1
        exists=rows==890
    else:rows=None;exists=False
    return {"schema":1,"phase":"46","dataset":"nikkei_index","private_core_sha":CORE_SHA,
      "status":"PASS_ORIGINAL_890_SHA_NEEDS_PIN" if exists else "BLOCKED_SOURCE_UNAVAILABLE",
      "exact_original_saved_path_found":target.exists(),
      "original_rows":rows,"required_rows":890,
      "885_substitute_used":False,"full_producer_certified":False,
      "release_ready":False,"errors":[],"deployed":False}

def final_gate(evidence:Path):
    target=Path(evidence)
    expected={("40",ds) for ds in DATASETS}
    expected|={("41",ds) for ds in DATASETS}
    expected|={("42_43",ds) for ds in DATASETS}
    expected|={("45",ds) for ds in DATASETS}
    expected|={("44","all_225"),("46","nikkei_index")}
    got={}
    for path in target.rglob("report.json"):
        d=read(path)
        key=(str(d.get("phase")),str(d.get("dataset")))
        if key in got:raise ValueError("Duplicate certificate per phase/dataset: "+str(key))
        got[key]=d
    if set(got)!=expected:
        raise ValueError("Missing/extra phase evidence: "+repr((expected-set(got),set(got)-expected)))
    failures=[k for k,d in got.items() if d.get("errors") or d.get("status") not in (STATUS_OK,"BLOCKED_SOURCE_UNAVAILABLE","PASS_ORIGINAL_890_SHA_NEEDS_PIN")]
    outstanding=[{"phase":k[0],"dataset":k[1],"status":v["status"]} for k,v in got.items()
                 if not v.get("full_producer_certified",False)]
    return {
      "schema":1,"phase":"47","status":"RESEARCH_PREDEPLOY_NO_GO" if not failures else "RESEARCH_AUDIT_FAILURE",
      "total_certificates":len(got),"dataset_certificates":len(got)-2,
      "errors":failures,"unresolved_verification_gates":outstanding,
      "release_ready":False,"pr62_merge_permitted":False,"phase48_executed":False,
      "production_p2_changed":False,"old_success_artifacts_recomputed":False,
      "nikkei_source_substituted":False,
      "next_steps":"Full Phase40 candidate stability and Phase41 walkforward, then new semantic/OR 29 CSV output ledger; browser QA; original Nikkei 890 data; independent review"
    }

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--phase",choices=("selftest","40","41","42_43","44","45","46","47"),required=True)
    p.add_argument("--core",type=Path)
    p.add_argument("--dataset")
    p.add_argument("--source-root",type=Path,default=Path("original_source"))
    p.add_argument("--phase38",type=Path)
    p.add_argument("--phase39",type=Path)
    p.add_argument("--evidence",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    if a.phase=="selftest":
        assert len(DATASETS)==8 and len(CORE_SHA)==40 and len(SRC225)==64
        assert len(RESULT_KINDS)==6
        print("PASS_PHASE40_47_ORCHESTRATOR_PREDEPLOY_ONLY");return 0
    if not a.report:raise ValueError("Independent report path required")
    if a.phase=="47":
        if not a.evidence:raise ValueError("All prior artifacts required for gate")
        return write(a.report,final_gate(a.evidence))
    if not a.core:raise ValueError("Exact pinned Private core required")
    core=a.core.resolve()
    if a.phase=="44":return write(a.report,all225(core,a.source_root.resolve()))
    if a.phase=="46":return write(a.report,nikkei_source(core))
    if not a.dataset:raise ValueError("Dataset required")
    if a.phase=="45":
        return write(a.report,html_source(core,a.dataset))
    if not a.phase38:raise ValueError("Source-bound Phase38 original SHA certificate required")
    ref=ref_for(core,a.dataset)
    src,p38=original_proof(core,a.dataset,ref,a.source_root.resolve(),a.phase38)
    if a.phase=="40":
        if not a.phase39:raise ValueError("Prior Phase39 bounded proof required")
        report=phase40(core,ref,src,p38,a.phase39,a.dataset)
    elif a.phase=="41":report=phase41(core,ref,src,p38,a.dataset)
    else:report=phase42_43(core,ref,src,p38,a.dataset)
    return write(a.report,report)

if __name__=="__main__":
    raise SystemExit(main())
