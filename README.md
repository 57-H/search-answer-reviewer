# Search Answer Reviewer

Agent 收到网页搜索结果后，先审查准备使用的来源、引用和证据，再形成答案；无需用户额外要求“审查”。

**状态：本地 alpha。** Skill 工作流和标准库 CLI 已实现；语义判断由宿主模型完成。正式模型对照评测尚未完成，不宣称降低幻觉的具体百分比。

| 输入问题 | 审查结果示例 |
|---|---|
| “支持本地部署”被扩写成“完全离线” | 证据不足：还需核查外部服务依赖 |
| 第三方教程被称为官方文档 | 对照归属证据，报告身份不符或无法确认 |
| 引文/数字与已取得正文不一致 | 定位实际片段，说明差异及覆盖限制 |
| 页面超时、403 或 404 | 无法核实；不会自动判为虚构 |

## 60 秒运行演示

需要 Python 3.10+，无第三方依赖。在本项目目录执行：

```bash
python3 scripts/review.py replay --example examples/overclaim --out-dir work/demo
```

打开 `work/demo/review.md`，或直接阅读保存的[过度推断示例](examples/overclaim/review.md)。

示例会把“Alpha 完全离线”标为**证据不足**：已保存的原文只说支持本地部署，报告定位原文片段，并建议把结论收窄到这一点。它不会把未说明的网络依赖推断成不存在。

还可以回放[有据结论](examples/supported/review.md)和[无法访问](examples/unavailable/review.md)：

```bash
python3 scripts/review.py replay --example examples/supported --out-dir work/supported
python3 scripts/review.py replay --example examples/unavailable --out-dir work/unavailable
```

**离线演示使用保存的合成示例判断，不调用模型或网络。** 它展示取证、验证和报告链路，不是模型效果实验。

