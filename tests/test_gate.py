import copy
import unittest

from fixtures import request
from reviewer_core.gate import SearchAuditGate


def search_request(question="Can Alpha run locally?", query="Alpha local deployment"):
    data = request(answer="Alpha docs", text="Alpha docs")
    data.update(mode="results", answer=None, evidence_mode="host_web", question=question)
    source = data["sources"][0]
    source.update(provenance="host_observation", retrieved_at="2026-09-17T00:00:00+00:00",
                  observation_ref="search-tool-call-1")
    data["claims"][0].update(text="Alpha docs", category="identity", anchor={
        "target": "source_declared", "source_id": "s1", "field": "title", "start": 0, "end": 10})
    data["network_actions"] = [{"id": "a1", "kind": "search", "target": query,
                                "status": "success", "observed_at": "2026-09-17T00:00:00+00:00",
                                "source_ids": ["s1"]}]
    return data


def audit(prepared):
    source = prepared["request"]["sources"][0]
    return {"schema_version": 1, "bundle_id": prepared["bundle_id"],
            "reviewer": {"kind": "host_model", "model": "test-model"},
            "findings": [{"claim_id": "c1", "verdict": "supported", "issue_codes": [],
                          "evidence": [{"source_id": "s1", "text_sha256": source["text_sha256"],
                                        "start": 0, "end": len(source["text"]), "quote": source["text"]}],
                          "action_ids": [], "reason": "The opened source has this title.",
                          "suggested_text": None, "unresolved": []}]}


