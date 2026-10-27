"""
evaluation/metrics.py
Metric computation for the evaluation report.

Definitions (all computed from real runs, nothing estimated):
  * Detection precision/recall are counted per diagnostic:
        TP = min(actual, expected), FP = max(actual - expected, 0),
        FN = max(expected - actual, 0), summed over all test programs.
  * Category accuracy: the SET of diagnostic categories reported equals the
    expected set (e.g. {syntax, semantic}).
  * Exact-count accuracy: number of reported errors equals the expected number.
  * A test PASSES only if category set matches AND the error count matches.
  * Repair success: for programs labelled with an expected_repair, the
    top-ranked candidate, once applied, resolves the target error without
    introducing new error codes.  If the program had exactly one expected
    error, the patched program must analyse with zero errors.
  * Correction coverage: labelled-fixable programs that got >= 1 candidate.
  * Regression rate: candidates (any program) whose patch introduced new errors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class TestOutcome:
    __test__ = False  # stop pytest collecting this as a test class
    test_id: str
    category: str
    passed: bool
    expected_errors: int
    actual_errors: int
    expected_categories: List[str]
    actual_categories: List[str]
    repair_expected: bool
    repair_generated: bool
    repair_success: bool
    candidates_total: int
    regressions: int
    analysis_time_ms: float
    repair_time_ms: float = 0.0
    notes: str = ""


@dataclass
class EvaluationMetrics:
    total: int = 0
    passed: int = 0
    category_match: int = 0
    count_match: int = 0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    repair_expected: int = 0
    repair_covered: int = 0
    repair_success: int = 0
    candidates_total: int = 0
    regressions: int = 0
    latencies: List[float] = field(default_factory=list)
    repair_latencies: List[float] = field(default_factory=list)

    @staticmethod
    def _div(a: float, b: float) -> float:
        return a / b if b else 0.0

    def precision(self) -> float:
        return self._div(self.tp, self.tp + self.fp)

    def recall(self) -> float:
        return self._div(self.tp, self.tp + self.fn)

    def f1(self) -> float:
        p, r = self.precision(), self.recall()
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict:
        d = self._div
        return {
            "total_tests": self.total,
            "passed": self.passed,
            "pass_rate": d(self.passed, self.total),
            "category_accuracy": d(self.category_match, self.total),
            "exact_count_accuracy": d(self.count_match, self.total),
            "precision": self.precision(),
            "recall": self.recall(),
            "f1": self.f1(),
            "repair_labelled_cases": self.repair_expected,
            "repair_coverage": d(self.repair_covered, self.repair_expected),
            "repair_success_rate": d(self.repair_success, self.repair_expected),
            "regression_rate": d(self.regressions, self.candidates_total),
            "candidates_total": self.candidates_total,
            "avg_analysis_ms": d(sum(self.latencies), len(self.latencies)),
            "avg_repair_ms": d(sum(self.repair_latencies), len(self.repair_latencies)),
        }


def compute_metrics(outcomes: List[TestOutcome]) -> EvaluationMetrics:
    m = EvaluationMetrics(total=len(outcomes))
    for o in outcomes:
        m.latencies.append(o.analysis_time_ms)
        if o.passed:
            m.passed += 1
        if set(o.expected_categories) == set(o.actual_categories):
            m.category_match += 1
        if o.actual_errors == o.expected_errors:
            m.count_match += 1
        a, e = max(o.actual_errors, 0), o.expected_errors
        m.tp += min(a, e)
        m.fp += max(a - e, 0)
        m.fn += max(e - a, 0)

        if o.repair_expected:
            m.repair_expected += 1
            m.repair_covered += int(o.repair_generated)
            m.repair_success += int(o.repair_success)
        if o.repair_generated:
            m.repair_latencies.append(o.repair_time_ms)
        m.candidates_total += o.candidates_total
        m.regressions += o.regressions
    return m