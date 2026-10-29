# Experiment A: output reliability

**Decision: neither configuration passes. Stop before semantic prompt tuning,
fresh holdout evaluation, or observation persistence.**

The 32 authorized live calls are complete. Model:
`nvidia/nemotron-3-super-120b-a12b`, through Nebius. No retries or extra inference
calls were made. No production code, database, migrations, or credentials changed.

## Frozen experiment

Each arm used the same 16 cases: ten historical failures
(003, 004, 006, 007, 008, 009, 012, 015, 020, 022) and six previously accepted
controls (001, 002, 005, 010, 017, 024). IDs have the prefix `pilot-v1-`.
There are 12 raw-content cases and four snippet cases per arm.

- A1: existing messages and 4,096-token limit; add strict JSON-schema output.
- A2: same messages and schema; increase only the limit to 8,192 tokens.
- Semantic prompt, prepared evidence, gold answers, model, backend validators,
  timeout, and unspecified provider sampling/reasoning defaults stayed fixed.
- Gold answers were loaded by offline comparison after both arms were saved,
  never supplied to the live runner.

The request used the existing Pydantic output model's JSON Schema unchanged.
The provider documents this output mechanism in its
[structured-output documentation](https://docs.tokenfactory.nebius.com/ai-models-inference/json).
Request acceptance does not establish semantic correctness or enforcement of
Python validators.

## Results

The historical column includes only the same selected 16 cases, not the full
24-case pilot. It is a historical reference, not a newly repeated baseline.

| Check | Historical | A1: schema / 4,096 | A2: schema / 8,192 | Required per arm |
| --- | ---: | ---: | ---: | ---: |
| Parseable JSON | 14/16 | 16/16 | 15/16 | 16/16 |
| Typed schema valid | 11/16 | 16/16 | 14/16 | 16/16 |
| Backend accepted | 6/16 | 12/16 | 7/16 | At least 15/16 |
| Truncated responses | 1 | 0 | 1 | 0 |
| Backend-accepted controls | 6/6 | 4/6 | 3/6 | 6/6 |
| Technical acceptance gate | Fail | **Fail** | **Fail** | Pass |

At this sample size, the 95% typed-schema target requires all 16 cases and the
90% backend-valid target requires at least 15. Backend acceptance is only a
mechanical validation result, not proof of usable semantic extraction.

## Critical semantic regression

Both arms returned single-character company values in **all 14 parseable
positive responses per arm**. For example, control 001 returned `A` instead of
ACTOM and control 002 returned `R` instead of Rentoza. Other free-text facts,
summaries, and evidence quotes also collapsed to characters. These values exist
in the saved provider responses; the exporter did not shorten them.

All five positive controls regressed in both arms, including some that passed
backend validation. The negative control 010 remained `assessed` with zero
events. A1 case 008 returned `insufficient_evidence` with zero events; its lack
of truncation must not be counted as recovery of the relevant event.

The current validator accepts nonempty strings and checks literal attachment
to supplied evidence. A one-character value supported by a matching character
can satisfy those mechanical checks without representing the company or event.
This exposed a validation blind spot. No validator was weakened or changed.

The request schema contains the nonblank-text pattern `\S`. A possible
interaction between that pattern and provider schema decoding merits a minimal
compatibility test. **The cause of the character collapse is not yet proven.**
It would be premature to attribute this to model capability generally, or to
declare that changing this regex alone fixes it.

The comparison's `positive_cases_usable_after_validation` field is inherited
from the earlier comparator and counts mechanically accepted positive outputs.
It does **not** mean these character-only outputs are usable. The semantic
review above takes precedence over that misleading metric label.

## Failure details

- A1: four `unmatched_evidence_quote` failures: 005, 006, 017, 020.
- A2: four `unmatched_evidence_quote` failures: 001, 006, 009, 012;
  three `unsupported_literal_fact` failures: 002, 007, 020;
  one `incomplete_model_response`: 008; and one `invalid_output_schema`: 024.
- A2 case 024 contains an all-null location rejected by the existing Python
  validator. JSON-schema conformance alone cannot enforce all custom validators.
- A2 case 008 reached 8,192 completion tokens, including 8,146 reported reasoning
  tokens. Increasing the total output allowance did not prevent truncation.
- There were no provider HTTP errors recorded in either arm.

## Usage and limitations

| Usage | A1 | A2 | Combined new calls |
| --- | ---: | ---: | ---: |
| Calls | 16 | 16 | 32 |
| Prompt tokens | 82,266 | 82,266 | 164,532 |
| Completion tokens | 30,291 | 39,307 | 69,598 |
| Total tokens | 112,557 | 121,573 | 234,130 |
| Reasoning tokens (included in completion) | 26,117 | 35,131 | 61,248 |

One response per case per arm cannot establish repeatability or a causal effect
of the token limit. These are development cases selected partly for previous
failures, not an unbiased accuracy estimate or fresh holdout. Gold comparisons
are diagnostic only; the known gold-review caveats remain unchanged.

## Verification and artifacts

- All 32 saved requests match frozen messages, input fingerprints, model,
  schema, and the relevant arm's token allowance exactly.
- Saved raw responses match the prediction records; parsed predictions match
  the provider's JSON content without repair or normalization.
- Frozen plan, runner, production-source hashes, historical predictions, label
  pack, gold answers, and gold-review hashes were verified unchanged.
- Both prediction files have 16 cases in the frozen order; comparison has 32
  case/arm records.
- Targeted offline suite: 72 tests passed. Experiment script lint and
  `git diff --check` passed.

Reviewable artifacts in this directory:

- `a1_schema_4096_predictions.jsonl`: complete first-arm outputs.
- `a2_schema_8192_predictions.jsonl`: complete second-arm outputs.
- `metrics.json`: structural counts, token usage, and diagnostic gold metrics.
- `comparison.jsonl`: per-case comparisons and control signatures.

Exact requests, responses, run metadata, and detailed control review are under
ignored `results/local/experiment_a_v1/`. Existing evidence remains under
ignored `data_local/pilot_v1/`. Nothing was committed during this task.

## Recommended next step

Keep Experiment B, fresh holdout C, and persistence paused. First isolate
schema/decoder compatibility with a tiny synthetic example containing a
multi-character company and a complete supporting sentence. Compare the
current string constraints with an equivalent full-string nonblank constraint,
changing only the provider schema representation and preserving backend
validation. Define semantic control checks that reject collapsed claims before
running another real-evidence batch. Do not silently repair predictions or
lower the acceptance targets.

This is a recommendation, not an additional experiment executed here. Changes
to production validation, the semantic contract, or a materially larger call
budget require separate review.

FRAGILE DECISIONS ENCOUNTERED:
- None enacted. No production contract or validation changes were made in
  response to the failures.
