# Experiment A4-R report

## Verdict

**FAIL — continue technical isolation.**

Adding `/no_think` to the first line of the system message did not make the five-case extraction sample technically reliable. Nebius accepted the requests, but reported reasoning tokens fell by only 3.62%, one recovery case still truncated, one control failed backend validation, and one control regressed semantically. The experiment therefore does not demonstrate that Nebius honored the directive as an effective reasoning-off control for this model.

## Frozen design

- Model: `nvidia/nemotron-3-super-120b-a12b`
- Provider: Nebius
- Cases: `pilot-v1-001`, `004`, `008`, `010`, and `017`
- R0: exact A3 request
- R1: exact request with `/no_think` prepended to the existing system message
- Strict pattern-free provider schema
- Output limit: 4,096 tokens
- No retries
- Production code unchanged

## Results

| Measure | A3 reference | A4-R R0 default | A4-R R1 `/no_think` | R1 gate |
|---|---:|---:|---:|---:|
| Cases | 5 | 5 | 5 | 5 |
| Parseable JSON | 3 | 3 | 4 | 5 |
| Typed-schema valid | 3 | 3 | 4 | 5 |
| Backend accepted | 3 | 2 | 3 | 5 |
| Truncations | 2 | 2 | 1 | 0 |
| Backend-valid controls | 3/3 | 2/3 | 2/3 | 3/3 |
| Backend-valid recovery cases | 0/2 | 0/2 | 1/2 | 2/2 |
| Character-collapse cases | 0 | 0 | 0 | 0 |
| Reported reasoning tokens | 10,563 | 10,986 | 10,588 | at least 75% below R0 |
| Reasoning reduction vs R0 | — | — | 3.62% | at least 75% |

## Per-case result

| Case | Role | R0 | R0 reasoning | R1 | R1 reasoning | Finding |
|---|---|---|---:|---|---:|---|
| 001 | control | accepted | 1,868 | unmatched evidence quote | 3,192 | Technical and semantic regression |
| 004 | recovery | truncated | 4,096 | accepted | 2,276 | Recovered |
| 008 | recovery | truncated | 3,239 | truncated | 3,752 | Did not recover |
| 010 | control | accepted | 114 | accepted | 131 | Correct zero-event result |
| 017 | control | unsupported literal fact | 1,669 | accepted | 1,237 | Improved, but omitted gold timing |

R1 produced one unmatched-evidence failure and one incomplete response. It produced no character-collapse failures. Because each arm intentionally used one call per case, recovery of case 004 cannot by itself establish causality; normal sampling variation remains a plausible explanation.

## Manual control review

- **001 regressed.** The company and signal keys were complete, but stage and geography changed, and a supporting quote failed exact evidence attachment.
- **010 remained correct.** It returned an assessed result with no events.
- **017 improved over R0.** Company, signal, completed stage, and country matched gold, but the relative timing `now` was omitted.

The frozen requirement of zero manual semantic regressions was not met.

## Harness incident

The first attempted R1 execution generated five local `invalid_provider_response` records without contacting Nebius. `SemanticExtractor` supplied the frozen messages to a wrapper that incorrectly expected the provider-modified messages, causing a local `ValueError` before the HTTP client. Those records and request metadata are preserved under explicit `local_harness_failure` names, and `a4r_no_think_4096_harness_incident.json` records the incident.

The experiment-only adapter was corrected and covered by an offline provider-boundary test before the five still-unused R1 calls were sent. The completed experiment made exactly ten external calls: five R0 and five R1.

## Interpretation

The directive was transmitted and Nebius returned normal completions, so this was not endpoint rejection. It did not materially suppress reported reasoning tokens and did not satisfy the frozen reliability gate. A4-S, A4-E, Experiment B, persistence work, and production changes remain stopped.
