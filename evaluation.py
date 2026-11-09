"""Synthetic-case evaluation harness for HAC-Renal AI.

This implements the evaluation plan described in the project requirements
document: recommendation concordance, accuracy of the dosing rules, detection
of high-risk situations, appropriate abstention when information is
insufficient, evidence traceability and processing time.

The harness always evaluates the DETERMINISTIC engine (``apply_rules``) and the
retrieval layer (``retrieve_evidence``) - never the language model - so the
numbers describe the rules and data, not a model's wording.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rules_engine import apply_rules
from evidence_retriever import retrieve_evidence

CASE_FILES = [
    os.path.join(ROOT, "data", "synthetic_cases.json"),
    os.path.join(ROOT, "data", "vancomycin_synthetic_cases.json"),
]

# Situations the system must never miss: a hard stop, a high-priority
# interaction, a case that needs a specialist, or a missing source row.
HIGH_RISK_DECISIONS = {
    "BLOCK",
    "HIGH_PRIORITY_INTERACTION_ALERT",
    "SPECIALIST_REVIEW_REQUIRED",
    "SOURCE_DATA_UNAVAILABLE",
}


def is_abstention(result):
    """True when the engine refused to invent a dose (safe failure)."""
    decision = (result or {}).get("decision")
    if decision in ("NEEDS_MORE_INFORMATION", "UNSUPPORTED_DRUG"):
        return True
    return decision == "BLOCK" and result.get("alert_code") == "MISSING_CRCL"


def load_cases(case_files=None):
    """Yield (source_file, case) for every synthetic case on disk."""
    for path in (case_files or CASE_FILES):
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        for case in payload.get("test_cases", []):
            yield os.path.basename(path), case


def compare(expected, actual):
    """Return the expected keys whose actual value differs (subset match)."""
    diffs = []
    for key, want in (expected or {}).items():
        got = (actual or {}).get(key)
        if got != want:
            diffs.append({"field": key, "expected": want, "actual": got})
    return diffs


def evaluate_case(source_file, case):
    """Run one synthetic case and return its metrics row."""
    expected = case.get("expected_output", {})
    start = time.perf_counter()
    actual = apply_rules(case.get("patient_input", {}))
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    evidence = retrieve_evidence(actual)
    diffs = compare(expected, actual)

    expected_high_risk = expected.get("decision") in HIGH_RISK_DECISIONS
    expected_abstention = expected.get("decision") in ("NEEDS_MORE_INFORMATION",) or (
        expected.get("decision") == "BLOCK"
        and expected.get("alert_code") == "MISSING_CRCL"
    )
    traceable = bool(evidence["sections"]) and bool(
        evidence["sources"] or evidence.get("source_rule")
    )

    return {
        "test_id": case.get("test_id"),
        "source_file": source_file,
        "expected_decision": expected.get("decision"),
        "actual_decision": actual.get("decision"),
        "concordant": not diffs,
        "mismatches": diffs,
        "high_risk_expected": expected_high_risk,
        "high_risk_detected": actual.get("decision") in HIGH_RISK_DECISIONS,
        "abstention_expected": expected_abstention,
        "abstained": is_abstention(actual),
        "traceable": traceable,
        "elapsed_ms": round(elapsed_ms, 3),
    }


def run_evaluation(case_files=None):
    """Evaluate every synthetic case and aggregate the metrics."""
    rows = [evaluate_case(src, case) for src, case in load_cases(case_files)]
    if not rows:
        return {"total_cases": 0, "rows": [], "metrics": {}}

    def _ratio(part, whole):
        return round(part / whole, 4) if whole else None

    high_risk = [r for r in rows if r["high_risk_expected"]]
    abstention = [r for r in rows if r["abstention_expected"]]
    times = [r["elapsed_ms"] for r in rows]

    metrics = {
        "total_cases": len(rows),
        "concordant_cases": sum(1 for r in rows if r["concordant"]),
        "concordance_rate": _ratio(sum(1 for r in rows if r["concordant"]), len(rows)),
        "high_risk_cases": len(high_risk),
        "high_risk_detected": sum(1 for r in high_risk if r["high_risk_detected"]),
        "high_risk_detection_rate": _ratio(
            sum(1 for r in high_risk if r["high_risk_detected"]), len(high_risk)
        ),
        "abstention_cases": len(abstention),
        "abstention_correct": sum(1 for r in abstention if r["abstained"]),
        "abstention_correct_rate": _ratio(
            sum(1 for r in abstention if r["abstained"]), len(abstention)
        ),
        "traceable_cases": sum(1 for r in rows if r["traceable"]),
        "traceability_rate": _ratio(sum(1 for r in rows if r["traceable"]), len(rows)),
        "mean_processing_ms": round(sum(times) / len(times), 3),
        "max_processing_ms": round(max(times), 3),
    }
    return {"total_cases": len(rows), "rows": rows, "metrics": metrics}


def format_report(summary):
    """Render the summary as a plain-text report."""
    metrics = summary.get("metrics") or {}
    lines = ["HAC-Renal AI - synthetic-case evaluation", "=" * 46]
    for row in summary.get("rows", []):
        flag = "PASS" if row["concordant"] else "FAIL"
        lines.append(
            "[%s] %-12s %s -> %s (%.2f ms)"
            % (flag, row["test_id"], row["expected_decision"],
               row["actual_decision"], row["elapsed_ms"])
        )
        for diff in row["mismatches"]:
            lines.append(
                "        %s: expected %r, got %r"
                % (diff["field"], diff["expected"], diff["actual"])
            )
    lines.append("-" * 46)
    if metrics:
        lines.append("concordance            : %d/%d (%s)"
                     % (metrics["concordant_cases"], metrics["total_cases"],
                        metrics["concordance_rate"]))
        lines.append("high-risk detection    : %d/%d (%s)"
                     % (metrics["high_risk_detected"], metrics["high_risk_cases"],
                        metrics["high_risk_detection_rate"]))
        lines.append("appropriate abstention : %d/%d (%s)"
                     % (metrics["abstention_correct"], metrics["abstention_cases"],
                        metrics["abstention_correct_rate"]))
        lines.append("evidence traceability  : %d/%d (%s)"
                     % (metrics["traceable_cases"], metrics["total_cases"],
                        metrics["traceability_rate"]))
        lines.append("processing time        : mean %.2f ms, max %.2f ms"
                     % (metrics["mean_processing_ms"], metrics["max_processing_ms"]))
    return "\n".join(lines)


def main():
    summary = run_evaluation()
    print(format_report(summary))
    return 0 if all(r["concordant"] for r in summary["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
