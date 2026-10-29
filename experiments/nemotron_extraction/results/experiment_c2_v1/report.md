# Experiment C2 result

Experiment C2 changed only the B2 system prompt. It added a passage-by-passage completeness check, an explicit secondary-event re-scan and a sharper distinction between `assessed` with no events and `insufficient_evidence`. It reused C1's eight development cases, exact evidence chunks, Super model, provider-default reasoning, strict pattern-free schema, 4,096-token limit, validators and zero-retry policy.

## Result

**FAIL — do not freeze the C2 prompt or begin detailed extraction.**

C2 fixed outcome calibration but did not improve event recall. It also regressed chunk-level grounding reliability.

| Metric | C1 | C2 |
| --- | ---: | ---: |
| Parseable JSON | 16/16 | 16/16 |
| Typed-schema valid | 16/16 | 16/16 |
| Backend-valid chunks | 16/16 | 15/16 |
| Truncations | 0 | 0 |
| Clear outcome matches | 3/6 | 6/6 |
| Clear exact event-count cases | 5/6 | 5/6 |
| Clear matched events | 2/3 | 2/3 |
| Clear event precision | 100% | 100% |
| Clear event recall | 66.67% | 66.67% |
| Clear signal precision | 80% | 80% |
| Clear signal recall | 80% | 80% |
| Gold-negative false-positive cases | 0/4 | 0/4 |

The prompt increased reported reasoning from 5,371 to 6,661 tokens and total usage from 55,044 to 59,544 tokens without recovering another clear-case event.

## What improved

Cases 013, 019 and 023 now correctly return `assessed` with an empty event list. Together with the already correct positive cases, this raises clear-case outcome agreement from 3/6 to 6/6. The new outcome wording is useful and should be retained as an independently supported prompt improvement.

All 16 provider responses completed with parseable, schema-valid JSON and no truncation or invalid passage IDs.

## What did not improve

Case 021 still returns only the Nestle layoff event. It does not return the separate sale of Nestle's remaining ice-cream operations to Froneri, so the expected `ma_consolidation` event remains missing. The general instruction to re-scan for acquisitions or disposals alongside layoffs was therefore insufficient.

The likely remaining ambiguity is signal policy, not output capacity. The catalogue describes `ma_consolidation` as a merger or acquisition but does not explicitly say how a divestiture or sale should be represented, while the gold answer treats this sale as `ma_consolidation`. Event-subject guidance also says to use the acquirer for an acquisition, whereas the gold answer uses Nestle, the seller, for this sale. A later experiment should resolve that policy explicitly before another broad live run.

## Regressions and manual-review findings

Case 014 chunk 006 returned `AtripleA recruitment & temps` while citing a title passage whose text used different literal characters, causing the unchanged backend validator to reject it as `unsupported_literal_fact`. The response was preserved and excluded without repair or retry.

On the same manual-review case, another valid chunk produced four `workplace_hiring` events for recruitment or listing entities rather than the expected employer event. This case remains outside the primary gate, but the result shows that a broad exhaustive scan can amplify false positives on job-listing pages. Future first-pass guidance must distinguish the employer undergoing workplace hiring from recruiters, job boards and duplicated listings.

Case 018 changed from the gold `insufficient_evidence` outcome to `assessed` with no events. It remains a manual-review case and does not affect the primary semantic gate. The distinction needs clearer policy for short snippets that describe a role but omit the employer.

## Interpretation

C2 separates two issues:

1. Outcome calibration can be fixed with prompt wording.
2. A general completeness checklist does not resolve secondary-event classification when the signal and subject policy are ambiguous.

The next experiment should be smaller than another eight-case run. It should freeze the proven outcome wording, then test explicit, general policies for seller/acquirer transactions and employer-versus-intermediary job evidence on the affected development cases plus controls. This must remain first-pass tuning; detailed semantic extraction, persistence and investigation remain paused.

No production prompt, extraction contract, validator, database model, migration, search execution or investigation behavior changed.
