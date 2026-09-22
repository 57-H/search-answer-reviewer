from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reviewer_core.ordinary import summarize_batch_review


def review(result_id="r1", *, used_in_answer=False, used_claim_ids=None, fact_reviews=None):
    return {
        "result_id": result_id,
        "task_fit": {"verdict": "matches", "reason": "Directly answers the request."},
        "source_identity": {"verdict": "verified", "reason": "Publisher and title were checked."},
        "used_in_answer": used_in_answer,
        "used_claim_ids": [] if used_claim_ids is None else used_claim_ids,
        "fact_reviews": [] if fact_reviews is None else fact_reviews,
    }


def batch(result_ids=None, reviews=None):
    return {
        "schema_version": 1,
        "batch_id": "batch-1",
        "result_ids": ["r1"] if result_ids is None else result_ids,
        "reviews": [review()] if reviews is None else reviews,
    }


class OrdinaryReviewTests(unittest.TestCase):
    def test_complete_review_produces_status_from_record(self):
        result = summarize_batch_review(batch())
        self.assertEqual(result["review_progress"], {"reviewed": 1, "total": 1})
        self.assertEqual(result["status_line"], "已审查 1/1")
        self.assertEqual(result["unreviewed_result_ids"], [])

    def test_missing_review_is_visible_instead_of_inventing_coverage(self):
        result = summarize_batch_review(batch(result_ids=["r1", "r2"], reviews=[review("r1")]))
        self.assertEqual(result["review_progress"], {"reviewed": 1, "total": 2})
        self.assertEqual(result["status_line"], "已审查 1/2")
        self.assertEqual(result["unreviewed_result_ids"], ["r2"])

    def test_used_fact_must_have_a_substantive_review_or_explicit_gap(self):
        incomplete = review(used_in_answer=True, used_claim_ids=["c1"])
        with self.assertRaisesRegex(ValueError, "used result has incomplete review"):
            summarize_batch_review(batch(reviews=[incomplete]))

        incomplete["fact_reviews"] = [{
            "claim_id": "c1",
            "verdict": "insufficient_evidence",
            "evidence_refs": [],
            "unresolved": ["The plan restriction is not stated in the captured page."],
        }]
        result = summarize_batch_review(batch(reviews=[incomplete]))
        self.assertEqual(result["review_progress"], {"reviewed": 1, "total": 1})

    def test_supported_fact_requires_captured_evidence(self):
        item = review(used_in_answer=True, used_claim_ids=["c1"], fact_reviews=[{
            "claim_id": "c1", "verdict": "supported", "evidence_refs": [], "unresolved": [],
        }])
        with self.assertRaisesRegex(ValueError, "evidence"):
            summarize_batch_review(batch(reviews=[item]))

        item["fact_reviews"][0]["evidence_refs"] = ["page-1#pricing"]
        result = summarize_batch_review(batch(reviews=[item]))
        self.assertEqual(result["used_result_ids"], ["r1"])

    def test_use_flag_and_claims_must_agree(self):
        item = review(used_in_answer=False, used_claim_ids=["c1"], fact_reviews=[{
            "claim_id": "c1", "verdict": "supported",
            "evidence_refs": ["page-1#feature"], "unresolved": [],
        }])
        with self.assertRaisesRegex(ValueError, "used_in_answer"):
            summarize_batch_review(batch(reviews=[item]))

    def test_zero_result_batch_is_explicit(self):
        result = summarize_batch_review(batch(result_ids=[], reviews=[]))
        self.assertEqual(result["review_progress"], {"reviewed": 0, "total": 0})
        self.assertEqual(result["status_line"], "已审查 0/0（无搜索结果）")

    def test_duplicate_or_unknown_result_reviews_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            summarize_batch_review(batch(reviews=[review(), review()]))
        with self.assertRaisesRegex(ValueError, "unknown"):
            summarize_batch_review(batch(reviews=[review("r2")]))


if __name__ == "__main__":
    unittest.main()
