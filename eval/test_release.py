import unittest

from release import assess_release


def coverage(observed=100, missed=5):
    return {
        "schema_version": 1,
        "manifest_provided": True,
        "scheduled_runs": 100,
        "runs": 100,
        "missing_run_ids": [],
        "observed_batches": observed,
        "used_batches": observed,
        "reviewed_before_use_batches": observed - missed,
        "missed_review_batches": missed,
        "per_batch_review_coverage": (observed - missed) / observed,
    }


def semantics(status="human_validated", serious=0, missing=None):
    methods = {
        name: {"missing_case_ids": []}
        for name in ("generic_prompt", "rules_only", "full_skill")
    }
    methods["full_skill"]["missing_case_ids"] = [] if missing is None else missing
    return {
        "schema_version": 1,
        "annotation_status": status,
        "serious_false_acceptances": serious,
        "methods": methods,
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

    def test_missing_semantic_case_blocks_release(self):
        checks = {"clean_install_reproduced": True, "deterministic_tests_passed": True,
                  "documentation_checks_passed": True}
        result = assess_release(coverage(), semantics(missing=["case-12"]), checks)
        self.assertFalse(result["ready"])
        self.assertIn("semantic_runs_complete",
                      [gate["name"] for gate in result["gates"] if not gate["passed"]])

    def test_missing_install_or_ci_evidence_blocks_release(self):
        result = assess_release(coverage(), semantics(), {
            "clean_install_reproduced": False,
            "deterministic_tests_passed": True,
            "documentation_checks_passed": False,
        })
        self.assertFalse(result["ready"])
        self.assertEqual([gate["name"] for gate in result["gates"] if not gate["passed"]],
                         ["clean_install", "documentation_checks"])

    def test_missing_scheduled_run_blocks_release(self):
        incomplete = coverage()
        incomplete["runs"] = 99
        incomplete["missing_run_ids"] = ["run-100"]
        result = assess_release(incomplete, semantics(), {
            "clean_install_reproduced": True,
            "deterministic_tests_passed": True,
            "documentation_checks_passed": True,
        })
        self.assertFalse(result["ready"])
        self.assertIn("scheduled_runs_complete",
                      [gate["name"] for gate in result["gates"] if not gate["passed"]])

    def test_unfrozen_coverage_run_blocks_release(self):
        unfrozen = coverage()
        unfrozen["manifest_provided"] = False
        result = assess_release(unfrozen, semantics(), {
            "clean_install_reproduced": True,
            "deterministic_tests_passed": True,
            "documentation_checks_passed": True,
        })
        self.assertFalse(result["ready"])
        self.assertIn("frozen_run_manifest",
                      [gate["name"] for gate in result["gates"] if not gate["passed"]])

    def test_schedule_count_must_match_runs_and_missing_ids(self):
        inconsistent = coverage()
        inconsistent["runs"] = 99
        with self.assertRaisesRegex(ValueError, "scheduled_runs"):
            assess_release(inconsistent, semantics(), {
                "clean_install_reproduced": True,
                "deterministic_tests_passed": True,
                "documentation_checks_passed": True,
            })

    def test_inconsistent_coverage_counts_are_rejected(self):
        inconsistent = coverage()
        inconsistent["reviewed_before_use_batches"] = 96
        with self.assertRaisesRegex(ValueError, "used_batches"):
            assess_release(inconsistent, semantics(), {
                "clean_install_reproduced": True,
                "deterministic_tests_passed": True,
                "documentation_checks_passed": True,
            })


if __name__ == "__main__":
    unittest.main()
