"""Validated ordinary-skill review records and user-visible coverage status."""
from __future__ import annotations

import copy

from .contracts import VERDICTS, record, require, strings, text

TASK_FIT_VERDICTS = {"matches", "partial", "fails", "unknown"}
IDENTITY_VERDICTS = {"verified", "mismatch", "unresolved"}
SUBSTANTIVE_FACT_VERDICTS = VERDICTS - {"not_reviewed", "out_of_scope"}


def _judgment(value: object, path: str, verdicts: set[str]) -> None:
    record(value, {"verdict", "reason"}, path)
    require(value["verdict"] in verdicts, path + ".verdict", "unknown verdict")
    text(value["reason"], path + ".reason")


def _validate_result_review(value: object, result_ids: set[str], seen: set[str], path: str) -> dict[str, object]:
    record(value, {"result_id", "task_fit", "source_identity", "used_claim_ids", "fact_reviews"}, path)
    text(value["result_id"], path + ".result_id")
    result_id = value["result_id"]
    require(result_id in result_ids, path + ".result_id", "unknown result")
    require(result_id not in seen, path + ".result_id", "duplicate result review")
    seen.add(result_id)
    _judgment(value["task_fit"], path + ".task_fit", TASK_FIT_VERDICTS)
    _judgment(value["source_identity"], path + ".source_identity", IDENTITY_VERDICTS)
    strings(value["used_claim_ids"], path + ".used_claim_ids")
    require(len(set(value["used_claim_ids"])) == len(value["used_claim_ids"]),
            path + ".used_claim_ids", "duplicate claim")
    require(isinstance(value["fact_reviews"], list), path + ".fact_reviews", "expected array")
    fact_reviews = {}
    for i, fact in enumerate(value["fact_reviews"]):
        fact_path = f"{path}.fact_reviews[{i}]"
        record(fact, {"claim_id", "verdict", "unresolved"}, fact_path)
        text(fact["claim_id"], fact_path + ".claim_id")
        require(fact["claim_id"] not in fact_reviews, fact_path + ".claim_id", "duplicate claim review")
        require(fact["verdict"] in VERDICTS, fact_path + ".verdict", "unknown verdict")
        strings(fact["unresolved"], fact_path + ".unresolved")
        if fact["verdict"] in {"insufficient_evidence", "unverifiable", "conflicted"}:
            require(bool(fact["unresolved"]), fact_path + ".unresolved", "state the unresolved gap")
        fact_reviews[fact["claim_id"]] = fact
    reviewed = all(
        claim_id in fact_reviews and fact_reviews[claim_id]["verdict"] in SUBSTANTIVE_FACT_VERDICTS
        for claim_id in value["used_claim_ids"]
    )
    return {"result_id": result_id, "reviewed": reviewed,
            "used_in_answer": bool(value["used_claim_ids"]), "record": copy.deepcopy(value)}


def summarize_batch_review(data: dict[str, object]) -> dict[str, object]:
    """Validate one ordinary-mode batch record and derive its coverage line.

    Missing result reviews remain valid, visible gaps. Existing review entries are
    strict so malformed data cannot inflate the reviewed numerator.
    """
    record(data, {"schema_version", "batch_id", "result_ids", "reviews"}, "batch_review")
    require(type(data["schema_version"]) is int and data["schema_version"] == 1,
            "batch_review.schema_version", "expected 1")
    text(data["batch_id"], "batch_review.batch_id")
    strings(data["result_ids"], "batch_review.result_ids")
    require(len(set(data["result_ids"])) == len(data["result_ids"]),
            "batch_review.result_ids", "duplicate result")
    require(isinstance(data["reviews"], list), "batch_review.reviews", "expected array")
    result_ids = set(data["result_ids"])
    seen: set[str] = set()
    states = [_validate_result_review(value, result_ids, seen, f"batch_review.reviews[{i}]")
              for i, value in enumerate(data["reviews"])]
    reviewed_ids = {state["result_id"] for state in states if state["reviewed"]}
    unreviewed = [result_id for result_id in data["result_ids"] if result_id not in reviewed_ids]
    used = [state["result_id"] for state in states if state["used_in_answer"]]
    reviewed, total = len(reviewed_ids), len(data["result_ids"])
    status_line = f"已审查 {reviewed}/{total}" if total else "已审查 0/0（无搜索结果）"
    return {
        "schema_version": 1,
        "batch_id": data["batch_id"],
        "review_progress": {"reviewed": reviewed, "total": total},
        "status_line": status_line,
        "reviewed_result_ids": [result_id for result_id in data["result_ids"] if result_id in reviewed_ids],
        "unreviewed_result_ids": unreviewed,
        "used_result_ids": used,
        "complete": not unreviewed,
    }
