import copy
from pathlib import Path
import tempfile
import unittest
from fixtures import request
from reviewer_core.contracts import validate_request, bundle_id, load_json, save_json


class ContractTests(unittest.TestCase):
    def test_valid_request_is_not_mutated(self):
        r = request()
        before = copy.deepcopy(r)
        self.assertEqual(validate_request(r), before)
        self.assertEqual(r, before)

    def test_rejects_invalid_inputs(self):
        for change in [lambda r: r.update(answer=""), lambda r: r.update(schema_version=True),
                       lambda r: r.update(reference_time="yesterday"),
                       lambda r: r.update(reference_time="2026-09-16"),
                       lambda r: r["sources"].append(copy.deepcopy(r["sources"][0])),
                       lambda r: r["claims"][0].update(source_ids=["missing"]),
                       lambda r: r["claims"][0]["anchor"].update(start=True),
                       lambda r: r["sources"][0].update(coverage="full"),
                       lambda r: r["sources"][0].update(text="\ud800"),
                       lambda r: r["sources"][0].update(requested_url="javascript:alert(1)"),
                       lambda r: r["claims"][0].update(text="Invented claim"),
                       lambda r: r.update(sources=[])]:
            r = request()
            change(r)
            with self.subTest(r=r), self.assertRaises(ValueError):
                validate_request(r)

    def test_results_only_uses_declared_title(self):
        r = request()
        r.update(mode="results", answer=None)
        r["claims"][0].update(text="Alpha docs", category="identity", anchor={
            "target": "source_declared", "source_id": "s1", "field": "title", "start": 0, "end": 10})
        validate_request(r)

    def test_hash_is_order_independent_but_content_sensitive(self):
        r = request()
        self.assertEqual(bundle_id(r), bundle_id(dict(reversed(list(r.items())))))
        changed = copy.deepcopy(r)
        changed["answer"] = "Fully offline."
        self.assertNotEqual(bundle_id(r), bundle_id(changed))

    def test_json_unicode_and_failed_save_preserves_file(self):
        with tempfile.TemporaryDirectory() as work:
            path = str(Path(work) / "a.json")
            save_json(path, {"text": "证据 🧪\nsecond"})
            self.assertEqual(load_json(path), {"text": "证据 🧪\nsecond"})
            with self.assertRaises(ValueError):
                save_json(path, {"text": "\ud800"})
            self.assertEqual(load_json(path), {"text": "证据 🧪\nsecond"})

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "a.json"
            path.write_text('{"answer": "first", "answer": "second"}')
            with self.assertRaises(ValueError):
                load_json(str(path))


if __name__ == "__main__":
    unittest.main()
