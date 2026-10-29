# Experiment A4-R2 report

## Verdict

**FAIL — the technical truncation problem is solved, but reasoning-off extraction is not semantically or evidentially reliable enough to use.**

Nebius applied `chat_template_kwargs: {"enable_thinking": false}` to all five real-evidence requests. Every response reported zero reasoning tokens, stopped normally, and produced parseable typed JSON. The frozen overall gate failed because only two responses passed backend validation, only one of three controls remained valid, one recovery case contained unsupported literal facts, and the other recovery case returned a semantically incorrect zero-event answer.

## Results

| Measure | A3 reference | A4-R default | A4-R `/no_think` | A4-R2 `enable_thinking: false` | A4-R2 gate |
|---|---:|---:|---:|---:|---:|
| Parseable JSON | 3/5 | 3/5 | 4/5 | **5/5** | 5/5 |
| Typed-schema valid | 3/5 | 3/5 | 4/5 | **5/5** | 5/5 |
| Backend accepted | 3/5 | 2/5 | 3/5 | **2/5** | 5/5 |
| Truncations | 2 | 2 | 1 | **0** | 0 |
| Backend-valid controls | 3/3 | 2/3 | 2/3 | **1/3** | 3/3 |
| Backend-valid recovery cases | 0/2 | 0/2 | 1/2 | **1/2** | 2/2 |
| Character-collapse cases | 0 | 0 | 0 | **0** | 0 |
| Reported reasoning tokens | 10,563 | 10,986 | 10,588 | **0** | 0 |
| Manual control regressions | — | — | 1 | **2** | 0 |

## Per-case findings

| Case | Role | Technical result | Backend result | Semantic finding |
|---|---|---|---|---|
| 001 | control | Complete, typed, zero reasoning | `unsupported_literal_fact` | Correct company and business expansion, but missed headcount growth and emitted unsupported geography/null literals |
| 004 | recovery | Complete, typed, zero reasoning | `unsupported_literal_fact` | Correct company and funding signal, but stage and geography semantics were wrong |
| 008 | recovery | Complete, typed, zero reasoning | Accepted | Incorrectly returned zero events despite three gold events |
| 010 | control | Complete, typed, zero reasoning | Accepted | Correct zero-event result |
| 017 | control | Complete, typed, zero reasoning | `unsupported_literal_fact` | Correct company and RTO signal, but stage, summary and null literals were wrong |

## What A4-R2 proves

The hosted Nebius endpoint reliably honored the thinking-off control in this five-case run. It eliminated the previous reasoning-token exhaustion and allowed both formerly truncated cases to produce final JSON. The strict provider schema also remained stable with no character collapse.

Disabling reasoning globally is not a viable extraction configuration under the current prompt. The model became concise and structurally reliable, but it lost important semantic recall and produced unsupported literal values. Case 008 is especially important: backend acceptance alone cannot identify a valid-looking zero-event false negative.

## Next decision boundary

The remaining problem is no longer malformed or truncated output. It is choosing how to retain enough reasoning for multi-event interpretation while preventing reasoning from consuming the final-answer budget. A bounded-reasoning experiment would require a provider control that Nebius accepts and applies, or a prompt/evidence decomposition that reduces semantic complexity. Neither option was started automatically.

Production code, persistence, migrations, signal observations and investigation searches were not changed.
