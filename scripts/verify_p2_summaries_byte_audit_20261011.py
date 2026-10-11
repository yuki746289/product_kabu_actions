# Created: 2026-10-11 JST
"""Read-only byte audit for the existing 712 per-sector P2 summary HTML pages.

Run only after isolated generation from saved CSV. Never change canonical data,
Production P2 v12, legacy HTML, or successful conditions-family artifacts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

SECTORS = ("technology","financials","consumer_goods","materials","capital_goods_others","transportation_utilities")
EXPECTED = {"single":33, "pair":121, "triple":558}
EXPECTED_TOTAL = sum(EXPECTED.values())
CORE_SHA = "c0c69be8e28ddfa5812c1bbe4ba3d33f432fbf02"
RENDER_SHA = "3dfb14cd0f05125c4bfce81d710db0ced073b7c3"


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):
            h.update(block)
    return h.hexdigest()


def check(args):
    if args.dataset not in SECTORS:
        raise ValueError("dataset must be one of the six approved 225-group sectors")
    root=args.repo_root.resolve()
    output=args.output_dir.resolve()
    evidence=args.audit_dir.resolve()
    site=(root/"preview/kabu").resolve()
    if (output==root/"build" or not output.is_relative_to(root/"build")
            or not output.is_dir() or evidence.exists() or not evidence.is_relative_to(root/"build")
            or site==output or site.is_relative_to(output)):
        raise ValueError("unsafe output/evidence directory")
    base=Path("analysis/225_group_all_period")/args.dataset
    rel=base/"summaries"
    old=site/rel
    new=output/rel
    files_old={p.name:p for p in old.glob("*.html") if p.is_file()}
    files_new={p.name:p for p in new.glob("*.html") if p.is_file()}
    if len(files_old)!=EXPECTED_TOTAL or len(files_new)!=EXPECTED_TOTAL:
        raise ValueError(f"expected 712 old+new pages, got {len(files_old)} old and {len(files_new)} new")
    if set(files_old)!=set(files_new):
        raise ValueError(f"new/old filename set mismatch: new-only={len(set(files_new)-set(files_old))}, old-only={len(set(files_old)-set(files_new))}")
    got={kind:sum(name.startswith(kind+"-") or name==kind+"_features.html"
                     for name in files_old) for kind in EXPECTED}
    if got!=EXPECTED:
        raise ValueError(f"712 summary family distribution drift: {got}")
    unexpected=[p.relative_to(output).as_posix() for p in output.rglob("*.html")
                if p.parent!=new]
    if unexpected:
        raise ValueError(f"unexpected HTML outside summary output folder: {unexpected[:5]}")
    manifest_file=output/"build_manifest.json"
    if not manifest_file.is_file():
        raise FileNotFoundError("generator manifest required")
    manifest=json.loads(manifest_file.read_text(encoding="utf-8"))
    if (manifest.get("execution_status")!="COMPLETED"
            or manifest.get("dataset")!=args.dataset
            or manifest.get("scope")!=["summaries"]
            or manifest.get("selected_conditions")!=447
            or manifest.get("generated_html")!=EXPECTED_TOTAL
            or manifest.get("source_html_copied") is not False
            or manifest.get("source_signals_recomputed") is not False
            or manifest.get("promotion_allowed") is not False):
        raise ValueError("renderer provenance/conditions scope failed")
    records=manifest.get("files")
    if len(records)!=EXPECTED_TOTAL:
        raise ValueError("generator inventory must include every HTML file")
    inv={r["path"]:r for r in records}
    expected_paths={str(rel/f) for f in files_new}
    if set(inv)!=expected_paths or any(x.get("dataset")!=args.dataset for x in records):
        raise ValueError("rendered manifest path/dataset mismatch")
    sources=manifest["source_inputs"]
    csv_checks={}
    for name in ("signal_level_features.csv","condition_detail_manifest.csv"):
        path=(site/base/name).resolve()
        value=sources.get(str(path))
        h=sha(path)
        if value is None or value.get("sha256")!=h or value.get("bytes")!=path.stat().st_size:
            raise ValueError(f"source CSV checksum mismatch: {name}")
        csv_checks[name]=h
    evidence.mkdir(parents=True,exist_ok=False)
    entries=[]
    mismatch=[]
    for name in sorted(files_old):
        older,newer=files_old[name],files_new[name]
        row={"path":str(rel/name),"family":name.split("-")[0].split("_")[0],
             "legacy_sha256":sha(older),"new_sha256":sha(newer),
             "legacy_bytes":older.stat().st_size,"new_bytes":newer.stat().st_size}
        row["byte_equal"]=(row["legacy_sha256"]==row["new_sha256"] and row["legacy_bytes"]==row["new_bytes"])
        if row["new_sha256"]!=inv[row["path"]].get("sha256"):
            raise ValueError(f"generator inventory SHA mismatch: {name}")
        entries.append(row)
        if not row["byte_equal"]:mismatch.append(row)
    status="PASS_BYTES" if not mismatch else "FAIL_BYTES"
    result={"schema":1,"status":status,"dataset":args.dataset,"expected_pages":EXPECTED_TOTAL,
            "matched_pages":len(entries)-len(mismatch),"failed_pages":len(mismatch),
            "group_counts":got,"source_csv_sha256":csv_checks,
            "private_core_sha":CORE_SHA,"legacy_renderer_sha":RENDER_SHA,
            "source_signals_recomputed":False,"source_html_modified":False,
            "deployment_allowed":False,
            "limits":["Existing HTML full-byte equality only; financial model correctness and real browser behavior not audited."]}
    (evidence/"summary_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (evidence/"pages.json").write_text(json.dumps(entries,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if mismatch:
        (evidence/"first_mismatches.json").write_text(json.dumps(mismatch[:20],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        raise SystemExit(2)


def selftest():
    assert EXPECTED_TOTAL==712
    assert len(SECTORS)==6
    assert CORE_SHA!=RENDER_SHA
    assert set(EXPECTED)=={"single","pair","triple"}
    print("PASS: sector/summary layout/legacy-core version invariants")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--dataset",choices=SECTORS)
    p.add_argument("--repo-root",type=Path)
    p.add_argument("--output-dir",type=Path)
    p.add_argument("--audit-dir",type=Path)
    a=p.parse_args()
    if a.selftest:selftest()
    else:
        if not all((a.dataset,a.repo_root,a.output_dir,a.audit_dir)):p.error("missing audit inputs")
        check(a)


if __name__=="__main__":main()
