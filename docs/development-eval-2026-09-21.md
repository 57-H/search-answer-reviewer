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

## Public revision rerun

On 2026-09-22, the same ten-run slice was repeated from the public GitHub archive for revision `a6e981ac1ad0b6a02f98b063cfbad5def44e6bdf`. The archive SHA-256 was `b921757c6a80f909d7fc7ac357f49ac3769ef6c2211e14db42ad43f0bf5e8cc6`. Model, reasoning effort, Codex version, web-search setting, task order, and isolation settings matched the baseline.

All ten processes completed. The skill activated in all 9 applicable tasks and did not activate in the non-search control. Every applicable task saved an ordinary batch record and invoked `ordinary-status` successfully. Median elapsed time was 209.440 seconds. Recorded usage was 1,520,685 input tokens, including 1,270,528 cached input tokens, and 22,526 output tokens.

Record inspection found that 8 of the 9 applicable batches had every answer-used result fully reviewed. In the comparison task, result `r1` was marked `used_in_answer` with four linked claims, but only one linked claim had a factual verdict. The command still exited successfully and returned `已审查 16/17`. This is an incomplete review record, so the observed development coverage was 8/9, not 9/9.

The follow-up fix makes `ordinary-status` reject any result marked `used_in_answer` unless all of its linked claims have substantive verdicts. Replaying the failing saved record now exits with `used result has incomplete review`.

After publishing that fix as revision `9e4c63eb2bea642974fe135fe685d5518dfd7257`, the comparison case was repeated from its public GitHub archive (`0310d779fd1a9b5f87b6ae2035950b8ddab94322b72318a1083c02465ad2d330`). The skill activated, saved reviews for all 11 returned results, and gave every claim linked to the three answer-used results a substantive verdict. `ordinary-status` succeeded with `已审查 11/11`, and the final answer copied that generated status. This targeted rerun verifies the defect path once; it does not establish a stable rate. The ten-run slice remains development evidence and does not satisfy the 100-batch Beta gate or the human-validated semantic gate.

## Current-public-revision repetition

A fresh ten-category repetition then used the public archive for revision `dc300ca4c6ea627b00e46b288a7844af4286ba60` (`2484fa04df2f1355e6bd005d1563f91aacc9beac29cb21538f34588bc52d6b78`). All ten processes completed. The skill activated in all 9 applicable tasks and did not activate in the non-search control. Eight applicable tasks produced valid ordinary records and successful status invocations. Median elapsed time was 185.339 seconds. Recorded usage was 1,358,025 input tokens, including 1,127,424 cached input tokens, and 20,462 output tokens.

The multi-round task created malformed JSON, so `ordinary-status` exited with code 2. The answer correctly displayed `搜索结果审查未完成`, but still included facts and a recommendation derived from that failed batch. This violates the unused-batch rule, so the repetition's development result is 8/9 applicable tasks with a valid recorded review, not 9/9.

The instruction was sharpened to require one repair-and-retry attempt after command failure and, if it still fails, an answer containing no batch-derived facts, links, comparisons, or recommendations. A same-model local-snapshot rerun of the multi-round case then produced two valid records: `已审查 26/26` for the initial batch and `已审查 16/16` for the supplementary batch. Both status commands succeeded before delivery. Because neither record was malformed in this rerun, it confirms multi-batch operation without directly exercising the new failure-retry branch.
