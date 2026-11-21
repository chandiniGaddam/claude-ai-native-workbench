#!/usr/bin/env python3
"""Fail (exit 1) unless the JUnit report satisfies the deterministic-test gate.

Usage: python scripts/check_gate.py reports/junit.xml [--min 8]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qe.gate import evaluate_junit_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("junit_xml", type=Path)
    parser.add_argument("--min", type=int, default=8, dest="min_passed")
    args = parser.parse_args()
    if not args.junit_xml.is_file():
        print(f"gate: FAIL\n  report not found: {args.junit_xml}")
        return 1
    result = evaluate_junit_file(args.junit_xml, args.min_passed)
    print(result.summary())
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
