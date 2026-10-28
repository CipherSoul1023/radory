**Radory Nemotron extraction pilot v1 — 29 October 2026**

**MIXED — improve prompt/contract and retest.**

Nemotron shows useful company/event recognition, but the current extraction implementation is not reliable enough to feed observations or investigation automatically. All 24 provider requests completed; only 14 outputs passed the existing backend validator. There are substantive omissions and timing/geography mistakes in addition to formatting failures. Continue developing and testing the extraction layer, but keep persistence and investigation outside this experiment until a revised version has been evaluated.

**Execution and isolation**

- Model requested and returned: `nvidia/nemotron-3-super-120b-a12b`, through the existing `NebiusClient` and `SemanticExtractor`.
- 24/24 requests, 24/24 complete provider responses saved, zero transport/HTTP failures, no retries, no reprompting, and no output repair. The one truncated response was saved exactly as returned.
- Existing prompt, signal catalogue, typed contract and validator were used unchanged. Maximum output budget: 4,096 tokens; sampling, reasoning and response-format controls were not supplied by the existing adapter and remained provider defaults. HTTP timeout: 60 seconds.
- All request messages matched the previously frozen system message and case inputs exactly. Requests contained only the system instructions/catalogue/schema and prepared semantic evidence. They contained no gold answers, review notes, discovery signal, discovery query, selection focus, or classifications derived from the answer key.
- Raw provider JSON was durably saved before adapter validation. All 24 prediction records were saved before the comparison script loaded the answer key. The gold key was checked for integrity and quote attachment before execution, but never used in request construction.
- 16 raw-content cases and eight snippet cases. Neither Tavily nor investigation was invoked. No production source, environment file, schema or database record changed.
- Provider-reported usage: 113,623 prompt tokens and 42,576 completion tokens, 156,199 total. Completion details identify 31,636 reasoning tokens. These are usage counts, not a verified billing amount. Summed request durations were 355.235 seconds.

The supplied gold key uses `case_id`, `expected`, and `challenge_tags`, not the earlier `GoldAnswerV1` shape. It was preserved verbatim and compared through an experiment-only mapping. Its 24 cases, 28 expected events and all 66 supporting passages were checked against the label pack. This is a working independent reference, not proof that every label or event grouping is uniquely correct.

**Validation results**

| Check | Result |
|---|---:|
| Provider responses saved | 24/24 |
| Parseable JSON objects | 22/24 |
| Typed output schema passed | 19/24 |
| Allowed signal keys, among parseable objects | 22/22 |
| Allowed enum values, among parseable objects | 22/22 |
| All cited quotations match, among parseable objects | 18/22 |
| Full backend validation passed | 14/24 |
| Full backend validation failed | 10/24 |

The independent quote audit checked 121 citation occurrences and found eight mismatches across four cases. Repeated citations count separately. Empty outputs vacuously pass quote checks; quote attachment is not proof that a quotation semantically supports the claim.

| Primary adapter failure | Count | Cases |
|---|---:|---|
| `invalid_output_schema` | 4 | 003, 007, 015, 022 |
| `unmatched_evidence_quote` | 2 | 004, 012 |
| `unsupported_literal_fact` | 3 | 006, 009, 020 |
| `incomplete_model_response` | 1 | 008 |

Case 007 contains trailing commas and is invalid JSON despite a `stop` finish reason. Case 008 reached `finish_reason=length` at 4,096 completion tokens, including 3,093 reasoning tokens, leaving truncated JSON. Case 003 adds an unsupported location-level `evidence` field. Case 015 supplies a wholly unknown location object instead of omitting it. Case 022 uses `{value: null, evidence: []}` where the contract requires the geographic field itself to be `null`.

**Clear-case scoring: 17 cases**

The seven memo-designated cases are excluded from these metrics. Signal precision/recall uses `(case_id, signal_key)` presence, so repeated events with the same signal do not inflate it. These are literal comparisons against the unchanged working gold. Extra labels are not automatically proven false positives.

