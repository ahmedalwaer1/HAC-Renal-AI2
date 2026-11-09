"""Synthetic test runner for HAC-Renal AI."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from orchestrator import evaluate_patient

SYNTHETIC_PATH = os.path.join(ROOT, "data", "synthetic_cases.json")


def load_test_cases():
    with open(SYNTHETIC_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_cases", [])


def compare(actual, expected):
    mismatches = []
    for key, exp_val in expected.items():
        act_val = actual.get(key)
        if act_val != exp_val:
            mismatches.append((key, exp_val, act_val))
    return mismatches


def main():
    cases = load_test_cases()
    print("=" * 70)
    print("HAC-Renal AI - Synthetic Test Runner (Sprint 2)")
    print("=" * 70)
    all_pass = True
    for tc in cases:
        tc_id = tc["test_id"]
        name = tc["test_name"]
        actual = evaluate_patient(tc["patient_input"])
        expected = tc["expected_output"]
        mismatches = compare(actual, expected)
        status = "PASS" if not mismatches else "FAIL"
        if mismatches:
            all_pass = False
        print("\n[%s] %s - %s" % (tc_id, name, status))
        print("  Actual:   %s" % json.dumps(actual, ensure_ascii=False))
        print("  Expected: %s" % json.dumps(expected, ensure_ascii=False))
        if mismatches:
            for key, exp, act in mismatches:
                print("  MISMATCH %s: expected=%r actual=%r" % (key, exp, act))
    print("\n" + "=" * 70)
    print("OVERALL: %s" % ("ALL PASS" if all_pass else "FAILURES PRESENT"))
    print("=" * 70)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
