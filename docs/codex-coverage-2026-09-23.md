# Codex 100-batch coverage experiment

This experiment measured whether the ordinary Skill produced a validated review record for each observed search-results batch. It does not measure whether every semantic judgment was correct.

## Setup

- Public revision: `0f7a51a5eaa87a0fb75453ee25b95cf9baf4154d`
- GitHub archive SHA-256: `678e8b31edcbc806e16116b9bb71b08d846fb858588d29cdf96e857382544442`
- Frozen manifest SHA-256: `960ddec2c7d971bc33d920253e4afaa6458d39020fc56d647577a34fc24ac3c6`
- Codex CLI: `0.155.0-alpha.9.2`
- Model: `gpt-5.6-luna`, low reasoning effort, web search enabled
- 100 new conversations: 90 applicable tasks and 10 non-search controls
- Ten repetitions of each category in `eval/cases-codex-beta.jsonl`

The development symlink was removed during every run. Each task used a repository-scoped installation extracted from the pinned public archive and an independent workspace. Failed, timed-out, untriggered, and incomplete runs remained in the schedule.

## Result

| Metric | Result |
|---|---:|
| Observed search or supplied-results batches | 100 |
| Batches with a distinct successful ordinary review record | 97 |
| Missed batches | 3 |
| Coverage proxy | 97% |
| Skill load failures | 1 applicable run |
| Runtime failures | 0 |
| False activations in non-search controls | 0/10 |
| Applicable runs without a generated status | 1/90 |
| Median elapsed time | 199.107 seconds |

Recorded model usage was 17,451,858 input tokens, including 14,626,816 cached input tokens, and 240,382 output tokens.

The numerical criterion of at most five missed batches was met in this proxy measurement. It does not make the project Beta-ready.

## Misses

`codex-multiround-01-r4` performed two searches but consolidated them into one successful `b1` record. The supplementary search therefore lacked its own batch record: one missed batch.

`codex-recommend-01-r7` attempted to load a nonexistent aliased Skill path and did not retry the repository-scoped path. It searched twice and answered without an ordinary review record: two missed batches.

## Interpretation limits

Codex's raw execution trace does not expose the protocol's `result_used` event. This report therefore uses a conservative proxy: every observed search or supplied-results batch is treated as used, and a batch counts as reviewed only when the same run contains a distinct successful `ordinary-status` batch ID. Extra status calls cannot raise the numerator above the number of observed batches.

This verifies structural record coverage, not the correctness of the model's task-fit, source-identity, or factual-support judgments. The frozen human-validated semantic comparison required by the release protocol is still incomplete. For those reasons, this experiment is published as development evidence rather than formal Beta release evidence.

The machine-readable summary is [`eval/results/codex-coverage-2026-09-23.json`](../eval/results/codex-coverage-2026-09-23.json).
