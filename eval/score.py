#!/usr/bin/env python3
"""Score saved review runs against separately maintained annotations; never call a model."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_core.contracts import ISSUES, VERDICTS, record, require, save_json


def overlap(a, b):
    if any(a.get(k) != b.get(k) for k in ("target", "source_id", "field")):
        return 0.0
    for value in (a, b):
        require(type(value.get("start")) is int and type(value.get("end")) is int,
                "anchor", "integer offsets required")
        require(0 <= value["start"] < value["end"], "anchor", "invalid range")
    return max(0, min(a["end"], b["end"]) - max(a["start"], b["start"])) / max(a["end"] - a["start"], b["end"] - b["start"])


def matches(expected, predicted, compatible):
    candidates = []
    for i, a in enumerate(expected):
        for j, b in enumerate(predicted):
            ratio = overlap(a["anchor"], b["anchor"])
            if ratio >= 0.5 and compatible(a, b):
                candidates.append((-ratio, a["anchor"]["start"], b["anchor"]["start"], i, j))
    used_a, used_b, pairs = set(), set(), []
    for _, _, _, i, j in sorted(candidates):
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            pairs.append((i, j))
    return pairs


def ratio(n, d):
    return n / d if d else None


def score_runs(gold: list[dict[str, object]], runs: list[dict[str, object]], *, allow_draft: bool = False) -> dict[str, object]:
    labels = {}
    annotation_statuses = set()
    for item in gold:
        record(item, {"case_id", "annotation_status", "key_claims"}, "gold")
        status = item["annotation_status"]
        require(status in {"human_validated", "draft_model_authored_not_human_validated"},
                "annotation_status", "unknown label status")
        require(status != "draft_model_authored_not_human_validated" or allow_draft,
                "annotation_status", "draft labels require --allow-draft; results are provisional")
        annotation_statuses.add(status)
        require(item["case_id"] not in labels, "case_id", "duplicate gold case")
        for c in item["key_claims"]:
            record(c, {"anchor", "expected_verdict", "issue_codes", "rationale", "evidence"}, "gold claim")
            require(c["expected_verdict"] in VERDICTS, "gold verdict", "unknown verdict")
            require(set(c["issue_codes"]) <= ISSUES, "gold issue", "unknown issue")
            if status == "human_validated":
                require(type(c.get("serious")) is bool, "gold claim.serious",
                        "human-validated claims must classify serious false-acceptance risk")
            elif "serious" in c:
                require(type(c["serious"]) is bool, "gold claim.serious", "boolean required")
            overlap(c["anchor"], c["anchor"])
        labels[item["case_id"]] = item["key_claims"]
    methods = defaultdict(list)
    seen = set()
    for run in runs:
        record(run, {"case_id", "method", "run_id", "status", "report", "usage", "elapsed_seconds"}, "run")
        require(run["case_id"] in labels, "case_id", "unknown case")
        require(run["method"] in ("generic_prompt", "rules_only", "full_skill"), "method", "unknown method")
        require(run["status"] in ("completed", "invalid_output", "runtime_error"), "status", "unknown status")
        key = (run["case_id"], run["method"], run["run_id"])
        require(key not in seen, "run_id", "duplicate run")
        seen.add(key)
        methods[run["method"]].append(run)
    output = {}
    for method, records in methods.items():
        counts = Counter()
        confusion = Counter()
        per_run = []
        for run in records:
            expected = labels[run["case_id"]]
            failed = run["status"] != "completed"
            counts["failed_runs"] += failed
            findings = [] if failed else run["report"]["findings"]
            predicted, unique = [], set()
            for f in findings:
                record(f, {"claim", "verdict", "issue_codes"}, "finding")
                require(f["verdict"] in VERDICTS and set(f["issue_codes"]) <= ISSUES, "finding", "invalid status or issue")
                a = f["claim"]["anchor"]
                overlap(a, a)
                key = json.dumps([a, f["verdict"], sorted(set(f["issue_codes"]))], sort_keys=True)
                if key not in unique:
                    unique.add(key)
                    predicted.append({"anchor": a, "verdict": f["verdict"], "issue_codes": sorted(set(f["issue_codes"]))})
            pairs = matches(expected, predicted, lambda a, b: True)
            linked = dict(pairs)
            counts["key_claims"] += len(expected)
            counts["extracted_key_claims"] += len(pairs)
            for i, c in enumerate(expected):
                v = predicted[linked[i]]["verdict"] if i in linked else "not_reviewed"
                confusion[(c["expected_verdict"], v)] += 1
                if c["expected_verdict"] == "supported":
                    counts["normal_claims"] += 1
                    counts["normal_claim_false_alarms"] += v not in {"supported", "not_reviewed", "out_of_scope"}
                if c["expected_verdict"] == "unverifiable":
                    counts["unverifiable_claims"] += 1
                    counts["unverifiable_as_contradicted"] += v == "contradicted"
                if c.get("serious", False):
                    counts["serious_claims"] += 1
                    counts["serious_false_acceptances"] += v == "supported" and c["expected_verdict"] != "supported"
            expected_issues = [{"anchor": c["anchor"], "issue": issue, "verdict": c["expected_verdict"]}
                               for c in expected for issue in set(c["issue_codes"])]
            predicted_issues = [{"anchor": c["anchor"], "issue": issue, "verdict": c["verdict"]}
                                for c in predicted for issue in c["issue_codes"]]
            pairs = matches(expected_issues, predicted_issues, lambda a, b: a["issue"] == b["issue"] and a["verdict"] == b["verdict"])
            tp, fp, fn = len(pairs), len(predicted_issues) - len(pairs), len(expected_issues) - len(pairs)
            counts.update(true_positives=tp, false_positives=fp, false_negatives=fn)
            per_run.append({"case_id": run["case_id"], "run_id": run["run_id"], "status": run["status"], "tp": tp, "fp": fp, "fn": fn})
        tp, fp, fn = counts["true_positives"], counts["false_positives"], counts["false_negatives"]
        result = {k: counts[k] for k in ["true_positives", "false_positives", "false_negatives", "failed_runs", "key_claims", "extracted_key_claims", "normal_claims", "normal_claim_false_alarms", "unverifiable_claims", "unverifiable_as_contradicted", "serious_claims", "serious_false_acceptances"]}
        result.update(runs=len(records), precision=ratio(tp, tp + fp), recall=ratio(tp, tp + fn),
                      f1=ratio(2 * tp, 2 * tp + fp + fn), claim_extraction_coverage=ratio(counts["extracted_key_claims"], counts["key_claims"]),
                      normal_claim_false_alarm_rate=ratio(counts["normal_claim_false_alarms"], counts["normal_claims"]),
                      unverifiable_as_contradicted_rate=ratio(counts["unverifiable_as_contradicted"], counts["unverifiable_claims"]),
                      missing_case_ids=sorted(set(labels) - {r["case_id"] for r in records}),
                      confusion=[{"expected": a, "predicted": b, "count": n} for (a, b), n in sorted(confusion.items())], per_run=per_run)
        for field in ("input_tokens", "output_tokens", "cached_tokens", "model_requests", "network_actions"):
            values = [(r.get("usage") or {}).get(field) for r in records]
            for value in values:
                require(value is None or (type(value) is int and value >= 0), "usage." + field, "nonnegative integer or null required")
            result[field + "_total"] = sum(values) if all(v is not None for v in values) else None
            result[field + "_missing_runs"] = sum(v is None for v in values)
        times = [r["elapsed_seconds"] for r in records]
        require(all(v is None or (type(v) in (int, float) and v >= 0) for v in times), "elapsed_seconds", "nonnegative number or null required")
        result["median_elapsed_seconds"] = statistics.median(times) if all(t is not None for t in times) else None
        output[method] = result
    return {"schema_version": 1,
            "annotation_status": "provisional_draft" if "draft_model_authored_not_human_validated" in annotation_statuses else "human_validated",
            "serious_false_acceptances": output.get("full_skill", {}).get("serious_false_acceptances"),
            "methods": output,
            "limitations": ["Scores depend on annotation quality; proposed edits require separate human review.",
                            "Issue TP requires matching anchor, issue code and verdict; failed runs stay in recall denominators.",
                            "Absent scheduled runs cannot be inferred: inspect missing_case_ids and the run manifest."]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--labels", required=True)
    p.add_argument("--runs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--allow-draft", action="store_true", help="Score model-authored draft labels for pipeline checks only; metrics remain provisional")
    args = p.parse_args()
    def rows(path):
        return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    try:
        require(Path(args.out).resolve() not in {Path(args.labels).resolve(), Path(args.runs).resolve()}, "output", "would overwrite input")
        save_json(args.out, score_runs(rows(args.labels), rows(args.runs), allow_draft=args.allow_draft))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        p.exit(2, f"Scoring failed: {exc}\n")


if __name__ == "__main__":
    main()
