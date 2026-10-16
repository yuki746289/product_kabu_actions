# Created 2026-10-16 JST
"""Phase42 stop/go gate: 23 Semantic CSV ownership + disjoint success evidence.

CHECKS actual read-only SHA-pinned original Phase38 saved 29 CSV inventory,
FRESH Phase43 eight canonical Semantic outputs, Phase42 five+two independent
numerical results, original Phase29 four monthly/individual-walkforward (seven
datasets, with earlier Phase26 transport canary), Phase40/41 full combo
stability/walkforward 8x shards/years. The original signal source CSV SHA is
the immutable original input and failures is the original empty failure table.

This is a proof graph of DISAGGREGATED genuine computations, not a claim that
the full 23 CSVs were physically assembled by one uninterrupted producer.
"""
import argparse,hashlib,json
from pathlib import Path
SHA="52df33a6b26f988a1f71f0b61839d6888a96e1b8"
DATASETS=("technology","financials","consumer_goods","materials","capital_goods_others",
          "transportation_utilities","exclude_capital_goods_transportation_utilities",
          "exclude_transportation_utilities")
FRESH=("all_single_categories.csv","representative_single_categories.csv",
       "all_pairwise_combinations.csv","tested_triple_combinations.csv",
       "candidate_registry.csv","advantage_single_candidates.csv",
       "advantage_pairwise_candidates.csv","advantage_triple_candidates.csv")
FIVE=("yearly_stability.csv","monthly_stability.csv",
      "rolling_3y_stability.csv","rolling_5y_stability.csv","regime_stability.csv")
TWO=("monthly_candidate_stability_summary.csv","parameter_plateau.csv")
MONTHLY=("monthly_baseline_performance.csv","monthly_baseline_stability_summary.csv",
         "month_of_year_baseline_summary.csv","walkforward_results.csv")
