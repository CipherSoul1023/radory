# Experiment A3: strict provider schema without regex patterns

## Decision

**FAIL — continue technical isolation**

Removing regex `pattern` constraints from the Nebius-facing strict schema fixed
the character-collapse failure on the 16 real-evidence cases, but A3 did not
pass the frozen technical gate. It is not technically reliable enough to proceed
to Experiment B.

A3 used `nvidia/nemotron-3-super-120b-a12b`, the exact frozen Experiment A case
selection, unchanged prompt/evidence/gold/backend validators, and a fixed 4,096
output-token allowance. It made 16 calls with no retries. Experiment B was not
started.

## Output-budget choice

The 4,096-token setting was frozen before execution because:

- A1 had zero truncations at 4,096.
- A2 still truncated a case at 8,192 when reasoning consumed almost the whole
  allowance.
- The compatibility probe removed character collapse at 4,096.
- Matching A1 makes provider-schema pattern removal the only request difference.

The budget was not increased during the run.

## Technical comparison

All counts use the same selected 16 cases. Character collapse counts audited
company names, summaries, related-company text, location/date text and evidence
quotes; enum values and block IDs are excluded.

| Metric | Historical | A1 strict / 4,096 | A2 strict / 8,192 | A3 no patterns / 4,096 |
| --- | ---: | ---: | ---: | ---: |
| Parseable JSON | 14/16 | 16/16 | 15/16 | 14/16 |
| Typed-schema valid | 11/16 | 16/16 | 14/16 | **13/16** |
| Backend accepted | 6/16 | 12/16 | 7/16 | **11/16** |
| Truncations | 1 | 0 | 1 | **2** |
| Backend-valid controls | 6/6 | 4/6 | 3/6 | **6/6** |
| Character-collapse cases | 0 | 14 | 14 | **0** |
| Character-collapse occurrences | 0 | 179 | 179 | **0** |
| Unmatched evidence quote | 2 | 4 | 4 | **1** |
| Unsupported literal fact | 3 | 0 | 3 | **1** |
| Incomplete response | 1 | 0 | 1 | **2** |
| Invalid schema response | 4 | 0 | 1 | **1** |

Frozen A3 gate:

| Requirement | Result | Pass? |
| --- | ---: | :---: |
| Typed schema | 16/16 required; 13/16 observed | No |
| Backend accepted | At least 15/16; 11/16 observed | No |
| Truncations | 0 required; 2 observed | No |
| Backend-valid controls | 6/6 required; 6/6 observed | Yes |
| Character collapse | 0 required; 0 observed | Yes |

## Remaining A3 failures by category

### Output-schema / backend contract gap

- `pilot-v1-003`: valid JSON and a provider-schema-conforming response, but the
  unchanged Pydantic validator rejected a location record whose country, market
  and submarket were all null. This is an `invalid_output_schema` result from a
  custom backend invariant that the provider schema did not enforce. The factual
  downsizing event was otherwise expressed with complete text.

### Truncation / reasoning-budget failures

- `pilot-v1-004`: `finish_reason=length`; all 4,096 completion tokens were
  reported as reasoning tokens and no parseable answer was returned.
- `pilot-v1-008`: the same failure: all 4,096 completion tokens were reasoning
  tokens and no parseable answer was returned.

These are real A3 gate failures. The run did not retry them or increase the
budget.

### Exact-evidence validation failures

- `pilot-v1-012`: `unmatched_evidence_quote`. The model produced a readable
  Telkom quotation but silently removed Markdown link markup around the CEO's
  name. Three claims reused that altered quotation, so it was not an exact
  contiguous substring of supplied evidence.
- `pilot-v1-015`: `unsupported_literal_fact`. The output labelled `Gauteng` as a
  market while citing a quote containing `JOHANNESBURG`; it also normalized
  Markdown/spacing in the timing quote (`By Reuters · 24 Oct 2012`). Backend
  validation correctly rejected the result. This combines semantic geography
  error with exact-quotation normalization.

