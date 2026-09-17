"""Strict, portable JSON contracts and atomic storage."""
from __future__ import annotations

import copy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

JSONRecord = dict[str, object]
VERDICTS = {"supported", "contradicted", "insufficient_evidence", "unverifiable", "conflicted", "out_of_scope", "not_reviewed"}
ISSUES = {"metadata_mismatch", "identity_mismatch", "quote_not_observed", "numeric_mismatch", "scope_mismatch", "overclaim", "unread_source", "source_unavailable", "insufficient_provenance", "conflicting_evidence", "missing_evidence"}


def require(condition: bool, path: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{path}: {message}")


def text(value: object, path: str, *, nullable: bool = False, empty: bool = False) -> None:
    if value is None and nullable:
        return
    require(isinstance(value, str), path, "expected string")
    require(empty or bool(value.strip()), path, "must not be empty")


def record(value: object, fields: set[str], path: str) -> None:
    require(isinstance(value, dict), path, "expected object")
    require(fields <= value.keys(), path, "missing fields: " + ", ".join(sorted(fields - value.keys())))


def strings(value: object, path: str) -> None:
    require(isinstance(value, list), path, "expected array")
    for i, v in enumerate(value):
        text(v, f"{path}[{i}]")


def date(value: object, path: str, nullable: bool = True) -> None:
    if value is None and nullable:
        return
    text(value, path)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{path}: expected ISO8601 date/time with timezone") from exc
    require(parsed.tzinfo is not None, path, "timezone required")


def url(value: object, path: str) -> None:
    if value is None:
        return
    text(value, path)
    try:
        parsed = urlsplit(value)
        require(parsed.scheme in {"http", "https"} and bool(parsed.hostname), path, "HTTP(S) URL required")
        require(not parsed.username and not parsed.password, path, "credential-bearing URL not allowed")
        parsed.port
        require(not any(c.isspace() for c in value), path, "URL contains whitespace")
    except ValueError as exc:
        raise ValueError(f"{path}: invalid URL ({exc})") from exc


def canonical(data: object) -> bytes:
    try:
        return json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (UnicodeError, TypeError, ValueError) as exc:
        raise ValueError("JSON: invalid Unicode or non-JSON value") from exc


def bundle_id(request: JSONRecord) -> str:
    return hashlib.sha256(canonical(request)).hexdigest()


def load_json(path: str) -> JSONRecord:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, key, "duplicate JSON key")
            result[key] = value
        return result

    data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs)
    require(isinstance(data, dict), "JSON", "top level must be object")
    canonical(data)
    return data


def save_json(path: str, data: JSONRecord) -> None:
    canonical(data)
    save_text(path, json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n")


def save_text(path: str, value: str) -> None:
    payload = value.encode("utf-8")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix="." + target.name, delete=False) as stream:
            name = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def anchor_text(request: JSONRecord, anchor: JSONRecord) -> str:
    record(anchor, {"target", "source_id", "field", "start", "end"}, "anchor")
    target = anchor["target"]
    if target == "answer":
        require(anchor["source_id"] is None and anchor["field"] is None, "anchor", "answer anchor has no source/field")
        value = request["answer"]
    else:
        require(target in {"source_declared", "source_text"}, "anchor.target", "unknown target")
        source = next((s for s in request["sources"] if s["id"] == anchor["source_id"]), None)
        require(source is not None, "anchor.source_id", "unknown source")
        field = anchor["field"]
        if target == "source_text":
            require(field == "text", "anchor.field", "expected text")
            value = source["text"]
        else:
            require(field in {"title", "publisher", "authors", "identifier"}, "anchor.field", "unknown declared field")
            value = source["declared"][field]
            if field == "authors":
                value = "\n".join(value)
    text(value, "anchor target", empty=True)
    start, end = anchor["start"], anchor["end"]
    require(type(start) is int and type(end) is int, "anchor", "integer offsets required")
    require(0 <= start < end <= len(value), "anchor", "offsets out of range")
    return value[start:end]


