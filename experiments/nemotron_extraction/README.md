# Nemotron extraction experiment

This disposable research workspace tests whether Nemotron can correctly interpret Tavily evidence for Radory. It is separate from production backend code and normal tests.

`cases/pilot_v1_manifest.json` lists 24 selected, unlabelled discovery results from the two development runs. Each case points to an exact prepared evidence input under `data_local/pilot_v1/inputs/`; the system message is stored once in `data_local/pilot_v1/system_message.txt`. These local snapshots are ignored by Git, and their SHA-256 hashes are recorded in the manifest.

Selection focus describes why a result was included, not the correct answer. Gold labels and live Nemotron predictions are kept separate. This pilot alone cannot establish production reliability.

## Live pilot v1

`scripts/run_pilot_v1.py` checks that the label pack recreates the frozen extraction messages exactly. Its default mode is offline. `--live` uses the existing extraction adapter with the configured Nemotron Super model, the existing 4,096-token limit, and at most one request per case. Existing output prevents accidental reruns. The runner never loads an answer key or review memo.

Complete provider responses are saved before validation or comparison. Predictions are in `results/pilot_v1_nemotron_predictions.jsonl`; exact requests, provider responses, settings, and hashes are under Git-ignored `results/local/pilot_v1/`.

`scripts/compare_pilot_v1.py --gold <path> --review <path>` runs offline and requires all 24 predictions first. It reads the supplied `case_id`/`expected` answer format without rewriting it into `GoldAnswerV1`. Verbatim reference copies are under Git-ignored `data_local/pilot_v1/reference/`. The seven review-memo cases are excluded from clear-case metrics. Field comparisons and signal-presence counts are diagnostics; the report explains semantic alternatives and limitations.

Run scripts from the repository root using `backend/.venv/Scripts/python.exe`. No production settings, database records, investigation searches, or gold answers are changed by this experiment.

## Output reliability experiment A

`cases/experiment_a_v1.json` freezes the 10 failed pilot cases and six successful controls, two configurations, a 32-call ceiling, and acceptance criteria. A1 adds schema-constrained output at 4,096 tokens. A2 retains that schema and raises only the output budget to 8,192. Both preserve the exact original system/evidence messages, model, schema, validator, timeout and unspecified sampling/reasoning settings. The existing production transport does not expose `response_format`, so an experiment-only subclass adds that documented request field; production code is unchanged.

`scripts/run_experiment_a.py` defaults to offline preflight. Live execution requires `--live --arm a1_schema_4096` or `--live --arm a2_schema_8192`. An arm cannot overwrite an existing run or retry a case. The plan was frozen before any inference; A2 requires A1's completion. Outputs live under `results/experiment_a_v1/`, with exact requests/responses and settings under ignored `results/local/experiment_a_v1/`.

`scripts/compare_experiment_a.py` requires both 16-case output files before loading the unchanged gold key. It measures the predefined technical gate and records control-case changes for semantic review. The original pilot is a historical reference, not a repeated contemporaneous baseline. Failure of the gate stops progression to semantic prompt changes or a fresh holdout; the thresholds are not relaxed after seeing results.

## Schema compatibility probe

`cases/schema_compatibility_v1.json` defines four short synthetic cases and three response-format modes. The probe keeps the semantic messages, evidence, model, 4,096-token limit, provider defaults and backend validation fixed. It compares the current strict JSON Schema, the same provider schema with only regex `pattern` keywords removed, and JSON-object mode. This is a disposable diagnosis of the single-character output collapse; it does not change the production extraction contract or establish real-evidence accuracy.

`scripts/run_schema_compatibility.py` defaults to an offline preflight and requires `--live` for its bounded 12-call run. It refuses overwrites and retries. `scripts/compare_schema_compatibility.py` checks mechanical validity, collapsed free-text values and explicit synthetic semantic anchors after all responses are saved. Exact requests and responses remain under ignored `results/local/schema_compatibility_v1/`.

## Experiment A3

`cases/experiment_a3_v1.json` references Experiment A's immutable plan and exact 16 real-evidence cases. A3 keeps the original prompt, evidence, model, backend contract, validation, timeout, provider defaults and 4,096-token budget. Its experiment-only strict provider schema removes only regex `pattern` keywords. The budget matches A1 because A1 had no truncations, A2 still truncated at 8,192, and this makes pattern removal the only A1/A3 request difference.

`scripts/run_experiment_a3.py` defaults to offline preflight and requires `--live` for the bounded 16-call, zero-retry run. `scripts/compare_experiment_a3.py` applies the existing comparison logic to Historical/A1/A2/A3 and adds the frozen character-collapse gate. Exact A3 requests and responses remain under ignored `results/local/experiment_a3_v1/`. A3 never advances into Experiment B automatically.

