# Experiment B2 report

## Verdict

**PASS — indexed evidence and explicit transaction grouping passed the frozen technical and semantic event-detection gates.**

Both Nemotron Super calls completed under the unchanged 4,096-token allowance. Both responses were parseable, schema-valid and backend-valid, and every cited passage ID existed. The aggregate contained exactly the three frozen gold events with no missing or extra event and both expected signal types.

This is a pass for the isolated case-008 compact first-pass experiment. It is not evidence that the design generalizes across the wider corpus.

## Results

| Measure | B1 exact quotations | B2 indexed passages | B2 gate |
|---|---:|---:|---:|
| Calls | 2 | **2** | 2 |
| Parseable JSON | 2/2 | **2/2** | 2/2 |
| Typed-schema valid | 2/2 | **2/2** | 2/2 |
| Backend-valid chunks | 1/2 | **2/2** | 2/2 |
| Truncations | 0 | **0** | 0 |
| Invalid evidence references | 2 unmatched quotes | **0 invalid passage IDs** | 0 |
| Reported reasoning tokens | 4,141 | **1,907** | observed only |
| Prompt tokens | 5,171 | **6,494** | observed only |
| Completion tokens | 5,004 | **2,220** | observed only |
| Aggregate gold events matched | 1/3 | **3/3** | 3/3 |
| Aggregate missing / extra events | 2 / 2 | **0 / 0** | 0 / 0 |

B2 used 42 passage instances across the two calls: 32 in chunk 001 and 10 in chunk 002. The repeated title had the same deterministic passage ID in both chunks and was collapsed once only during offline aggregation. No model response was repaired or normalized.

## Per-chunk findings

Chunk 001 completed after 919 reported reasoning tokens. It returned the January 2021 joint-control transaction and the later additional-shareholding transaction as separate Stanlib M&A events. Each event cited the paragraph that directly describes it. Passage IDs avoided B1's failure where unusual source characters changed while the model copied a quotation.

Chunk 002 completed after 988 reported reasoning tokens. It returned one Aker Horizons event containing both `ma_consolidation` and `market_entry`, and did not create a second event for Mainstream. This fixes B1's event-boundary and counterparty duplication errors.

Manual review found one citation-precision caveat. The Aker M&A signal correctly cites the acquisition paragraph, but its evidence list also includes one paragraph about the earlier Stanlib transaction and the Aker/Mainstream section heading. The claim remains directly supported by another cited passage, so the frozen gate passes, but later validation should measure irrelevant surplus references rather than checking ID existence alone.

## Execution note

Both provider calls completed and were saved before a local aggregate step detected a duplicate passage ID for the title repeated across chunks. The aggregator was fixed to collapse only byte-equivalent repeated passages and reject conflicting duplicates. The aggregate was then rebuilt from the two saved backend-valid responses with zero additional provider calls.

## Interpretation

B2 supports the compact two-pass direction:

1. Deterministic passage IDs are more reliable than asking the model to reproduce exact quotations containing damaged or unusual characters.
2. Explicit transaction identity rules can make Super group multiple signals onto one event and avoid duplicate counterparty events.
3. Compact first-pass output leaves enough completion capacity for reasoning without truncation on this difficult case.

The next responsible step is a frozen fresh holdout covering multiple event shapes, irrelevant evidence, multiple companies and zero-event cases. That holdout should measure event recall, duplicate events, signal accuracy, invalid passage IDs and irrelevant surplus citations. Detailed pass-two extraction, observation persistence and investigation should remain paused until the first-pass behavior generalizes.

No production prompt, extraction contract, validator, persistence model, migration, search execution or investigation behavior changed.
