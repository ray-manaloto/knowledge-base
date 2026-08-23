# Lane: contradicted — session-review sweep, scope = f74823ff-3ee4-4b02-a2af-11106a762c9f.jsonl (2026-08-23)

Scope note: this transcript is the round that produced commits `8f285ce0` (U0),
`e4d3d27a` (U8b0), `17623a32`/`a7ae6d7b` (corpus tracking, closing #317),
`b9ce6e0a` (U4b) and `24d11e49` (work-memory) — the same round `.agent/plans/session-2026-08-23-c.md`
describes. A prior `contradicted.md` in this directory covered a *different* jsonl
(`096161cc-...`) and its three findings are unrelated to this scope; not re-verified here.

## Finding 1 — CLAUDE.md and do-not.md still say ONLY `memory/` is committed under `graphify-out/`; this round tracked 106 more files there and never updated either

- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/CLAUDE.md:169` (root, auto-loaded every
  session) — Layout table row for `graphify-out/`: *"Committed: **only `memory/`** (authored
  work-memory)."*
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/rules/do-not.md:65` (item 5 of
  the "authoritative list of things agents ... must not do") — *"**Do NOT commit `graphify-out/`
  beyond `memory/`.** Everything else is DERIVED and rebuilt by `kb-build` / `kb-artifacts`; at
  aggregate scale the graph exceeds git/GitHub limits."*

This round's own commit `a7ae6d7be1c0` ("chore(corpus): track the staged provider evidence,
closing #317 as TRACKED") tracked 106 files under
`graphify-out/graphify-semantic-corpus-chunks/9e1adc3b.../` — deliberately, per Ray's 2026-08-23
ruling recorded in `.gitignore:69-84` ("`graphify-out/graphify-semantic-corpus-chunks/` is
DELIBERATELY NOT listed [in .gitignore], and is now TRACKED rather than merely visible ... Ray
settled it 2026-08-23 in favour of tracking"). Verified live on disk:

```
$ git ls-files graphify-out/ | wc -l
347
$ git ls-files graphify-out/ | head -1
graphify-out/graphify-semantic-corpus-chunks/9e1adc3b7df53844cdc50f4a69f801ef329a47df0d96b7f2f229e5423b1797ad/chunks/0001/adapter-metadata.json
```

Control arm: `git ls-files graphify-out/memory/` also returns files (the claim's own carve-out is
real), so the probe discriminates — it is specifically the *"only"* / *"beyond `memory/`"* wording
that is now false, not the whole row.

This is not a stale historical note; it is a currently-loaded invariant. `do-not.md` item 5 is
phrased as a hard "Do NOT," and `CLAUDE.md`'s own preamble says these instructions "OVERRIDE any
default behavior and you MUST follow them exactly as written." An agent reading `do-not.md` at face
value after this round would see 346 tracked files outside `memory/` and could reasonably conclude
someone violated the invariant and try to untrack them — which would silently re-open #317 and
destroy the retained provider evidence the round just spent $41.78 producing. The `.gitignore`
comment anticipated exactly this failure mode for the ignore-file layer ("an entry here would
un-track it by the back door") but the same reasoning was never carried to `CLAUDE.md` or
`do-not.md`, the two docs an agent is actually told to treat as binding.

Cost: high if left standing into the next round — it is a live trap for the *next* agent, not a
cosmetic doc gap, and it sits in the two files most likely to be read literally (root `CLAUDE.md`
and the invariants list). Remedy: amend both lines in the same commit that lands this round's PR —
e.g. "Committed: `memory/`, and `graphify-semantic-corpus-chunks/` per #317's 2026-08-23 ruling
(retained provider evidence)" — so the two docs agree with the `.gitignore` comment and with each
other.

## Finding 2 — `GATE_TASKS` has six gates; the code comment describing it and the rule file both still say "four"

- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/gates.py:139` —
  `GATE_TASKS = ("lint", "test", "brain-audit", "eval", "graph-size", "hk-test")` — **six** entries.
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/gates.py:419` — a
  docstring/comment on `_run_batch`, in the SAME file, describing a bug fix: *"It is reachable on
  the ship path, since all **four** `GATE_TASKS` are one batch."*
- `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/rules/verify-before-advancing.md:22`
  — *"`mise run kb-gates` runs all **four** and records each result ..."*

The comment inside `gates.py` is a textbook case of "read a comment against the code it sits on":
it names the exact symbol (`GATE_TASKS`) whose definition is 280 lines above it in the same file,
and the definition it is describing has six members, not four. `CLAUDE.md`'s own Layout-table row
for `mise.toml` independently confirms the six-gate reality (*"`hk-test` ... in `GATE_TASKS` since
2026-08-19"*, naming it as a sixth addition alongside `graph-size`), so this is not ambiguous about
which count is current — `CLAUDE.md` and the `GATE_TASKS` tuple agree with each other; the code
comment and the rule file are the two documents that disagree with both.

Verified:
```
$ grep -n 'GATE_TASKS = ' python/src/kb_setup/gates.py
139:GATE_TASKS = ("lint", "test", "brain-audit", "eval", "graph-size", "hk-test")
$ grep -n 'all four' python/src/kb_setup/gates.py .claude/rules/verify-before-advancing.md
python/src/kb_setup/gates.py:419:    reachable on the ship path, since all four `GATE_TASKS` are one batch.
.claude/rules/verify-before-advancing.md:22:**Always (any code/config/docs change):** `mise run kb-gates` runs all four and
```

This drift predates this round (the comment cites "Cold lane round 2," an earlier session, and
`graph-size`/`hk-test` were added later per `CLAUDE.md`'s own dated note) — but it is still live and
uncorrected on disk today, in exactly the file whose job is to be the single source of truth for
what a "gate" means in this repo, and in the rule file every session is told overrides default
behavior. Low functional risk (nobody's code branches on the literal count "four"), but it is the
same class of trust defect as Finding 1: a reader who trusts the count next to `GATE_TASKS` gets a
false one from the two places most likely to be skimmed instead of grepped.

Remedy: fix both to say "six," or better, stop hardcoding the count and reference `len(GATE_TASKS)`
/ "every task in `GATE_TASKS`" so the next addition (there have already been two) cannot re-open the
same gap a third time.

## Coverage

**Reached and analysed:** this round's five landing commits' actual diffs (`8f285ce0`, `e4d3d27a5aa3`,
`17623a327323`, `b9ce6e0a4a8b`, `a7ae6d7be1c0`) cross-checked against the invariants/rule files that
describe the surfaces they touch — `do-not.md` items 1-5, `CLAUDE.md`'s Layout table row for
`graphify-out/`, `.gitignore`'s corpus-chunks carve-out comment, `sources/codex.manifest`'s
`build = skip` reason against the U0 commit body and the actual `graph.py` diff (confirmed
`is_package_manifest_path`/TOML-route support landed — the skip reason's premise, "a TOML file needs
new machinery," is now literally false for the codex source, matching the handoff's own OWED item
5 ["Lift `codex`'s `build = skip`"] — reported here as a live contradiction rather than re-filed,
since it is a deferral already recorded inside this reviewed window); `GATE_TASKS` in `gates.py`
against every place its count is asserted in prose (`gates.py:419`, `verify-before-advancing.md:22`,
`CLAUDE.md`'s `hk-test` row); the `_ACCEPTED_CLAUDE_VERSION`/`_CURRENT_CLAUDE_VERSION` pair in
`graphify_semantic_slice.py` (already self-corrected under #464, currently 2.1.238/2.1.241, no live
contradiction — the comment explicitly disclaims equality now); `_MAX_TOTAL_COST_USD` (63.0, matches
the settled-context figure, no drift); U8b0's biome pin (`mise.toml:63` = 2.5.10) against `hk.pkl`'s
`workflow_lint` gate comments — self-consistent, no contradiction found; the mise-tasks-only.md
`kb-check`/`kb-gates` distinction against `mise.toml`'s actual `[tasks.check]`/`[tasks.kb-check]`
definitions — present and named as expected, no drift found there.

Existing prior-round `.agent/kb/reports/agents/2026-08-23-session-review/refute-contradicted-*.md`
and `refute-*.md` files were spot-checked by filename/grep to avoid re-deriving already-refuted
claims (e.g. the AGENTS.md-existence and graphify-pin-version findings from the earlier
`096161cc-...`-scoped `contradicted.md` were not re-verified here — different scope, already
refuted in this same directory).

**Opened but not finished analysing:** `sources/REGISTRY.md` rows the handoff cites as "110-113"
for this round's new registrations — spot-checked rows 79-89 while orienting and found no
contradiction there, but did not locate or verify the actual cited rows against the 8-source U0
registration list; `antigravity_review_usage`'s claim that `--adversarial` is "unreachable from the
[agy-delegate] script" (settled-context JSON) — grepped this repo's own docs (`.claude/skills/kb-review/references/lanes.md`,
`kb-session-review/SKILL.md`, `kb-session-reflect/SKILL.md`) for corroborating or conflicting text
and found mentions but did not read the antigravity plugin's own installed source to confirm the
script/command split it asserts; the fuller `docs/plans/2026-08-23-directive-execution-plan.md`
(1,600+ lines) was only grepped for `JSON-only`/`build = skip`, not read end to end for further
plan-vs-code drift.

**Never reached:** the `.claude/skills/kb-curator`, `goal-engineering`, `tool-currency`,
`orchestrator-routing` SKILL.md bodies (only sections directly implicated by this round's diffs were
checked); `hk.pkl` read line-by-line against `zero-bash-logic.md`'s claims (spot-checked only the
biome-comment region); the ~2,795-line transcript itself was never read directly (per the
no-.jsonl-in-context instruction) beyond `head`/`tail`/`wc` for scope confirmation — all findings
here come from cross-reading the repo's committed docs/code/history that the transcript's own work
produced, not from transcript content; `currency.toml`'s `[tool.codex]` DRIFT-shape entry
(`currency.toml:1696-1816`) was located but not read in full against the manifest's `build = skip`
state for a second angle on Finding-1-adjacent codex machinery.

## GitHub repos touched

_None._ All evidence is from this repo's own tracked files, its git history, and its installed
`.venv` — no external repo source or docs were fetched for this analysis.
