"""
evaluation/run_tests.py
Repeatable evaluation script.

    python evaluation/run_tests.py                 # rules-only
    python evaluation/run_tests.py --hybrid        # rules-only AND rules+AI, side by side
    python evaluation/run_tests.py --output evaluation/results_latest.json

--hybrid needs a real AI provider (AI_PROVIDER + API key in .env).  If none is
configured the hybrid run is SKIPPED and reported as skipped - it is never
simulated, so every number printed here comes from a real run.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from compiler.models import Severity, VerificationStatus
from compiler.orchestrator import Orchestrator
from evaluation.metrics import TestOutcome, compute_metrics
from repair.ai_provider import ai_available, generate_ai_candidates
from repair.patcher import apply_candidate
from repair.ranking import rank_candidates
from repair.rules import generate_deterministic_candidates
from repair.verifier import verify_candidate

OK_STATUSES = (VerificationStatus.VERIFIED, VerificationStatus.TARGET_RESOLVED)


def load_test_cases(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_single(tc: dict, use_ai: bool = False) -> TestOutcome:
    orch = Orchestrator()
    t0 = time.monotonic()
    result = orch.analyze(tc["source"])
    analysis_ms = (time.monotonic() - t0) * 1000

    errors = [d for d in result.diagnostics if d.severity == Severity.ERROR]
    actual_errors = len(errors)
    actual_cats = sorted({d.category.value for d in errors})
    expected_errors = tc.get("expected_errors", 0)
    expected_cats = sorted(tc.get("expected_categories", []))

    # ---- repair ----
    t1 = time.monotonic()
    candidates = generate_deterministic_candidates(result)
    if use_ai:
        candidates += generate_ai_candidates(result)
    for c in candidates:
        verify_candidate(c, result)
    ranked = rank_candidates(candidates)
    repair_ms = (time.monotonic() - t1) * 1000

    repair_expected = tc.get("expected_repair") is not None
    repair_success = False
    if ranked:
        top = ranked[0]
        if top.verification_status in OK_STATUSES:
            patched, err = apply_candidate(result.source, top)
            if not err:
                after = orch.analyze(patched)
                after_errs = [d for d in after.diagnostics if d.severity == Severity.ERROR]
                new_codes = {d.code for d in after_errs} - {d.code for d in errors}
                if expected_errors == 1:
                    repair_success = len(after_errs) == 0
                else:
                    repair_success = len(after_errs) < actual_errors and not new_codes

    # ---- strict pass rule ----
    passed = (actual_cats == expected_cats) and (actual_errors == expected_errors)
    notes = []
    if actual_cats != expected_cats:
        notes.append(f"categories {actual_cats} vs expected {expected_cats}")
    if actual_errors != expected_errors:
        notes.append(f"errors {actual_errors} vs expected {expected_errors}")
    if repair_expected and not repair_success:
        notes.append("repair not successful")

    return TestOutcome(
        test_id=tc["id"], category=tc["category"], passed=passed,
        expected_errors=expected_errors, actual_errors=actual_errors,
        expected_categories=expected_cats, actual_categories=actual_cats,
        repair_expected=repair_expected, repair_generated=bool(ranked),
        repair_success=repair_success, candidates_total=len(ranked),
        regressions=sum(c.verification_status == VerificationStatus.REGRESSION for c in ranked),
        analysis_time_ms=analysis_ms, repair_time_ms=repair_ms,
        notes="; ".join(notes),
    )


def run_suite(test_cases: list, use_ai: bool) -> list:
    outcomes = []
    for tc in test_cases:
        try:
            outcomes.append(run_single(tc, use_ai))
        except Exception as exc:  # a crash is a failed test, not a hidden one
            outcomes.append(TestOutcome(
                test_id=tc["id"], category=tc["category"], passed=False,
                expected_errors=tc.get("expected_errors", 0), actual_errors=-1,
                expected_categories=[], actual_categories=[],
                repair_expected=tc.get("expected_repair") is not None,
                repair_generated=False, repair_success=False,
                candidates_total=0, regressions=0, analysis_time_ms=0,
                notes=f"EXCEPTION: {exc}",
            ))
    return outcomes


def print_summary(label: str, md: dict) -> None:
    print(f"\n--- {label} ---")
    print(f"  Tests passed (strict):   {md['passed']}/{md['total_tests']} ({md['pass_rate']*100:.1f}%)")
    print(f"  Category accuracy:       {md['category_accuracy']*100:.1f}%")
    print(f"  Exact error-count acc.:  {md['exact_count_accuracy']*100:.1f}%")
    print(f"  Detection precision:     {md['precision']:.3f}")
    print(f"  Detection recall:        {md['recall']:.3f}")
    print(f"  Detection F1:            {md['f1']:.3f}")
    print(f"  Repair-labelled cases:   {md['repair_labelled_cases']}")
    print(f"  Correction coverage:     {md['repair_coverage']*100:.1f}%")
    print(f"  Repair success rate:     {md['repair_success_rate']*100:.1f}%")
    print(f"  Regression rate:         {md['regression_rate']*100:.1f}% of {md['candidates_total']} candidates")
    print(f"  Avg analysis latency:    {md['avg_analysis_ms']:.1f} ms")
    print(f"  Avg repair latency:      {md['avg_repair_ms']:.1f} ms")


def main() -> None:
    ap = argparse.ArgumentParser(description="CompilerSense AI Evaluation")
    ap.add_argument("--quick", action="store_true", help="Print summary only")
    ap.add_argument("--hybrid", action="store_true", help="Also run rules+AI (needs API key)")
    ap.add_argument("--output", default="", help="Write JSON results here")
    args = ap.parse_args()

    cases = load_test_cases(str(Path(__file__).parent / "test_cases.json"))
    print(f"Running {len(cases)} test cases...")

    runs = {}
    rules = run_suite(cases, use_ai=False)
    runs["rules_only"] = rules
    if not args.quick:
        print()
        for o in rules:
            print(f"  [{'PASS' if o.passed else 'FAIL'}] {o.test_id:<12} "
                  f"errors={o.actual_errors}/{o.expected_errors}  {o.notes}")

    print("\n" + "=" * 62 + "\nEVALUATION SUMMARY\n" + "=" * 62)
    summaries = {"rules_only": compute_metrics(rules).to_dict()}
    print_summary("RULES ONLY", summaries["rules_only"])

    if args.hybrid:
        if ai_available():
            hyb = run_suite(cases, use_ai=True)
            runs["hybrid"] = hyb
            summaries["hybrid"] = compute_metrics(hyb).to_dict()
            print_summary("HYBRID (rules + AI)", summaries["hybrid"])
        else:
            print("\n--- HYBRID (rules + AI) ---\n  SKIPPED: no AI provider configured "
                  "(set AI_PROVIDER and the API key in .env).")
            summaries["hybrid"] = "skipped: no AI provider configured"
    print("=" * 62)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"metrics": summaries,
                       "outcomes": {k: [vars(o) for o in v] for k, v in runs.items()}},
                      f, indent=2)
        print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()