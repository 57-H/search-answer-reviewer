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

results 模式的详细审查要求 `task_fit` 数组，每个返回来源各一条；只审查已有答案且没有搜索结果批次时可省略。每条为 `{source_id, verdict, reason, matched_requirements, unmet_requirements}`，其中 verdict 取 `matches` / `partial` / `fails` / `unknown`。`matches` 须列出至少一个已满足需求，且未满足需求为空；其他结论须列出未满足或尚未核实的需求。`task_fit` 判断结果与用户任务的匹配程度，与来源身份或事实断言的 `findings` 分开。

例如用户要求 Windows 且离线，来源只确认 Windows 时，填入 `{"source_id":"s1","verdict":"partial","reason":"页面没有说明离线运行","matched_requirements":["Windows"],"unmet_requirements":["离线运行"]}`。不能因为来源真实，就把这条结果标为 `matches`。

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

review.json 保留 original_answer、question、sources、network_actions、mechanical_checks、findings、task_fit、scope 与 summary。
scope.semantic_review_status=not_performed/partial/complete 表示执行覆盖，不表示答案无误。
每个 Finding 包含原始 claim，供报告回查和评测锚点匹配。
退出码 0 表示成功生成报告；2 表示输入/判断不合法；1 表示文件操作失败。

## 普通模式批次记录

普通 Skill 每次收到一批搜索结果后保存一个轻量记录。完整示例见 [`examples/ordinary-batch-review.json`](../examples/ordinary-batch-review.json)。顶层字段为：

| 字段 | 约定 |
|---|---|
| schema_version | 整数 1 |
| batch_id | 本次搜索批次的稳定 ID |
| result_ids | 按搜索返回顺序排列的全部结果 ID；零结果用空数组 |
| reviews | 已完成的 ResultReview 数组；缺失的结果保留在分母中 |

每个 ResultReview 必须包含：

- `result_id`：对应 `result_ids`，不得重复；
- `task_fit`：`{verdict, reason}`，verdict 为 matches / partial / fails / unknown；
- `source_identity`：`{verdict, reason}`，verdict 为 verified / mismatch / unresolved；
- `used_in_answer`：布尔值，表示该结果是否影响最终答案（包括支持、排除或收窄结论）；
- `used_claim_ids`：该结果中实际影响最终答案的事实 ID；没有使用时为空数组；
- `fact_reviews`：`{claim_id, verdict, evidence_refs, unresolved}` 数组。被使用的每个事实都须出现，且 verdict 不能是 not_reviewed 或 out_of_scope。supported / contradicted / conflicted 必须引用已经捕获的证据；证据不足、无法核实或冲突时，`unresolved` 必须写明缺口。

运行：

```bash
python3 scripts/review.py ordinary-status --input work/batch-review.json
```

脚本只根据记录生成 `已审查 x/y`，不会猜测缺失判断。`x` 是满足上述完整性要求的结果数，`y` 是 `result_ids` 总数。这个状态表示审查覆盖，不表示结果匹配或断言得到支持。

## Codex 运行轨迹

真实触发评测使用 JSONL，每行一个运行。运行字段为 `schema_version`、`run_id`、`case_id`、`method`、`status`、`platform`、`codex_version`、`model`、`settings`、`skill_revision`、`task_category`、`events`、`usage` 和 `elapsed_seconds`。

事件按数组顺序表示实际发生顺序：

- `{"type":"skill_activated"}`；
- `{"type":"search_results","batch_id":"b1","result_ids":["r1"]}`；
- `{"type":"review_recorded","batch_id":"b1","record":{...普通模式批次记录...}}`；
- `{"type":"result_used","batch_id":"b1","result_id":"r1"}`；
- `{"type":"answer_delivered"}`。

只有在首次 `result_used` 之前已有完整审查记录的批次，才计入逐批审查覆盖率的分子。失败、超时、未触发和格式错误运行仍须保留。零结果批次单独计数，不进入“已用于答案的批次”分母。
