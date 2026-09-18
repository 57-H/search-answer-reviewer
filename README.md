# Search Answer Reviewer

**让搜索结果先经过证据审查，再进入回答。**

Search Answer Reviewer 是一个面向搜索增强任务的 agent skill。它检查三件事：**结果是否回答用户的问题、是否对应所声称的来源、答案中的关键事实是否得到来源支持**。发现问题时，它指出具体缺口，并建议收窄或修正相关表述。

| 要防的错误 | 具体例子 | 审查后的处理 |
|---|---|---|
| 搜索结果答非所问 | 用户要支持 Windows 且可离线运行的工具，结果却是 macOS 专用的在线服务；或只找到泛泛介绍，没有回答具体问题 | 对照任务目标、对象和硬条件；无匹配结果时针对缺口补搜，仍找不到就说明限制，不把不匹配的候选当成推荐 |
| 来源身份弄错 | 搜索结果被称为“官方文档”，打开却是第三方教程；论文链接指向另一篇文章 | 对照实际页面的标题、作者、发布者或稳定标识符；身份不符就不按原身份引用 |
| 引用内容不符 | 答案中的引文、数字或年份与取得的原文不同 | 定位原文片段，指出差异，并保留版本、时间等适用条件 |
| 结论超出证据 | 页面只说“支持本地部署”，答案却写“完全离线” | 标为证据不足；补查缺失条件，或把结论收窄到原文能支持的程度 |
| 答案里出现未经核实的新事实 | 搜索记录只证明“支持某功能”，最终推荐却写成“免费版支持” | 在输出前复核新增断言；无法证实时删除、补查或明确说明不确定 |

打不开、403、404 或搜索不到的页面会被标为**无法核实**，不会仅凭这些现象断定来源是虚构的。本项目审查的是已取得证据与断言的对应关系，不自动裁定网页所述事实在现实中一定成立。

## 快速体验

需要 Python 3.10+，不需要安装第三方依赖。在项目目录运行：

```bash
python3 scripts/review.py replay --example examples/overclaim --out-dir work/demo
```

查看 `work/demo/review.md`，或直接阅读[示例审查报告](examples/overclaim/review.md)。在这个示例里，来源只证明“支持本地部署”，因此“完全离线”会被标为**证据不足**；报告给出原文位置和可接受的收窄表述。

