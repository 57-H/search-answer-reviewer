"""Synthetic fixtures; no external pages or model calls."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def request(answer="Alpha supports local deployment.", text="Alpha supports local deployment."):
    metadata = {"title": "Alpha docs", "publisher": None, "authors": [], "identifier": None}
    return {
        "schema_version": 1, "mode": "answer", "evidence_mode": "provided",
        "reference_time": "2026-09-16T00:00:00+00:00", "question": "Can Alpha run locally?",
        "answer": answer, "sources": [{
            "id": "s1", "requested_url": "https://example.org/docs",
            "resolved_url": "https://example.org/docs", "kind": "page", "provenance": "supplied",
            "declared": dict(metadata), "observed": dict(metadata), "text": text,
            "access": "readable", "coverage": "complete", "retrieved_at": None,
            "published_at": None, "updated_at": None, "observation_ref": None,
        }], "claims": [{
            "id": "c1", "text": answer,
            "anchor": {"target": "answer", "source_id": None, "field": None, "start": 0, "end": len(answer)},
            "category": "ordinary_fact", "importance": "decision", "source_ids": ["s1"],
        }], "excluded": [], "network_actions": [],
    }


def judgment(prepared, verdict="supported"):
    source = prepared["request"]["sources"][0]
    return {
        "schema_version": 1, "bundle_id": prepared["bundle_id"],
        "reviewer": {"kind": "saved_demo", "model": None},
        "findings": [{
            "claim_id": "c1", "verdict": verdict, "issue_codes": [],
            "evidence": [{"source_id": "s1", "text_sha256": source["text_sha256"],
                          "start": 0, "end": len(source["text"]), "quote": source["text"]}],
            "action_ids": [], "reason": "The supplied text explicitly states local deployment.",
            "suggested_text": None, "unresolved": [],
        }],
    }
