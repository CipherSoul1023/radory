# Experiment B1 report

## Verdict

**FAIL — compact detection removed the observed truncation, but it did not pass the frozen technical or semantic gate.**

Both Nemotron Super calls completed with `finish_reason: stop` under the unchanged 4,096-token allowance. This confirms that removing detailed second-pass fields materially reduced output pressure. One of the two chunks nevertheless failed exact evidence validation, and the valid chunk did not preserve the expected event boundary.

## Results

| Measure | A5-R verbose extraction | B1 compact detection | B1 gate |
|---|---:|---:|---:|
| Calls | 2 | **2** | 2 |
| Parseable JSON | 1/2 | **2/2** | 2/2 |
| Typed-schema valid | 1/2 | **2/2** | 2/2 |
| Backend-valid chunks | 1/2 | **1/2** | 2/2 |
| Truncations | 1 | **0** | 0 |
| Reported reasoning tokens | 4,691 | **4,141** | observed only |
| Prompt tokens | 7,451 | **5,171** | observed only |
| Completion tokens | 6,389 | **5,004** | observed only |
| Aggregate gold events matched | 1/3 | **1/3** | 3/3 |
| Aggregate extra events | 0 | **2** | 0 |
| Unmatched evidence quotations | not comparable | **2** | 0 |

The B1 aggregate contains only backend-valid chunk outputs. Since chunk 001 failed validation, its two semantically relevant Stanlib events were not included. Chunk 002 contributed three accepted records, but only one matched a frozen gold event under company-aware matching.

## Per-chunk findings

Chunk 001 completed after 1,362 reasoning tokens and identified both Stanlib acquisition events. Its first transaction quotation changed corrupted quotation characters present in the prepared input. The quote was therefore not an exact substring, causing both its company and signal evidence references to fail validation. The second transaction quotation was exact. Because validation operates on the chunk output as a unit, the valid second event was not included in the aggregate.

Chunk 002 completed after 2,779 reasoning tokens and returned contract-valid, grounded output. It recognized Aker's market entry and the Aker/Mainstream acquisition. It represented those facts as two separate Aker records and a third Mainstream record. The frozen gold represents the transaction as one Aker event with both signals and treats Mainstream as the counterparty, so B1 introduced an extra event and failed to group the two signals onto the same real-world event.

## Interpretation

The compact two-pass direction remains promising specifically for token reliability: the same evidence and model that truncated under the verbose contract completed both compact calls. B1 does not yet establish a reliable first pass. Two issues remain isolated:

1. The model can alter unusual source characters while attempting to quote verbatim, which causes exact-evidence validation failure.
2. The compact prompt does not yet enforce a stable event identity rule strongly enough to combine multiple signals for one transaction or avoid a duplicate counterparty event.

The next experiment should change only the compact first-pass representation or instructions for evidence references and event identity. It should retain Nemotron Super, default reasoning, the frozen chunks and the compact field scope. Detailed stage, geography, timing and summary extraction should remain out of scope until first-pass event detection passes its own gate.

No production prompt, extraction contract, validator, persistence model, migration, search execution, or investigation behavior changed.
