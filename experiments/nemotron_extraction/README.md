# Nemotron extraction experiment

This disposable research workspace tests whether Nemotron can correctly interpret Tavily evidence for Radory. It is separate from production backend code and normal tests.

`cases/pilot_v1_manifest.json` lists 24 selected, unlabelled discovery results from the two development runs. Each case points to an exact prepared evidence input under `data_local/pilot_v1/inputs/`; the system message is stored once in `data_local/pilot_v1/system_message.txt`. These local snapshots are ignored by Git, and their SHA-256 hashes are recorded in the manifest.

Selection focus describes why a result was included, not the correct answer. Gold labels and live Nemotron predictions are kept separate. This pilot alone cannot establish production reliability.

## Live pilot v1

`scripts/run_pilot_v1.py` checks that the label pack recreates the frozen extraction messages exactly. Its default mode is offline. `--live` uses the existing extraction adapter with the configured Nemotron Super model, the existing 4,096-token limit, and at most one request per case. Existing output prevents accidental reruns. The runner never loads an answer key or review memo.

Complete provider responses are saved before validation or comparison. Predictions are in `results/pilot_v1_nemotron_predictions.jsonl`; exact requests, provider responses, settings, and hashes are under Git-ignored `results/local/pilot_v1/`.

`scripts/compare_pilot_v1.py --gold <path> --review <path>` runs offline and requires all 24 predictions first. It reads the supplied `case_id`/`expected` answer format without rewriting it into `GoldAnswerV1`. Verbatim reference copies are under Git-ignored `data_local/pilot_v1/reference/`. The seven review-memo cases are excluded from clear-case metrics. Field comparisons and signal-presence counts are diagnostics; the report explains semantic alternatives and limitations.

Run scripts from the repository root using `backend/.venv/Scripts/python.exe`. No production settings, database records, investigation searches, or gold answers are changed by this experiment.
