# Pre-migration extraction evaluation

Radory now has an opt-in, offline-testable extraction pipeline. It is not connected to
radar job completion, Celery, API endpoints, investigation, or persisted observations.
No extraction tables or migrations exist yet. The existing discovery architecture remains intact.

## Responsibilities and wiring

1. `backend/app/search/evidence.py` reads `SearchResult -> SearchQuery -> SearchJob`.
   `prepare_search_result(result, workspace_id=...)` verifies the requested workspace and
   snapshots IDs, query context, title, URL, provider fields, timestamps, and source policy.
   A caller must obtain workspace context through the existing authorization boundary; this
   preparation function is not a new authentication or authorization endpoint.
2. Preparation prefers nonempty string `raw_payload["raw_content"]`, falling back to
   `SearchResult.content`. Whitespace-only or invalid raw-content values use the snippet.
   No usable body is a preparation failure, never an assessed document with zero signals.
   Nonempty raw content is not proof of a complete or readable article: login pages and
   incomplete extracts still need semantic assessment.
3. Normalization only standardizes line endings and trims outer whitespace. It does not
   summarize text, remove paragraphs, infer geography, or silently truncate documents.
   URL normalization preserves path and query parameters; it is not aggressive canonicalization.
   Preferred-source matches use hostname boundaries and are recorded per discovery occurrence.
4. `group_identical_evidence` groups identical semantic inputs within a workspace and retains
   every source reference. Source URL equality alone never authorizes reuse. Input identity
   includes title, selected text, content basis, publication context, coverage, and preparation
   version. Unchanged content from several sources can share interpretation, with all origins kept.
5. `backend/app/search/extraction_contract.py` defines strict, bounded Pydantic input/output
   schemas. Signal keys come from all 17 entries in `SIGNAL_LIBRARY`, including signals that
   are excluded from broad discovery. These are experimental contracts for evaluation, not
   approved database schema or investigation trigger rules.
6. `backend/app/search/extractor.py` requires an explicitly supplied client and model.
   Its `CompletionClient` interface matches the existing asynchronous `NebiusClient`.
   It supplies the signal catalogue, output schema, instructions, and semantic evidence.
   It does not send workspace IDs, discovery query/signal, scores, ranks, or preferred sources
   to the model. Those remain backend provenance.
7. Model output is validated before it becomes an in-memory candidate result. No model output
   writes to the database or starts another search. `evaluate_prepared_evidence` groups inputs,
   checks an explicit batch call budget before execution, and invokes the adapter sequentially.

## Contract and validation

The model returns `outcome` and an `events` list. Each event includes:

- Subject company; related companies and their roles where supported.
- A factual summary and one or more supported signal keys.
- Event stage: planned, underway, completed, cancelled, or unclear.
- Supported geographic mentions and their event/origin/destination role.
- Verbatim timing expressions with precision, without invented calendar dates.
- Missing facts drawn from the bounded vocabulary in the output schema.
- Exact quotations and block IDs attached to assertions and signal classifications.

An assessed document with no relevant findings is a successful result with zero events.
`insufficient_evidence` is a distinct successful semantic outcome with zero events.
Malformed JSON, invalid schema, unrecognized keys, missing quotations, incomplete model
responses, and provider failures are extraction failures, not zero-signal findings.

Backend validation checks quotation membership in the actual supplied blocks. Company names,
geography, and timing must also appear verbatim in their cited passages. Unknown geography
remains null, unknown timing uses an empty list, and unknown stage can be unclear.
This deliberately conservative contract does not normalize aliases or geographic hierarchies.

These checks cannot establish semantic entailment. A real quotation may still refer to another
company, describe a negated event, or concern a historical location. Candidates still require
quality evaluation and later investigation policy. A valid quote is not a verified opportunity.

## Initial verification results

