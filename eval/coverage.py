#!/usr/bin/env python3
"""Score saved Codex execution traces for review-before-use coverage; never call a model."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_core.contracts import record, require, save_json, strings, text
from reviewer_core.ordinary import summarize_batch_review

RUN_STATUSES = {"completed", "invalid_output", "runtime_error", "timeout", "untriggered"}
EVENT_TYPES = {"skill_activated", "search_results", "review_recorded", "result_used", "answer_delivered"}
TASK_CATEGORIES = {"factual_lookup", "recommendation", "comparison", "citation_check",
                   "version_sensitive", "unavailable_page", "multi_round", "existing_results",
                   "correction_search", "non_search_control"}


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _validate_usage(value: object, path: str) -> None:
    if value is None:
        return
    require(isinstance(value, dict), path, "expected object or null")
    for field in ("input_tokens", "output_tokens", "cached_tokens", "model_requests", "network_actions"):
        amount = value.get(field)
        require(amount is None or (type(amount) is int and amount >= 0),
                path + "." + field, "nonnegative integer or null required")


def _validate_run(run: dict[str, object], index: int) -> None:
    path = f"runs[{index}]"
    record(run, {"schema_version", "run_id", "case_id", "method", "status", "platform",
                 "codex_version", "model", "settings", "skill_revision", "task_category",
                 "events", "usage", "elapsed_seconds"}, path)
    require(type(run["schema_version"]) is int and run["schema_version"] == 1,
            path + ".schema_version", "expected 1")
    for field in ("run_id", "case_id", "method", "platform", "codex_version", "model", "skill_revision"):
        text(run[field], path + "." + field)
    require(run["status"] in RUN_STATUSES, path + ".status", "unknown status")
    require(run["task_category"] in TASK_CATEGORIES, path + ".task_category", "unknown category")
    require(isinstance(run["settings"], dict), path + ".settings", "expected object")
    require(isinstance(run["events"], list), path + ".events", "expected array")
    _validate_usage(run["usage"], path + ".usage")
    elapsed = run["elapsed_seconds"]
    require(elapsed is None or (type(elapsed) in (int, float) and elapsed >= 0),
            path + ".elapsed_seconds", "nonnegative number or null required")


def _score_run(run: dict[str, object]) -> dict[str, object]:
    batches: dict[str, dict[str, object]] = {}
    review_events: dict[str, list[tuple[int, dict[str, object]]]] = {}
    uses: dict[str, list[tuple[int, str]]] = {}
    activated = False
    for event_index, event in enumerate(run["events"]):
        path = f"events[{event_index}]"
        record(event, {"type"}, path)
        require(event["type"] in EVENT_TYPES, path + ".type", "unknown event")
        event_type = event["type"]
        if event_type == "skill_activated":
            activated = True
        elif event_type == "search_results":
            record(event, {"batch_id", "result_ids"}, path)
            text(event["batch_id"], path + ".batch_id")
            strings(event["result_ids"], path + ".result_ids")
            require(len(set(event["result_ids"])) == len(event["result_ids"]),
                    path + ".result_ids", "duplicate result")
            require(event["batch_id"] not in batches, path + ".batch_id", "duplicate batch")
            batches[event["batch_id"]] = {"index": event_index, "result_ids": list(event["result_ids"])}
        elif event_type == "review_recorded":
            record(event, {"batch_id", "record"}, path)
            text(event["batch_id"], path + ".batch_id")
            require(event["batch_id"] in batches, path + ".batch_id", "review before search batch")
            require(isinstance(event["record"], dict), path + ".record", "expected object")
            summary = summarize_batch_review(event["record"])
            require(summary["batch_id"] == event["batch_id"], path + ".record.batch_id", "batch mismatch")
            require(event["record"]["result_ids"] == batches[event["batch_id"]]["result_ids"],
                    path + ".record.result_ids", "must match returned result order")
            review_events.setdefault(event["batch_id"], []).append((event_index, summary))
        elif event_type == "result_used":
            record(event, {"batch_id", "result_id"}, path)
            text(event["batch_id"], path + ".batch_id")
            text(event["result_id"], path + ".result_id")
            require(event["batch_id"] in batches, path + ".batch_id", "unknown batch")
            require(event["result_id"] in batches[event["batch_id"]]["result_ids"],
                    path + ".result_id", "unknown result")
            uses.setdefault(event["batch_id"], []).append((event_index, event["result_id"]))

    missed, covered = [], []
    categories = Counter()
    for batch_id, batch_uses in uses.items():
        all_results_covered = True
        had_prior_review = False
        for use_index, result_id in batch_uses:
            prior = [(index, summary) for index, summary in review_events.get(batch_id, []) if index < use_index]
            had_prior_review = had_prior_review or bool(prior)
            if not any(result_id in summary["reviewed_result_ids"] for _, summary in prior):
                all_results_covered = False
        if all_results_covered:
            covered.append(batch_id)
        else:
            missed.append(batch_id)
            categories["incomplete_review_record" if had_prior_review else "review_skipped"] += 1
    expects_activation = run["task_category"] != "non_search_control"
    if expects_activation and not activated:
        categories["skill_not_activated"] += 1
    return {
        "activated": activated,
        "expects_activation": expects_activation,
        "observed_batches": len(batches),
        "zero_result_batches": sum(not batch["result_ids"] for batch in batches.values()),
        "used_batches": len(uses),
        "covered_batch_ids": covered,
        "missed_batch_ids": missed,
        "failure_categories": categories,
    }


def score_traces(runs: list[dict[str, object]], *,
                 manifest: list[dict[str, object]] | None = None) -> dict[str, object]:
    scheduled = {}
    if manifest is not None:
        for index, item in enumerate(manifest):
            path = f"manifest[{index}]"
            record(item, {"run_id", "case_id", "method", "task_category"}, path)
            for field in ("run_id", "case_id", "method"):
                text(item[field], path + "." + field)
            require(item["task_category"] in TASK_CATEGORIES, path + ".task_category", "unknown category")
            require(item["run_id"] not in scheduled, path + ".run_id", "duplicate scheduled run")
            scheduled[item["run_id"]] = item
    seen = set()
    totals = Counter()
    categories = Counter()
    per_run = []
    elapsed_values = []
    usage_values = {field: [] for field in
                    ("input_tokens", "output_tokens", "cached_tokens", "model_requests", "network_actions")}
    for index, run in enumerate(runs):
        _validate_run(run, index)
        require(run["run_id"] not in seen, f"runs[{index}].run_id", "duplicate run")
        if manifest is not None:
            require(run["run_id"] in scheduled, f"runs[{index}].run_id", "run is not in frozen manifest")
            expected = scheduled[run["run_id"]]
            for field in ("case_id", "method", "task_category"):
                require(run[field] == expected[field], f"runs[{index}].{field}", "does not match frozen manifest")
        seen.add(run["run_id"])
        scored = _score_run(run)
        totals["runs"] += 1
        totals["failed_runs"] += run["status"] != "completed"
        totals["activation_expected_runs"] += scored["expects_activation"]
        totals["activated_expected_runs"] += scored["activated"] and scored["expects_activation"]
        totals["negative_control_runs"] += not scored["expects_activation"]
        totals["negative_control_false_activations"] += scored["activated"] and not scored["expects_activation"]
        totals["observed_batches"] += scored["observed_batches"]
        totals["zero_result_batches"] += scored["zero_result_batches"]
        totals["used_batches"] += scored["used_batches"]
        totals["reviewed_before_use_batches"] += len(scored["covered_batch_ids"])
        totals["missed_review_batches"] += len(scored["missed_batch_ids"])
        categories.update(scored["failure_categories"])
        elapsed_values.append(run["elapsed_seconds"])
        for field, values in usage_values.items():
            values.append((run["usage"] or {}).get(field))
        per_run.append({"run_id": run["run_id"], "case_id": run["case_id"],
                        "status": run["status"], "activated": scored["activated"],
                        "observed_batches": scored["observed_batches"],
                        "used_batches": scored["used_batches"],
                        "covered_batch_ids": scored["covered_batch_ids"],
                        "missed_batch_ids": scored["missed_batch_ids"]})
    result = {field: totals[field] for field in
              ("runs", "failed_runs", "observed_batches", "zero_result_batches", "used_batches",
               "reviewed_before_use_batches", "missed_review_batches")}
    result.update(
        schema_version=1,
        scheduled_runs=len(scheduled) if manifest is not None else totals["runs"],
        missing_run_ids=sorted(set(scheduled) - seen) if manifest is not None else [],
        skill_activation_rate=ratio(totals["activated_expected_runs"], totals["activation_expected_runs"]),
        negative_control_false_activation_rate=ratio(totals["negative_control_false_activations"],
                                                     totals["negative_control_runs"]),
        per_batch_review_coverage=ratio(totals["reviewed_before_use_batches"], totals["used_batches"]),
        failure_categories={name: categories[name] for name in
                            ("skill_not_activated", "review_skipped", "incomplete_review_record", "semantic_misjudgment")},
        per_run=per_run,
        median_elapsed_seconds=(statistics.median(elapsed_values)
                                if elapsed_values and all(value is not None for value in elapsed_values) else None),
    )
    for field, values in usage_values.items():
        result[field + "_total"] = sum(values) if all(value is not None for value in values) else None
        result[field + "_missing_runs"] = sum(value is None for value in values)
    result["limitations"] = [
        "Coverage records whether review happened before use; it does not prove the semantic judgment was correct.",
        "Zero-result batches are reported separately and are not part of the used-batch coverage denominator.",
        "Semantic misjudgment requires separately frozen human labels and is not inferred from execution order.",
    ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", required=True)
    parser.add_argument("--manifest", help="Frozen JSONL schedule; omitted runs remain visible")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        rows = [json.loads(line) for line in Path(args.runs).read_text(encoding="utf-8").splitlines() if line.strip()]
        manifest = ([json.loads(line) for line in Path(args.manifest).read_text(encoding="utf-8").splitlines() if line.strip()]
                    if args.manifest else None)
        inputs = {Path(args.runs).resolve()} | ({Path(args.manifest).resolve()} if args.manifest else set())
        require(Path(args.out).resolve() not in inputs, "output", "would overwrite input")
        save_json(args.out, score_traces(rows, manifest=manifest))
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Coverage scoring failed: {exc}\n")


if __name__ == "__main__":
    main()
