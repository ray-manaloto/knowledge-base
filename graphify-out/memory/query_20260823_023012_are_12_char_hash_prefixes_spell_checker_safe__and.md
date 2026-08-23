---
type: "query"
date: "2026-08-23T02:30:12.198042+00:00"
question: "Are 12-char hash prefixes spell-checker-safe, and may a test seed its authority fixture from the real recorded authority?"
contributor: "graphify"
outcome: "corrected"
correction: "Two beliefs this round held and had to overturn, both in an authorization artifact:\n\n1. \"A 12-char hex prefix is short enough for the spell-checker.\" It is not: typos\n   tokenizes hex on digit boundaries and reads `ba`/`caf` inside a prefix as words,\n   and hk's `typos --write-changes` commit hook then REWROTE a short commit id in\n   the ledger (`29caf043` → a letter inserted). Full 40/64-hex hashes pass typos'\n   hex heuristic (probed with a control arm); machine-written ledgers belong in\n   `proseExclude` like `graphify-out/memory/**`. And the comment describing the\n   hazard must not quote the trigger tokens — four arm runs failed on my own\n   comment, not on the bait.\n\n2. \"Tests may seed their authority fixture from the real recorded authority.\" The\n   first real `record --accept` flipped five of them to \"nothing to record\" — the\n   fixture encoded the repo's CURRENT staleness as a premise. A test must derive its\n   authority from the candidate and perturb the identity digests itself; and an\n   authority-file test must assert structure, never the pre-accept literal digests.\n\nCorollary worth carrying: `graphify_semantic_corpus.py` AND `graphify_semantic_corpus_run.py`\nare digested into every plan (`planner_sha256`, `runner_sha256`) — an edit to either,\neven a message wording, is a re-authorization. Now by tool, but still a decision.\n"
---

# Q: Are 12-char hash prefixes spell-checker-safe, and may a test seed its authority fixture from the real recorded authority?

## Answer

The 2026-08-22 (f) landing session: PR #459 (the ninth session-review lane) was
cold-reviewed by codex (2 rounds, 5 findings, all prose in the lane brief, all fixed),
shipped, read against three bots, and landed (main 5dabbc59). Then the deferred
"record-verb fork" was decided WITH the evidence: a fresh semantic-corpus plan moved
exactly the two IDENTITY digests (plan manifest, execution config) and left both
DECISION digests (advisories, exclusions) byte-identical — the same class as all seven
hand re-records — so Ray chose to BUILD the verb on corpus-gate-bundle-rebased and let
its first real run be the eighth record.

The verb (`kb-setup graphify-semantic-corpus record [--plan-dir P] [--accept]
[--accept-decision-change NAME[,NAME]]`) plans fresh or takes a plan dir, stages the
six plan members in isolation (a plan dir must hold exactly six files), verifies
structural completeness, classifies which of the four recorded authority digests
move, refuses a moved DECISION digest unless named, and on --accept atomically
replaces the canonical dir (retaining the old one as `…superseded-<ts>/`), rewrites
the authority — now the data file `graphify_semantic_corpus_authority.json`, read at
import — appends one ledger bullet (`docs/agents/graphify-semantic-corpus-authority-ledger.md`),
re-verifies execution_authorized and rolls back on failure. It was specced in FOUR
premise-verifier rounds (each found a load-bearing gap: the planner digests its own
file — `planner_sha256` — so the verb is routed from cli.py and the planner is never
edited; exactly-six-files; ruff SLF001 on private names; `encode_canonical` sorts keys
and appends the newline), implemented by the codex lane (one sandbox-only failure: a
taplo panic; native lint rc 0), cold-reviewed cross-family by Gemini in two rounds
(7 findings: 2 confirmed+fixed — `_Transaction.__exit__` swallowed BaseException; the
cli usage implied a positional PATH — 4 refuted, 1 accepted), and its first real
`--accept` recorded the 0.9.48 / effort-high / $63 / 170-unit / 26-chunk plan:
`moved = plan_manifest + execution_config`, decision digests unchanged, authorized
after. That turned 22 red tests green (the stale canonical plan was the cause) and
exposed two more that the staleness had masked (a test stub's literal
`graphify_version="0.9.45"` beside a live 0.9.48 runtime).

Shipped as PR #463 (15 commits, receipt cold:antigravity, gates 6/6 at 9b9131e1);
landing is the next session's first act, followed by a Claude 2.1.241 resync (the
live binary already moved; the slice freezes 2.1.240), a ninth record by the tool,
re-scoping #455/#456/#411/#457/#458, and the deep extraction run.


## Outcome

- Signal: corrected
- Correction: Two beliefs this round held and had to overturn, both in an authorization artifact:

1. "A 12-char hex prefix is short enough for the spell-checker." It is not: typos
   tokenizes hex on digit boundaries and reads `ba`/`caf` inside a prefix as words,
   and hk's `typos --write-changes` commit hook then REWROTE a short commit id in
   the ledger (`29caf043` → a letter inserted). Full 40/64-hex hashes pass typos'
   hex heuristic (probed with a control arm); machine-written ledgers belong in
   `proseExclude` like `graphify-out/memory/**`. And the comment describing the
   hazard must not quote the trigger tokens — four arm runs failed on my own
   comment, not on the bait.

2. "Tests may seed their authority fixture from the real recorded authority." The
   first real `record --accept` flipped five of them to "nothing to record" — the
   fixture encoded the repo's CURRENT staleness as a premise. A test must derive its
   authority from the candidate and perturb the identity digests itself; and an
   authority-file test must assert structure, never the pre-accept literal digests.

Corollary worth carrying: `graphify_semantic_corpus.py` AND `graphify_semantic_corpus_run.py`
are digested into every plan (`planner_sha256`, `runner_sha256`) — an edit to either,
even a message wording, is a re-authorization. Now by tool, but still a decision.
