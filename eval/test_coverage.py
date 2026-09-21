import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coverage import score_traces


def review_record(batch_id="b1", result_id="r1"):
    return {
        "schema_version": 1,
        "batch_id": batch_id,
        "result_ids": [result_id],
        "reviews": [{
            "result_id": result_id,
            "task_fit": {"verdict": "matches", "reason": "Direct answer."},
            "source_identity": {"verdict": "verified", "reason": "Identity checked."},
            "used_claim_ids": ["c1"],
            "fact_reviews": [{"claim_id": "c1", "verdict": "supported", "unresolved": []}],
        }],
    }


def run(events, *, run_id="run-1", status="completed"):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "case_id": "case-1",
        "method": "full_skill",
        "status": status,
        "platform": "Codex",
        "codex_version": "test-version",
        "model": "test-model",
        "settings": {},
        "skill_revision": "abc123",
        "task_category": "factual_lookup",
        "events": events,
        "usage": None,
        "elapsed_seconds": None,
    }


class CoverageTests(unittest.TestCase):
    def test_review_before_use_counts_as_covered(self):
        metrics = score_traces([run([
            {"type": "skill_activated"},
            {"type": "search_results", "batch_id": "b1", "result_ids": ["r1"]},
            {"type": "review_recorded", "batch_id": "b1", "record": review_record()},
            {"type": "result_used", "batch_id": "b1", "result_id": "r1"},
            {"type": "answer_delivered"},
        ])])
        self.assertEqual(metrics["used_batches"], 1)
        self.assertEqual(metrics["reviewed_before_use_batches"], 1)
        self.assertEqual(metrics["missed_review_batches"], 0)
        self.assertEqual(metrics["per_batch_review_coverage"], 1.0)
        self.assertEqual(metrics["skill_activation_rate"], 1.0)

    def test_review_after_first_use_is_a_missed_review(self):
        metrics = score_traces([run([
            {"type": "search_results", "batch_id": "b1", "result_ids": ["r1"]},
            {"type": "result_used", "batch_id": "b1", "result_id": "r1"},
            {"type": "review_recorded", "batch_id": "b1", "record": review_record()},
        ])])
        self.assertEqual(metrics["reviewed_before_use_batches"], 0)
        self.assertEqual(metrics["missed_review_batches"], 1)
        self.assertEqual(metrics["per_batch_review_coverage"], 0.0)
        self.assertEqual(metrics["failure_categories"]["skill_not_activated"], 1)

    def test_incomplete_record_before_use_is_a_missed_review(self):
        record = review_record()
        record["reviews"][0]["fact_reviews"] = []
        metrics = score_traces([run([
            {"type": "skill_activated"},
            {"type": "search_results", "batch_id": "b1", "result_ids": ["r1"]},
            {"type": "review_recorded", "batch_id": "b1", "record": record},
            {"type": "result_used", "batch_id": "b1", "result_id": "r1"},
        ])])
        self.assertEqual(metrics["missed_review_batches"], 1)
        self.assertEqual(metrics["failure_categories"]["incomplete_review_record"], 1)

    def test_failed_and_untriggered_runs_are_retained(self):
        failed = run([], run_id="failed", status="runtime_error")
        untriggered = run([
            {"type": "search_results", "batch_id": "b1", "result_ids": ["r1"]},
            {"type": "result_used", "batch_id": "b1", "result_id": "r1"},
        ], run_id="untriggered")
        metrics = score_traces([failed, untriggered])
        self.assertEqual(metrics["runs"], 2)
        self.assertEqual(metrics["failed_runs"], 1)
        self.assertEqual(metrics["skill_activation_rate"], 0.0)
        self.assertEqual(metrics["missed_review_batches"], 1)

    def test_non_search_controls_measure_false_activation_separately(self):
        control = run([], run_id="control")
        control["task_category"] = "non_search_control"
        correct = score_traces([control])
        self.assertIsNone(correct["skill_activation_rate"])
        self.assertEqual(correct["negative_control_false_activation_rate"], 0.0)

        control["events"] = [{"type": "skill_activated"}]
        incorrect = score_traces([control])
        self.assertEqual(incorrect["negative_control_false_activation_rate"], 1.0)
        self.assertEqual(incorrect["failure_categories"]["skill_not_activated"], 0)

    def test_zero_result_batches_are_reported_but_not_coverage_denominator(self):
        metrics = score_traces([run([
            {"type": "skill_activated"},
            {"type": "search_results", "batch_id": "b0", "result_ids": []},
            {"type": "review_recorded", "batch_id": "b0", "record": review_record("b0", "unused") | {"result_ids": [], "reviews": []}},
        ])])
        self.assertEqual(metrics["observed_batches"], 1)
        self.assertEqual(metrics["zero_result_batches"], 1)
        self.assertEqual(metrics["used_batches"], 0)
        self.assertIsNone(metrics["per_batch_review_coverage"])

    def test_duplicate_run_or_batch_is_rejected(self):
        one = run([])
        with self.assertRaisesRegex(ValueError, "duplicate run"):
            score_traces([one, copy.deepcopy(one)])
        with self.assertRaisesRegex(ValueError, "duplicate batch"):
            score_traces([run([
                {"type": "search_results", "batch_id": "b1", "result_ids": []},
                {"type": "search_results", "batch_id": "b1", "result_ids": []},
            ])])

    def test_frozen_manifest_exposes_missing_runs(self):
        manifest = [
            {"run_id": "run-1", "case_id": "case-1", "method": "full_skill", "task_category": "factual_lookup"},
            {"run_id": "run-2", "case_id": "case-2", "method": "full_skill", "task_category": "comparison"},
        ]
        metrics = score_traces([run([])], manifest=manifest)
        self.assertEqual(metrics["scheduled_runs"], 2)
        self.assertEqual(metrics["missing_run_ids"], ["run-2"])

        unknown = run([], run_id="outside")
        with self.assertRaisesRegex(ValueError, "manifest"):
            score_traces([unknown], manifest=manifest)


if __name__ == "__main__":
    unittest.main()
