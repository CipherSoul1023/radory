# Experiment A5-D report

## Verdict

**FAIL — deterministic evidence decomposition did not recover case 008's events while reasoning remained disabled.**

Both non-overlapping chunks returned complete, parseable, typed and backend-valid `events: []` responses. The aggregate therefore also contained zero events. The frozen gold answer contains three supported events involving `ma_consolidation` and `market_entry`, so the semantic gate failed completely.

## Results

| Measure | A4-E full evidence | A5-D decomposed | A5-D gate |
|---|---:|---:|---:|
| Model calls | 1 | **2** | 2 |
| Parseable JSON | 1/1 | **2/2** | 2/2 |
| Typed-schema valid | 1/1 | **2/2** | 2/2 |
| Backend-valid outputs | 1/1 | **2/2** | 2/2 |
| Truncations | 0 | **0** | 0 |
| Reported reasoning tokens | 0 | **0** | 0 |
| Aggregate backend valid | Yes | **Yes** | Yes |
| Gold events matched | 0/3 | **0/3** | 3/3 |
| Signal presence TP / extra / missing | 0 / 0 / 2 | **0 / 0 / 2** | 2 / 0 / 0 |

The two calls used 7,451 prompt tokens and 28 completion tokens. Each response stopped normally after returning the minimal zero-event object.

## Evidence audit

Chunk 001 contains the January 2021 approved Greenstreet/SCDA 3 merger and the subsequently approved additional-shareholding transaction. Chunk 002 contains the approved Aker/Mainstream acquisition and explicitly states that the transaction will establish Aker's entry into South Africa. The source evidence needed for the frozen gold events is present inside the individual chunks; no cross-chunk inference is required to detect at least one event in either chunk.

## Interpretation

This result rules out document length and multi-section context as sufficient explanations for case 008's failure under the current reasoning-off configuration. Making the evidence shorter did not change the answer at all. The remaining leading explanation is that reasoning-disabled inference is too shallow for the model to map formal merger language and future-control language to Radory's signal catalogue.

The clean next isolation is to run the same two frozen chunks with normal reasoning restored. Smaller chunks may let reasoning finish within the unchanged 4,096-token budget, unlike the original full-document case that exhausted its reasoning allowance. That test must keep the evidence, grounding prompt, schema, model, validators and aggregation fixed and change only `enable_thinking`.

No production prompt, evidence preparation, model contract, validator, database model, migration, persistence path or investigation behavior changed.
