# Evaluation protocol

This directory contains an evaluation *scaffold*, not a measured improvement. `cases-dev.jsonl` has 12 synthetic development cases; `cases-test.jsonl` has 24 synthetic candidate holdout cases. Their labels are model-authored drafts (`draft_model_authored_not_human_validated`). The cases are short and stylized, and their `topic_group` / `source_group` values are case identifiers rather than a verified independence split. Do not publish accuracy or hallucination-reduction claims from these files as-is.

## Before a real comparison

1. Have a human check each source and answer, mark every decision-relevant claim with an exact character span, expected verdict, issue code, evidence and rationale. Resolve disagreements or record disputed claims separately. Change a case's `annotation_status` to `human_validated` only after that check. Keep the checked labels out of every review prompt and tool response.
2. Freeze the test cases and labels before reviewing model outputs. Add real, permission-safe examples across source existence/identity, quotations/numbers/scope, correct answers, and inaccessible or partial sources. Split by actual upstream source and topic; do not treat the current synthetic per-case group names as proof against leakage.
3. Run the same model, version, context, input evidence and maximum search/read budget for all three methods. Record the full prompt/skill version, tool observations, failed calls, elapsed time and available usage. If the host cannot expose usage, store `null`, not zero.

| Method | Reviewer instructions |
|---|---|
| `generic_prompt` | Ask for a citation and factuality audit with the shared output schema. |
| `rules_only` | Provide `references/review-rules.md` but no CLI/workflow. |
| `full_skill` | Use `SKILL.md`, its references and the CLI. |

Use one completed or failed run for every scheduled case and method. A first comparison is 24 cases × 3 methods × 1 model × 1 repetition = 72 scheduled runs. The present repository contains no such run set. Report the model/version and single-run limitation; do not infer cross-model or repeatability gains.

## Files and scoring

Each case row contains `case_id`, `input`, `topic_group`, `source_group` and `data_origin`. `input` follows `references/schema.md`; its `claims` may be empty because claim extraction is part of the evaluation. Each gold row contains `case_id`, `annotation_status` and `key_claims`. A human-validated key claim has an exact `anchor`, `expected_verdict`, `issue_codes`, `evidence`, `rationale` and boolean `serious`. Set `serious: true` only when accepting the claim as supported would change the answer or recommendation despite a clear hard-condition violation or missing critical evidence.

Each run row contains `case_id`, `method`, `run_id`, `status` (`completed`, `invalid_output`, or `runtime_error`), `report`, `usage` and `elapsed_seconds`. For a completed run, `report.findings` follows the reviewer report schema. `usage` may be `null`; otherwise record available `input_tokens`, `output_tokens`, `cached_tokens`, `model_requests` and `network_actions` as nonnegative integers, with unavailable values as `null`. Failed runs stay in the recall denominator. Store every scheduled run, including failures, and inspect `missing_case_ids` in scorer output.

After human validation, score saved runs with:

```bash
python3 eval/score.py --labels eval/labels-test.jsonl --runs work/eval/runs.jsonl --out work/eval/metrics.json
```

Until then, a pipeline smoke check can use `--allow-draft`. Its output is marked `annotation_status: provisional_draft` and must not be presented as measured efficacy. Without that flag, scoring draft labels fails.

Issue true positives require a one-to-one match on target/source/field, at least 0.5 span overlap relative to the longer span, and the same issue code **and** verdict. Duplicate findings cannot increase true positives. Precision has no value with zero predicted issues; recall has no value with zero expected issues. The scorer also reports claim-extraction coverage, verdict confusion, normal-claim false alarms, unavailable-as-contradicted errors, failures, missing cases, time and usage completeness. Review proposed replacement text separately for new unsupported facts; the scorer does not certify its semantics.

Unit tests validate these counting rules and CLI constraints. Offline `replay` examples validate report generation from saved synthetic judgments. Neither constitutes an independent model comparison.

## Ordinary Skill coverage evaluation

The primary Beta metric comes from complete Codex execution traces, not from skill-loading logs. Start from a clean repository-link installation with no development symlink and a new conversation. Use the balanced task list in `cases-codex-beta.jsonl`; run enough scheduled tasks and repetitions to observe at least 100 real search-result batches. Retain completed, failed, timed-out, invalid, and untriggered runs.

For every run, record the metadata and ordered events defined in `references/schema.md`. A batch is covered only when every result used by the answer has a valid ordinary batch review before its first `result_used` event. Score saved traces with:

```bash
python3 eval/coverage.py \
  --manifest work/eval/run-manifest.jsonl \
  --runs work/eval/codex-runs.jsonl \
  --out work/eval/coverage.json
```

Create and freeze `work/eval/run-manifest.jsonl` before running; `run-manifest.example.jsonl` shows one repetition. Expand it to the intended repetitions rather than editing the schedule after seeing results. The report exposes scheduled runs that never produced a trace in `missing_run_ids`.

The report keeps skill activation rate as a diagnostic and reports failures as `skill_not_activated`, `review_skipped`, or `incomplete_review_record`. Non-search controls are excluded from the activation-rate denominator and reported through `negative_control_false_activation_rate`. Semantic misjudgment is deliberately not inferred from event order; assess it with frozen human labels and `score.py`.

The coverage denominator is batches whose results influenced an answer or decision. `observed_batches` includes every returned batch and is used for the 100-batch minimum. Zero-result batches are retained and reported separately but cannot be “used” as evidence.

## Beta release assessment

After the real trace run and human semantic review, store the three local verification booleans shown in `checks-template.json`, then combine the evidence:

```bash
python3 eval/release.py \
  --coverage work/eval/coverage.json \
  --semantics work/eval/semantic-metrics.json \
  --checks work/eval/checks.json \
  --out work/eval/release.json
```

`ready: true` requires at least 100 observed batches, at most 5 missed-review batches, human-validated semantic labels, zero serious false acceptances for `full_skill`, a reproducible clean installation, passing deterministic tests, and passing documentation checks. Do not publish Beta reliability claims while any gate is false. Preserve the raw JSONL traces, frozen labels, prompts, skill revision, Codex version, model/settings, failures, elapsed time and available usage alongside the report.