No output was repaired or normalized after generation.

## Manual review of all six controls

All controls were parseable, typed-schema valid and backend accepted. Company
names, summaries, supporting passages, dates and locations were complete rather
than character fragments. That confirms the pattern-removal finding on real
evidence. Semantic quality still has issues:

| Control | Manual finding |
| --- | --- |
| 001 ACTOM | Complete company, summary, evidence, two expected signals, stage and Pretoria geography. No material regression; geography was more specifically separated into Pretoria / Pretoria West. |
| 002 Rentoza | Complete main business-rescue event, date and evidence; matches the historical control. It omitted the separate 2022 funding/expansion event in gold. `Sandton-based` was treated as the event market, which is debatable. |
| 005 ENGIE | Complete leadership event and date; expected signal present. It omitted the earlier separate leadership appointment in gold and incorrectly repeated `South Africa` as country, market and submarket. |
| 010 negative | Correctly returned `assessed` with zero events. |
| 017 SARS | Complete company, RTO summary, quotation and country. It omitted gold's `now` timing and retained `underway` rather than gold's `completed`; the historical control also used `underway`, but did include `now`. |
| 024 Pictet & Cie | Complete office-opening evidence and country. It added `business_expansion` where gold expects `market_entry`, and treated `has opened its first office` as an unclear timing expression although gold leaves timing empty. |

The controls therefore recovered mechanically from A1/A2's collapse, but they
did not establish semantic readiness.

## Frozen-gold diagnostics

These are literal diagnostics, not an accuracy claim; known gold-review caveats
remain unchanged.

| Metric | Historical | A1 | A2 | A3 |
| --- | ---: | ---: | ---: | ---: |
| Outcome matches | 11/16 | 15/16 | 14/16 | 12/16 |
| Event-count matches | 6/16 | 9/16 | 8/16 | 7/16 |
| Gold events matched | 10/24 | 13/24 | 10/24 | 11/24 |
| Gold events missing | 14 | 11 | 14 | 13 |
| Extra events | 0 | 1 | 3 | 0 |
| Signal presence true positives | 11 | 13 | 13 | 11 |
| Signal presence extra vs gold | 2 | 5 | 2 | 3 |
| Signal presence missing vs gold | 13 | 11 | 11 | 13 |
| Signal precision | 0.846 | 0.722 | 0.867 | 0.786 |
| Signal recall | 0.458 | 0.542 | 0.542 | 0.458 |

A3 restored complete literal values: subject-company literal matches rose from
zero in A1/A2 to 10, while geography and timing still showed semantic omissions
or misclassification. A3's 11 backend-accepted cases include nine usable positive
cases under the existing comparator; that remains below the technical gate and
does not authorize persistence.

## Usage

| Usage | A3 |
| --- | ---: |
| Calls | 16 |
| Prompt tokens | 82,266 |
| Completion tokens | 32,530 |
| Total tokens | 114,796 |
| Reasoning tokens (included in completion) | 26,425 |
| Summed request duration | 183.143 seconds |

## Integrity and boundary

- Exact A3 requests and full provider responses are preserved under ignored
  `results/local/experiment_a3_v1/`.
- Reviewable predictions, comparison, control review and metrics are isolated in
  this directory; A1, A2 and the compatibility probe were not overwritten.
- The live runner did not load gold answers. Frozen gold was loaded only by the
  offline comparator after all 16 responses were saved.
- Production extraction code, Pydantic models, validators, signal catalogue,
  database and migrations were unchanged.
- Experiment B, persistence and investigation were not started.

Removing regex patterns solves the character-collapse symptom, but the remaining
typed-schema gap, exact-evidence failures and reasoning-budget truncations require
continued technical isolation before semantic prompt tuning.

FRAGILE DECISIONS ENCOUNTERED:
- None enacted. No production provider-schema representation, reasoning setting,
  token budget or validation behavior was changed.
