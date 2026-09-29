# Graphify fork and knowledge-base Claude handoff

This directory is a read-only handoff snapshot. It does not transfer write ownership or prove delivery acceptance. The live delivery task remains `01a0ca59-2291-76a0-a5e7-bc6163a8567f` until its sole writer explicitly relinquishes after all owned processes settle.

Read in this order:

1. [Takeover packet](CLAUDE-TAKEOVER-20260928.md) for Git locations, delivery steps and the three-phase writer protocol.
2. [Issue history](GRAPHIFY-FORK-KB-ISSUE-HISTORY-20260928.md) for F01-F08 and K01-K14 failures and controls.
3. [Request addendum](REQUEST-GAP-ADDENDUM-20260927.md) for scoped open decisions without dropping the original gates.
4. [Rebase automation review](REBASE-AUTOMATION-REVIEW-20260928.md) for direct conflict and test-run examples referenced by the issue history.
5. [Subagent DAG](GRAPHIFY-SUBAGENT-DAG-20260928.md) for the review-ready modular dependency plan; it is not activated writer authority.

The associated [Claude takeover skill](skills/claude-graphify-takeover-v1/SKILL.md) and [issue-learning skill](skills/graphify-issue-learning-v1/SKILL.md) are bundled as portable reference copies. Their local-path instructions were adapted; the originals remain unchanged in the watch directory. The watcher-only skill is not included because it is not part of Claude’s review. The packet names local evidence paths, current worktrees, and a watch-owned `mise` validator. Those paths and the validator are not cloned with this documentation. If any are unavailable, record that coverage gap. The takeover packet’s A26/A27 worktree and deadline observations are historical; re-read the current attempt (A28 or later). Re-check mutable source heads, processes, receipts, PR state and native goal status directly before claiming progress. Never infer a lease transfer from this publication, a cutoff, an archived task, or a green check.

This publication exposed a fresh-worktree test setup gap: the first plain `mise run check` lacked the `sources/graphify` and `sources/skillopt` clones, and later concurrent `uv run` tasks pruned the optional codegen tools from one shared environment. The mirrored [review skill](../../../.claude/skills/kb-review/SKILL.md) now routes preparation through `mise run kb-worktree-ready`, requires plain `mise run check` and `mise run kb-gates`, and links the [worktree publication procedure](../../../.claude/skills/kb-review/references/worktree-publish.md). The canonical test task routes to `kb_setup.test_gate`, which returns NOT_RUN with a preparation command when its inputs are absent; `pyproject.toml` keeps both default dependency groups installed. The previous diagnostic `UV_NO_SYNC=1` pass is not acceptance evidence.

## Source integrity at publication preparation

The values in the table identify the original watch-owned files. The published
copies are recorded separately in [MANIFEST.sha256](MANIFEST.sha256); formatting
and local-path adaptation changed some published bytes without changing the
authoritative delivery contract.

| File | Original source SHA-256 |
| --- | --- |
| [CLAUDE-TAKEOVER-20260928.md](CLAUDE-TAKEOVER-20260928.md) | `5b74db19f4fe6aa5e8246a8ede9558fca376270ad75a39bcf69d88bb9c5845cd` |
| [GRAPHIFY-FORK-KB-ISSUE-HISTORY-20260928.md](GRAPHIFY-FORK-KB-ISSUE-HISTORY-20260928.md) | `ddba21583a9863f367544a39d4fc55bfc4dea12ed2b8faf11f6f0364787f7ca9` |
| [REQUEST-GAP-ADDENDUM-20260927.md](REQUEST-GAP-ADDENDUM-20260927.md) | `d068e657e8db73a258ca2fabe1bdca8dc94ee39faa438591a05cfecdec260bde` |
| [REBASE-AUTOMATION-REVIEW-20260928.md](REBASE-AUTOMATION-REVIEW-20260928.md) | `b3609a7e715fb15d5443ffdd6b577b83d6b27a5baf7e7f5facd5a6c83fedda70` |
| [GRAPHIFY-SUBAGENT-DAG-20260928.md](GRAPHIFY-SUBAGENT-DAG-20260928.md) | `11f53ab6e01469d89470775fa2301845c4798048dbbb50dea4231b76293bbda4` |
| [Claude takeover skill](skills/claude-graphify-takeover-v1/SKILL.md) | `398a84f0f7692a8918fdd8d4124ac0b145b0fab5a277949374188b8721915a99` |
| [Issue-learning skill](skills/graphify-issue-learning-v1/SKILL.md) | `5fa56adaa09d5bc3e3cfdf5143077af5b14b6afb8694757a849965e6487fd543` |

## Frozen delivery contract

The approved contract is bundled here for review: [GOAL](contract/GOAL.started.txt), [SPEC](contract/SPEC.approved.md), [TICKETS](contract/TICKETS.approved.md), and [2026-09-24 amendment](contract/AMENDMENT-20260924-v1.md). These are formatted reference copies of the approved contract, not amended requirements. The authoritative original files remain in the delivery evidence directory; verify their SHA-256 values below before relying on them. SHA-256: GOAL `e548a94f02ffeb9bfeb9304ef63051ef54c46e7b33444218edbb25105b2bd74f`; SPEC `c48ef1b093d2d1eef4c4a9729da8d8f7bf0998e2a96fe6da1dda1961712b38b1`; TICKETS `2a91e64437e97aa52fbc9176a608fdfe722afa36f146059a95aa69d0c9115e34`; amendment `7390a620927efbcf038c3356554641a2b9cc10105e63c958aec6d54a19f2ebee`. The live writer still owns the authoritative evidence index and acceptance.

## Read-only review prompt for Claude

```text
Review the Graphify fork and knowledge-base handoff in this directory. Begin read-only. Verify MANIFEST.sha256 for the published copies; if the original evidence is accessible, independently verify the original-source hashes in README.md. Read the takeover packet, issue history, scoped addendum, and frozen contract snapshots. Independently check the current delivery task, source worktrees/refs, active attempt, direct build and review receipts, and original GOAL/SPEC/TICKETS/amendment if accessible. Distinguish verified current facts from historical snapshots and inaccessible evidence. List all vague, missing, conflicting, stale, or failed instructions you encounter, including resolved and refuted issues, with exact file/section/hash and session/receipt provenance. Return a bounded digest: covered and inaccessible session windows, open gates, blockers, safe next action, and a provisional instruction-issue list. Do not edit either repository, evidence index, native goal, or this handoff; do not dispatch another writer. A later separate start signal is required after the current writer explicitly relinquishes and processes settle.
```
