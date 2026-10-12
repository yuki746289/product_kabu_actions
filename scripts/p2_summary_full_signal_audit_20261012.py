# Created: 2026-10-12 10:10 JST
"""Verify saved P2 summary candidate metrics directly from already-saved signals.
Does not rebuild signals, existing CSV/HTML, previous successful artifacts or P2 v12.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

CORE_SHA="0e2d5722d6764102adfe6995b793f533b60b1532"
FILES={"single":"advantage_single_candidates.csv","pair":"advantage_pairwise_candidates.csv","triple":"advantage_triple_candidates.csv"}
SECTORS=("technology","financials","consumer_goods","materials","capital_goods_others","transportation_utilities")
H=(5,10,20)

def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as fp:
        for part in iter(lambda:fp.read(1048576),b""): h.update(part)
    return h.hexdigest()

def canon_params(s):
    return json.dumps(json.loads(s),sort_keys=True,separators=(",",":"),ensure_ascii=False)

def compare(block,mask,ys,base,pop,kind,errors):
    n=int(mask.sum())
    want={"count":float(n),"retention_pct":n*100/pop}
    for h in H:
        y=ys[h]; ok=mask & np.isfinite(y)
        w=float(y[ok].mean()*100) if ok.any() else float("nan")
        want[f"win_{h}d_pct"]=w
        want[f"win_uplift_{h}d_pp"]=w-base[h]
    for idx,row in block.iterrows():
        for k,expected in want.items():
            observed=float(pd.to_numeric(row[k],errors="coerce"))
            if np.isnan(expected): same=np.isnan(observed)
            else: same=np.isfinite(observed) and abs(observed-expected)<=(1e-8 if k=="count" else 0.025)
            if not same:
                errors.append(f"{kind} row={idx} {k} saved={observed} signal={expected}")
                if len(errors)>=20: raise AssertionError("20 metric mismatches; stop shard")
    return len(block)

def singles(frame,candidates,ys,base,errors):
    from run_p2_stage_b_logic_validation_v2 import _fan_masks,_ema_masks,_rci_masks
    from run_p2_stage_b_logic_validation_v2_pricefix import _price_masks_corrected
    work=candidates.copy()
    work["param_key"]=work.params_json.astype(str).map(canon_params)
    pending={(str(f),p):g for (f,p),g in work.groupby(["feature","param_key"],sort=False)}
    count=0; variants=0; n=len(frame)
    def take(feature,params,cats):
        nonlocal count,variants
        group=pending.pop((feature,canon_params(json.dumps(params))),None)
        if group is None: return
        variants+=1
        values=np.asarray(cats).astype(str)
        for category,part in group.groupby("category",sort=False):
            count+=compare(part,values==str(category),ys,base,n,"single",errors)
    for params,cats in _fan_masks(frame): take("fan",params,cats)
    for params,cats in _ema_masks(frame): take("ema",params,cats)
    for params,cats in _price_masks_corrected(frame): take("price",params,cats)
    for params,cats in _rci_masks(frame,"long"): take(f"weekly_rci{int(params['span'])}",params,cats)
    for (feat,p),part in list(pending.items()):
        if feat.startswith("daily_rci") or feat=="causal_regime":
            if feat not in frame: raise AssertionError("missing saved daily/regime feature")
            pending.pop((feat,p));variants+=1
            values=frame[feat].astype(str).to_numpy()
            for cat,g in part.groupby("category",sort=False):
                count+=compare(g,values==str(cat),ys,base,n,"single",errors)
    if pending: raise AssertionError(f"unmatched saved parameters: {len(pending)}")
    if count!=len(candidates): raise AssertionError("single row coverage incomplete")
    return count,variants

def combinations(frame,candidates,ys,base,kind,errors):
    from finalize_p2_nikkei_complete_baseline import _feature_masks
    masks=_feature_masks(frame); done=0; seen=set()
    for idx,row in candidates.iterrows():
        terms=tuple((str(row[f"feature{i}"]),str(row[f"category{i}"]))
          for i in range(1,3 if kind=="pair" else 4))
        if terms in seen: raise AssertionError("duplicate candidate semantic condition")
        seen.add(terms)
        for term in terms:
            if term not in masks: raise AssertionError(f"unrecognized feature category: {term}")
        mask=np.logical_and.reduce([masks[t] for t in terms])
        done+=compare(candidates.loc[[idx]],mask,ys,base,len(frame),kind,errors)
        if (done%500)==0: print(f"{kind} independently checked {done}/{len(candidates)}",flush=True)
    if done!=len(candidates): raise AssertionError("candidate row coverage incomplete")
    return done,len(seen)

def audit(root,sector,kind):
    if sector not in SECTORS or kind not in FILES: raise ValueError("unsupported audit shard")
    actual=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    if actual!=CORE_SHA: raise AssertionError("Private source SHA mismatch")
    src=root/"preview/kabu/analysis/225_group_all_period"/sector
    p=[src/FILES[kind],src/"signal_level_features.csv",src/"semantic_status.json"]
    before={q.name:digest(q) for q in p}
    status=json.loads(p[2].read_text(encoding="utf-8"))
    if status.get("overall_pass") is not True: raise AssertionError("old semantic status not PASS")
    candidates=pd.read_csv(p[0],low_memory=False)
    frame=pd.read_csv(p[1],low_memory=False)
    if frame.empty or candidates.empty or len(frame)!=int(status["source_rows"]):
        raise AssertionError("saved frame population or candidate inventory invalid")
    ys={h:pd.to_numeric(frame[f"moved_predicted_{h}d"],errors="coerce").to_numpy(float) for h in H}
    base={h:float(np.nanmean(ys[h])*100) for h in H}
    errors=[]
    if kind=="single": rows,parts=singles(frame,candidates,ys,base,errors)
    else: rows,parts=combinations(frame,candidates,ys,base,kind,errors)
    if errors: raise AssertionError("; ".join(errors[:3]))
    if any(digest(q)!=before[q.name] for q in p): raise AssertionError("saved input mutated")
    diff=subprocess.check_output(["git","-C",str(root),"diff","--name-only"],text=True).strip()
    if diff: raise AssertionError("private tracked sources mutated")
    return {"status":"PASS_FULL_SAVED_SIGNAL_NUMERIC","sector":sector,"kind":kind,
            "rows":rows,"parameter_groups_or_conditions":parts,"population":len(frame),
            "fields":["count","retention_pct"]+[f"{f}_{h}d_{suffix}" for h in H for f,suffix in
            (("win","pct"),("win_uplift","pp"))],
            "input_sha256":before,"private_sha":actual,"source_signals_recomputed":False,
            "successful_artifacts_rerun":False,"deployment_allowed":False,
            "limit":"Compared existing feature classifiers and saved signals, not price-history or v12 logic provenance."}

def main():
    ap=argparse.ArgumentParser()
    for arg in ("core","sector","kind","out"): ap.add_argument("--"+arg,required=True)
    a=ap.parse_args();root=Path(a.core).resolve();out=Path(a.out).resolve()
    if out.exists() or out==root/"build" or not out.is_relative_to(root/"build"):
        raise ValueError("output must be a fresh isolated core/build subdirectory")
    out.mkdir(parents=True)
    try: record=audit(root,a.sector,a.kind)
    except Exception as ex:
        record={"status":"FAIL","sector":a.sector,"kind":a.kind,
                "reason_type":type(ex).__name__,"reason":str(ex)[:750],
                "private_sha":CORE_SHA,"deployment_allowed":False}
    (out/"full_signal_audit.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(record,ensure_ascii=False),flush=True)
    if record["status"]!="PASS_FULL_SAVED_SIGNAL_NUMERIC": sys.exit(1)

if __name__=="__main__": main()
