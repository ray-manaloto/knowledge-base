# Refutation lane — finding 20 (native graphify hook-guard vs custom graph_first)

## What is TRUE in the finding
- `.claude/settings.json:19,39` wires `graphify hook-guard search` (Bash|Grep) and
  `graphify hook-guard read` (Read|Glob). Confirmed live: every Bash call in this
  session returns `MANDATORY: graphify-out/graph.json exists...`.
- `mise exec -- graphify --version` -> `graphify 0.9.45` (matches pin).
- The five named rule files do NOT mention the native mechanism (verified below).

## What is REFUTED
The offered probe `grep -rn 'graphify hook-guard' .claude/ CLAUDE.md docs/` is a
TOKEN-SPELLING BOUND. Re-run with the variant `hook-guard`:

    docs/research/reports/2026-08-05-graphify-capability-expert.md:156:
    | `hook-check` / `hook-guard` (1958-1974) | graphify's own PreToolUse guard — §0b |

And §0b of that same committed report (lines 45-55) IS the native-vs-custom
check, run and recorded:

    ### 0b. graphify's own hook is fighting this repo's hook
    Every Bash call this session returned
    `MANDATORY: graphify-out/graph.json exists. You MUST run graphify query …`.
    That string is graphify's, not the harness's: `GX/cli.py:578-586` (`_SEARCH_NUDGE`),
    with `_READ_NUDGE` (`cli.py:588-604`) and a **hard deny** `_READ_DENY`
    (`cli.py:610-628`, `permissionDecision: "deny"`, once per session, gated by
    `_hook_strict_enabled` / `GRAPHIFY_HOOK_STRICT`, `cli.py:425-433`). It instructs an
    agent to run exactly the raw `graphify query` that `kb_setup.hook_guard:72` DENIES.
    Two guards in direct contradiction; this repo's wins (`mise run kb-query`). Worth
    knowing it is a vendored string, not a system opinion.

Second, independent route: `docs/graphify-reference.md:164` (the doc CLAUDE.md
names as the graphify mental model):
    `--strict` install blocks the first raw read → redirects to `graphify query`
    (toggle `GRAPHIFY_HOOK_STRICT`).

## Control arm for the probe
`grep -rn 'graphify hook-guard' docs/` -> 0 hits (the finding's answer),
while `grep -rn 'hook-guard' docs/` -> 2 hits including the one above.
Same corpus, same command shape, different spelling => the probe could only ever
have returned "absent" for docs/.

## DECISIVE: the tracked, indexed research index already states the overlap
`docs/research/README.md:64` (tracked, the index `research-repo-enumeration.md`
points at), verbatim excerpt:

    ... and the `MANDATORY: run graphify query` banner on every Bash call is
    **graphify's own vendored hook text** (`cli.py:578-628`), instructing an
    agent to run the command `kb_setup.hook_guard` denies.

`git ls-files --error-unmatch docs/research/reports/2026-08-05-graphify-capability-expert.md`
-> TRACKED.

So the native-vs-custom check WAS run and WAS recorded, on 2026-08-05, with
source line cites and a disposition ("this repo's wins"). The finding's clause
"despite `tool-currency-and-native-first.md` explicitly mandating this exact
native-vs-custom check be run and recorded" is false on the recorded half.

## Narrow residue that survives (verified, control-armed)
`for f in <the 5 named files>; do grep -n -i -e 'hook-guard' -e 'nudge' -e
'PreToolUse' -e 'strict' -e "graphify's own" $f; done`
-> hits only for unrelated tokens (`mise-tasks-only.md:14,48`, `do-not.md:52`,
`CLAUDE.md:62`), none naming the native mechanism. Control arm: the same command
DID return matches from those files, so the probe discriminates.
That residue is "the 5 rule files do not cross-reference an already-written
research finding" — a doc-linkage nit, not "no rule file ... ever mentions"
elevated to an unrecorded native-first violation.

## Relation to other findings this round
Supports finding 1 (META-CIRCLE): this lane re-derived, as a novel gap, a
conclusion already committed to disk in `docs/research/` on 2026-08-05.
No other listed finding contradicts.
