#!/usr/bin/env python3
"""Combine saved coverage, semantic, installation, and CI evidence into Beta release gates."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_core.contracts import load_json, record, require, save_json


def assess_release(coverage: dict[str, object], semantics: dict[str, object],
                   checks: dict[str, object]) -> dict[str, object]:
    record(coverage, {"schema_version", "observed_batches", "used_batches",
                      "reviewed_before_use_batches", "missed_review_batches",
                      "per_batch_review_coverage"}, "coverage")
    record(semantics, {"schema_version", "annotation_status", "serious_false_acceptances"}, "semantics")
    record(checks, {"clean_install_reproduced", "deterministic_tests_passed",
                    "documentation_checks_passed"}, "checks")
    for path, value in (("coverage.observed_batches", coverage["observed_batches"]),
                        ("coverage.used_batches", coverage["used_batches"]),
                        ("coverage.reviewed_before_use_batches", coverage["reviewed_before_use_batches"]),
                        ("coverage.missed_review_batches", coverage["missed_review_batches"]),
                        ("semantics.serious_false_acceptances", semantics["serious_false_acceptances"])):
        require(type(value) is int and value >= 0, path, "nonnegative integer required")
    for field in ("clean_install_reproduced", "deterministic_tests_passed", "documentation_checks_passed"):
        require(type(checks[field]) is bool, "checks." + field, "boolean required")
    gates = [
        {"name": "observed_batches", "passed": coverage["observed_batches"] >= 100,
         "actual": coverage["observed_batches"], "required": ">= 100"},
        {"name": "missed_reviews", "passed": coverage["missed_review_batches"] <= 5,
         "actual": coverage["missed_review_batches"], "required": "<= 5"},
        {"name": "human_validated_labels", "passed": semantics["annotation_status"] == "human_validated",
         "actual": semantics["annotation_status"], "required": "human_validated"},
        {"name": "serious_false_acceptances", "passed": semantics["serious_false_acceptances"] == 0,
         "actual": semantics["serious_false_acceptances"], "required": 0},
        {"name": "clean_install", "passed": checks["clean_install_reproduced"],
         "actual": checks["clean_install_reproduced"], "required": True},
        {"name": "deterministic_tests", "passed": checks["deterministic_tests_passed"],
         "actual": checks["deterministic_tests_passed"], "required": True},
        {"name": "documentation_checks", "passed": checks["documentation_checks_passed"],
         "actual": checks["documentation_checks_passed"], "required": True},
    ]
    ready = all(gate["passed"] for gate in gates)
    return {"schema_version": 1, "ready": ready, "status": "ready" if ready else "blocked", "gates": gates}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--semantics", required=True)
    parser.add_argument("--checks", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        inputs = {Path(args.coverage).resolve(), Path(args.semantics).resolve(), Path(args.checks).resolve()}
        require(Path(args.out).resolve() not in inputs, "output", "would overwrite input")
        result = assess_release(load_json(args.coverage), load_json(args.semantics), load_json(args.checks))
        save_json(args.out, result)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"Release assessment failed: {exc}\n")


if __name__ == "__main__":
    main()
