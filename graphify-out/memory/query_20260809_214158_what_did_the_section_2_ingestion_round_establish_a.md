---
type: "query"
date: "2026-08-09T21:41:58.729211+00:00"
question: "What did the section-2 ingestion round establish about screening and ingesting candidate libraries?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the section-2 ingestion round establish about screening and ingesting candidate libraries?

## Answer

Ingest first, then answer — and the ingestion is what makes the answer survive.

Thirteen candidates screened on R10 (last commit within one month), twelve
ingested as kind=code (free, no LLM), one deliberately deferred to a docs mirror.
Graph went 359,069 -> 425,989 nodes, 0 dangling, 0 malformed.

THE INSTRUMENT MATTERS MORE THAN THE DATES, which expire in a month:
R10 must read the last commit on the DEFAULT BRANCH. pushed_at counts any branch
and read picologging ~10 months more alive than main is; release date answers a
different question entirely, and is what the parallel dotfiles session screened
on. Three routes, three answers, same verdict here only by luck.

sort=updated nearly cost the whole R8 answer. A GitHub search for Rust-backed
Python logging returned only hobby repos under that sort; re-sorted by stars it
surfaced logly (379 stars) and logxide immediately. A display bound turning
absent into unreachable.

The two probes have different blind spots and that is the transferable finding:
the dotfiles session used per-package PyPI lookups, which can only find names you
already guessed, and so missed both. But THEY found logbook, which the GitHub
sweep missed. Neither route is complete; run both.

R8's answer: satisfiable on the SERIALISATION side (msgspec is C-backed, orjson
Rust-backed, both mature) and NOT on the logging-framework side, where the mature
C++ option (picologging) is dead and the live ones are v0.2.2 and 35 stars.

A CONCLUSION CAN BE RIGHT FOR A REASON THAT DOES NOT TRANSFER. The dotfiles
session reached the same R8 verdict via "the throughput ceiling is a subprocess
round-trip to a Node CLI" — a fact about THEIR workload. This repo's expensive
path is a 425k-node graph build. Same answer, and carrying their sentence across
would have been a correctly-sourced fact applied to a repo it was never true of.

## Outcome

- Signal: useful