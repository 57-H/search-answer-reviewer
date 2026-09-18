# 强制触发：宿主搜索门

`SearchAuditGate` 是宿主与搜索后端之间的同步入口。**保证范围仅限经过该入口的搜索调用。** 宿主必须把原始搜索工具留在 agent 可用工具列表之外，只暴露门控工具；否则 agent 可以绕过审查。门控不能证明模型的语义判断一定正确，只能保证审查调用、报告校验和失败不放行。

```python
from reviewer_core.gate import SearchAuditGate

gate = SearchAuditGate(search_backend, host_auditor)
audited = gate.search(user_question, search_query)
# 仅在这里把 audited["sources"] 和 audited["report"] 交给 agent。
```

运行时把本项目 `scripts/` 加入 Python 模块路径。`search_backend(question, query)` 必须执行一次真实搜索，返回符合 [schema.md](schema.md) 的 `mode="results"`、`evidence_mode="host_web"` Request。保留原问题；记录本次成功的 search Action，`target` 等于本次 query，并把每个返回来源 ID 放进该 Action 的 `source_ids`。每条 Source 要有真实的 `host_observation`、`observation_ref`、`retrieved_at`，并至少有一条锚定自身声明字段（如标题或标识符）的 Claim。搜索后端可以按需要读取页面，但必须记录读取动作与真实可得的正文；不能把搜索摘要伪装成页面证据。

`host_auditor(prepared)` 在收到冻结后的 Prepared 时执行本 skill 的语义审查，并返回同一 `bundle_id` 的 Judgments。审查者须为 `host_model` 或 `human`；保存演示不能冒充现场审查。每个返回来源须有一条 `task_fit` 需求匹配判断，以及至少一个实质性事实结论（包括有具体原因的 `unverifiable` 或 `insufficient_evidence`）。来源缺失、需求匹配判断缺失或重复、事实审查遗漏、旧 bundle、伪造引文或回调异常都会阻止交付。空搜索结果仍调用审查器，返回 `status="no_results"`。

门控返回 `{"status", "sources", "report", "review_progress", "status_line"}`。`review_progress` 是 `{"passed": x, "total": y}`；`total` 为本次返回的来源数，只有 `task_fit=matches` 且关联断言全部为 `supported` 的结果才计入 `passed`。`status_line` 使用程序计算的文字，例如 `搜索结果审查通过 2/3 条`；无结果时为 `搜索结果审查：无结果（0/0）`。不匹配的来源仍保留在报告中，可用于解释排除理由，但不可当作满足需求的推荐。宿主应只把这个门控结果交给 agent。若要求每次都对用户可见，宿主还应在工具返回后直接显示 `status_line`，避免依赖模型自发转述；多次搜索逐次显示，不把一次查询的数字误当全程总数。

多次相同查询也逐次审查，不依赖缓存跳过审核；如果宿主在门控外做缓存或另外暴露浏览器、搜索 API、内置 WebSearch，这些路径不受保证。

Codex 的 [Hooks 文档](https://learn.chatgpt.com/docs/hooks) 说明 `PostToolUse` 覆盖本地函数和 MCP 工具，但不覆盖托管 WebSearch。因此单靠安装 skill 或添加 Codex hook，无法强制接管该内置搜索。若使用 OpenAI API 自建 agent，可把搜索实现为应用自己处理的函数工具，在返回工具结果给模型前调用此门控；不要同时向模型开放可绕过它的内置搜索工具。