| Measure | Result | Interpretation |
|---|---:|---|
| Backend-accepted outputs | 12/17 | A valid empty output counts here, even if semantically wrong |
| Typed outputs available for automated field comparison | 14/17 | Rejected grounding outputs can still be typed |
| Outcome matches | 9/17 | Includes unavailable typed outputs as misses |
| Event-count matches | 10/17 | Does not imply correct event identity |
| Positive cases with a visible event in parseable raw JSON | 10/12 | Includes two schema-invalid responses; no repaired JSON |
| Positive cases with a backend-accepted event | 6/12 | The usable pipeline result |
| Typed-output signal presence: TP / extra / missing | 10 / 2 / 11 | Missing includes unavailable responses |
| Typed-output signal precision / recall | 83.3% / 47.6% | Diagnostic reference scores, before semantic adjudication |
| Backend-accepted signal precision / recall | 88.9% / 38.1% | 8 TP, 1 extra, 13 missing |
| Gold-negative cases returning no events | 5/5 | No positive-event false alarms on these five cases |
| Gold-negative cases correctly returning `assessed` + `[]` | 1/5 | Four were incorrectly classified as insufficient evidence |

There are 19 expected events in the clear set. Eight align to events in typed outputs. Eleven are unavailable or omitted: six belong to cases without a typed usable structure (003, 008, 022), and five are omitted from otherwise typed outputs (002, 005, 006, 021).

| Field | Literal matches among eight aligned typed events | Matches over all 19 expected events |
|---|---:|---:|
| Subject company | 6/8 (75%) | 6/19 (31.6%) |
| Complete signal-key set | 5/8 (62.5%) | 5/19 (26.3%) |
| Stage | 6/8 (75%) | 6/19 (31.6%) |
| Geography field sets | 4/8 (50%) | 4/19 (21.1%) |
| Timing expression + precision sets | 4/8 (50%) | 4/19 (21.1%) |

Company-name review finds both literal mismatches to be understandable name variants: ENGIE versus ENGIE South Africa, and Global Political Solutions, LLC with versus without `(GPS)`. All eight aligned subjects identify the intended company. This does not recover the missing events or fix their validation failures. These conditional scores must not be presented as accuracy over all expected events.

Geography comparison is limited by the gold format's one geography object versus the model contract's multiple locations and roles. In particular, origin/destination pairs or multiple supported countries must not automatically be marked wrong because the gold object is singular. Timing comparison is also literal: `effective 1 June 2026` versus `1 June 2026` is the same date with different span boundaries, unlike unsupported use of a publication date as event time.

**Per-case findings**

IDs below omit the `pilot-v1-` prefix. “Pass” means backend validation passed, not that the semantics are correct. The comparison JSONL retains exact field differences; the comments distinguish definite failures from reasonable alternatives.

