# Nemotron schema compatibility probe

**Result: the current strict provider schema reproduces the single-character
collapse. Removing only its regex `pattern` keywords eliminates the collapse in
this probe while retaining strict structural output. JSON-object mode also
eliminates the collapse. No mode passed the complete frozen acceptance gate.**

This disposable experiment used `nvidia/nemotron-3-super-120b-a12b` through the
configured Nebius endpoint. It made 12 calls: four short synthetic cases across
three response-format modes. There were no retries, provider HTTP errors,
production changes, database writes, or real-evidence searches.

## Controlled comparison

All modes received identical system instructions, signal catalogue, embedded
output schema, user evidence, model, 4,096-token limit, timeout, and unspecified
provider sampling/reasoning defaults. Only the API `response_format` changed:

1. `strict_current`: the unchanged Pydantic JSON Schema with strict output.
2. `strict_without_patterns`: the same strict provider schema with only three
   regex `pattern` keywords removed. All types, required fields, enums, length
   limits, array bounds, references, and `additionalProperties` rules remained.
3. `json_object`: JSON-object mode without a provider-enforced schema.

The production Pydantic model and backend validator remained unchanged in all
three modes. Expected synthetic answers were never included in model messages.

## Results

| Check | Strict current | Strict without patterns | JSON object | Frozen target |
| --- | ---: | ---: | ---: | ---: |
| Parseable JSON | 4/4 | 4/4 | 4/4 | 4/4 |
| Typed schema valid | 4/4 | 4/4 | 4/4 | 4/4 |
| Backend accepted | 2/4 | 4/4 | 4/4 | 4/4 |
| Truncations | 0 | 0 | 0 | 0 |
| Collapsed free-text occurrences | 32 | 0 | 0 | 0 |
| Exact semantic-anchor matches | 1/4 | 2/4 | 2/4 | 4/4 |
| Complete acceptance gate | **Fail** | **Fail** | **Fail** | Pass |

The strict-current mode collapsed every positive case. Company names, summaries,
locations, timing expressions, and evidence quotes became single characters such
as `B`, `S`, and `北`. The negative zero-event case remained correct. One positive
collapsed response passed backend validation because the character `S` genuinely
appeared in its evidence, confirming the previously observed validation blind
spot.

Both alternatives returned full company names, summaries, locations/timing when
selected, and complete supporting passages. All eight alternative responses
passed the unchanged typed contract and backend validator.

## Frozen semantic-anchor failures

The evaluator was not relaxed after seeing results:

- Strict-without-patterns case 002 correctly found Bluebird Finance,
  `rto_change`, and `planned`, but omitted the explicitly stated Cape Town
  location. It returned the supported timing expression
  `starting 1 September 2027` while the frozen anchor required exact equality to
  `1 September 2027`.
- JSON-object case 002 included Cape Town but used the same longer, supported
  timing expression, so it also failed exact anchor equality.
- Both alternative modes classified the Solaris Data case as `market_entry` but
  omitted the frozen secondary `business_expansion` classification. The company,
  completed stage, Johannesburg, South Africa, and May 2027 were correct.
- The office-opening case and zero-event negative case matched every frozen
  anchor in both alternative modes.

The longer timing expression is not a hallucination or evidence-attachment
failure. The second signal is a genuine classification disagreement on a
synthetic case that supports overlapping catalogue concepts. These observations
explain the metric; they do not retroactively turn either gate into a pass.

## Interpretation

This controlled result is strong evidence that the provider's handling of the
regex `pattern` keywords in this strict response schema triggers the character
collapse. The strict modes differed only by those keywords, and all three
positive cases changed from collapsed values to full text when they were
removed. JSON-object mode independently produced full text.

The probe has one response per case and mode, so it does not establish
repeatability or prove the provider's internal mechanism. It also does not test
real Tavily evidence or overall semantic accuracy. The production `pattern`
validation still serves a useful purpose: rejecting whitespace-only values.
Removing it from backend validation based on this probe would be unjustified.

The safest candidate is a **provider-facing schema without regex patterns while
retaining the full Pydantic contract and validation after the response**. This
preserves more structural enforcement than JSON-object mode. It remains an
experiment candidate until it succeeds on real evidence.

## Usage

| Usage | Strict current | Strict without patterns | JSON object | Total |
| --- | ---: | ---: | ---: | ---: |
| Calls | 4 | 4 | 4 | 12 |
| Prompt tokens | 11,494 | 11,494 | 11,494 | 34,482 |
| Completion tokens | 4,587 | 5,509 | 4,728 | 14,824 |
| Total tokens | 16,081 | 17,003 | 16,222 | 49,306 |
| Reasoning tokens (included above) | 3,816 | 4,319 | 3,601 | 11,736 |

## Verification and next boundary

- All 12 saved requests exactly match the frozen case, mode, model, messages,
  token limit, and response format.
- Saved raw provider responses exactly match the reviewable prediction records;
  no output repair or normalization occurred.
- Runner, plan, and production-source hashes were verified; production files
  remained unchanged.
- No HTTP errors or configured secret values were found in reviewable artifacts.
- Exact request/response records remain under ignored
  `results/local/schema_compatibility_v1/`.

The next evidence-producing step should be an experiment-only A3 arm on the same
16 real cases used by Experiment A, using the strict provider schema without
regex patterns and the unchanged backend validator. Its criteria should retain
the prior structural gate and explicitly reject collapsed factual values. Do not
change production transport, semantic prompts, persistence, or investigation
logic before that real-evidence result is reviewed.

FRAGILE DECISIONS ENCOUNTERED:
- Pending: whether to adopt a provider-specific schema representation without
  regex patterns. This affects external model behavior and should not enter
  production until the real-evidence A3 arm confirms it.
