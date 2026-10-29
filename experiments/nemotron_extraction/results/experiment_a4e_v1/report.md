# Experiment A4-E report

## Verdict

**FAIL — the grounding addendum improved mechanical acceptance, but the extraction layer is still not reliable enough to proceed to Experiment B.**

The addendum raised backend acceptance from 2/5 in A4-R2 to 4/5 without reintroducing reasoning tokens, truncation, invalid JSON, schema failures or character collapse. It did not pass the frozen grounding gate because case 001 still emitted the unsupported string `"null"`. It also failed the semantic gate: only three of six gold events and three of six expected signal presences were recovered, with case 008 again returning zero events despite three supported events.

## Frozen comparison

| Measure | A4-R2 | A4-E | A4-E gate |
|---|---:|---:|---:|
| Parseable JSON | 5/5 | **5/5** | 5/5 |
| Typed-schema valid | 5/5 | **5/5** | 5/5 |
| Backend accepted | 2/5 | **4/5** | 5/5 |
| Truncations | 0 | **0** | 0 |
| Backend-valid controls | 1/3 | **2/3** | 3/3 |
| Backend-valid recovery cases | 1/2 | **2/2** | 2/2 |
| Character-collapse cases | 0 | **0** | 0 |
| Reported reasoning tokens | 0 | **0** | 0 |
| Unsupported-literal failures | 3 | **1** | 0 |
| Gold events matched | 3/6 | **3/6** | 6/6 |
| Signal presence TP / extra / missing | 3 / 0 / 3 | **3 / 0 / 3** | 6 / 0 / 0 |
| Positive cases usable after validation | 0/4 | **2/4** | 4/4 |

A4-E used 29,301 prompt tokens and 1,834 completion tokens across the five calls. Every call stopped normally and reported zero reasoning tokens.

## Per-case findings

| Case | Role | Backend result | Semantic finding |
|---|---|---|---|
| 001 | control | `unsupported_literal_fact` | Found ACTOM and business expansion, but missed headcount growth, used the wrong stage/geographic level and emitted `"null"` as a string |
| 004 | recovery | Accepted | Found Float and funding expansion, but treated the planned expansion as the stage of the completed funding event and repeated the country as market/submarket |
| 008 | recovery | Accepted | Returned zero events despite three gold M&A/market-entry events; severe false negative |
| 010 | control | Accepted | Correct zero-event result |
| 017 | control | Accepted | Found SARS, RTO change and completed stage, but repeated the country as market/submarket and missed relative timing |

## Interpretation

The prompt addendum helped with literal grounding. It corrected the earlier unsupported company expansion in case 017 and the unsupported timing phrase in case 004, producing two newly usable positive outputs. It did not consistently enforce JSON nulls, and its synthetic examples did not prevent the model from copying a supported country name into unsupported market and submarket roles.

Backend acceptance remains necessary but insufficient for semantic quality. Cases 004 and 017 pass because each geographic value appears literally in its quotation, even though the value is assigned to the wrong geographic level. Case 008 demonstrates the larger limitation: a valid zero-event response can pass every deterministic validation while missing real events.

The experiment therefore isolates two remaining problems:

1. **Grounding/schema adherence:** one literal `"null"` survives despite an explicit instruction to use JSON null.
2. **Semantic extraction:** multi-event recall, secondary-signal recall, event-stage anchoring and geographic-role classification remain unreliable with reasoning disabled.

No production prompt, validator, model contract, database model, migration, persistence path or investigation behavior changed. A later experiment should not be called Experiment B yet; the next test needs to isolate semantic recall on the difficult cases or evaluate a supported bounded-reasoning/decomposition strategy without weakening deterministic validation.
