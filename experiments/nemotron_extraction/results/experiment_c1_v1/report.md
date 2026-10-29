# Experiment C1 fresh-holdout report

## Verdict

**FAIL — B2 remained technically reliable, but it did not pass the frozen semantic holdout gate.**

All 16 Nemotron Super responses were parseable, typed, backend-valid and complete. There were no truncations or invalid passage IDs. Across the six clear-scoring cases, predictions contained no extra event and no negative case produced a false-positive event. The holdout nevertheless failed because event recall was 66.7% and only three of six outcomes matched.

## Frozen holdout

C1 used the eight pilot cases excluded from Experiment A. None was used by the A-series reliability and semantic experiments or by B1/B2 tuning. Six cases use the existing clear scoring set; cases 014 and 018 retain their pre-existing manual-review designation and are reported outside the primary gate.

The original evidence was deterministically split into 16 non-overlapping chunks of at most 2,400 characters. The unchanged B2 indexed compact schema, system message, Super model, provider-default reasoning and 4,096-token allowance were used with zero retries.

## Results

| Measure | C1 result | Frozen gate |
|---|---:|---:|
| Provider calls | 16 | 16 |
| Parseable JSON | **16/16** | 16/16 |
| Typed-schema valid | **16/16** | 16/16 |
| Backend-valid chunks | **16/16** | 16/16 |
| Backend-valid case aggregates | **8/8** | 8/8 |
| Truncations | **0** | 0 |
| Invalid passage references | **0** | 0 |
| Clear exact event-count cases | **5/6** | at least 5/6 |
| Clear outcome matches | **3/6** | at least 5/6 |
| Clear event precision | **100%** | at least 80% |
| Clear event recall | **66.7%** | at least 80% |
| Clear signal precision | **80%** | at least 80% |
| Clear signal recall | **80%** | at least 80% |
| Clear negative cases with a false-positive event | **0/4** | 0 |

Provider-reported usage was 49,140 prompt tokens and 5,904 completion tokens, including 5,371 reasoning tokens, for 55,044 total tokens.

## Clear-case findings

Case 011 was the strongest positive result. The model returned one Global Political Solutions event with `market_entry`, `office_opening` and `leadership_buildout`, all directly supported by its cited passage. It also returned `business_expansion`; the title explicitly says the company expands operations into Sub-Sahara Africa, so this is a plausible overlapping label rather than an invented event.

Cases 013, 016, 019 and 023 correctly produced no events. Case 016 correctly used `assessed`. Cases 013, 019 and 023 used `insufficient_evidence` even though each page is understandable enough to conclude that no company event is present. This outcome-calibration problem caused three gate failures without creating false-positive events.

Case 021 exposed the substantive recall failure. The model correctly detected Nestle SA's retrenchments and cited the passage describing notices and severance discussions. It missed the separate sale of Nestle's remaining ice-cream operations to Froneri even though the same supplied and cited passage explicitly describes that transaction. Event recall therefore fell to two of three expected clear events.

## Manual-review cases

Case 014 returned assessed with no events. The working gold treats a SoluGrowth Office Manager vacancy as `workplace_hiring`; the evidence names the company and describes office-operations responsibilities, making that classification plausible. Recruitment-aggregator attribution was already marked ambiguous, so this miss does not affect the primary gate.

Case 018 correctly returned `insufficient_evidence` for a short facilities-manager search snippet that does not identify a supported company event.

## Execution note

The first run saved nine successful provider responses, then an offline aggregate step rejected case 014 because its six chunks contained 152 passages while the per-call evidence model allowed 100. The aggregate validator was changed to validate the already bounded chunk references against a combined passage map without constructing another provider-input model. Prefix-safe resume then made only the seven remaining calls. No completed request was repeated, no model output was repaired and gold remained unavailable until all 16 responses and eight aggregates were saved.

## Interpretation

B2's indexed evidence and compact structured output solve the earlier mechanical failures: output formatting, truncation, copied-quotation corruption and invalid evidence references were all clean on this holdout. The remaining problems are semantic:

1. Super can stop after the primary event and miss a distinct secondary event in the same passage.
2. Super overuses `insufficient_evidence` when it can understand the evidence and should return `assessed` with no events.
3. Overlapping signal policy remains visible for `business_expansion`, although the extra case-011 label is textually defensible.

The next experiment should change only first-pass semantic instructions: require a complete passage-by-passage event inventory before output and sharpen the difference between assessed-zero and insufficient evidence. It should retest this holdout plus separate untouched cases before detailed pass-two extraction begins. Persistence and investigation should remain paused.

No production prompt, extraction contract, validator, database model, migration, search execution or investigation behavior changed.
