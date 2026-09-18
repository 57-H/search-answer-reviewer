"""Synchronous, fail-closed boundary between a search backend and an agent."""
from __future__ import annotations

import copy
from typing import Callable

from .checks import prepare
from .contracts import record, require, text
from .report import build_report


class SearchAuditGate:
    """Expose this search method to the agent; keep the raw backend private.

    The backend returns a results-mode Request containing the real search action
    and one anchored source-declaration claim for every returned source. The
    auditor receives Prepared and returns Judgments with per-source task fit
    for that same bundle.
    """

    def __init__(self, backend: Callable[[str, str], dict[str, object]],
                 auditor: Callable[[dict[str, object]], dict[str, object]]) -> None:
        self._backend = backend
        self._auditor = auditor

    def search(self, question: str, query: str) -> dict[str, object]:
        text(question, "question")
        text(query, "query")
        raw = self._backend(question, query)
        require(isinstance(raw, dict), "search backend", "must return a results-mode Request")
        prepared = prepare(raw)
        request = prepared["request"]
        require(request["mode"] == "results" and request["evidence_mode"] == "host_web",
                "search backend", "live search requires results / host_web mode")
        require(request["question"] == question, "search backend.question", "must preserve the user question")

        actions = [action for action in request["network_actions"]
                   if action["kind"] == "search" and action["target"] == query and action["status"] == "success"]
        require(bool(actions), "search backend.network_actions", "missing successful search action for this query")
        covered = {source_id for action in actions for source_id in action["source_ids"]}
        for source in request["sources"]:
            source_id = source["id"]
            require(source_id in covered, source_id, "result is not linked to the search action")
            require(source["provenance"] == "host_observation" and source["observation_ref"]
                    and source["retrieved_at"], source_id, "live result needs an actual host observation")
            claims = [claim for claim in request["claims"]
                      if claim["anchor"]["target"] == "source_declared"
                      and claim["anchor"]["source_id"] == source_id
                      and source_id in claim["source_ids"]]
            require(bool(claims), source_id, "result needs a source-declaration review claim")

        judgments = self._auditor(copy.deepcopy(prepared))
        record(judgments, {"reviewer", "findings"}, "auditor result")
        require("task_fit" in judgments, "auditor result", "missing per-result task fit")
        record(judgments["reviewer"], {"kind", "model"}, "auditor result.reviewer")
        require(judgments["reviewer"]["kind"] in {"host_model", "human"},
                "auditor result.reviewer", "live gate requires a fresh reviewer")
        report = build_report(prepared, judgments)
        fit_by_source = {entry["source_id"]: entry for entry in report["task_fit"]}
        require(not request["sources"] or report["scope"]["semantic_review_status"] == "complete",
                "auditor result", "incomplete claim review")
        findings = {finding["claim_id"]: finding for finding in report["findings"]}
        for source in request["sources"]:
            source_id = source["id"]
            related = [claim for claim in request["claims"]
                       if claim["anchor"]["target"] == "source_declared"
                       and claim["anchor"]["source_id"] == source_id
                       and source_id in claim["source_ids"]]
            require(any(findings[claim["id"]]["verdict"] not in {"not_reviewed", "out_of_scope"}
                        for claim in related), source_id, "result was not substantively reviewed")
        passed = 0
        for source in request["sources"]:
            related_findings = [finding for finding in report["findings"]
                                if source["id"] in finding["claim"]["source_ids"]]
            if (fit_by_source[source["id"]]["verdict"] == "matches" and related_findings
                    and all(finding["verdict"] == "supported" for finding in related_findings)):
                passed += 1
        total = len(request["sources"])
        status_line = (f"搜索结果审查通过 {passed}/{total} 条" if total
                       else "搜索结果审查：无结果（0/0）")
        return {"status": "reviewed" if request["sources"] else "no_results",
                "sources": copy.deepcopy(request["sources"]), "report": report,
                "review_progress": {"passed": passed, "total": total},
                "status_line": status_line}
