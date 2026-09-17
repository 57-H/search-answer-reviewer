# 数据格式（v1）

完整可运行输入见 `examples/overclaim/request.json`；匹配的保存判断见 `examples/overclaim/judgments.json`。这些是合成示例，不是实际线上核验。

## Request

| 字段 | 类型/取值 |
|---|---|
| schema_version | 整数 1 |
| mode | answer / results |
| evidence_mode | provided / host_web |
| reference_time | 带时区的 ISO8601 时间 |
| question | 非空字符串或 null |
| answer | answer 模式须非空；results 模式可 null |
| sources | Source 数组 |
| claims | Claim 数组；空数组不会被算作审核通过 |
| excluded | `{text, reason}` 数组 |
| network_actions | Action 数组，失败也保留 |

## Source

必需字段：id、requested_url、resolved_url、kind、provenance、declared、observed、text、access、coverage、retrieved_at、published_at、updated_at、observation_ref。

- kind：page / snippet / metadata_record。
- provenance：supplied / host_observation；不得把用户提供的文本改称在线观测。
- declared/observed 均为 `{title, publisher, authors, identifier}`；authors 是字符串数组，其余字段未知时为 null。
- access：readable / not_found / restricted / timeout / empty / error_page / not_read / other_error。
- coverage：complete / partial / unknown；complete 只表示本页面所选提取范围，不表示全网站。
- URL 可以 null；非空时只接受无凭证的 HTTP(S)。CLI 不请求这些 URL。
- 三个日期均可 null；不以抓取日期填充发布日期。
- observation_ref 是宿主工具观测引用或日志定位，可 null；它不是密码学证明。
- text 保留取得的原文，失败无正文用空字符串；snippet 即使有正文也不能作为实质结论的最终证据。
- prepare 自动计算 text_sha256，模型不要猜测它。

## Claim 与锚点

必需字段：id、text、anchor、category、importance、source_ids。

category：existence / identity / quotation / number / scope / ordinary_fact。
importance：decision / supporting。source_ids 是关联来源 ID 数组。

anchor 为 `{target, source_id, field, start, end}`；start/end 是 Python Unicode 字符索引，左闭右开，不能使用 UTF-8 字节位置。

- target=answer：source_id/field 为 null，答案对应切片必须等于 claim.text。
- target=source_declared：field 取 title/publisher/authors/identifier；authors 先以换行连接。
- target=source_text：field=text；用于审查搜索结果摘要。

声明与证据必须分开：source_text 锚定摘要时，该摘要不能再拿来证明自身。

## Action

`{id, kind, target, status, observed_at, source_ids}`。
kind=search/read；status=success/failure；observed_at 带时区。一次查询或一个读取 URL 算一次动作。只记录真实执行的动作。

## Prepared

prepare 输出 `{schema_version, bundle_id, request, mechanical_checks}`。
不要手改这个文件；修改原 request 后重新 prepare。相同输入的 bundle_id 稳定，内容变化会使旧 judgments 失效。

## Judgments

```json
{
  "schema_version": 1,
  "bundle_id": "使用 prepare 输出的实际值",
  "reviewer": {"kind": "host_model", "model": null},
  "findings": []
}
```

reviewer.kind=host_model/human/saved_demo；model 未知可 null，不虚构模型名称。

每个 Finding：

| 字段 | 约定 |
|---|---|
| claim_id | 对应已提取 Claim，不得重复 |
| verdict | supported / contradicted / insufficient_evidence / unverifiable / conflicted / out_of_scope / not_reviewed |
| issue_codes | review-rules.md 中的类型数组，无问题用空数组 |
| evidence | EvidenceRef 数组 |
| action_ids | 访问失败等实际 Action ID 数组 |
| reason | 具体判断理由 |
| suggested_text | 有据的局部替换建议；无证据用 null |
| unresolved | 具体缺口数组；insufficient_evidence/unverifiable 必需非空 |

EvidenceRef：`{source_id, text_sha256, start, end, quote}`。
quote 必须等于原始正文切片；`locate` 可产生候选位置与 match_kind，后者只是排版匹配信息。
supported/contradicted 必须有证据；conflicted 至少两个不同证据位置。supported 不可同时填写错误类型或未解决项。
metadata_record 仅可用于 existence/identity 的确定结论。snippet 不进入最终 evidence。
unverifiable 必须能在关联来源限制或失败 Action 中找到依据；未提交的 Claim 自动标为 not_reviewed。

## Report

review.json 保留 original_answer、question、sources、network_actions、mechanical_checks、findings、scope 与 summary。
scope.semantic_review_status=not_performed/partial/complete 表示执行覆盖，不表示答案无误。
每个 Finding 包含原始 claim，供报告回查和评测锚点匹配。
退出码 0 表示成功生成报告；2 表示输入/判断不合法；1 表示文件操作失败。