| Case | Validation | Findings |
|---|---|---|
| 001 ACTOM | Pass | Correct company, both gold signals and underway stage. Uses Pretoria West as market rather than the gold's Pretoria/Pretoria West city-submarket split. Geography granularity needs a clearer policy; this is not an invented place. |
| 002 Rentoza | Pass | Correct rescue event and date; omits the explicitly described 2022 funding/expansion event. Sandton is present in the evidence as the company's base; its use as event location is reviewable, not a fabricated city. |
| 003 Vodacom | Fail: schema | Recognizes layoffs but supplies an extra location field and changes a hyphen inside three quotations. Summary wrongly upgrades potentially affected 113 employees to confirmed impact and conflates the consulted 400 with a completed/planned cut figure. Omits the earlier round. |
| 004 Float | Fail: quote | Correct funding subject and completed funding stage. Strips Markdown from a quoted sentence. Extra `business_expansion` is a plausible label for the stated expansion plan, but a single completed stage risks treating intended expansion as already completed. Not a proven signal false positive. |
| 005 ENGIE | Pass | Correct company and leadership signal; name variant is acceptable. Marks the appointment planned although the article says it has appointed him and dates the effective appointment before the article date. Omits the prior Managing Director appointment. Date span includes “effective”, a harmless literal difference. |
| 006 Sigma | Fail: literal support | Correct principal hiring event; cites “across the country” for the literal country name, which fails the contract. Puts three cities in submarket fields. Omits the earlier domestic-business launch and two supported timing expressions. Multiple locations themselves are legitimate despite the gold's single geography object. |
| 007 Micros — review | Fail: JSON | Trailing commas prevent acceptance. Visible response text identifies the acquirer, M&A and unclear stage correctly. The extra expansion label is plausible; do not treat it as conclusively wrong. Publication date used as event time and very short role quotations also warrant review. No repaired output was scored. |
| 008 Tribunal mergers | Fail: length | Truncated at the 4,096-token budget. Cannot evaluate the full three-transaction extraction from an incomplete response. Counted as execution/contract failure, not evidence that the model deliberately found zero transactions. |
| 009 Isuzu — review | Fail: literal support | `market_entry` for the new operating entity is the memo's policy ambiguity, not an automatic false positive. However, the response omits explicit acquisition/consolidation coverage and supplies “recently” without a supporting quotation. Those are separate definite issues. |
| 010 Security operation | Pass | Correct `assessed` with zero events. |
| 011 GPS | Pass | Correct company variant, office opening, market entry and stage. Misses the supported leadership signal. Extra expansion is plausible for the new division. Treats the release date as an exact event date, contrary to the extraction instruction. |
| 012 Telkom — review | Fail: quote | Correctly keeps the tentative full move unclear. Origin and destination locations are sensible, not an automatic mismatch with the gold's destination-only shape. Removes a link from quotations, misses the already-completed partial move, and uses the strategic review's “next month” as event timing with precision `month` instead of `relative`. |
| 013 Property sale | Pass | No false positive, but returns insufficient evidence rather than an assessed non-event. |
| 014 SoluGrowth — review | Pass | Abstains with insufficient evidence. The memo flags uncertainty over the aggregator/employer attribution; treat this as a plausible conservative alternative pending human adjudication, not a definitive missed-company error. |
| 015 ArcelorMittal — review | Fail: schema | Signal scope for a regulatory stoppage remains reviewable. Separately, supplies an all-null location object, changes a Markdown-linked company quotation, and does not distinguish the date of reporting/receipt from actual shutdown. The schema/grounding failures are definite regardless of classification policy. |
| 016 Funding statistics | Pass | No invented company event; outcome is insufficient rather than assessed-zero. |
| 017 SARS | Pass | Correct subject, signal and “now”. Stage is underway versus gold completed: this exposes policy withdrawal versus enforcement as different event anchors. Retain the literal mismatch; human review should settle that stage convention. |
| 018 Generic jobs — review | Pass | Matches working gold insufficient-evidence outcome. The memo's assessed-zero alternative remains permissible for adjudication. One ambiguous case cannot establish general insufficient-evidence accuracy. |
| 019 Property rental | Pass | No invented event; outcome is insufficient rather than assessed-zero. |
| 020 Xtensible — review | Fail: literal support | Correct company, office opening, geography and underway stage. Stage matches the working gold, so the completed/underway ambiguity does not create a mismatch here. Omits the expansion label; invents the timing placeholder “unspecified” instead of using an empty timing list. |
| 021 Nestlé | Pass | Definite semantic false negative: returns insufficient evidence despite explicit local retrenchment notices and a separate sale to Froneri. Both events are omitted. |
| 022 Visa | Fail: schema | Identifies the correct company, leadership signal and completed stage. Three named countries are supported and should not be penalized because the gold kept its singular country null. Wrong null-object encoding prevents acceptance; report dateline is also treated as event timing. |
| 023 Relocation guide | Pass | No invented move; outcome is insufficient rather than assessed-zero. |
| 024 Pictet | Pass | Correct subject, opening and completed stage. Misses market entry under the working gold; repeats country South Africa as market and puts the verb phrase “has opened” in timing. Those last two fields pass literal quotation checks but are semantically inappropriate. |

**Manual-review cases**

Cases 007, 009, 012, 014, 015, 018 and 020 were run identically and are excluded from the 17-case primary scores. Two passed backend validation (014 and 018); both returned insufficient evidence, so none of the six working-gold positive cases yielded an accepted event. This does not make every semantic difference in these seven cases wrong.

Plausible alternatives are explicitly retained for the extra expansion label in 007, market-entry policy in 009, the relocation interpretation in 012, conservative abstention in 014, regulatory-stoppage scope in 015, and the alternative outcome convention in 018. The 020 stage already agrees with gold. Independent JSON, quotation and unsupported-timing failures remain definite technical failures. No human adjudication is claimed as completed by this report.

**Failure patterns and what the pilot establishes**

