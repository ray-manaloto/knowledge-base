# Refutation attempt — finding 16 (lane: contradicted)

CLAIM: Root CLAUDE.md Quick Start (line 93) instructs `graphify install --project`
directly; reinforced by CLAUDE.md:15 and do-not.md:9.

VERDICT: **NOT REFUTED.** Every load-bearing sub-claim reproduced, and the
end-to-end hook (not just `decide()`) denies the command.

## Probes

1. Line anchor, exact:
   `grep -n "graphify install" CLAUDE.md .claude/CLAUDE.md .claude/rules/do-not.md .claude/rules/mise-tasks-only.md`
   -> `CLAUDE.md:93:graphify install --project                    # project-scoped skill + graphify-out/`
      `CLAUDE.md:15:   \`graphify install --project\`. Never bare \`graphify install\` (mutates`
      `.claude/rules/do-not.md:9:   - \`graphify install --project\` → **project only** (adds`
      `.claude/rules/mise-tasks-only.md:26:| \`graphify install --project\` ... | \`mise run kb-skill-refresh\` ...`
   Line 93 sits inside a ```bash fence under `## Quick start` (sed -n '85,100p').

2. END-TO-END hook, not just decide() (this is stronger than the original evidence):
   `echo '{"tool_name":"Bash","tool_input":{"command":"graphify install --project"}}' | uv run --project ./python kb-setup hookguard`
   -> `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": "Do not run \`graphify install\` by hand. ... NOT ALLOWED — graphify install mutates config; this KB is project-only. ..."}}`
   CONTROL ARM: same entrypoint, `graphify explain foo` -> **no output, rc=0** (allowed).
   So the probe discriminates; it is not a deny-everything guard.

   Wiring confirmed live: `.claude/settings.json` PreToolUse block 2,
   matcher `Bash|Grep`, command `uv run --project "${CLAUDE_PROJECT_DIR:-.}/python" kb-setup hookguard`.

3. Flag-blindness confirmed at source:
   `hook_guard.py:86` `"install": "NOT ALLOWED — graphify install mutates config; this KB is project-only"`
   `hook_guard.py:142-147` matches `_GRAPHIFY_CMD.group(1)` (the subcommand) only; flags never inspected.
   Both `graphify install` and `graphify install --project` return the identical reason string.

4. Test coverage:
   `grep -c -i "install" tests/test_hook_guard.py` -> **0** (rc=1)
   CONTROL: `grep -c -i "query" tests/test_hook_guard.py` -> **2**. Probe discriminates.
   `grep -rn "graphify install" tests/` -> **no hits** anywhere in tests/.

5. No authoring gate can catch it: `skill_lint.DEFAULT_SKILL_GLOBS` (skill_lint.py:66) is
   `(".claude/skills/*/SKILL.md", ".agents/skills/*/SKILL.md")` — `CLAUDE.md` is out of scope.
   So the contradiction is unreachable by every existing gate.

6. No tracking issue: `gh issue list --state all --search "graphify install --project quick start"` -> `[]`.
   CONTROL: `--search "graphify install"` -> 10 issues returned. Search discriminates.

## Refutation angles tried and failed

- *Maybe the guard fails open on the `--project` flag.* No — flags are never read (probe 3),
  and the live end-to-end run denies (probe 2).
- *Maybe kb_setup.hook_guard is no longer wired and only graphify's vendored hook runs.*
  No — settings.json carries BOTH; the `kb-setup hookguard` block is present and produced the deny.
- *Maybe the line is prose, not an instruction.* No — it is a bare command line inside a
  ```bash fence in `## Quick start`.
- *Maybe a same-file corrective neutralises it.* Partially, and it makes the file
  self-contradictory rather than consistent: **CLAUDE.md:60** says "Never run graphify by hand —
  drive it through a mise task", 33 lines ABOVE the fence that tells you to run it.
  Same shape in do-not.md: **do-not.md:51** rule 3 says "Do NOT run graphify by hand at all",
  while do-not.md:5 says "always pass `--project`" and :9 describes it as project-only/safe.

## Scope caveat (the one place the finding is loose)

Calling do-not.md:9 a "reinforcement" is the weakest link: line 9 is a *description of effects*
inside a rule whose rule 3 (line 51) forbids the hand-run outright. do-not.md:5's imperative
("always pass `--project`") is the better citation for the reinforcement claim. This does not
change the verdict — CLAUDE.md:93 alone carries it.

## Contradiction with other findings in the set

None. **Finding 15** (graphify's vendored `hook-guard search` telling the agent to run raw
`graphify query`) is the same class at a different artifact and CORROBORATES rather than
contradicts: settings.json:14-23 is confirmed present in the same file I read for probe 2,
and its advisory text fired on every Bash call in this session
("MANDATORY: ... You MUST run `graphify query \"<question>\"` before grepping raw files"),
while `decide("graphify query ...")` redirects to `mise run kb-query`.
No other listed finding touches CLAUDE.md:93.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under audit; issue search.