- Full backend suite: 138 tests passed. One existing Starlette test-client deprecation warning.
- Ruff lint passed across `app` and `tests`; all eight extraction Python files passed formatting.
- Offline command-line report: 17/17 fixture cases matched expected outcomes.
- The report used 16 authored response replays and zero live provider calls. Empty evidence
  was rejected before a call; two duplicate discovery origins shared one replay.
- Invalid quotation, geography, date, and malformed-output cases passed by being rejected,
  not by producing accepted observations.
- No database migrations, production extraction hooks, or persisted observations were added.

## Evaluation bounds and reuse

- Current evaluation input limit: 60,000 text characters total, including titles.
- Oversized documents fail before a provider call. Chunking is not implemented.
- Default output cap: 4,096 tokens; an explicit override must be between 1 and 8,192.
- These are evaluation limits, not a tokenization guarantee or a paid-run budget approval.
- One adapter invocation makes at most one provider request. There are no automatic retries.
- Truncated output (`finish_reason` other than `stop`) is rejected.
- Cache identities include workspace, input fingerprint, full extraction specification,
  requested model, and output-token setting. Returned provider model/usage metadata is recorded.
- Reuse currently occurs only within one evaluation batch. There is no durable cache,
  cross-process lease, atomic persistence, or exactly-once provider-call guarantee.
- A provider model alias may change behind the same requested name; stable model selection
  and persistent-cache invalidation must be settled before enabling a durable cache.

## Run the offline evaluation

From `backend/` in PowerShell:

```powershell
.venv\Scripts\python.exe -m app.search.evaluate_extraction --fixtures tests/fixtures/extraction_cases.json --output extraction-report.json
```

Choose a new report path each time: the command refuses to overwrite an existing file.
Without `--output`, it prints the complete JSON report. A nonzero exit code means fixture
expectations failed. No environment credentials, HTTP clients, or database connections are
needed by this CLI. Its transient ORM records exercise the same preparation mapping as real
results. Separate SQLite tests verify preparation against actual stored model relationships.

The 17 synthetic fixtures replay authored completion responses. They cover market entry,
unknown city, misleading discovery query, multiple signals and companies, historical completed
moves, cancellation, no signal, negation, insufficient evidence, snippet fallback, duplicate
origins, invented quotes/geography/dates, malformed output, instructions embedded in evidence,
and empty evidence. Some cases cover more than one behavior.

The report contains candidate output, attached quotations, origin links, input identity,
status/error codes, call counts, and comparisons with authored expectations. It verifies
pipeline wiring and validation; it does not measure real Nemotron accuracy or demonstrate
that a live model will resist prompt injection. Invalid semantic interpretations that cite
real passages require evaluation beyond these deterministic checks.

Run backend tests and lint from `backend/`:

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\ruff.exe check app tests
.venv\Scripts\ruff.exe format --check app/search/evidence.py app/search/extraction_contract.py app/search/extractor.py app/search/evaluate_extraction.py tests/test_evidence.py tests/test_extraction_contract.py tests/test_extractor.py tests/test_extraction_evaluation.py
```

## Next approval checkpoints

Before live evaluation, select the exact configured model, verify its response behavior,
agree on call/token limits and estimated cost, and select representative documents. The
previous 260 discovery results predate raw-content enablement, so they do not constitute a
full-content extraction evaluation. A separately approved second discovery run is now available:
see [the raw-content run report](raw-content-discovery-run.md) for coverage and preservation
checks. Its raw content has not yet been evaluated with Nemotron. Any further retrieval
requires its own bounded approval.

Before migration, review actual semantic quality and finalize observation granularity,
extraction/source associations, stable evidence retention, cache invalidation, and retry rules.
Current successful query execution can replace `SearchResult` rows, so extraction provenance
must not rely on a cascading result foreign key alone. The in-memory snapshots here are not
yet durable records.

Investigation mappings, budgets, preferred sources, and persistence remain separate work.
The discovery query schema's rank-1/2 and job/signal/rank constraints must not silently become
the contract for company-specific investigation queries.
