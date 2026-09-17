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

Each case row contains `case_id`, `input`, `topic_group`, `source_group` and `data_origin`. `input` follows `references/schema.md`; its `claims` may be empty because claim extraction is part of the evaluation. Each gold row contains `case_id`, `annotation_status` and `key_claims`. A key claim has an exact `anchor`, `expected_verdict`, `issue_codes`, `evidence` and `rationale`.

Each run row contains `case_id`, `method`, `run_id`, `status` (`completed`, `invalid_output`, or `runtime_error`), `report`, `usage` and `elapsed_seconds`. For a completed run, `report.findings` follows the reviewer report schema. `usage` may be `null`; otherwise record available `input_tokens`, `output_tokens`, `cached_tokens`, `model_requests` and `network_actions` as nonnegative integers, with unavailable values as `null`. Failed runs stay in the recall denominator. Store every scheduled run, including failures, and inspect `missing_case_ids` in scorer output.

After human validation, score saved runs with:

```bash
python3 eval/score.py --labels eval/labels-test.jsonl --runs work/eval/runs.jsonl --out work/eval/metrics.json
```

Until then, a pipeline smoke check can use `--allow-draft`. Its output is marked `annotation_status: provisional_draft` and must not be presented as measured efficacy. Without that flag, scoring draft labels fails.

Issue true positives require a one-to-one match on target/source/field, at least 0.5 span overlap relative to the longer span, and the same issue code **and** verdict. Duplicate findings cannot increase true positives. Precision has no value with zero predicted issues; recall has no value with zero expected issues. The scorer also reports claim-extraction coverage, verdict confusion, normal-claim false alarms, unavailable-as-contradicted errors, failures, missing cases, time and usage completeness. Review proposed replacement text separately for new unsupported facts; the scorer does not certify its semantics.

Unit tests validate these counting rules and CLI constraints. Offline `replay` examples validate report generation from saved synthetic judgments. Neither constitutes an independent model comparison.
