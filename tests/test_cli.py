from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from fixtures import request, judgment
from reviewer_core.checks import prepare
from reviewer_core.contracts import save_json, load_json

CLI = Path(__file__).resolve().parents[1] / "scripts" / "review.py"


class CLITests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], capture_output=True, text=True)

    def test_cli_only_exposes_review_commands(self):
        help_result = self.invoke("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("{prepare,finalize,replay,locate}", help_result.stdout)

    def test_prepare_finalize_and_refuse_stale_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            save_json(str(work / "input.json"), request())
            done = self.invoke("prepare", "--input", work / "input.json", "--out", work / "prepared.json")
            self.assertEqual(done.returncode, 0, done.stderr)
            p = load_json(str(work / "prepared.json"))
            j = judgment(p)
            save_json(str(work / "judgments.json"), j)
            done = self.invoke("finalize", "--prepared", work / "prepared.json", "--judgments", work / "judgments.json", "--out-dir", work)
            self.assertEqual(done.returncode, 0, done.stderr)
            before = (work / "review.json").read_bytes()
            self.assertEqual(load_json(str(work / "review.json"))["summary"]["supported"], 1)
            j["bundle_id"] = "stale"
            save_json(str(work / "judgments.json"), j)
            done = self.invoke("finalize", "--prepared", work / "prepared.json", "--judgments", work / "judgments.json", "--out-dir", work)
            self.assertEqual(done.returncode, 2)
            self.assertEqual((work / "review.json").read_bytes(), before)

    def test_prepare_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            save_json(str(path), request())
            before = path.read_bytes()
            done = self.invoke("prepare", "--input", path, "--out", path)
            self.assertEqual(done.returncode, 2)
            self.assertIn("overwrite", done.stderr)
            self.assertEqual(path.read_bytes(), before)

    def test_replay_labels_saved_demo_and_is_not_fresh_model_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            example = root / "example"
            save_json(str(example / "request.json"), request())
            j = judgment(prepare(request()))
            j["reviewer"] = {"kind": "host_model", "model": "historical-test"}
            save_json(str(example / "judgments.json"), j)
            done = self.invoke("replay", "--example", example, "--out-dir", root / "out")
            self.assertEqual(done.returncode, 0, done.stderr)
            report = load_json(str(root / "out" / "review.json"))
            self.assertEqual(report["scope"]["reviewer"]["kind"], "saved_demo")
            self.assertIn("回放", done.stdout)

    def test_locate_returns_evidence_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prepared.json"
            save_json(str(path), prepare(request()))
            done = self.invoke("locate", "--prepared", path, "--source", "s1", "--quote", "local deployment")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('"start": 15', done.stdout)


if __name__ == "__main__":
    unittest.main()
