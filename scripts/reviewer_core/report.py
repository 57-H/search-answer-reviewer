"""One JSON report drives a readable, escaped Markdown view."""
from __future__ import annotations

from collections import Counter
import copy
import html
import re
from .checks import unreviewed, validate_judgments, validate_task_fit, verify_prepared
from .contracts import VERDICTS

LABELS = {"supported": "有证据支持", "contradicted": "存在矛盾", "insufficient_evidence": "证据不足",
          "unverifiable": "无法核实", "conflicted": "证据冲突", "out_of_scope": "范围外", "not_reviewed": "未审查"}
FIT_LABELS = {"matches": "匹配", "partial": "部分匹配", "fails": "不匹配", "unknown": "无法判断"}


def build_report(prepared: dict[str, object], judgments: dict[str, object] | None) -> dict[str, object]:
    verify_prepared(prepared)
    request = prepared["request"]
    findings = validate_judgments(prepared, judgments) if judgments is not None else [unreviewed(c["id"]) for c in request["claims"]]
    task_fit = validate_task_fit(prepared, judgments) if judgments is not None else []
    counts = Counter(f["verdict"] for f in findings)
    reviewed = len(findings) - counts["not_reviewed"]
    status = "not_performed" if not reviewed else ("partial" if counts["not_reviewed"] else "complete")
    claims = {c["id"]: c for c in request["claims"]}
    for finding in findings:
        c = claims[finding["claim_id"]]
        finding["claim"] = copy.deepcopy(c)
    return {"schema_version": 1, "bundle_id": prepared["bundle_id"],
            "scope": {"mode": request["mode"], "evidence_mode": request["evidence_mode"],
                      "reference_time": request["reference_time"], "excluded": copy.deepcopy(request["excluded"]),
                      "semantic_review_status": status,
                      "reviewer": copy.deepcopy(judgments["reviewer"]) if judgments is not None else None,
                      "recorded_network_actions": len(request["network_actions"]),
                      "within_default_action_budget": len(request["network_actions"]) <= 4,
                      "enforcement": "host_workflow_and_recorded_actions_only"},
            "question": request["question"], "original_answer": request["answer"],
            "sources": copy.deepcopy(request["sources"]), "network_actions": copy.deepcopy(request["network_actions"]),
            "mechanical_checks": copy.deepcopy(prepared["mechanical_checks"]), "findings": findings,
            "task_fit": task_fit,
            "summary": {"extracted_claims": len(findings), "reviewed": reviewed,
                        **{v: counts[v] for v in sorted(VERDICTS)}}}


def escape(value: object) -> str:
    value = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_\[\]()#|>])", r"\\\1", value).replace("\n", "<br>")


def render_markdown(report: dict[str, object]) -> str:
    scope, summary = report["scope"], report["summary"]
    heading = "搜索答案证据审查"
    if scope["semantic_review_status"] == "not_performed":
        heading += " — 尚未完成语义审查"
    reviewer = scope["reviewer"]
    reviewer_label = f"`{reviewer['kind']}` / {escape(reviewer['model'] or '未记录模型标识')}" if reviewer else "未执行"
    lines = [f"# {heading}", "", f"Bundle: `{report['bundle_id']}`", "",
             f"模式：{escape(scope['mode'])} / {escape(scope['evidence_mode'])}；时间基准：{escape(scope['reference_time'])}。",
             f"语义审查状态：{escape(scope['semantic_review_status'])}；审核者：{reviewer_label}。",
             f"已提取 {summary['extracted_claims']} 条，已审查 {summary['reviewed']} 条；这不代表覆盖全文全部事实。",
             "", "结论仅针对已取得材料；来源可访问、原文存在及现实事实成立是不同问题。哈希验证内容一致性，不认证来源身份。", "",
             "| 原断言 | 结论 | 问题类型 |", "|---|---|---|"]
    for f in report["findings"]:
        lines.append(f"| {escape(f['claim']['text'])} | {LABELS[f['verdict']]} | {escape(', '.join(f['issue_codes']) or '—')} |")
    if report["task_fit"]:
        lines += ["", "## 搜索结果与需求的匹配", "", "| 来源 | 匹配程度 | 已满足的需求 | 未满足或未核实的需求 | 原因 |",
                  "|---|---|---|---|---|"]
        for fit in report["task_fit"]:
            lines.append(f"| {escape(fit['source_id'])} | {FIT_LABELS[fit['verdict']]} | "
                         f"{escape(', '.join(fit['matched_requirements']) or '—')} | "
                         f"{escape(', '.join(fit['unmet_requirements']) or '—')} | {escape(fit['reason'])} |")
    for f in report["findings"]:
        lines += ["", f"## {escape(f['claim_id'])} · {LABELS[f['verdict']]}", "", escape(f["reason"])]
        for e in f["evidence"]:
            lines += ["", f"证据 {escape(e['source_id'])}，字符 [{e['start']}, {e['end']})：", "", "> " + escape(e["quote"])]
        if f["action_ids"]:
            lines += ["", "访问记录：" + escape(", ".join(f["action_ids"]))]
        if f["suggested_text"]:
            lines += ["", "局部修改建议：" + escape(f["suggested_text"])]
        for gap in f["unresolved"]:
            lines += ["", "未解决：" + escape(gap)]
    lines += ["", "## 来源与覆盖范围", ""]
    for s in report["sources"]:
        lines += [f"- {escape(s['id'])}：{escape(s['resolved_url'] or s['requested_url'] or '未提供 URL')}；"
                  f"{escape(s['kind'])} / {escape(s['provenance'])} / {escape(s['access'])} / {escape(s['coverage'])}。",
                  f"  抓取时间：{escape(s['retrieved_at'] or '未记录')}；正文 SHA-256：`{s['text_sha256']}`。"]
    lines += ["", "## 机械观察与未覆盖项", ""]
    for c in report["mechanical_checks"]:
        lines.append(f"- {escape(c['claim_id'] or c['source_id'] or '任务')} · {escape(c['code'])}：{escape(c['detail'])}")
    for excluded in scope["excluded"]:
        lines.append(f"- 排除：{escape(excluded['text'])}；{escape(excluded['reason'])}")
    lines += ["", f"记录的联网动作：{scope['recorded_network_actions']} / 默认 4；仅统计已记录动作，不拦截宿主调用。", ""]
    return "\n".join(lines)
