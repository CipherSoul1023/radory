# Nebius `enable_thinking` compatibility report

## Verdict

**PASS — the hosted Nebius endpoint accepts and applies `chat_template_kwargs: {"enable_thinking": false}` for `nvidia/nemotron-3-super-120b-a12b`.**

## Results

| Measure | Provider default | `enable_thinking: false` |
|---|---:|---:|
| HTTP status | 200 | 200 |
| Finish reason | `stop` | `stop` |
| Reported reasoning tokens | 99 | 0 |
| Completion tokens | 110 | 10 |
| Final answer present | yes | yes |
| Parsed answer | 1517 | 1517 |
| Answer correct | yes | yes |
| Duration | 2.890 s | 0.766 s |

The treatment request differed from the control request only by the top-level `chat_template_kwargs` field. The exact treatment value was `{"enable_thinking": false}`. Two requests and two responses were preserved locally; no retry occurred.

## Interpretation

This synthetic result establishes provider acceptance and practical reasoning suppression for the tested request shape. It does not establish semantic extraction quality or consistency on real evidence. The appropriate next experiment is a frozen A4-R2 run on cases 004 and 008 plus the existing controls, with the same extraction prompt, evidence, strict pattern-free schema, validation, output budget, timeout and sampling defaults. The only request difference should be `chat_template_kwargs: {"enable_thinking": false}`.

A4-R2 was not started automatically. Production code, Radory evidence, gold answers, persistence and investigation logic were not changed.
