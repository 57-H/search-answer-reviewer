#!/usr/bin/env python3
"""Batch evidence preparation and review reporting; Python 3.10+, no network."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from reviewer_core.checks import prepare, verify_prepared
from reviewer_core.contracts import load_json, require, save_json, save_text
from reviewer_core.evidence import locate_quote
from reviewer_core.ordinary import summarize_batch_review
from reviewer_core.report import build_report, render_markdown


def different_outputs(outputs: list[Path], inputs: list[Path]) -> None:
    for output in outputs:
        require(output.resolve() not in {p.resolve() for p in inputs}, "output", "would overwrite an input")


def write_report(prepared, judgments, directory, inputs):
    report = build_report(prepared, judgments)
    markdown = render_markdown(report)
    paths = [Path(directory) / "review.json", Path(directory) / "review.md"]
    different_outputs(paths, inputs)
    save_json(str(paths[0]), report)
    save_text(str(paths[1]), markdown)
    print(json.dumps({"report": str(paths[0]), "markdown": str(paths[1]), "summary": report["summary"],
                      "semantic_review_status": report["scope"]["semantic_review_status"]}, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("prepare", help="Validate and freeze request; no semantic review")
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p = subs.add_parser("finalize", help="Validate host judgments and render report")
    p.add_argument("--prepared", required=True)
    p.add_argument("--judgments")
    p.add_argument("--out-dir", required=True)
    p = subs.add_parser("replay", help="Replay saved example judgments, no fresh model call")
    p.add_argument("--example", required=True)
    p.add_argument("--out-dir", required=True)
    p = subs.add_parser("locate", help="Find evidence spans; location is not semantic support")
    p.add_argument("--prepared", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--quote", required=True)
    p = subs.add_parser("ordinary-status", help="Validate an ordinary-mode batch review and derive 已审查 x/y")
    p.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            different_outputs([Path(args.out)], [Path(args.input)])
            p = prepare(load_json(args.input))
            save_json(args.out, p)
            print(json.dumps({"bundle_id": p["bundle_id"], "claims": len(p["request"]["claims"]),
                              "mechanical_checks": p["mechanical_checks"]}, ensure_ascii=False))
        elif args.command == "finalize":
            inputs = [Path(args.prepared)] + ([Path(args.judgments)] if args.judgments else [])
            write_report(load_json(args.prepared), load_json(args.judgments) if args.judgments else None, args.out_dir, inputs)
        elif args.command == "replay":
            example = Path(args.example)
            p = prepare(load_json(str(example / "request.json")))
            j = load_json(str(example / "judgments.json"))
            j["reviewer"] = {"kind": "saved_demo", "model": j.get("reviewer", {}).get("model")}
            write_report(p, j, args.out_dir, [example / "request.json", example / "judgments.json"])
            print("回放 saved_demo：使用保存的示例判断，未调用模型或网络。")
        elif args.command == "locate":
            p = verify_prepared(load_json(args.prepared))
            s = next((s for s in p["request"]["sources"] if s["id"] == args.source), None)
            require(s is not None, "source", "unknown source")
            refs = [{"source_id": s["id"], "text_sha256": s["text_sha256"], **m} for m in locate_quote(s["text"], args.quote)]
            print(json.dumps({"matches": refs, "coverage": s["coverage"], "access": s["access"]}, ensure_ascii=False, indent=2))
        elif args.command == "ordinary-status":
            print(json.dumps(summarize_batch_review(load_json(args.input)), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(f"Invalid review input: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"File operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
