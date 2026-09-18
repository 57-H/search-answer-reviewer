# 如何让每次搜索都先经过审查

如果你只是把本仓库安装为 skill，**不需要做下面的配置**。AI 会按照 [SKILL.md](../SKILL.md) 的说明审查搜索结果，但不能保证每次都执行。

如果你正在开发自己的 AI 应用，并且**能控制它调用哪个搜索工具**，可以按本页把搜索接入 `SearchAuditGate`。这样，每次经过这个入口的搜索都会先完成审查，结果才会交给 AI。门控保证的是“审查确实执行、记录通过校验”；判断结果是否正确，仍取决于负责审查的模型或人工审核者。

> **Codex 用户请先看这里：**仅安装 skill，或给 Codex 内置 WebSearch 配置本地 `PostToolUse` 钩子，不能强制拦截它。Codex 的[钩子文档](https://learn.chatgpt.com/docs/hooks)明确列出托管 WebSearch 不经过本地工具钩子。要实现强制触发，需要使用你能控制的搜索工具或自己编写 AI 应用。

## 开始前准备

你需要：

1. Python 3.10+ 和本仓库的完整目录。
2. 一个能由你的代码调用的网页搜索工具或搜索 API。
3. 一个能读取搜索结果并给出审查判断的 AI 模型调用，或人工审核流程。
4. 修改 AI 应用工具列表的权限：能够只开放审查后的搜索入口，关闭原始搜索入口。

本仓库不提供搜索 API、模型账号或现成的线上服务；你需要把自己使用的搜索工具和模型接进来。

## 第 1 步：让你的代码能导入门控

如果尚未下载仓库，先运行：

```bash
git clone https://github.com/57-H/search-answer-reviewer.git
```

将下载后的 `scripts/` 目录加入 Python 模块路径，然后导入门控：

```python
import sys

sys.path.insert(0, "/你的路径/search-answer-reviewer/scripts")
from reviewer_core.gate import SearchAuditGate
```

把示例路径替换为仓库在你电脑或服务器上的实际路径。如果你已用其他方式设置 `PYTHONPATH`，不需要再调用 `sys.path.insert`。

## 第 2 步：接入你自己的搜索工具

在 AI 应用中编写 `search_backend(question, query)`。它执行一次真实搜索，并把这次返回的结果整理为本项目的 Request。**不要填写想象中的页面内容、访问时间或读取记录。**

```python
def search_backend(question: str, query: str) -> dict:
    # 在这里调用你自己的搜索 API，并按下方清单整理返回结果。
    raise NotImplementedError("请接入真实搜索工具并返回 Request")
```

返回内容至少要满足这些要求：

- `schema_version` 填 `1`；`question` 原样使用传入的用户问题；`mode` 填 `results`，`evidence_mode` 填 `host_web`，`answer` 填 `None`，`reference_time` 填带时区的当前时间。没有排除项时，`excluded` 填空数组。
- `sources` 中每条结果都有独立 ID、搜索返回的 URL 和标题等元数据，并将 `provenance` 填为 `host_observation`，记录真实的工具调用标识 `observation_ref` 与抓取时间 `retrieved_at`。如果读到了正文，保存真实正文；只拿到搜索摘要时，标为 `snippet`，不要伪装成已读页面。
- `claims` 为每条返回结果至少创建一个来源身份断言，例如待核查的标题，并关联该来源 ID。
- `network_actions` 记录本次成功的搜索动作：`target` 等于 `query`，`source_ids` 包含本次返回的全部来源 ID。实际读取页面和失败的动作也应如实记录。

字段格式、取值和锚点位置见[数据格式](schema.md)。[门控测试中的 `search_request()`](../tests/test_gate.py) 是一个可运行的**合成数据示例**，可用于理解结构，但不能当成真实联网结果。

## 第 3 步：接入负责审查的模型或人工流程

编写 `review_results(prepared)`。`prepared` 包含用户问题和上一步的搜索结果。把 [SKILL.md](../SKILL.md)、[审查规则](review-rules.md)和[数据格式](schema.md)提供给负责审查的模型，让它只根据当前 `prepared` 生成 Judgments；如果由人工审核，就按相同格式填写：

```python
def review_results(prepared: dict) -> dict:
    # 在这里调用你的模型或人工审核流程，并返回结构化审查判断。
    raise NotImplementedError("请接入实际审查流程并返回 Judgments")
```

每次返回都必须包含：

- 与 `prepared["bundle_id"]` 完全一致的 `bundle_id`，以及 `schema_version: 1`。
- `reviewer`：`kind` 填 `host_model` 或 `human`；`model` 填实际模型名称，不知道时填 `None`。
- `task_fit`：**每条搜索结果一条**，判断它与用户需求是 `matches`、`partial`、`fails` 还是 `unknown`，并写明已满足、未满足或尚未核实的需求。
- `findings`：逐条核查来源身份和需要用到的事实。支持或矛盾的结论必须引用真实取得的原文；证据不足和无法核实时写明缺口。

具体 JSON 字段见[数据格式](schema.md)。[门控测试中的 `audit()`](../tests/test_gate.py) 展示了最小结构，但其中的判断是测试用的固定结果；真实接入必须对**当前**搜索结果重新审查。修改搜索结果后，旧 `bundle_id` 的判断不能复用。

## 第 4 步：只向 AI 开放审查后的搜索入口

前三步完成后，在你的 AI 应用里创建门控，并让 AI 的搜索工具调用它：

```python
gate = SearchAuditGate(search_backend, review_results)

def audited_search(question: str, query: str) -> dict:
    return gate.search(question, query)
```

在工具列表中**只注册 `audited_search`**。不要同时把原始搜索 API、原始搜索函数或另一条不经门控的搜索路径交给 AI，否则它仍可能绕过审查。让 AI 遵循本项目的 [SKILL.md](../SKILL.md)，并把门控返回的 `sources` 和 `report` 一起交给它，让它看到哪些结果不符合需求、哪些事实证据不足。

门控会阻止**未经审查**的结果，不会自动删除已经审查但不符合需求的来源。后者保留在报告中，用来说明排除理由；AI 不应把它们推荐给用户。

## 第 5 步：显示审查状态并验证配置

门控返回的 `status_line` 可以直接展示给用户，例如 `搜索结果审查通过 2/3 条`。如果希望**每次搜索后都显示**，请在你的应用界面里显示这个字段；不要让 AI 自己猜测通过数量。`x/y` 只对应本次搜索：一条结果必须既满足用户需求，又通过关联事实核查，才计入 `x`。

例如命令行应用可以在每次工具调用后执行 `print(result["status_line"])`；网页或桌面应用则用自己的界面函数显示同一个字段。

接好真实搜索工具和审查器后，至少试这三种情况：

1. 一条相关且有证据的结果：能得到 `1/1`，AI 收到结果和报告。
2. 一条真实但答非所问的结果：得到 `0/1`；报告说明不匹配，AI 不应把它作为符合需求的推荐。
3. 审查器不返回判断或返回旧 `bundle_id`：门控抛错，AI 不应收到未经审查的搜索结果。

仓库自带的门控单元测试可用于检查门控本身：

```bash
python3 -m unittest discover -s tests -p test_gate.py -v
```

这些测试不代替你对自己搜索 API、模型调用和工具列表的实际接入测试。门控无法证明模型的语义判断一定正确，也无法覆盖应用中绕过门控的其他搜索路径。
