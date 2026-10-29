# Experiment A5-R report

## Verdict

**FAIL — default reasoning recovered correct semantic signals, but one of the two chunks still exhausted the 4,096-token completion allowance.**

A5-R changed only the reasoning control from A5-D. The reasoning-off baseline returned zero events from both chunks. With default reasoning restored, chunk 002 produced a fully grounded Aker acquisition event matching all frozen gold fields and both expected signal types. Chunk 001 recognized the Greenstreet/Stanlib transactions in its partial answer but stopped for length before completing valid JSON, so neither of those events could be accepted.

## Results

| Measure | A5-D thinking off | A5-R default reasoning | A5-R gate |
|---|---:|---:|---:|
| Model calls | 2 | **2** | 2 |
| Parseable JSON | 2/2 | **1/2** | 2/2 |
| Typed-schema valid | 2/2 | **1/2** | 2/2 |
| Backend-valid chunks | 2/2 | **1/2** | 2/2 |
| Truncations | 0 | **1** | 0 |
| Reported reasoning tokens | 0 | **4,691** | observed only |
| Aggregate events | 0 | **1** | 3 |
| Gold events matched | 0/3 | **1/3** | 3/3 |
| Signal presence TP / extra / missing | 0 / 0 / 2 | **2 / 0 / 0** | 2 / 0 / 0 |

The two calls used 7,451 prompt tokens and 6,389 completion tokens. Chunk 001 used 3,029 reasoning tokens and finished with `length`. Chunk 002 used 1,662 reasoning tokens, stopped normally and returned one accepted event.

## Manual semantic review

The accepted chunk-002 event matched the frozen Aker gold event on company, the combined `ma_consolidation` and `market_entry` signals, planned stage, South Africa country value and timing. All eight evidence quotations matched the supplied chunk.

Chunk 001's incomplete answer contained a complete first Greenstreet/SCDA 3 event and had started the subsequent Stanlib event when generation stopped. This output cannot be parsed or persisted, but it demonstrates that default reasoning found the evidence that the thinking-off run completely missed.

## Interpretation

For this case, semantic recall depends materially on reasoning. Evidence decomposition helped enough for one of the two reasoning-enabled calls to finish with an exact event, but a 2,352-character chunk containing two related transactions remained too complex for the 4,096-token completion allowance.

This result does not justify enabling unrestricted reasoning in production: its completion behavior remains unreliable. It does, however, narrow the next isolation. The first chunk should be decomposed more finely using a frozen deterministic rule while retaining default reasoning. That test would determine whether one-event-scale chunks can preserve the semantic gain and avoid truncation without relying on an unsupported reasoning-budget parameter.

No production prompt, evidence preparation, model contract, validator, database model, migration, persistence path or investigation behavior changed.
