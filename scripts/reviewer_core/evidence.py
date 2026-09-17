"""Keep original evidence text and reproducible character offsets."""
from __future__ import annotations

import copy
import hashlib
import re
from .contracts import record, require, text as check_text


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def freeze_sources(sources: list[dict[str, object]]) -> list[dict[str, object]]:
    result = copy.deepcopy(sources)
    for source in result:
        source["text_sha256"] = digest(source["text"])
    return result


def _normalized(text: str) -> tuple[str, list[tuple[int, int]]]:
    chars, positions = [], []
    for m in re.finditer(r"\s+|\S", text):
        chars.append(" " if m.group().isspace() else m.group())
        positions.append((m.start(), m.end()))
    return "".join(chars), positions


def locate_quote(text: str, quote: str) -> list[dict[str, object]]:
    if not quote.strip():
        return []
    def find_all(haystack, needle):
        start = 0
        while True:
            pos = haystack.find(needle, start)
            if pos < 0:
                return
            yield pos
            start = pos + 1
    exact = [{"start": i, "end": i + len(quote), "quote": text[i:i + len(quote)], "match_kind": "exact"}
             for i in find_all(text, quote)]
    if exact:
        return exact
    normalized, positions = _normalized(text)
    needle, _ = _normalized(quote)
    result = []
    for i in find_all(normalized, needle):
        start, end = positions[i][0], positions[i + len(needle) - 1][1]
        result.append({"start": start, "end": end, "quote": text[start:end], "match_kind": "whitespace_normalized"})
    return result


def validate_evidence(ref: dict[str, object], sources: list[dict[str, object]]) -> None:
    record(ref, {"source_id", "text_sha256", "start", "end", "quote"}, "evidence")
    source = next((s for s in sources if s["id"] == ref["source_id"]), None)
    require(source is not None, "evidence.source_id", "unknown source")
    require(ref["text_sha256"] == source["text_sha256"] == digest(source["text"]), "evidence.text_sha256", "stale evidence hash")
    start, end = ref["start"], ref["end"]
    require(type(start) is int and type(end) is int, "evidence", "integer offsets required")
    require(0 <= start < end <= len(source["text"]), "evidence", "offsets out of range")
    check_text(ref["quote"], "evidence.quote")
    require(source["text"][start:end] == ref["quote"], "evidence.quote", "not the original text")
