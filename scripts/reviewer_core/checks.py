"""Mechanical observations and evidence-bound model judgments."""
from __future__ import annotations

from collections import Counter
import copy
import re
from .contracts import ISSUES, VERDICTS, bundle_id, record, require, strings, text, validate_request
from .evidence import freeze_sources, locate_quote, validate_evidence


def prepare(request: dict[str, object]) -> dict[str, object]:
    request = validate_request(request)
    request["sources"] = freeze_sources(request["sources"])
    checks = []
    def add(code, detail, source_id=None, claim_id=None):
        checks.append({"claim_id": claim_id, "source_id": source_id, "code": code, "detail": detail})
    for s in request["sources"]:
        if s["access"] != "readable":
            add("unread_source" if s["access"] == "not_read" else "source_unavailable",
                f"Access={s['access']}; this does not prove fabrication or nonexistence.", s["id"])
        if s["coverage"] != "complete":
            add("limited_coverage", f"Coverage={s['coverage']}; a missing passage may be outside the captured text.", s["id"])
        if s["provenance"] != "host_observation" or not s["observation_ref"] or not s["retrieved_at"]:
            add("insufficient_provenance", "This snapshot does not establish current online availability or publisher identity.", s["id"])
        if s["kind"] == "snippet":
            add("snippet_only", "Search snippet: discovery material, not final substantive evidence.", s["id"])
        for field in ("title", "publisher", "authors", "identifier"):
            a, b = s["declared"][field], s["observed"][field]
            if a and b and a != b:
                add("metadata_difference", f"Declared/observed {field} differ; inspect aliases, versions and identity before judging.", s["id"])
    sources = {s["id"]: s for s in request["sources"]}
    for c in request["claims"]:
        readable = [sources[sid] for sid in c["source_ids"] if sources[sid]["access"] == "readable" and sources[sid]["kind"] != "snippet"]
        if not readable:
            add("missing_evidence", "No readable non-snippet evidence linked to this claim.", claim_id=c["id"])
        if c["category"] == "quotation":
            matches = [(s["id"], locate_quote(s["text"], c["text"])) for s in readable]
            if any(m for _, m in matches):
                for sid, hits in matches:
                    if hits:
                        add("quote_located", {"matches": hits, "limitation": "Location is not semantic support."}, sid, c["id"])
            else:
                add("quote_not_observed", "Not located in captured evidence; not proof of a fabricated quote.", claim_id=c["id"])
        if c["category"] == "number":
            numbers = re.findall(r"(?<![\w.])[+-]?\d+(?:[.,]\d+)*(?:%|‰)?", c["text"])
            add("numeric_candidates", {"numbers": numbers, "instruction": "Check values, units, denominators and dates in context; literal presence is insufficient."}, claim_id=c["id"])
    actions = request["network_actions"]
    if len(actions) > 4:
        add("budget_exceeded", f"Recorded {len(actions)} actions; default budget is 4. Host execution is not intercepted.")
    failures = Counter((a["kind"], a["target"]) for a in actions if a["status"] == "failure")
    for (kind, target), count in failures.items():
        if count > 2:
            add("repeated_failure", f"{kind} {target}: {count} recorded failures, exceeding the default limit of 2.")
    return {"schema_version": 1, "bundle_id": bundle_id(request), "request": request, "mechanical_checks": checks}


def verify_prepared(prepared: dict[str, object]) -> dict[str, object]:
    record(prepared, {"schema_version", "bundle_id", "request", "mechanical_checks"}, "prepared")
    require(type(prepared["schema_version"]) is int and prepared["schema_version"] == 1, "prepared.schema_version", "expected 1")
    expected = prepare(prepared["request"])
    require(expected == prepared, "prepared", "snapshot, hash or mechanical checks changed; prepare again")
    return expected


def unreviewed(claim_id: str) -> dict[str, object]:
    return {"claim_id": claim_id, "verdict": "not_reviewed", "issue_codes": [], "evidence": [], "action_ids": [],
            "reason": "No semantic judgment submitted for this claim.", "suggested_text": None,
            "unresolved": ["Semantic review has not been performed."]}


