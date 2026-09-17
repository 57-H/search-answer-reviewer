import copy
import unittest
from fixtures import request, judgment
from reviewer_core.checks import prepare, validate_judgments


class CheckTests(unittest.TestCase):
    def test_readable_page_does_not_generate_semantic_verdict(self):
        p = prepare(request())
        self.assertNotIn("verdict", str(p["mechanical_checks"]))
        self.assertEqual(validate_judgments(p, {"schema_version": 1, "bundle_id": p["bundle_id"],
                         "reviewer": {"kind": "host_model", "model": None}, "findings": []})[0]["verdict"], "not_reviewed")

    def test_missing_page_or_quote_is_not_called_fabricated(self):
        for access in ["not_found", "restricted", "timeout", "not_read"]:
            r = request()
            r["sources"][0].update(text="", access=access, coverage="unknown")
            checks = prepare(r)["mechanical_checks"]
            self.assertTrue(checks)
            self.assertNotIn("fabricated", str(checks))
        r = request("Imaginary quotation", "Some other excerpt")
        r["claims"][0]["category"] = "quotation"
        r["sources"][0]["coverage"] = "partial"
        self.assertIn("quote_not_observed", [c["code"] for c in prepare(r)["mechanical_checks"]])

    def test_rejects_stale_tampered_and_unsupported_judgments(self):
        p = prepare(request())
        for change in [lambda j: j.update(bundle_id="old"),
                       lambda j: j["findings"][0].update(evidence=[]),
                       lambda j: j["findings"][0].update(claim_id="missing"),
                       lambda j: j["findings"][0].update(verdict="conflicted"),
                       lambda j: j["findings"][0]["evidence"][0].update(quote="Invented"),
                       lambda j: j["findings"].append(copy.deepcopy(j["findings"][0])),
                       lambda j: j["findings"][0].update(action_ids=["absent"])]:
            j = judgment(p)
            change(j)
            with self.subTest(j=j), self.assertRaises(ValueError):
                validate_judgments(p, j)
        j = judgment(p)
        p["request"]["answer"] = "Changed"
        with self.assertRaises(ValueError):
            validate_judgments(p, j)

    def test_snippets_cannot_prove_substantive_claims(self):
        for kind in ["snippet", "metadata_record"]:
            r = request()
            r["sources"][0]["kind"] = kind
            p = prepare(r)
            with self.assertRaises(ValueError):
                validate_judgments(p, judgment(p))

    def test_unverifiable_requires_a_material_limitation(self):
        r = request()
        r["sources"][0].update(provenance="host_observation", observation_ref="tool-1", retrieved_at=r["reference_time"])
        p = prepare(r)
        j = judgment(p, "unverifiable")
        j["findings"][0].update(evidence=[], unresolved=["No accessible evidence"])
        with self.assertRaises(ValueError):
            validate_judgments(p, j)
        r["sources"][0].update(access="restricted", text="")
        p = prepare(r)
        j["bundle_id"] = p["bundle_id"]
        self.assertEqual(validate_judgments(p, j)[0]["verdict"], "unverifiable")

    def test_insufficient_evidence_needs_explicit_gap(self):
        p = prepare(request("Alpha works offline."))
        j = judgment(p, "insufficient_evidence")
        with self.assertRaises(ValueError):
            validate_judgments(p, j)
        j["findings"][0].update(unresolved=["External service dependencies were not described."], issue_codes=["overclaim"])
        self.assertEqual(validate_judgments(p, j)[0]["verdict"], "insufficient_evidence")

    def test_budget_overrun_is_observed_not_hidden(self):
        r = request()
        r["network_actions"] = [{"id": f"a{i}", "kind": "read", "target": "https://example.org/docs",
                                 "status": "failure", "observed_at": r["reference_time"], "source_ids": ["s1"]} for i in range(5)]
        codes = {c["code"] for c in prepare(r)["mechanical_checks"]}
        self.assertIn("budget_exceeded", codes)
        self.assertIn("repeated_failure", codes)


if __name__ == "__main__":
    unittest.main()
