import unittest
from fixtures import request, judgment
from reviewer_core.checks import prepare
from reviewer_core.report import build_report, render_markdown


class ReportTests(unittest.TestCase):
    def test_no_review_is_explicit_not_success(self):
        p = prepare(request())
        report = build_report(p, None)
        self.assertEqual(report["scope"]["semantic_review_status"], "not_performed")
        self.assertEqual(report["summary"]["supported"], 0)
        self.assertEqual(report["summary"]["not_reviewed"], 1)
        self.assertIn("尚未完成语义审查", render_markdown(report))

    def test_empty_claim_list_never_passes(self):
        r = request()
        r["claims"] = []
        p = prepare(r)
        j = judgment(p)
        j["findings"] = []
        self.assertEqual(build_report(p, j)["scope"]["semantic_review_status"], "not_performed")

    def test_report_keeps_provenance_and_original_text(self):
        r = request()
        r["sources"][0]["coverage"] = "partial"
        p = prepare(r)
        report = build_report(p, judgment(p))
        self.assertEqual(report["sources"][0]["coverage"], "partial")
        self.assertEqual(report["scope"]["evidence_mode"], "provided")
        self.assertEqual(report["summary"]["reviewed"], 1)
        md = render_markdown(report)
        self.assertIn("supplied", md)
        self.assertIn("partial", md)
        self.assertIn("Alpha supports local deployment.", md)
        self.assertIn("saved_demo", md)

    def test_source_markup_is_escaped(self):
        p = prepare(request("<script>alert(1)</script>|x", "<script>alert(1)</script>|x"))
        md = render_markdown(build_report(p, judgment(p)))
        self.assertNotIn("<script>", md)
        self.assertIn("&lt;script&gt;", md)

    def test_missing_fetch_time_is_readable(self):
        p = prepare(request())
        md = render_markdown(build_report(p, judgment(p)))
        self.assertIn("抓取时间：未记录", md)
        self.assertNotIn("抓取时间：None", md)


if __name__ == "__main__":
    unittest.main()
