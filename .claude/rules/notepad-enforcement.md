# Notepad Enforcement: Agents Must Record Findings

All agents performing research, debugging, ingestion, or multi-step analysis
MUST write findings to the notepad immediately — not at session end.

## The notepad is a file, not a tool

The notepad is **`.agent/notepad.md`** (gitignored). Write to it with the ordinary
Write/Edit tools, appending as you go.

Do not reach for an MCP "notepad" tool: the tools that name once carried ship
with the `oh-my-claudecode` plugin, which is not enabled in this repo, so they
are absent from every session. A rule that names an unreachable mechanism is
unfollowable — name the file.

## This repo has a SECOND, durable memory: use both

`.agent/notepad.md` is scratch and gitignored. The knowledge graph's
work-memory is committed and is what makes the corpus self-improving:

- `mise run kb-remember -- --question "Q" --answer "A" --outcome useful`
  records the outcome of an ingestion or query into `graphify-out/memory/`
  (the ONE committed subdirectory of an otherwise derived tree).
- `mise run kb-reflect` aggregates that memory into `reflections/LESSONS.md`
  plus the learning overlay.

**Both, every time.** The notepad carries the running condensed finding for
*this* session; `kb-remember` carries the durable lesson for every future
session and every consumer repo. Skipping the second is how a lesson stays
private to a transcript nobody will read again.

## Rules

1. **Write findings as you go**: After each significant discovery, append it to
   `.agent/notepad.md`. Mark critical items so they survive a skim.

2. **What to record**: Root causes found, design decisions made, dead ends
   explored, verification results, and any context the next agent will need.

3. **Never batch findings**: Do not accumulate findings in memory and write
   them all at session end. Each finding should be persisted within the same
   step it was discovered.

4. **Research agents especially**: Any multi-file analysis or research sweep
   MUST write intermediate findings before proceeding to the next file or step.
   An agent that dies after 40 minutes holding everything in memory leaves
   nothing; one writing incrementally leaves everything it had reached.

5. **Close the ingestion loop**: every `kb-add` / `kb-merge` cycle ends with
   `kb-remember` + `kb-reflect`. That is not bookkeeping — it is the mechanism
   by which the corpus gets smarter per ingestion (`kb-curator` MANDATE).

## Verification

After an agent completes work, check `.agent/notepad.md` for findings. If it is
empty or stale relative to the work performed, the agent did not comply.

## See also

- `agent-report-persistence.md` — the full-fidelity layer; this rule covers
  the running condensed findings.
- `omc-directory-conventions.md` — where each artifact type lives.