`replay` 使用保存的合成材料和判断，展示报告生成流程，不会联网或重新调用模型。另有[有据结论](examples/supported/review.md)、[无法访问](examples/unavailable/review.md)两个示例，以及基于 [Python 官方文档](https://docs.python.org/3.10/library/sqlite3.html) 的[真实来源核查记录](examples/python-doc-version/context.md)。

## 如何接入

### 作为 agent skill 使用

把仓库链接交给支持安装 skill 的 agent，并说明 **skill 位于仓库根目录**：

```text
请从 https://github.com/57-H/search-answer-reviewer 安装仓库根目录的 Search Answer Reviewer skill，保留整个目录结构，并运行 README 中的 replay 示例验证安装。
```

若安装器要求指定仓库内路径，请使用 `.`，并将 skill 命名为 `search-answer-reviewer`。安装时需保留 `SKILL.md`、`scripts/` 和 `references/` 的相对位置。Codex 的 `$skill-installer` 支持从其他 GitHub 仓库安装 skill；安装后若未显示，可重启 Codex。Skill 指导 agent 在搜索工具返回结果后审查准备使用的来源，并在回答前检查新加入的重要事实；用户无需每次单独提出审查要求。

仅安装 skill 时，是否每次执行仍取决于宿主模型和工具调用路径。它不能拦截所有搜索工具，也不能机械保证每次触发。

### 在自建 agent 中强制审查

如果宿主可以控制搜索入口，可接入 [`SearchAuditGate`](scripts/reviewer_core/gate.py)。门控会先取得搜索结果，再要求宿主审查器核对每条返回来源；报告通过校验后，结果才会交给 agent。审查缺失、引用无效或审查器报错时，门控不会放行。接入参数和约束见[宿主集成说明](references/host-integration.md)。

```python
from reviewer_core.gate import SearchAuditGate

gate = SearchAuditGate(search_backend, host_auditor)
audited = gate.search(user_question, search_query)
```

要保证这一路径中的**每次搜索**都被审查，宿主须只向 agent 暴露门控搜索工具，并隐藏可绕过门控的原始搜索工具。这个保证针对“审查流程确实执行并通过校验”，不代表模型对证据的语义判断一定正确。Codex 内置托管 WebSearch 不能由本地 `PostToolUse` 钩子强制接管；使用该内置工具时，skill 仍是模型遵循的工作指引。

门控会返回可展示的状态行，例如 **`搜索结果审查通过 2/3 条`**。分母是本次返回的来源数；只有结果与需求匹配，且关联断言全部获得 `supported` 判断，才计入分子。相关但不满足硬条件的来源仍可作为排除候选的证据，不会被算作匹配的推荐。若希望用户每次都看到状态，应由宿主直接展示门控返回的 `status_line`，而不是让模型自行计算或转述。没有门控报告时，不应输出“审查通过”的数字。

## 一个真实案例：核对 45 条论文参考文献

在核对 [MicroFM（CVPR 2026）](https://openaccess.thecvf.com/content/CVPR2026/html/Zhan_MicroFM_Physics-guided_Flow_Matching_for_Isotropic_Microscopy_Reconstruction_CVPR_2026_paper.html) 参考文献的任务中，agent 从用户提供的 PDF 提取 45 条条目，查找可访问的论文页面，并用本项目的审查流程核对标题与稳定标识符。[完整报告](examples/microfm-references/review.md)、[输入记录](examples/microfm-references/request.json)和[审查判断](examples/microfm-references/judgments.json)保存在仓库中。

核查发现了两个很有代表性的陷阱：第 [14] 条的标题搜索曾指向一篇无关论文，使用参考文献中的 arXiv 编号才找到对应预印本；第 [45] 条在用户 PDF 中标为 2020 年，而 [ICCV 原始页面](https://openaccess.thecvf.com/content_iccv_2017/html/Zhu_Unpaired_Image-To-Image_Translation_ICCV_2017_paper.html)标为 2017 年。交付的链接区分了开放全文、预印本和 DOI 页面。

报告中的 45/45 表示**文献身份与记录匹配**，不表示每篇全文都能免费下载，也不证明论文内容正确。这个案例由用户显式调用 skill 完成，不用于证明门控的自动触发效果或幻觉率改善。

## 审查流程与输出

Skill 将原问题、答案、断言和来源整理为 `request.json`；宿主负责网页搜索、页面读取和语义判断，项目中的 Python 工具负责固定证据、定位原文、校验判断和生成报告。具体数据格式见 [schema](references/schema.md)，判断标准见[审查规则](references/review-rules.md)。

```bash
python3 scripts/review.py prepare --input work/request.json --out work/prepared.json
python3 scripts/review.py locate --prepared work/prepared.json --source s1 --quote 'source passage'
python3 scripts/review.py finalize --prepared work/prepared.json --judgments work/judgments.json --out-dir work/report
```

`locate` 用于需要精确原文位置的情况。`judgments.json` 由宿主对当前 `bundle_id` 生成；若不提供语义判断，`finalize` 只会生成明确标注“尚未完成语义审查”的机械报告。项目本身不需要专属 API Key，联网能力和模型用量取决于宿主。

审查会区分“来源确实存在”“原文确实这样写”和“结论由证据支持”。来源无法访问、搜索不到或页面片段不完整时，结果会保留为无法核实或证据不足，不会直接判为虚构。对于普通搜索任务，agent 可以仅披露影响答案的重要问题；需要逐条核验时，可输出完整报告。

## 适用边界

- 仅凭搜索结果可核对来源身份和可见元数据；要判断引用、数字与结论，通常还需读取正文。只有用户提供的快照时，不能声称验证了当前线上状态。
- Python 工具校验记录与证据位置，不独立判断事实真假或推论是否成立。报告不提供通用“真实性评分”。
- 默认最多补查 4 次、一轮补证；这是 skill 的工作预算，不是宿主的硬性拦截。大规模文献核对等任务可能超出预算，并在报告中披露。
- 外部页面文本被视为待审查的数据，而不是 agent 指令；本项目不构成完整的安全隔离系统。

## 测试与评测

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s eval -p test_score.py -v
```

这些测试验证程序约束，不代表模型审查准确率。[评测协议](eval/protocol.md)提供案例和评分方式；其中的标签仍是未经人工复核的草稿，目前没有可据以宣称幻觉率降低的对照结果。

## 许可

本项目采用 [MIT License](LICENSE)。外部链接内容的权利归原作者；离线演示材料均已标注为合成示例。