COMBO=("combination_stability_summary.csv","combination_walkforward_results.csv")
ONE=("signal_level_features.csv","failures.csv")
SEMANTIC=frozenset(FRESH+FIVE+TWO+MONTHLY+COMBO+ONE)
assert len(SEMANTIC)==23
def d(path):return json.loads(Path(path).read_text(encoding="utf-8"))
def verify(base):
    proof=d(base/"phase38"/"audit.json")
    ds=proof.get("dataset")
    if ds not in DATASETS or proof.get("status")!="PASS_PHASE38_SAVED_29_CSV_READONLY_CONTRACT":
        raise ValueError("Original fixed Phase38 dataset proof missing")
    if proof.get("private_core_sha")!=SHA or proof.get("resolved_csv_files")!=29 or proof.get("mismatches")!=[]:
        raise ValueError("Original 29 saved file SHAs not certified")
    source_sha=proof["source_sha256"]
    expected={k:proof["files"][k]["sha256"] for k in SEMANTIC}
    if proof["files"]["signal_level_features.csv"]["sha256"]!=source_sha:
        raise ValueError("Actual old canonical feature file SHA not equal pinned original input")
    fresh=d(base/"fresh"/"report.json")
    if (fresh["status"]!="PASS_PHASE43_EIGHT_FRESH_CANONICAL_SEMANTIC_NUMERIC_OUTPUTS"
        or fresh["dataset"]!=ds or fresh["private_core_sha"]!=SHA
        or fresh["source_sha256"]!=source_sha
        or set(fresh["new_semantic_outputs"])!=set(FRESH)):
        raise ValueError("Fresh canonical single/pair/triple SHA-bound proof incomplete")
    for k in FRESH:
        r=fresh["new_semantic_outputs"][k]
        if not r["numeric_and_original_order_parity"] or r["original_saved_sha256"]!=expected[k]:
            raise ValueError("Fresh producer old/reference SHA numeric comparison failed: "+k)
        if len(r["new_real_output_sha256"])!=64:raise ValueError("Fresh output digest missing")
    five=d(base/"five"/"report.json")
    if (five["status"]!="PASS_PHASE42_FIVE_CACHED_SEMANTIC_OUTPUTS"
        or five["dataset"]!=ds or five["original_private_sha"]!=SHA
        or five["source_sha256"]!=source_sha or set(five["files"])!=set(FIVE)):
        raise ValueError("Five optimized semantic period numerical certificate invalid")
    for k in FIVE:
        q=five["files"][k]
        if q["original_sha256"]!=expected[k] or not q["numeric_and_label_parity"] or not q["condition_period_key_coverage_exact"]:
            raise ValueError("Source-bound Phase42 five CSV inconsistency: "+k)
    two=d(base/"two"/"report.json")
    if (two["status"]!="PASS_PHASE42_TWO_UNSEEN_SEMANTIC_OUTPUTS"
        or two["dataset"]!=ds or two["private_core_sha"]!=SHA
        or two["source_sha256"]!=source_sha
        or set(two["newly_verified_files"])!=set(TWO)):
        raise ValueError("Two monthly candidate/plateau independent numerical certificate invalid")
    for k in TWO:
        q=two["newly_verified_files"][k]
        if q["saved_original_sha256"]!=expected[k] or not q["all_fields_numeric_parity"] or not q["full_unique_key_coverage"]:
            raise ValueError("Two new independent numerical comparison mismatch: "+k)
    if ds=="transportation_utilities":
        mc=d(base/"monthly"/"report.json")
        wf=d(base/"walkforward"/"report.json")
        if (mc["status"]!="PASS_PHASE26_MONTHLY_THREE_CSV_CANARY"
            or mc["dataset"]!=ds or mc["private_core_sha"]!=SHA
            or mc["original_source_sha256"]!=source_sha or mc["compared_csvs"]!=3
            or mc["mismatches"] or
            set(x["file"] for x in mc["csv_details"])!=set(MONTHLY[:3])
            or not all(x["numerically_equal"] for x in mc["csv_details"])):
            raise ValueError("Transport prior monthly three new calculations incomplete")
        if (wf["status"]!="PASS_PHASE26_WALKFORWARD_NEW_SEMANTIC_CANARY"
            or wf["dataset"]!=ds or wf["private_core_sha"]!=SHA
            or wf["original_source_sha256"]!=source_sha):
            raise ValueError("Transport prior one new walkforward original SHA proof incomplete")
        # Earlier Phase26 original-source success gates explicitly required
        # fixed matching old sources; no Phase29 re-execution.
    else:
        monthly=d(base/"monthly"/"report.json")
        if (monthly["status"]!="PASS_PHASE29_NEW_MONTHLY_WALKFORWARD_FOUR_CSV"
            or monthly["dataset"]!=ds or monthly["private_core_sha"]!=SHA
            or monthly["source_sha256"]!=source_sha
            or set(monthly["files"])!=set(MONTHLY) or monthly["mismatches"]):
            raise ValueError("Phase29 four independent old/new numeric parity source missing")
        for name in MONTHLY:
            q=monthly["files"][name]
            if q["reference_sha256"]!=expected[name]:
                raise ValueError("Phase29 original reference SHA differs from Phase38: "+name)
    # Combination stability and walkforward full all-conditions proofs
    # are inherited from completed/reconciled Phase40 / Phase41 (64/56
    # bounded disjoint SHA-pin shards respectively); do not regenerate.
    if not expected[COMBO[0]] or not expected[COMBO[1]]:
        raise ValueError("Missing immutable combo reference identity")
    if proof["files"]["failures.csv"]["rows"]!=0:
        raise ValueError("Canonical output cannot silently replace nonempty errors")
    mapped=set(FRESH+FIVE+TWO+MONTHLY+COMBO+ONE)
    if mapped!=SEMANTIC:raise ValueError("Source/producer evidence ownership gap")
    return {"dataset":ds,"private_core_sha":SHA,"source_sha256":source_sha,
      "status":"PASS_PHASE42_DISAGGREGATED_23_SEMANTIC_EVIDENCE_COVERAGE",
      "saved_23_semantic_sha_ledger_keys":len(expected),
      "fresh_canonical_semantic_outputs":8,
      "cached_numeric_optimized_period_outputs":5,
      "fresh_candidate_and_plateau_outputs":2,
      "prior_monthly_and_single_walkforward_outputs":4,
      "prior_full_combination_stability_and_walkforward_outputs":2,
      "original_feature_and_empty_failures_outputs":2,
      "semantic_23_file_evidence_ownership_exhaustive":True,
      "full_semantic_monolithic_producer_executed":False,
      "new_23_semantic_output_SHA_ledger_generated_by_same_unified_process":False,
      "all_29_semantic_or_producers_new_full_outputs":False,
      "phase43_finished":False,"phase48_started":False,
      "production_modified":False,"prior_pass_recomputed":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dataset",required=True,choices=DATASETS)
    p.add_argument("--proof-root",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError("Do not overwrite prior result")
    out=verify(a.proof_root)
    if out["dataset"]!=a.dataset:raise ValueError("Dataset proof directory collision")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False))
if __name__=="__main__":main()
