# Search Answer Reviewer

**让 AI 在使用搜索结果回答问题前，先检查结果是否答题、来源是否对得上、结论是否有证据。**

Search Answer Reviewer 是一个用于网页搜索任务的 skill。它针对搜索回答中常见的失误：找到真实但不符合需求的页面、把第三方内容当成官方来源、误引数字或年份，以及把来源没有证明的内容写进最终答案。

## 它能做什么

- **检查是否答题**：对照用户的目标和硬条件（例如平台、版本、是否离线），标出不匹配或只满足部分条件的结果。没有合适结果时，针对缺口补搜；仍找不到就说明限制。
- **核对来源与证据**：检查链接对应的标题、作者和发布者；将引文、数字及关键结论与取得的原文对照。
- **复核最终答案**：发现答案中新出现或说得过满的事实，给出证据不足、存在矛盾或无法核实等判断，并建议如何收窄表述。

页面打不开或搜索不到，不会仅凭这一点被判为虚构。这个 skill 审查的是**回答有没有得到已取得证据的支持**，不会替任何网页保证其内容一定正确。

## 如何使用

把仓库链接发给支持安装 skill 的 AI 助手，并说明 skill 位于仓库根目录：

```text
请从 https://github.com/57-H/search-answer-reviewer 安装仓库根目录的 Search Answer Reviewer skill，保留完整目录结构。
```

运行脚本需要 Python 3.10+，无需第三方 Python 依赖或本项目专属 API Key。安装后，skill 会指导 AI 在网页搜索结果返回后进行审查；你也可以在任务中明确要求“使用 Search Answer Reviewer 审查搜索结果”。仅安装 skill 不能保证 AI 每次搜索都执行它；如需强制执行，可按[接入说明](references/host-integration.md)配置搜索门控。

想先看一份报告，可在仓库目录运行：

```bash
python3 scripts/review.py replay --example examples/overclaim --out-dir work/demo
```

然后打开 `work/demo/review.md`。这是使用保存材料的[离线演示](examples/overclaim/review.md)，展示了为什么“支持本地部署”不能直接写成“完全离线”。

## 可以得到什么

审查结果会指出哪些搜索结果符合需求，哪些来源或断言有问题，以及需要补查什么。需要逐条核验时，可生成可阅读的 `review.md` 和便于程序处理的 `review.json`。接入搜索门控后，还可以显示 **`搜索结果审查通过 x/y 条`**；这个数字只统计需求匹配且事实核查通过的结果。

在一项[核对 45 条论文参考文献的实际任务](examples/microfm-references/review.md)中，审查发现了一条标题搜索造成的错误论文匹配，以及一条参考文献与原始会议页面不一致的年份记录。报告保留了每条文献的核对结果和可访问链接。

更多细节见 [skill 指令](SKILL.md)和[接入说明](references/host-integration.md)。项目采用 [MIT License](LICENSE)。