class GateTests(unittest.TestCase):
    def test_each_search_audits_before_releasing_results(self):
        events = []

        def backend(question, query):
            events.append("search")
            return search_request(question, query)

        def reviewer(prepared):
            events.append("audit")
            return audit(prepared)

        gate = SearchAuditGate(backend, reviewer)
        for _ in range(2):
            result = gate.search("Can Alpha run locally?", "Alpha local deployment")
            events.append("released")
            self.assertEqual(result["status"], "reviewed")
            self.assertEqual(result["report"]["summary"]["supported"], 1)
            self.assertEqual(len(result["sources"]), 1)
            self.assertEqual(result["review_progress"], {"passed": 1, "total": 1})
            self.assertEqual(result["status_line"], "搜索结果审查通过 1/1 条")
        self.assertEqual(events, ["search", "audit", "released"] * 2)

    def test_stale_or_missing_review_fails_closed(self):
        for reviewer in [lambda prepared: None,
                         lambda prepared: {**audit(prepared), "bundle_id": "stale"},
                         lambda prepared: {**audit(prepared), "findings": []}]:
            with self.subTest(reviewer=reviewer), self.assertRaises(ValueError):
                SearchAuditGate(search_request, reviewer).search("Can Alpha run locally?", "Alpha local deployment")

    def test_extra_unreviewed_claim_blocks_release(self):
        data = search_request()
        extra = copy.deepcopy(data["claims"][0])
        extra["id"] = "c2"
        extra["anchor"] = {"target": "source_text", "source_id": "s1", "field": "text",
                           "start": 0, "end": 10}
        data["claims"].append(extra)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            SearchAuditGate(lambda question, query: data, audit).search(
                "Can Alpha run locally?", "Alpha local deployment")

    def test_pass_count_is_per_result_and_requires_all_related_claims_supported(self):
        data = search_request()
        second = copy.deepcopy(data["sources"][0])
        second["id"] = "s2"
        data["sources"].append(second)
        claim = copy.deepcopy(data["claims"][0])
        claim["id"] = "c2"
        claim["anchor"]["source_id"] = "s2"
        claim["source_ids"] = ["s2"]
        data["claims"].append(claim)
        data["network_actions"][0]["source_ids"].append("s2")

        def mixed(prepared):
            result = audit(prepared)
            result["findings"].append({"claim_id": "c2", "verdict": "insufficient_evidence",
                                       "issue_codes": ["missing_evidence"], "evidence": [],
                                       "action_ids": [], "reason": "The captured text is inadequate.",
                                       "suggested_text": None, "unresolved": ["Need a source page."]})
            return result

        result = SearchAuditGate(lambda question, query: data, mixed).search(
            "Can Alpha run locally?", "Alpha local deployment")
        self.assertEqual(result["review_progress"], {"passed": 1, "total": 2})
        self.assertEqual(result["status_line"], "搜索结果审查通过 1/2 条")

    def test_one_unresolved_claim_keeps_its_result_out_of_pass_count(self):
        data = search_request()
        extra = copy.deepcopy(data["claims"][0])
        extra["id"] = "c2"
        extra["anchor"] = {"target": "source_text", "source_id": "s1", "field": "text",
                           "start": 0, "end": 10}
        data["claims"].append(extra)

        def mixed(prepared):
            result = audit(prepared)
            result["findings"].append({"claim_id": "c2", "verdict": "insufficient_evidence",
                                       "issue_codes": ["missing_evidence"], "evidence": [],
                                       "action_ids": [], "reason": "The text does not establish this claim.",
                                       "suggested_text": None, "unresolved": ["Need more context."]})
            return result

        result = SearchAuditGate(lambda question, query: data, mixed).search(
            "Can Alpha run locally?", "Alpha local deployment")
        self.assertEqual(result["review_progress"], {"passed": 0, "total": 1})
        self.assertEqual(result["status_line"], "搜索结果审查通过 0/1 条")

    def test_every_returned_source_needs_a_review_claim(self):
        data = search_request()
        second = copy.deepcopy(data["sources"][0])
        second["id"] = "s2"
        data["sources"].append(second)
        data["network_actions"][0]["source_ids"].append("s2")
        calls = []
        with self.assertRaisesRegex(ValueError, "s2"):
            SearchAuditGate(lambda question, query: data, lambda prepared: calls.append(prepared)).search(
                "Can Alpha run locally?", "Alpha local deployment")
        self.assertEqual(calls, [])

    def test_saved_demo_cannot_pass_live_gate(self):
        def demo(prepared):
            result = audit(prepared)
            result["reviewer"]["kind"] = "saved_demo"
            return result

        with self.assertRaisesRegex(ValueError, "reviewer"):
            SearchAuditGate(search_request, demo).search("Can Alpha run locally?", "Alpha local deployment")

    def test_live_gate_rejects_unobserved_source(self):
        data = search_request()
        data["sources"][0]["provenance"] = "supplied"
        with self.assertRaisesRegex(ValueError, "s1"):
            SearchAuditGate(lambda question, query: data, audit).search(
                "Can Alpha run locally?", "Alpha local deployment")

    def test_out_of_scope_does_not_count_as_result_review(self):
        def skip(prepared):
            result = audit(prepared)
            finding = result["findings"][0]
            finding.update(verdict="out_of_scope", evidence=[],
                           reason="Skipped this result", issue_codes=[])
            return result

        with self.assertRaisesRegex(ValueError, "s1"):
            SearchAuditGate(search_request, skip).search("Can Alpha run locally?", "Alpha local deployment")

    def test_empty_search_still_invokes_auditor(self):
        data = search_request()
        data["sources"] = []
        data["claims"] = []
        data["network_actions"][0]["source_ids"] = []
        calls = []

        def empty_audit(prepared):
            calls.append(prepared["bundle_id"])
            return {"schema_version": 1, "bundle_id": prepared["bundle_id"],
                    "reviewer": {"kind": "host_model", "model": "test-model"}, "findings": []}

        result = SearchAuditGate(lambda question, query: data, empty_audit).search(
            "Can Alpha run locally?", "Alpha local deployment")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["status"], "no_results")
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["review_progress"], {"passed": 0, "total": 0})
        self.assertEqual(result["status_line"], "搜索结果审查：无结果（0/0）")


if __name__ == "__main__":
    unittest.main()
