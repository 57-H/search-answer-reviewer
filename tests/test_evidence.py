import copy
import unittest
from fixtures import request
from reviewer_core.evidence import freeze_sources, locate_quote, validate_evidence


class EvidenceTests(unittest.TestCase):
    def test_normalization_returns_original_unicode_offsets(self):
        text = "🧪 Alpha supports\n local deployment."
        m = locate_quote(text, "supports local deployment")[0]
        self.assertEqual(text[m["start"]:m["end"]], "supports\n local deployment")
        self.assertEqual(m["quote"], "supports\n local deployment")
        self.assertEqual(m["match_kind"], "whitespace_normalized")

    def test_numbers_and_word_boundaries_are_not_deleted(self):
        for text, quote in [("Fee -10.5 USD", "Fee 10.5 USD"), ("10 00", "1000"), ("USD 10", "EUR 10")]:
            self.assertEqual(locate_quote(text, quote), [])

    def test_multiple_occurrences_are_kept(self):
        self.assertEqual([m["start"] for m in locate_quote("yes no yes", "yes")], [0, 7])
        self.assertEqual(locate_quote("any text", ""), [])

    def test_hash_does_not_upgrade_provenance_or_mutate_input(self):
        sources = request()["sources"]
        frozen = freeze_sources(sources)
        self.assertNotIn("text_sha256", sources[0])
        self.assertEqual(frozen[0]["provenance"], "supplied")
        self.assertEqual(len(frozen[0]["text_sha256"]), 64)

    def test_stale_or_invented_evidence_is_rejected(self):
        sources = freeze_sources(request()["sources"])
        ref = {"source_id": "s1", "text_sha256": sources[0]["text_sha256"],
               "start": 0, "end": 5, "quote": "Alpha"}
        validate_evidence(ref, sources)
        for key, value in [("source_id", "s2"), ("text_sha256", "0" * 64),
                           ("quote", "Bravo"), ("start", -1), ("start", True), ("end", 999)]:
            bad = copy.deepcopy(ref)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_evidence(bad, sources)
        sources[0]["text"] = "Alpha changed"
        with self.assertRaises(ValueError):
            validate_evidence(ref, sources)


if __name__ == "__main__":
    unittest.main()
