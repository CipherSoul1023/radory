# Nemotron extraction experiment

This disposable research workspace tests whether Nemotron can correctly interpret Tavily evidence for Radory. It is separate from production backend code and normal tests.

`cases/pilot_v1_manifest.json` lists 24 selected, unlabelled discovery results from the two development runs. Each case points to an exact prepared evidence input under `data_local/pilot_v1/inputs/`; the system message is stored once in `data_local/pilot_v1/system_message.txt`. These local snapshots are ignored by Git, and their SHA-256 hashes are recorded in the manifest.

Selection focus describes why a result was included, not the correct answer. Human gold labels and live Nemotron evaluation are separate next steps. This pilot alone cannot establish production reliability.
