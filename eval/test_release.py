import unittest

from release import assess_release


def coverage(observed=100, missed=5):
    return {
        "schema_version": 1,
        "observed_batches": observed,
        "used_batches": observed,
        "reviewed_before_use_batches": observed - missed,
        "missed_review_batches": missed,
        "per_batch_review_coverage": (observed - missed) / observed,
    }


def semantics(status="human_validated", serious=0):
    return {
        "schema_version": 1,
        "annotation_status": status,
        "serious_false_acceptances": serious,
    }


class ReleaseTests(unittest.TestCase):
    def test_all_release_gates_must_pass(self):
        result = assess_release(coverage(), semantics(), {
            "clean_install_reproduced": True,
            "deterministic_tests_passed": True,
            "documentation_checks_passed": True,
        })
        self.assertTrue(result["ready"])
        self.assertTrue(all(gate["passed"] for gate in result["gates"]))

    def test_too_few_batches_or_six_misses_blocks_release(self):
        self.assertFalse(assess_release(coverage(99, 0), semantics(), {
            "clean_install_reproduced": True,
            "deterministic_tests_passed": True,
            "documentation_checks_passed": True,
        })["ready"])
        self.assertFalse(assess_release(coverage(100, 6), semantics(), {
            "clean_install_reproduced": True,
            "deterministic_tests_passed": True,
            "documentation_checks_passed": True,
        })["ready"])

    def test_draft_labels_or_serious_false_acceptance_blocks_release(self):
        checks = {"clean_install_reproduced": True, "deterministic_tests_passed": True,
                  "documentation_checks_passed": True}
        self.assertFalse(assess_release(coverage(), semantics("provisional_draft"), checks)["ready"])
        self.assertFalse(assess_release(coverage(), semantics(serious=1), checks)["ready"])

    def test_missing_install_or_ci_evidence_blocks_release(self):
        result = assess_release(coverage(), semantics(), {
            "clean_install_reproduced": False,
            "deterministic_tests_passed": True,
            "documentation_checks_passed": False,
        })
        self.assertFalse(result["ready"])
        self.assertEqual([gate["name"] for gate in result["gates"] if not gate["passed"]],
                         ["clean_install", "documentation_checks"])


if __name__ == "__main__":
    unittest.main()
