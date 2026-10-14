# Created: 2026-10-14 JST
"""Phase35 bounded exhaustive OR raw numeric parity, only unseen original rows.

Exact original canonical _combo_metrics is called only for raw OR conditions
not covered by previous successful Phase15/16/21/23/24 and Phase32/33 audits.
Partition by SHA256(condition_key) % (4 for OR2, 8 for OR3).
Prior successful OR conditions are NEVER recomputed; original saved raw CSVs
and successful artifacts are never overwritten or regenerated. Only audit JSON
leaves the runner. Full new-OR parity still includes inherited prior independent
direct-metric proof for its old sample; do not conflate direct proof with new
producer execution on those skipped conditions.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

CORE_SHA = "52df33a6b26f988a1f71f0b61839d6888a96e1b8"
GROUPS = ("technology", "financials", "consumer_goods", "materials",
          "capital_goods_others", "transportation_utilities")
EXCLUSIONS = {
    "exclude_capital_goods_transportation_utilities":
        (137426, 170, "cdd8dabcbd19342dfab36723f3fd93ccbf8f6b2b577e7fa4619f3dfc6794aca2"),
    "exclude_transportation_utilities":
        (166470, 205, "d3cc96b84c34682300ccd2d1b0ea87a4d605b522050da7493f064d57b3d5e8f1"),
}
DATASETS = GROUPS + tuple(EXCLUSIONS)
KINDS = {"or2": ("or_pairwise_all.csv", 4, 2),
         "or3": ("or_triple_all.csv", 8, 3)}
PREVIOUS_FEATURES = {"causal_regime"} | {
    f"daily_rci{span}_{part}" for span in (9, 14, 26)
    for part in ("position", "direction", "state")
}
PRIOR_LEGACY_PER_KIND = 40  # Phase15:8, Phase16:24, Phase21/23/24:8
PRIOR_NEW_PER_KIND = 12  # Phase32:4 and Phase33:8
PREVIOUS_STATUS = "PASS_PHASE33_NEXT_UNSEEN_OR2_OR3_BOUNDED"


def selftest() -> None:
    assert set(KINDS) == {"or2", "or3"} and len(DATASETS) == 8
    assert len(PREVIOUS_FEATURES) == 10
    assert PRIOR_LEGACY_PER_KIND == 8 + 24 + 8
    assert PRIOR_NEW_PER_KIND == 4 + 8
    assert all(n > 0 for _,n,_ in KINDS.values())
    assert len(CORE_SHA) == 40
    assert all((k, n) in (("or2", 2), ("or3", 3))
               for k, (_, _, n) in KINDS.items())
    print("PASS_PHASE35_DISJOINT_EXHAUSTIVE_RAW_OR_SHARD_CONTRACT")


def sha_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rows_for_kind(reference: Path, kind: str, pool_keys: set) -> tuple[list, set, dict]:
    raw_name, shards, n = KINDS[kind]
    with (reference/raw_name).open(encoding="utf-8-sig", newline="") as inp:
        reader = csv.DictReader(inp)
        cols = reader.fieldnames or []
        required = {"condition_key", "condition_type", "mask_hash",
                    "count", "component_count"} | {
                        f"{p}{i}" for p in ("feature", "category")
                        for i in range(1, n+1)}
        if not required.issubset(cols) or len(cols) != len(set(cols)):
            raise ValueError("Original OR reference header/key contract incomplete")
        rows = []
        keys = set()
        labels_seen = set()
        legacy = []
        unseen = []
        for row in reader:
            labels = tuple((row[f"feature{i}"], row[f"category{i}"])
                           for i in range(1, n+1))
            key = row["condition_key"]
            if (not key or key in keys or labels in labels_seen
                or row["condition_type"] != kind
                or int(row["component_count"]) != n):
                raise ValueError("Malformed or duplicate saved full raw OR rows")
            keys.add(key)
            labels_seen.add(labels)
            data = (kind, labels, row)
            rows.append(data)
            if all(f in PREVIOUS_FEATURES for f, _ in labels):
                legacy.append(data)
            elif all(x in pool_keys for x in labels):
                unseen.append(data)
        legacy.sort(key=lambda z: hashlib.sha256(json.dumps(
            [n,z[1]], separators=(",",":")).encode()).hexdigest())
        unseen.sort(key=lambda z: hashlib.sha256(json.dumps(
            [n,z[1]], separators=(",",":"), ensure_ascii=False
        ).encode("utf-8")).hexdigest())
        if len(legacy) < PRIOR_LEGACY_PER_KIND or len(unseen) < PRIOR_NEW_PER_KIND:
            raise ValueError("Original reference does not contain prior proof selector scope")
        skip = {z[2]["condition_key"] for z in legacy[:PRIOR_LEGACY_PER_KIND]}
        skip.update(z[2]["condition_key"] for z in unseen[:PRIOR_NEW_PER_KIND])
        if len(skip) != PRIOR_LEGACY_PER_KIND + PRIOR_NEW_PER_KIND:
            raise ValueError("Already-certified old/new OR selector overlap")
        for _, labels, row in rows:
            if row["condition_key"] not in skip and any(x not in pool_keys for x in labels):
                raise ValueError("Old raw OR component missing from new pinned component pool")
        meta = {
            "raw_file":raw_name,"raw_count":len(rows),"prior_legacy_skipped":PRIOR_LEGACY_PER_KIND,
            "prior_new_skipped":PRIOR_NEW_PER_KIND,
            "unseen_total":len(rows)-len(skip),
            "original_raw_sha256":sha_digest(reference/raw_name),
            "selector_sha256":hashlib.sha256(
                "\n".join(sorted(skip)).encode("utf-8")).hexdigest(),
            "shard_count":shards,
        }
        return rows, skip, meta


def verify(core: Path, reference: Path, source_root: Path, proof4: Path,
           proof33: Path, dataset: str, kind: str, index: int) -> dict:
    if dataset not in DATASETS or kind not in KINDS:
        raise ValueError("Unapproved original OR dataset or raw kind")
    raw_name, shards, n = KINDS[kind]
    if index < 0 or index >= shards:
        raise ValueError("Unapproved deterministic OR shard index")
    head = subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"],
                                   text=True).strip()
    if head != CORE_SHA:
        raise ValueError("Private immutable original SHA drift")
    expected_ref = (core/"preview/kabu/analysis"/
                    ("225_group_all_period" if dataset in GROUPS
                     else "225_exclusion_all_period")/dataset).resolve()
    if reference != expected_ref:
        raise ValueError("Original reference directory does not match dataset")
    if dataset in GROUPS:
        source = reference/"signal_level_features.csv"
    else:
        found = list(source_root.rglob("features.csv"))
        if len(found) != 1:
            raise ValueError("Require exactly one saved original exclusion features artifact")
        source = found[0]

    sys.path.insert(0,str(core/"scripts"))
    import analyze_p2_or_combinations as calc
    import build_p2_225_or_bundle as common
    import finalize_p2_nikkei_complete_baseline as fin
    import p2_common_phase21_new_or_bounded_20261013 as comparing
    from p2_html_core.p03_common_analysis_plan import digest

    source_sha = digest(source)
    p4 = json.loads(proof4.read_text(encoding="utf-8"))
    if dataset in GROUPS:
        data = (p4.get("groups") or {}).get(dataset) or {}
        rows, tickers = data.get("row_count"), data.get("ticker_count")
        if (p4.get("status") != "PASS_EXACT_SAVED_SIX_GROUP_ID_PARTITION"
            or data.get("csv_sha256") != source_sha
            or data.get("duplicate_ids") is not False
            or not isinstance(rows,int) or rows<=0
            or not isinstance(tickers,int) or tickers<=0):
            raise ValueError("Phase4 original group source identity invalid")
    else:
        rows, tickers, original = EXCLUSIONS[dataset]
        data = p4.get("saved_exclusion") or {}
        if (p4.get("status") != "PASS_EXACT_SAVED_EXCLUSION_ID_DIFFERENCE"
            or p4.get("variant") != dataset or source_sha != original
            or data.get("csv_sha256") != source_sha
            or data.get("row_count") != rows or data.get("ticker_count") != tickers
            or data.get("duplicate_ids") is not False):
            raise ValueError("Phase4 exclusion original features/identity invalid")
    p33 = json.loads(proof33.read_text(encoding="utf-8"))
    if (p33.get("status") != PREVIOUS_STATUS
        or p33.get("dataset") != dataset
        or p33.get("private_core_sha") != CORE_SHA
        or p33.get("source_sha256") != source_sha
        or p33.get("new_or2_conditions") != 8
        or p33.get("new_or3_conditions") != 8
        or p33.get("skipped_prior_phase32_per_kind") != 4
        or p33.get("mismatch_count") != 0
        or p33.get("prior_phase32_new_or_recomputed") is not False):
        raise ValueError("Earlier Phase33 saved-source OR proof not certified")
    ref_status = reference/"semantic_status.json"
    stat_sha = digest(ref_status)
    status = json.loads(ref_status.read_text(encoding="utf-8"))
    if (status.get("overall_pass") is not True
        or status.get("or_full_universe_pass") is not True
        or status.get("source_rows") != rows or status.get("source_tickers") != tickers):
        raise ValueError("Saved original OR universe status not certified")

    singles = reference/"advantage_single_candidates.csv"
    singles_sha = digest(singles)
    raw_sha = digest(reference/raw_name)
    prior_sha = p33.get("original_or2_sha256") if n==2 else p33.get("original_or3_sha256")
    if raw_sha != prior_sha:
        raise ValueError("Saved raw OR hash diverges from Phase33 certified source")
    frame = common.prepare_frame(source)
    if len(frame) != rows or frame["ticker"].astype(str).nunique() != tickers:
        raise ValueError("Common OR input changed original source cardinality")
    calc.OUT = reference
    pool = calc._component_pool(frame, fin._feature_masks(frame))
    lookup = {(str(r["feature"]),str(r["category"])):r for r in pool}
    if len(lookup)!=len(pool) or not lookup:
        raise ValueError("Unexpected duplicate/empty original OR component pool")
    allrows, skips, counts = rows_for_kind(reference,kind,set(lookup))
    expected_status = "or2_raw_rows" if n==2 else "or3_raw_rows"
    if expected_status in status and status[expected_status]!=len(allrows):
        raise ValueError("Old status raw OR universe count differs from original rows")
    # Every raw condition can belong to just one modulo shard. Previous proofs
    # are skipped *before* the numerical inner producer is ever called.
    selected = [
        data for data in allrows
        if data[2]["condition_key"] not in skips and
        int(hashlib.sha256(data[2]["condition_key"].encode("utf-8")).hexdigest(),16)%shards == index
    ]
    if not selected:
        raise ValueError("Unexpected empty preplanned original OR shard")
    base = calc._baseline(frame)
    failures = []
    fields = 0
    for offset, (_, labels, old) in enumerate(selected):
        result = calc._combo_metrics(frame,kind,[lookup[label] for label in labels],base)
        mismatched = comparing.compare_new_with_original(old,result)
        fields += len(result)-1
        if mismatched:
            failures.extend({"index":offset,"column":item} for item in mismatched[:3])
            if len(failures)>=12:
                break
    if (digest(source)!=source_sha or digest(singles)!=singles_sha
        or digest(reference/raw_name)!=raw_sha or digest(ref_status)!=stat_sha):
        raise ValueError("Original source or old OR reference modified during audit")
    return {
        "schema":1,
        "status":"PASS_PHASE35_NEW_RAW_OR_SHARD" if not failures else "FAIL_PHASE35_NEW_RAW_OR_SHARD",
        "dataset":dataset,"kind":kind,"shard_index":index,"shard_count":shards,
        "private_core_sha":CORE_SHA,"source_sha256":source_sha,
        "original_rows":rows,"original_tickers":tickers,
        "raw_file":raw_name,"original_raw_count":counts["raw_count"],
        "original_raw_sha256":counts["original_raw_sha256"],
        "prior_legacy_skipped":counts["prior_legacy_skipped"],
        "prior_new_skipped":counts["prior_new_skipped"],
        "selector_sha256":counts["selector_sha256"],
        "remaining_unseen_total":counts["unseen_total"],
        "selected_raw_rows":len(selected),"numeric_fields_checked":fields,
        "mismatch_count":len(failures),"error_sample":failures[:12],
        "new_common_combo_metrics_called":True,
        "prior_certified_conditions_recomputed":False,
        "prior_success_artifacts_recomputed":False,
        "full_raw_bundle_recomputed":False,"source_signals_recomputed":False,
        "original_data_modified":False,"production_changed":False,
        "html_generated":False,"release_ready":False,
        "legacy_direct_proof_is_new_producer_certification":False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dataset", choices=DATASETS)
    ap.add_argument("--kind", choices=sorted(KINDS))
    ap.add_argument("--index", type=int)
    for a in ("core","reference","source-root","proof4","proof33","report"):
        ap.add_argument("--"+a,type=Path)
    a=ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    if any(getattr(a,k) is None for k in
           ("dataset","kind","index","core","reference","source_root","proof4","proof33","report")):
        ap.error("Pinned source, Phase4 and Phase33 proof, scope and new report required")
    if a.report.exists():
        raise FileExistsError("Do not overwrite old certified evidence")
    result = verify(a.core.resolve(),a.reference.resolve(),a.source_root.resolve(),
                    a.proof4.resolve(),a.proof33.resolve(),a.dataset,a.kind,a.index)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ("error_sample","source_sha256","original_raw_sha256")},
                     ensure_ascii=False))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__=="__main__":
    raise SystemExit(main())
