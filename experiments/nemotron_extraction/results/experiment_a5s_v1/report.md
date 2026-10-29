# Experiment A5-S report

## Verdict

**FAIL — finer paragraph chunks did not prevent truncation and introduced context-loss errors.**

A5-S split A5-R's failed 2,352-character chunk into three non-overlapping parts of 1,117, 1,011 and 220 characters. Only the short irrelevant part passed backend validation. The first event-bearing part returned complete but invalid output with unsupported empty locations, unmatched quotations and incorrect event interpretation. The second event-bearing part again exhausted the 4,096-token completion allowance.

## Results

| Measure | A5-R failed chunk | A5-S finer parts | A5-S gate |
|---|---:|---:|---:|
| New model calls | 1 | **3** | 3 |
| Parseable JSON | 0/1 | **2/3** | 3/3 |
| Typed-schema valid | 0/1 | **1/3** | 3/3 |
| Backend-valid new outputs | 0/1 | **1/3** | 3/3 |
| Truncations | 1 | **1** | 0 |
| Reported reasoning tokens | 3,029 | **5,213** | observed only |
| New accepted events | 0 | **0** | 2 |
| Aggregate gold events matched | 1/3 | **1/3** | 3/3 |
| Aggregate signal presence TP / extra / missing | 2 / 0 / 0 | **2 / 0 / 0** | 2 / 0 / 0 |

The three new calls used 10,160 prompt tokens and 7,571 completion tokens. The aggregate retained only A5-R's previously validated Aker event; no new event passed validation.

## Per-part findings

Part 001 returned Greenstreet and Aker merger candidates, but its JSON violated the contract by emitting wholly empty location records. Six quotations also failed exact matching because the model altered corrupted quotation characters in the supplied text. Semantically, it assigned the article date to the earlier January merger and classified Aker as completed without the later paragraph that establishes a planned acquisition and market entry.

Part 002 contained the detailed Greenstreet/Stanlib transaction language. Despite being only 1,011 characters, it used 2,860 reasoning tokens and still stopped for length before completing JSON.

Part 003 contained only a Stanlib fund description and correctly returned `insufficient_evidence` with no events.

## Interpretation

Character count is not the controlling variable. Event density, repeated transaction descriptions, the verbose output contract and the amount of reasoning all contribute to completion size. Arbitrary paragraph boundaries can also remove the context needed to distinguish a party listing from a supported event stage or market-entry signal.

Further blind character splitting is not recommended. The next design discussion should compare two explicit experimental directions:

1. A compact first-pass event detector that returns only event identity, candidate signals and evidence references, followed by detailed extraction for accepted candidates.
2. A different model or provider configuration that can reason within a controllable budget while preserving the current single-pass contract.

Either direction changes the extraction strategy rather than a routine parameter, so it should be chosen deliberately before another paid run. No production prompt, evidence preparation, model contract, validator, database model, migration, persistence path or investigation behavior changed.
