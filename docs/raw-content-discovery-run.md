# Raw-content discovery run — 2026-10-27

Completed one additional development discovery run to collect fuller source evidence for
the forthcoming Nemotron extraction evaluation. The original run was retained intact.
This report contains operational metadata only; retrieved article content remains in Neon.

## Runs retained

| Run | SearchJob ID | Queries | Result records | Status |
| --- | --- | ---: | ---: | --- |
| Original snippet-based run | `d8192521-0cd2-452f-9bb4-43e1dbb5f9b7` | 26 | 260 | completed |
| New raw-content-enabled run | `97c881c7-e4a1-48af-bdaf-d68220555733` | 26 | 260 | completed |

There are now two jobs and 520 result records. Result counts do not represent unique companies,
validated signals, or unique articles across the two runs.

## Execution and verification

- Used the same existing development workspace and its current brokerage profile:
  South Africa / Pretoria / Menlyn.
- Created a distinct job through the existing `create_search_job` service. Persisted all
  26 query rows before execution, each with `include_raw_content=True`.
- Executed only the new job's persisted query IDs sequentially through the existing
  `execute_search_query` engine. This was an operator-run collection, not a new API or
  Celery wiring change. The original job's queries were never retried.
- Retained existing discovery templates and source policies: 13 signals, two queries each,
  basic search depth, and up to ten results per query.
- Started at 20:29:16 UTC and completed at 20:32:19 UTC on 2026-10-27.
- All 26 queries succeeded on their first attempt; no failed, pending, or running queries remained.
- Every query returned ten results. Provider usage records were present for all 26 queries
  and reported a total of 26 credits.
- Audited the final database state at approximately 20:32:41 UTC.

## Raw-content availability

| Measurement | Value |
| --- | ---: |
| New result records | 260 |
| Records with nonempty string `raw_content` | 211 (81.2%) |
| Records without nonempty string `raw_content` | 49 (18.8%) |
| Distinct exact result URLs in the new run | 252 |
| Distinct hashes of nonempty raw-content strings | 203 |
| Shortest nonempty raw content, trimmed characters | 808 |
| Median nonempty raw content, trimmed characters | 10,004 |
| Longest nonempty raw content, trimmed characters | 587,091 |
| Records whose raw content alone exceeds 60,000 trimmed characters | 9 |

Content is stored in each new `SearchResult.raw_payload["raw_content"]` when returned.
Nonempty raw content is an availability check, not a guarantee of complete, relevant, readable
article text. The exact-string hash count is not semantic deduplication and does not replace
the extraction pipeline's full-input fingerprint.

The nine oversized records already exceed the current extraction evaluation text limit before
adding titles. They need an explicit handling decision before model evaluation; this run did
not truncate or discard their stored content. Records without raw content remain available for
snippet-based evaluation, subject to normal evidence preparation checks.

## Preservation check

Before creating the new job, computed a SHA-256 fingerprint over the original job row,
all its query rows, and all its result rows, including IDs, metadata, timestamps, content,
and full provider payloads. Rows were ordered by ID and serialized consistently.

The final fingerprint matched the pre-run fingerprint exactly. Original counts remained
26 queries and 260 results. No original job, query, or result fields changed.

No application code, configuration, environment files, or schema changed for this collection.
No Nemotron calls, signal-observation writes, or investigation searches were performed.
Temporary runner and audit-state files were removed after verification. This commit records
the run summary; Git does not contain the database results or credentials.
