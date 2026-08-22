---
type: "query"
date: "2026-08-22T16:48:16.186510+00:00"
question: "Which repo actually guards the value-revealing credential verbs at its PreToolUse hook?"
contributor: "graphify"
outcome: "useful"
---

# Q: Which repo actually guards the value-revealing credential verbs at its PreToolUse hook?

## Answer

Neither repo guarded them. `kb_setup.secret_guard` (#441, commit b82ae397) is now
the only PreToolUse guard in either repo covering the credential VERBS.

The set is exactly the commands whose SUCCESS case writes a value to stdout:
`fnox get`/`export`, `fnox list --values`/`-V`, `doppler secrets get`/`download`,
bare `doppler secrets`, `security find-*-password -w`/`-g`, a bare
`env`/`printenv`/`set`, and the paired `:+`/`:-` substitution over one name.

Two departures from the ticket's proposed list, both control-armed:

1. BARE `doppler secrets` is denied and #441 did not ask for it. Its own `--help`
   documents `--only-names` as "only print the secret names; omit all values", so
   omitting the flag is what prints them. Denying only the two named verbs would
   have missed the shortest way to dump the project.
2. Only the PAIRED substitution is denied, never a lone `:-` default. That form is
   among the commonest idioms in shell; every measured defect in this repo's four
   existing guards has been a FALSE POSITIVE, never an evasion, so the rule stays
   narrow.

That asymmetry is why half the test file pins the ALLOW set rather than treating
it as the absence of a deny: `[[ -v NAME ]]`, `fnox list`/`check`/`doctor`,
`doppler secrets --only-names`, and `doppler secrets set` (the sanctioned
nine-step add). A guard that refuses the procedure it protects is worse than none.

EVIDENCE. Arms `.agent/kb/arms/secret-guard-441.toml`: 6/6 died, 1/1 control held,
and TWO of the six break the ALLOW direction on purpose. Live in a real session
hook: `fnox get SOME_KEY` refused with its remedy while `[[ -v .. ]]` and
`fnox list` both ran.

THE GUARD'S FIRST TWO CATCHES WERE BOTH ITS AUTHOR, and they point opposite ways.

TRUE POSITIVE: posting the correction comment via `gh issue comment --body "..."`
was denied, because a DOUBLE-QUOTED body holding the paired substitution is
expanded by the shell before `gh` ever sees it — with a real credential name that
comment would have carried a value into a public issue. Remedy: `--body-file`.
This repo's "prose to a CLI goes via a FILE" lesson, arriving for the fourth time.

FALSE POSITIVE, twenty minutes later: writing THIS file through a QUOTED heredoc
(`<<'EOF'`) was denied too. A quoted heredoc never expands, so there was nothing
to leak. Fixed by stripping quoted-heredoc bodies before the substitution scan
and reusing `graph_first.HEREDOC` rather than writing a second matcher — an
UNQUOTED heredoc still expands and is still scanned. The pair is the lesson: the
same rule produced the guard's best catch and its first false alarm within one
session, and only the second one is a defect.

WHAT IT STILL DOES NOT DO: a redirect guard, not a sandbox — command substitution,
`sh -c`, `eval` and aliases pass by design. It cannot see a verb nobody thought
of, which no mutation sweep can detect either. And it does not touch vendored
`sources/media/**`: a dangerous fence there still reaches the graph; the guard is
what stops it being RUN.


## Outcome

- Signal: useful