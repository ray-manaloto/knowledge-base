---
type: "query"
date: "2026-09-03T06:30:22.498238+00:00"
question: "Does kb-codex --review --output persist the lane's report?"
contributor: "graphify"
outcome: "corrected"
correction: "`kb-codex --review --output <path>` SILENTLY DROPS THE FLAG.\n\nI passed `--output .agent/kb/review/reports/review-<sha>-cold.md` expecting the\nlane to persist its own report — the exact remedy the previous round's handoff\nprescribed after losing a transcript to the reaped scratchpad. No file was\nwritten. The lane ran fine, rc 0, and the report simply did not exist.\n\nControl-armed, both directions, via `--print-argv` (which spawns nothing):\n\n  review mode: `codex review --base origin/main -c developer_instructions=\"…\"`\n               -> no `-o` anywhere\n  exec mode:   `codex exec --sandbox read-only -o /tmp/x.md -c … -- -`\n               -> `-o` present\n\nSo the flag is honoured in exec mode and dropped in review mode. It is ACCEPTED\nby the argument parser in both, which is what makes it dangerous: nothing errors,\nnothing warns, and the caller's evidence-persistence step becomes a no-op at\nexactly the moment it is being relied on.\n\nTHE GENERAL FORM: an accepted flag that does nothing is worse than a rejected\none. A rejected flag fails loudly at the call site; an ignored one succeeds and\ntakes the guarantee with it. When a flag exists to produce an ARTIFACT, the arm\nis to check the artifact, not the exit code — rc 0 says the command ran, never\nthat the flag did anything.\n\nI recovered by copying the 391,827-byte transcript out of the scratchpad by hand\nbefore it was reaped, so nothing was lost this time. The previous round was not\nso lucky and had to reconstruct its report from commit bodies.\n"
---

# Q: Does kb-codex --review --output persist the lane's report?

## Answer

The cold `codex review` lane, given a METHOD paragraph, found 3 P2 findings on a
DOCS-ONLY diff — and all three were the same species: a figure or a citation that
was believed because it sat beside something authoritative-looking.

1. `list_repositories` returns **15 repository entries**, of which only **14** are
   `status: ready` / `queryable: true`. One
   (`ray-manaloto/pydantic-deepagent-auto-claude`) is `not_started`,
   `queryable: false`, `nodeCount: null`. The branch had written "15 indexed
   repositories". Confirmed by a second, independent call by the caller.
2. An ELI5 page turned a tool-NAME count into a CAPABILITY claim — "21 of its 24
   tools have no answer on our side". The TOML comment beside it was careful to
   say "a tool count, not a capability count"; the page dropped the qualifier.
   Several hosted names have a local answer under a different name
   (`graphify_node` vs `get_node`).
3. Two files attributed the HOSTED 24-tool count to
   `sources/graphify/graphify/serve.py:1614-1744` — the file that defines the
   LOCAL ten-tool server. The lane AST-walked its `list_tools` and got the local
   ten back, which is the probe that settles it. The 24 was correct; its
   provenance was not.

WHAT THE METHOD PARAGRAPH BOUGHT. It said, in substance: do not review by reading;
for every numeric or factual claim, construct the derivation and RUN it, and check
CLI/config claims against pinned argument definitions rather than help text or
error strings. On a diff with no executable code this is the ONLY thing that could
have produced findings 1 and 3 — both are invisible to a reading pass, because
prose that cites a real file at real line numbers reads as sourced.

WHAT THE LANE GOT WRONG, and why checking it mattered. It reported that the
15-repo error also appeared in the two `graphify-out/memory/` files. It does not:
those say "returned 15 repositories, among them <name> at status: ready,
queryable: true", which is an accurate statement about what the call returned.
Accepting a correct finding's STATED SCOPE without checking it would have produced
an incorrect edit to committed work-memory.

VERIFIED: 24 / 10 / 3 and the 13,152 nodes all hold, by two independent routes
(the lane's `comm` over sorted registries, and the caller counting this session's
own `mcp__graphify__*` / `mcp__kb__*` tool roster).


## Outcome

- Signal: corrected
- Correction: `kb-codex --review --output <path>` SILENTLY DROPS THE FLAG.

I passed `--output .agent/kb/review/reports/review-<sha>-cold.md` expecting the
lane to persist its own report — the exact remedy the previous round's handoff
prescribed after losing a transcript to the reaped scratchpad. No file was
written. The lane ran fine, rc 0, and the report simply did not exist.

Control-armed, both directions, via `--print-argv` (which spawns nothing):

  review mode: `codex review --base origin/main -c developer_instructions="…"`
               -> no `-o` anywhere
  exec mode:   `codex exec --sandbox read-only -o /tmp/x.md -c … -- -`
               -> `-o` present

So the flag is honoured in exec mode and dropped in review mode. It is ACCEPTED
by the argument parser in both, which is what makes it dangerous: nothing errors,
nothing warns, and the caller's evidence-persistence step becomes a no-op at
exactly the moment it is being relied on.

THE GENERAL FORM: an accepted flag that does nothing is worse than a rejected
one. A rejected flag fails loudly at the call site; an ignored one succeeds and
takes the guarantee with it. When a flag exists to produce an ARTIFACT, the arm
is to check the artifact, not the exit code — rc 0 says the command ran, never
that the flag did anything.

I recovered by copying the 391,827-byte transcript out of the scratchpad by hand
before it was reaped, so nothing was lost this time. The previous round was not
so lucky and had to reconstruct its report from commit bodies.
