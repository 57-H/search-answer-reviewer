import copy
import unittest
from score import score_runs


def anchor(start=0, end=10):
    return {"target": "answer", "source_id": None, "field": None, "start": start, "end": end}


def gold(verdict="contradicted", issues=None, serious=False):
    return [{"case_id": "x", "annotation_status": "human_validated", "key_claims": [{"anchor": anchor(), "expected_verdict": verdict,
             "issue_codes": ["numeric_mismatch"] if issues is None else issues,
             "evidence": [], "rationale": "Synthetic scoring test", "serious": serious}]}]


def run(status="completed", findings=None, case_id="x"):
    return {"case_id": case_id, "method": "full_skill", "run_id": "r1", "status": status,
            "report": {"findings": [] if findings is None else findings}, "usage": None, "elapsed_seconds": None}


def finding(start=0, end=10, verdict="contradicted", issues=None):
    return {"claim": {"anchor": anchor(start, end)}, "verdict": verdict,
            "issue_codes": ["numeric_mismatch"] if issues is None else issues}


class ScoreTests(unittest.TestCase):
    def test_draft_labels_require_explicit_provisional_opt_in(self):
        draft = gold()
        draft[0]["annotation_status"] = "draft_model_authored_not_human_validated"
        with self.assertRaisesRegex(ValueError, "draft"):
            score_runs(draft, [run()])
        scored = score_runs(draft, [run()], allow_draft=True)
        self.assertEqual(scored["annotation_status"], "provisional_draft")

    def test_validated_labels_allow_standard_scoring(self):
        checked = gold()
        checked[0]["annotation_status"] = "human_validated"
        scored = score_runs(checked, [run()])
        self.assertEqual(scored["annotation_status"], "human_validated")

    def test_missing_annotation_status_is_rejected(self):
        unlabeled = gold()
        del unlabeled[0]["annotation_status"]
        with self.assertRaises(ValueError):
            score_runs(unlabeled, [run()])

    def test_duplicate_findings_cannot_double_count_true_positive(self):
        m = score_runs(gold(), [run(findings=[finding(), finding()])])["methods"]["full_skill"]
        self.assertEqual(m["true_positives"], 1)
        self.assertEqual(m["false_positives"], 0)
        self.assertEqual(m["recall"], 1.0)

    def test_failed_run_retained_in_recall_denominator(self):
        m = score_runs(gold(), [run("runtime_error")])["methods"]["full_skill"]
        self.assertEqual(m["false_negatives"], 1)
        self.assertEqual(m["recall"], 0.0)
        self.assertIsNone(m["precision"])
        self.assertEqual(m["failed_runs"], 1)
        self.assertIsNone(m["input_tokens_total"])

    def test_whole_answer_flag_cannot_match_specific_error(self):
        m = score_runs(gold(), [run(findings=[finding(0, 1000)])])["methods"]["full_skill"]
        self.assertEqual(m["true_positives"], 0)
        self.assertEqual(m["false_positives"], 1)
        self.assertEqual(m["false_negatives"], 1)

    def test_unavailable_is_not_a_contradiction(self):
        m = score_runs(gold("unverifiable", ["source_unavailable"]),
                       [run(findings=[finding(verdict="contradicted", issues=["source_unavailable"])])])["methods"]["full_skill"]
        self.assertEqual(m["true_positives"], 0)
        self.assertEqual(m["unverifiable_as_contradicted"], 1)

    def test_normal_claim_false_alarm(self):
        m = score_runs(gold("supported", []), [run(findings=[finding(verdict="insufficient_evidence")])])["methods"]["full_skill"]
        self.assertEqual(m["normal_claim_false_alarm_rate"], 1.0)
        self.assertIsNone(m["recall"])

    def test_unknown_case_and_duplicate_run_are_rejected(self):
        with self.assertRaises(ValueError):
            score_runs(gold(), [run(case_id="unknown")])
        r = run()
        with self.assertRaises(ValueError):
            score_runs(gold(), [r, copy.deepcopy(r)])

    def test_distinct_repeats_count_and_missing_cases_are_visible(self):
        g = gold()
        second = copy.deepcopy(g[0])
        second["case_id"] = "y"
        g.append(second)
        r1, r2 = run("runtime_error"), run("runtime_error")
        r2["run_id"] = "r2"
        m = score_runs(g, [r1, r2])["methods"]["full_skill"]
        self.assertEqual(m["false_negatives"], 2)
        self.assertEqual(m["missing_case_ids"], ["y"])

    def test_serious_false_acceptance_requires_human_label_and_supported_prediction(self):
        accepted = run(findings=[finding(verdict="supported", issues=[])])
        scored = score_runs(gold("insufficient_evidence", ["missing_evidence"], serious=True), [accepted])
        self.assertEqual(scored["methods"]["full_skill"]["serious_false_acceptances"], 1)
        self.assertEqual(scored["serious_false_acceptances"], 1)

    def test_human_validated_claims_must_classify_seriousness(self):
        labels = gold()
        del labels[0]["key_claims"][0]["serious"]
        with self.assertRaisesRegex(ValueError, "serious"):
            score_runs(labels, [run()])


if __name__ == "__main__":
    unittest.main()
