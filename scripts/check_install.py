#!/usr/bin/env python3
"""Copy the repository like a fresh install and run its public offline commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SKIP = shutil.ignore_patterns(".git", "work", "__pycache__", "*.pyc", ".venv", ".env", ".env.*", ".DS_Store")


def run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout or "command failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    source = Path(args.root).resolve()
    for required in ("SKILL.md", "README.md", "scripts/review.py", "references/schema.md",
                     "examples/overclaim/request.json", "examples/overclaim/judgments.json"):
        if not (source / required).is_file():
            print(f"clean install missing required file: {required}", file=sys.stderr)
            return 1
    try:
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "search-answer-reviewer"
            shutil.copytree(source, installed, ignore=SKIP)
            run([sys.executable, "scripts/review.py", "replay", "--example", "examples/overclaim",
                 "--out-dir", "work/demo"], installed)
            batch = {
                "schema_version": 1,
                "batch_id": "install-smoke",
                "result_ids": [],
                "reviews": [],
            }
            batch_path = installed / "work" / "batch-review.json"
            batch_path.parent.mkdir(parents=True, exist_ok=True)
            batch_path.write_text(json.dumps(batch), encoding="utf-8")
            run([sys.executable, "scripts/review.py", "ordinary-status", "--input", str(batch_path)], installed)
            if not (installed / "work" / "demo" / "review.md").is_file():
                raise RuntimeError("replay did not create review.md")
    except (OSError, RuntimeError) as exc:
        print(f"clean install smoke failed: {exc}", file=sys.stderr)
        return 1
    print("clean install smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