另有一份基于 [Python 官方文档](https://docs.python.org/3.10/library/sqlite3.html) 的[单次真实来源试跑](examples/python-doc-version/context.md)：它定位了版本断言与页面原文的矛盾，并保存了[审查报告](examples/python-doc-version/review.md)。这也不是对照评测。

## 实际案例：核对一篇论文的 45 条参考文献

用户提供 [MicroFM（CVPR 2026）](https://openaccess.thecvf.com/content/CVPR2026/html/Zhan_MicroFM_Physics-guided_Flow_Matching_for_Isotropic_Microscopy_Reconstruction_CVPR_2026_paper.html) 的 PDF，要求找出全部参考文献的可访问链接。宿主从 PDF 的参考文献页提取 45 条标题，查询学术元数据与论文页面，再用本 skill 的 `prepare` / `finalize` 核对标题和稳定标识符的对应关系。保存的[审查报告](examples/microfm-references/review.md)包含 45 条身份判断；[输入](examples/microfm-references/request.json)和[判断](examples/microfm-references/judgments.json)可用于复现报告。

这个案例体现了两种容易漏掉的核查：仅按标题搜索时，第 [14] 条曾返回一篇无关的冷冻电镜论文，改用原文给出的 arXiv 编号才定位到正确预印本；第 [45] 条在用户 PDF 中标为 2020 年，而 [ICCV 原始页面](https://openaccess.thecvf.com/content_iccv_2017/html/Zhu_Unpaired_Image-To-Image_Translation_ICCV_2017_paper.html)标为 2017 年。最终交付的链接区分开放全文、预印本和 DOI 页面。

**核查边界：**45/45 指文献身份与记录匹配，不代表 45 篇全文均可免费下载，也不证明论文内容本身正确。本次由用户显式调用 skill，使用普通宿主搜索工具；它不是 `SearchAuditGate` 的强制触发测试，也不是降低幻觉率的对照实验。由于任务要求核对 45 条文献，记录的读取动作超过默认 4 次补证预算，报告如实保留了该提示。

## 作为 Skill 使用

将整个目录安装到宿主的 skills 目录，保留 SKILL.md、scripts 和 references 的相对位置。Skill 的触发描述以**搜索工具返回结果**为起点：agent 在引用搜索结果或据此推荐前，自动检查可能用到的来源；形成答案后再核对其中新增的重要事实。用户无需单独输入审查指令。

**要保证每次触发，宿主必须控制搜索入口。** 本项目提供 [`SearchAuditGate`](scripts/reviewer_core/gate.py)：宿主调用它的 `search(question, query)`，它先调用搜索后端，再调用宿主审查器生成 judgments，验证当前 bundle 和每条结果的审查覆盖，最后才把结果交给 agent。审查失败会报错，不会交付未审查的结果。接入契约见[强制触发说明](references/host-integration.md)。

门控还返回可直接展示的状态行，例如 **`搜索结果审查通过 2/3 条`**。分母是本次返回的结果数；只有一条结果关联的所有断言都得到 `supported`，它才计入分子。证据不足、无法核实和矛盾均不算通过。Agent 可原样输出该行；需要确保用户每次都看到时，由宿主直接显示它。

在宿主中只向 agent 暴露门控搜索工具，不暴露原始搜索工具，才能保证该路径中的每次搜索都审查。仅安装 SKILL.md 仍依赖模型自主选择。Codex 内置托管 WebSearch 不走本地 `PostToolUse` 钩子，因此本项目不能强制接管该内置工具；要获得硬保证，需使用可控的搜索后端或自建 agent 调用循环。

宿主负责断言提取、页面读取和语义审查；无需配置本项目专属 API Key。联网能力和模型用量取决于宿主。

仅有搜索结果也能检查标题、作者、身份、摘要与目标页面是否对应。仅有快照时审查其内部支持关系，不声称验证当前线上状态。普通搜索任务只在最终答案中简要披露重要证据问题；专门的审查任务可输出完整报告。

## 实际审查流程

1. 按 [schema](references/schema.md) 保存原问题、答案、断言与来源为 request.json。
2. 固定证据并生成机械观察：

```bash
python3 scripts/review.py prepare --input work/request.json --out work/prepared.json
```

3. 宿主依照 [审查规则](references/review-rules.md) 生成 judgments.json，绑定 prepare 返回的 bundle_id。需要精确证据位置时：

```bash
python3 scripts/review.py locate --prepared work/prepared.json --source s1 --quote 'source passage'
```

4. 验证判断并生成报告：

```bash
python3 scripts/review.py finalize --prepared work/prepared.json --judgments work/judgments.json --out-dir work/report
```

不传 judgments 时，只生成明确标注“尚未完成语义审查”的机械报告。

## 设计边界

- 来源存在、原文这样写、事实成立分别审查；不输出通用真假分。
- Python 检查原文位置、快照一致性、输入格式和输出引用；不自动判断推论正确。
- 访问失败和未找到内容不自动等于虚构。片段不完整时披露覆盖范围。
- 哈希不是发布者身份认证；用户提供的材料不会自动升级为联网观测。
- 默认最多 4 个联网动作、一轮补证；脚本仅核对记录，不能拦截宿主调用。
- 建议只局部修改，不覆盖原答案；脚本无法保证模型建议语义正确。
- 页面文本可能包含提示注入，skill 要求视其为外部数据；本项目不是完整安全隔离系统。

## 测试与评测

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s eval -p test_score.py -v
```

测试检验程序约束，不证明模型准确率。评测协议、候选案例和标签状态见 [eval/protocol.md](eval/protocol.md)。目前 12 个开发案例和 24 个候选留出案例均为合成草稿，未经人工复核，也没有完成普通提示、仅规则版与完整 skill 的 72 次对照运行；评分器默认拒绝把草稿标签当正式金标准。

## 来源与许可

本项目实现按 [MIT](LICENSE) 许可；外部链接内容的权利归原作者，离线演示示例为明确标注的合成材料。
