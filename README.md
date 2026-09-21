# Search Answer Reviewer

Search Answer Reviewer 是一个面向网页搜索任务的 Agent Skill。它要求 AI 在使用每批搜索结果前检查三件事：结果是否回答用户需求、来源身份是否与描述一致、最终答案使用的事实是否有已取得的证据或明确记录的缺口。

它主要处理这些问题：

- 搜索结果真实存在，但对象、版本、时间或用户硬条件不匹配；
- 第三方页面被误写成官方来源，或标题、作者、发布者对应错误；
- 页面只证明较弱结论，答案却扩大成完全离线、免费商用、长期维护等强结论；
- 搜索完成后，最终答案又加入未经审查的数字、价格、限制或推荐理由；
- 页面打不开或材料不足时，AI 把“无法核实”误写成“来源虚构”或确定结论。

## 安装和使用

把仓库链接交给支持 Agent Skills 的 AI 助手，并说明安装仓库根目录的 skill：

```text
请从 https://github.com/57-H/search-answer-reviewer 安装仓库根目录的 Search Answer Reviewer skill，保留完整目录结构。
```

目前首先针对 Codex 验证，其他 AI 助手尚未验证。安装后可以直接提出需要网页搜索的任务，也可以明确要求“使用 Search Answer Reviewer 审查搜索结果”。普通 Skill 依赖 AI 自主加载，无法保证每次托管搜索都触发；实际可靠性以运行轨迹中的逐批审查覆盖率衡量。

每批结果审查后，AI 应从保存的记录生成并显示：

```text
已审查 x/y
```

这里的 `x` 表示已经完成需求匹配、来源身份判断，并核查了答案实际使用事实的结果数；`y` 是该批返回的结果总数。“已审查”不等于结果正确或推荐通过。可以用仓库自带示例查看计算方式：

```bash
python3 scripts/review.py ordinary-status --input examples/ordinary-batch-review.json
```

需要生成详细证据报告时，运行离线示例：

```bash
python3 scripts/review.py replay --example examples/overclaim --out-dir work/demo
```

脚本要求 Python 3.10+，不需要第三方 Python 依赖或本项目专属 API Key。

## 使用效果

AI 会用审查结论调整最终答案：排除不符合硬条件的候选，收窄证据没有支持的表述，区分官方与第三方来源，并把仍无法核实的条件明确告诉用户。专门的审查任务还可以生成 `review.md` 和 `review.json`。

在一项[核对 45 条论文参考文献的实际案例](examples/microfm-references/review.md)中，审查发现了一条标题搜索造成的错误论文匹配，以及一条参考文献与原始会议页面不一致的年份记录。

当前仓库是 Beta 候选。发布门槛是至少 100 批真实搜索结果中漏审不超过 5 批，并且人工核定案例中没有尚未修复的严重误放行。仓库尚未发布满足该门槛的实测数据，因此不宣称稳定触发率或降低幻觉的百分比。评测方式见[评测协议](eval/protocol.md)。

如果你在开发自己的 AI 应用，并且能控制搜索入口，可以参考[实验性搜索门控接入](references/host-integration.md)。门控不属于普通 Skill 的 Beta 承诺。

项目采用 [MIT License](LICENSE)。