def validate_request(data: JSONRecord) -> JSONRecord:
    canonical(data)
    fields = {"schema_version", "mode", "evidence_mode", "reference_time", "question", "answer", "sources", "claims", "excluded", "network_actions"}
    record(data, fields, "request")
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "schema_version", "expected 1")
    require(data["mode"] in ("answer", "results"), "mode", "unknown mode")
    require(data["evidence_mode"] in ("provided", "host_web"), "evidence_mode", "unknown mode")
    date(data["reference_time"], "reference_time", False)
    text(data["question"], "question", nullable=True)
    text(data["answer"], "answer", nullable=data["mode"] == "results")
    for field in ("sources", "claims", "excluded", "network_actions"):
        require(isinstance(data[field], list), field, "expected array")
    ids = set()
    for i, s in enumerate(data["sources"]):
        p = f"sources[{i}]"
        record(s, {"id", "requested_url", "resolved_url", "kind", "provenance", "declared", "observed", "text", "access", "coverage", "retrieved_at", "published_at", "updated_at", "observation_ref"}, p)
        text(s["id"], p + ".id")
        require(s["id"] not in ids, p + ".id", "duplicate source")
        ids.add(s["id"])
        for field in ("requested_url", "resolved_url"):
            url(s[field], p + "." + field)
        require(s["kind"] in ("page", "snippet", "metadata_record"), p + ".kind", "unknown kind")
        require(s["provenance"] in ("supplied", "host_observation"), p + ".provenance", "unknown provenance")
        require(s["coverage"] in ("complete", "partial", "unknown"), p + ".coverage", "unknown coverage")
        require(s["access"] in ("readable", "not_found", "restricted", "timeout", "empty", "error_page", "not_read", "other_error"), p + ".access", "unknown access")
        text(s["text"], p + ".text", empty=s["access"] != "readable")
        text(s["observation_ref"], p + ".observation_ref", nullable=True)
        for field in ("retrieved_at", "published_at", "updated_at"):
            date(s[field], p + "." + field)
        for field in ("declared", "observed"):
            meta = s[field]
            record(meta, {"title", "publisher", "authors", "identifier"}, p + "." + field)
            for key in ("title", "publisher", "identifier"):
                text(meta[key], p + "." + field + "." + key, nullable=True)
            strings(meta["authors"], p + "." + field + ".authors")
        if data["mode"] == "results":
            require(bool(s["declared"]["title"] or s["declared"]["identifier"] or s["requested_url"]), p, "result needs title, identifier or URL")
    claim_ids = set()
    for i, c in enumerate(data["claims"]):
        p = f"claims[{i}]"
        record(c, {"id", "text", "anchor", "category", "importance", "source_ids"}, p)
        text(c["id"], p + ".id")
        require(c["id"] not in claim_ids, p + ".id", "duplicate claim")
        claim_ids.add(c["id"])
        text(c["text"], p + ".text")
        strings(c["source_ids"], p + ".source_ids")
        require(set(c["source_ids"]) <= ids, p + ".source_ids", "unknown source")
        require(c["category"] in ("existence", "identity", "quotation", "number", "scope", "ordinary_fact"), p + ".category", "unknown category")
        require(c["importance"] in ("decision", "supporting"), p + ".importance", "unknown importance")
        require(anchor_text(data, c["anchor"]) == c["text"], p + ".anchor", "text does not match original span")
    for i, excluded in enumerate(data["excluded"]):
        record(excluded, {"text", "reason"}, f"excluded[{i}]")
        text(excluded["text"], "excluded.text")
        text(excluded["reason"], "excluded.reason")
    action_ids = set()
    for i, action in enumerate(data["network_actions"]):
        p = f"network_actions[{i}]"
        record(action, {"id", "kind", "target", "status", "observed_at", "source_ids"}, p)
        text(action["id"], p + ".id")
        require(action["id"] not in action_ids, p + ".id", "duplicate action")
        action_ids.add(action["id"])
        require(action["kind"] in ("search", "read"), p + ".kind", "unknown kind")
        require(action["status"] in ("success", "failure"), p + ".status", "unknown status")
        text(action["target"], p + ".target")
        date(action["observed_at"], p + ".observed_at", False)
        strings(action["source_ids"], p + ".source_ids")
        require(set(action["source_ids"]) <= ids, p + ".source_ids", "unknown source")
    return copy.deepcopy(data)