## Experiment A4-R

`cases/experiment_a4r_v1.json` isolates A3's reasoning-only truncations using cases 004 and 008 plus controls 001, 010 and 017. Both five-case arms retain the strict pattern-free schema, exact evidence, semantic instructions, model, 4,096-token limit, timeout and provider defaults. R0 repeats the exact A3 request. R1 adds `/no_think` as the first line of the existing system message, the position documented for Nemotron 3 Super, without using undocumented Nebius request-level reasoning parameters.

`scripts/run_experiment_a4r.py` requires an explicit arm and `--live`; the no-think arm cannot start before the default arm is complete. The ten-call experiment has no retries or overwrites. `scripts/compare_experiment_a4r.py` compares reported reasoning tokens, finish reasons, schema/backend validity, recovery of both failures, character collapse and the three controls. It does not start A4-S, A4-E or Experiment B.

The completed result is recorded in `results/experiment_a4r_v1/report.md`. The no-think arm failed its frozen gate: reported reasoning fell by only 3.62%, case 008 still truncated, and control 001 regressed. An initial zero-network local harness failure is retained separately and documented in the result set; it did not consume provider calls.

## Nebius `enable_thinking` compatibility probe

`cases/enable_thinking_compatibility_v1.json` defines a two-call synthetic probe for the model-specific `chat_template_kwargs: {"enable_thinking": false}` control. The control and treatment use the same short arithmetic task, strict one-field JSON schema, model, sampling configuration, output limit and timeout. The treatment adds only `chat_template_kwargs`; it sends no Radory evidence and does not use `reasoning_budget`, `low_effort` or another undocumented Nebius control.

`scripts/run_enable_thinking_compatibility.py` defaults to offline preflight and requires `--live` for the zero-retry run. Exact requests and responses remain under ignored `results/local/enable_thinking_compatibility_v1/`. The reviewable result records provider acceptance, reported reasoning tokens, finish reason and final-answer validity, and never starts A4-R2 automatically.

The completed probe passed. Nebius returned HTTP 200 for both requests; the control used 99 reported reasoning tokens, while `enable_thinking: false` used zero and returned the same correct final answer. See `results/enable_thinking_compatibility_v1/report.md`. This establishes capability only; it does not establish real-evidence extraction quality.

## Experiment A4-R2

`cases/experiment_a4r2_v1.json` applies the verified `enable_thinking: false` control to A4-R's two reasoning-truncation cases and three controls. It freezes the A4-R evidence, semantic messages, model, strict pattern-free schema, 4,096-token limit, timeout, provider sampling defaults and backend validation. The request adds only `chat_template_kwargs` and permits five calls with no retries.

`scripts/run_experiment_a4r2.py` defaults to offline preflight and requires `--live`. `scripts/compare_experiment_a4r2.py` loads gold only after all responses are saved and compares A4-R2 with A3, A4-R default and A4-R `/no_think`. Exact requests and responses remain under ignored `results/local/experiment_a4r2_v1/`. A4-R2 never starts a later experiment or modifies production code automatically.

A4-R2 eliminated reasoning and truncation on all five cases, but failed the overall gate. All responses were parseable and typed, while only two passed backend validation; controls 001 and 017 regressed, case 004 contained unsupported literal facts, and case 008 returned a semantically incorrect zero-event answer. See `results/experiment_a4r2_v1/report.md`.

## Experiment A4-E

`cases/experiment_a4e_v1.json` freezes a narrow evidence-grounding prompt addendum on A4-R2's five cases. Reasoning remains disabled. Evidence, model, provider schema, production contract and validators, token limit, timeout and sampling defaults remain unchanged. The addendum teaches JSON nulls, verbatim literal fields, actual temporal expressions, restraint with truncated text, and evidence-based stage selection using unrelated synthetic examples.

`scripts/run_experiment_a4e.py` defaults to offline preflight and requires `--live` for five zero-retry calls. `scripts/compare_experiment_a4e.py` measures mechanical grounding separately from semantic event and signal recall, loading gold only after all provider responses are saved. Exact requests and responses remain under ignored `results/local/experiment_a4e_v1/`. Production extraction behavior remains unchanged.

A4-E improved backend acceptance from two to four of five cases without reasoning or truncation, but failed both frozen gates. Case 001 still emitted an unsupported string `"null"`, and only three of six gold events and signal presences were recovered. See `results/experiment_a4e_v1/report.md`.
