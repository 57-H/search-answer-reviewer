# Development evaluation: mandatory ordinary review gate

This is a development experiment, not Beta release evidence. It used the frozen public revision `8e42b57`, Codex CLI `0.155.0-alpha.9.2`, `gpt-5.6-luna`, low reasoning effort, web search enabled, ignored user configuration, and a clean repository-scoped installation from the GitHub commit archive.

## Baseline run

The first repetition covered all ten categories in `eval/cases-codex-beta.jsonl`: nine search or supplied-result tasks and one non-search control. All ten processes completed. Median elapsed time was 161.092 seconds. Recorded usage was 940,305 input tokens, including 684,032 cached input tokens, and 8,891 output tokens.

Observed behavior:

- the skill activated in all 9 applicable tasks;
- the non-search control did not activate the skill;
- no applicable task produced a successful `ordinary-status` invocation or a saved ordinary batch record;
- 8 of the 9 applicable tasks nevertheless printed a handwritten `已审查 x/y` line.

This is classified as **activated but review skipped**, with an invalid user-visible coverage claim. It demonstrates why activation rate cannot substitute for review-before-use coverage. These ten runs are excluded from release evidence because they exposed a workflow defect that was then changed.

## Root cause and minimal check

The ordinary status command appeared late in a long workflow, after the full evidence-bundle and detailed-report path. The model loaded `SKILL.md` but treated record creation and the status command as optional while drafting the answer.

The minimal change moved a binary ordinary-mode gate before result use: a result may be used only after `work/batch-review.json` validates through `ordinary-status`; otherwise the answer must report `搜索结果审查未完成` and omit that batch's facts.

One same-model, same-settings development rerun of `codex-factual-01` then:

- loaded the skill and ordinary schema;
- saved `work/batch-review.json`;
- successfully invoked `ordinary-status`;
- copied the generated `已审查 12/12` status into the final answer.

This single rerun supports the root-cause hypothesis but does not establish a stable rate. The frozen release suite must restart from the revised public commit. Raw development traces remain under the ignored local `work/eval/formal/` directory.