1. **Output reliability needs work.** Invalid JSON, null encoding, extra fields and truncation reject otherwise interpretable findings. This run does not establish that enabling a particular provider parameter will fix them; any changed output/reasoning configuration needs a separate bounded test.
2. **Literal citations are fragile around source Markdown.** Float, Telkom and ArcelorMittal quotations remove or rewrite link syntax. Vodacom replaces an ASCII hyphen with a non-breaking hyphen. These are exact-attachment failures, not all fabricated facts. Any future normalization must be deterministic and versioned before freezing evidence; these pilot inputs and outputs were not normalized or repaired.
3. **Quotation existence alone is insufficient.** Sigma's country value is absent from its cited phrase. Pictet's country-as-market and verb-as-timing pass the present validator. A quote can exist while supporting the wrong kind of claim. Exact quote validation must remain alongside semantic evaluation.
4. **Secondary and historical events are repeatedly missed.** Every parseable positive output contains only one event. Rentoza's earlier funding, ENGIE's earlier appointment, Sigma's launch and Telkom's completed partial move are examples. The Nestlé response misses even the primary layoff event.
5. **Outcome calibration is weak.** Five gold-negative cases produce no events, but four are classified insufficient. The sole expected-insufficient case matches; additional negative/insufficient cases are needed to distinguish a reliable abstention policy from overuse of that outcome.
6. **Timing and geographic roles are unreliable.** Publication dates become event dates; unknown time becomes a placeholder; city/country/submarket levels are confused. Short exact passages do not prevent these semantic errors.
7. **Some apparent errors belong to the reference or policy.** Company aliases, multi-location output, overlapping expansion labels, and event-stage anchors require explicit adjudication. The report keeps these separate from definite misses. It does not change the frozen gold key or quietly award corrected scores.

There are no positive-event false alarms on the five clear negative cases. The two extra clear-set signal labels are expansion labels on genuine events and are plausible under the catalogue; they should not be advertised as two proven hallucinations. Definite coverage failures include the Nestlé abstention, omitted secondary events, missing leadership classification on GPS, and unsupported timing/geographic fields. Pipeline recall also falls because valid-looking content is rejected by the contract.

The next experiment should address structured output and token budgeting, preserve exact evidence attachment, clarify non-event versus insufficient-evidence outcomes, and require a deliberate pass over secondary/historical events. Then retest a versioned prompt/contract with approved spending limits and an additional untouched sample. Do not weaken validation merely to increase the pass rate. This purposively selected 24-case pilot, including seven ambiguous labels, is too small to establish production reliability or to attribute every failure to the model rather than the current prompt/contract/settings.

**Artifacts and integrity**

- `pilot_v1_nemotron_predictions.jsonl`: all original predictions, complete provider responses, adapter errors, diagnostics and request hashes.
- `pilot_v1_comparison.jsonl`: field comparisons, unmatched events, signal differences, scoring-set membership and separate semantic-review notes.
- `local/pilot_v1/`: exact requests/responses, run metadata, machine metrics and review annotations; Git-ignored.
- `../data_local/pilot_v1/reference/`: verbatim supplied gold and review memo; Git-ignored.
- Gold SHA-256: `d2a5e0a39cdf64380602f44658647d7d28cb0eedd733af00ef8d665972da9852`.
- Review SHA-256: `a79b905f17a75d72bc2aa86716e08525487f39a9848a62940e87ed67ab579aa5`.
- Local label-pack SHA-256: `2b5d276fe5a2c0773b70b3ab225b55b5512cb49cc361763e99ac12affd616e0d`.
- The supplied attachment has different JSON whitespace and SHA-256 `7497b2b93b641b3ef438a7fefa6a81778b85d124207d6901b58f646f4d45a6db`, but all 24 parsed records are identical to the local label pack.
- Predictions SHA-256: `1b04e11a1d2611d5361cde9cdebf9790c1f358a24ddc4c889432ac03c4cb4df2`.

Verification: 67 targeted extraction/harness tests passed; Ruff and `git diff --check` passed. All 24 saved requests, input hashes/fingerprints and raw-response copies were rechecked. Original gold/review files, the label pack, the executing runner and production source hashes are unchanged. A scan against configured credential values found none in generated artifacts.

Git status: only the experiment README is modified; the three requested result files and the three experiment scripts are untracked. Local evidence, reference copies, exact requests/responses and metadata remain ignored. No commit was created. No investigation, broker-fit scoring or production persistence was implemented.

FRAGILE DECISIONS ENCOUNTERED:
- None. The authorized bounded pilot was executed; unresolved classification policies remain flagged for adjudication rather than being changed.
