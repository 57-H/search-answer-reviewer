#!/usr/bin/env python3
"""Fail when a Markdown file links to a missing local file."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from urllib.parse import unquote

LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SKIP_PARTS = {".git", "work", "__pycache__", ".venv"}


def missing_links(root: Path) -> list[str]:
    missing = []
    for document in sorted(root.rglob("*.md")):
        if SKIP_PARTS.intersection(document.relative_to(root).parts):
            continue
        content = document.read_text(encoding="utf-8")
        for raw in LINK.findall(content):
            target = raw.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = unquote(target.split("#", 1)[0])
            if target and not (document.parent / target).resolve().exists():
                missing.append(f"{document.relative_to(root)} -> {target}")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    missing = missing_links(root)
    if missing:
        print("Missing local documentation links:", file=sys.stderr)
        for item in missing:
            print("- " + item, file=sys.stderr)
        return 1
    print("documentation links passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