def validate_judgments(prepared: dict[str, object], judgments: dict[str, object]) -> list[dict[str, object]]:
    verify_prepared(prepared)
    record(judgments, {"schema_version", "bundle_id", "reviewer", "findings"}, "judgments")
    require(type(judgments["schema_version"]) is int and judgments["schema_version"] == 1, "judgments.schema_version", "expected 1")
    require(judgments["bundle_id"] == prepared["bundle_id"], "bundle_id", "stale judgments; review the current bundle")
    reviewer = judgments["reviewer"]
    record(reviewer, {"kind", "model"}, "reviewer")
    require(reviewer["kind"] in ("host_model", "human", "saved_demo"), "reviewer.kind", "unknown kind")
    text(reviewer["model"], "reviewer.model", nullable=True)
    request = prepared["request"]
    claims = {c["id"]: c for c in request["claims"]}
    sources = {s["id"]: s for s in request["sources"]}
    actions = {a["id"]: a for a in request["network_actions"]}
    require(isinstance(judgments["findings"], list), "findings", "expected array")
    found = {}
    for f in judgments["findings"]:
        record(f, {"claim_id", "verdict", "issue_codes", "evidence", "action_ids", "reason", "suggested_text", "unresolved"}, "finding")
        text(f["claim_id"], "finding.claim_id")
        cid = f["claim_id"]
        require(cid in claims and cid not in found, "finding.claim_id", "unknown or duplicate claim")
        text(f["verdict"], "finding.verdict")
        v = f["verdict"]
        require(v in VERDICTS, "finding.verdict", "unknown verdict")
        strings(f["issue_codes"], "finding.issue_codes")
        require(set(f["issue_codes"]) <= ISSUES, "finding.issue_codes", "unknown issue")
        require(len(set(f["issue_codes"])) == len(f["issue_codes"]), "finding.issue_codes", "duplicate issue")
        text(f["reason"], "finding.reason")
        text(f["suggested_text"], "finding.suggested_text", nullable=True)
        strings(f["unresolved"], "finding.unresolved")
        strings(f["action_ids"], "finding.action_ids")
        require(set(f["action_ids"]) <= actions.keys(), "finding.action_ids", "unknown action")
        require(isinstance(f["evidence"], list), "finding.evidence", "expected array")
        for ref in f["evidence"]:
            validate_evidence(ref, request["sources"])
            s = sources[ref["source_id"]]
            require(s["access"] == "readable", "finding.evidence", "source is not readable evidence")
            require(s["kind"] != "snippet", "finding.evidence", "search snippets are not final evidence")
            if v in {"supported", "contradicted", "conflicted"}:
                require(s["kind"] == "page" or claims[cid]["category"] in {"existence", "identity"}, "finding.evidence", "metadata cannot prove substantive claims")
        if v in {"supported", "contradicted", "conflicted"}:
            require(bool(f["evidence"]), "finding.evidence", "a conclusive judgment needs evidence")
        if v == "supported":
            require(not f["issue_codes"] and not f["unresolved"], "finding", "supported cannot contain unresolved errors")
        if v == "conflicted":
            positions = {(e["source_id"], e["start"], e["end"]) for e in f["evidence"]}
            require(len(positions) >= 2, "finding.evidence", "conflict requires two distinct evidence positions")
        if v in {"insufficient_evidence", "unverifiable"}:
            require(bool(f["unresolved"]), "finding.unresolved", "name the evidence gap")
        if v == "unverifiable":
            linked = [sources[sid] for sid in claims[cid]["source_ids"]]
            limited = not linked or any(s["access"] != "readable" or s["coverage"] != "complete" or s["provenance"] != "host_observation" or not s["observation_ref"] or not s["retrieved_at"] for s in linked)
            failed = any(actions[aid]["status"] == "failure" for aid in f["action_ids"])
            require(limited or failed, "finding.unverifiable", "cite a failed action or material limitation")
        if f["suggested_text"] is not None:
            require(bool(f["evidence"]), "finding.suggested_text", "replacement needs evidence; use unresolved for a no-evidence clarification")
        found[cid] = copy.deepcopy(f)
    return [found.get(c["id"], unreviewed(c["id"])) for c in request["claims"]]
