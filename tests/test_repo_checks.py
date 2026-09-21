from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC_CHECK = ROOT / "scripts" / "check_docs.py"
INSTALL_CHECK = ROOT / "scripts" / "check_install.py"


class RepositoryCheckTests(unittest.TestCase):
    def test_documentation_check_reports_missing_relative_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("[missing](docs/nope.md)\n", encoding="utf-8")
            done = subprocess.run([sys.executable, str(DOC_CHECK), "--root", str(root)],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 1)
            self.assertIn("docs/nope.md", done.stderr)

    def test_current_documentation_links_resolve(self):
        done = subprocess.run([sys.executable, str(DOC_CHECK), "--root", str(ROOT)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_clean_install_smoke_uses_only_copied_public_files(self):
        done = subprocess.run([sys.executable, str(INSTALL_CHECK), "--root", str(ROOT)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("clean install smoke passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
