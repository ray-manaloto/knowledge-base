---
type: "query"
date: "2026-08-27T00:46:51.573912+00:00"
question: "Why does the knowledge-base keep drifting off its own research-funnel mandate, and what actually enforces each clause?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why does the knowledge-base keep drifting off its own research-funnel mandate, and what actually enforces each clause?

## Answer

# Why the knowledge-base drifts off its own mandate — 2026-08-26c

Ray restated the project's goal and said it "keeps not being followed": the KB is
a RESEARCH FUNNEL — all research to the KB first; web research STORED into
graphify sources so it is never repeated; sources staleness-tracked and
auto-resynced; delivered as claude/codex plugins plus a CLI. "this repo becomes
the tool."

## The diagnosis is mechanical, not behavioural

The mandate has been in the repo, verbatim, since 2026-08-02
(`docs/direction/2026-08-02-ray-directives.md:94,96,102,114,124`). It is FILE 1
OF 11 in an append-only log, and every reader takes only the newest:
`CLAUDE.md:173` ("clear-prep reads the newest one"), `kb-resume/SKILL.md`
(`ls -t … | head -2`), and — found by the adversarial pass —
`kb-session-review/SKILL.md:41` and `session-review.js:91` as well. NO hook,
gate or task anywhere reads the full log. A directive filed there is archived,
not adopted, which is why Ray has to keep repeating it.

Neither auto-loaded instruction file states the purpose. `CLAUDE.md:3-5` and
`AGENTS.md:3-5` both describe the ARTIFACT ("a knowledge graph any agent connects
to"). An agent reading its instructions faithfully concludes the job is
maintaining a graph — which is what every round has done.

## Five clauses, zero mechanisms

| clause | enforcement |
|---|---|
| research to the KB first | `graph_first` matches `Bash\|Grep` only; `hook_guard.py:279` hard-codes that set, so web tools are unreachable even if the matcher widened |
| web research stored | `kb-add` is `run = "graphify add"` into a gitignored dir + 6 manual steps |
| never researched twice | nothing. No URL index. `REGISTRY.md` (113 rows) has zero tooling |
| staleness + resync | 1 of 4 source classes; `kb-update` invoked by no hook, cron, gate or CI |
| plugins + CLI | no plugin manifest exists (0 at root vs 189 under `sources/`) |

## The round proved its own diagnosis

`git diff --numstat main..HEAD -- sources/` -> 0 lines, 0 files. Control
`-- docs/` -> 4,821 lines / 33 files. 6,450 lines added, ZERO to the corpus.
Measured independently by a second blind lane: `curl` ran 31 times, 0 wrote into
`sources/`, `kb-add`/`kb-fetch` never used. Clause 2 scored 0 for 31.

## The single most transferable measurement

"Every task that is HOOK-ENFORCED was used; every task that is only DOCUMENTED
was not." Against 140/274 open issues serving no mandate clause, 0 of 48 P0/P1
serving the funnel or plugins, 8.82 shell segments per agent Bash call, 445 no-op
`cd` prefixes, 37.3% of thinking tokens on plumbing, and a 3.5x cost ratio
between a sanctioned task call and its hand-rolled equivalent.

## What the platform already provides

Ray has asked for structured logging with enum error codes and runbooks in 4 of
11 direction files over 9+ days. It kept reading as scope. It is not scope: the
OTEL `claude_code.tool_result` event already emits `success`, `error_type`
(an enum — "Error:ENOENT", "ShellError"), `duration_ms` and
`tool_parameters.full_command` (`monitoring-usage.md:631-657`), and a PostToolUse
hook exiting 2 surfaces stderr TO CLAUDE (`hooks.md:778`) so a runbook can be
delivered at the moment of failure. `PreToolUse.updatedInput` rewrites a command
before it runs (`hooks.md:1006`), so `set -o pipefail` needs no `~/.zshrc` change.
Every piece was documented and unread.


## Outcome

- Signal: useful