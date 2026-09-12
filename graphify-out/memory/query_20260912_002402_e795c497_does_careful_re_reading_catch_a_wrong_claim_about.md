---
type: "query"
date: "2026-09-12T00:24:02.631493+00:00"
question: "Does careful re-reading catch a wrong claim about where something is declared?"
contributor: "graphify"
outcome: "corrected"
correction: "Nine wrong claims in one round, all one shape: a plausible file or rule named\nwithout the probe that would settle it. NOT ONE was caught by re-reading; every\none fell to a probe down a DIFFERENT route — config-read to TOML parse, `grep -n`\nto `sed -n`, `grep -rl` to `file(1)` (a \"config\" was a Mach-O binary), bare\nbasename to explicit path, reading a type to COMPILING against it, `command -v`\nto an explicit path (a mise shim shadowed the real claude and answered\nplausibly).\n\nThe belief overturned: that careful re-reading catches a wrong claim. It does\nnot. A wrong answer from the wrong instrument does not LOOK wrong — one hit, a\nclean rc=1, a line that exists — so nothing invites a second look. Care is spent\nreading the output, and the output is fine.\n\nInstances 5, 7 and 8 were made AFTER the pattern had been named aloud, including\nby the lane that named it. Knowing the pattern does not avoid it; changing the\ninstrument does. Recorded as `.claude/rules/change-the-route.md`.\n"
---

# Q: Does careful re-reading catch a wrong claim about where something is declared?

## Answer

# Round: G00 built and armed; the dotfiles function-hooks issue filed

Two deliverables and one method finding.

**G00 (#753)** — `mise run kb-guard-inventory-check` reconciles a committed
inventory of this repo's whole enforcement surface against live state: 21
registrations (28 effective cases), 11 guard modules / 4,024 lines, 15
`do-not.md` invariants. Membership is REACHABILITY via `ast.walk` over
`ImportFrom` at all depths; ids are semantic strings, never indices; three axes
(Disposition x CurrentSurface x OwnerKind); `RegistrationState` has four values
and the gate REJECTS a row claiming `installed`/`exercised`, which are G04's. No
count is stored — all re-derived. Armed 6/7, control held.

**dotfiles#1020** — "Evaluate Claude Code function hooks: runtime compatibility,
guard preservation, and measured cost". 887 lines, four codex lanes, all rc=0,
none refused.

**The corrected numbers that mattered**: the programme report published 7 guard
modules / 2,859 lines; the truth is 11 / 4,024, because its census came from a
NAME pattern and four guards contain none of its tokens — one live for a month.
M7's arithmetic is 3+3+1+6 not 3+2+1+7, so the migration target is 6 new
enforcements plus #7 as a timing upgrade. 18 registrations is not the coverage
denominator; 28 effective cases is.

**The Bash finding, which decides dotfiles' adoption**: the `#92533` mitigation
is NOT "one literal matcher per tool" — the upstream reproducer IS a literal
`{tool:"Bash"}` passthrough. The rule is never register `tool.call` on Bash, so
dotfiles' Bash guard is the one thing that cannot migrate.


## Outcome

- Signal: corrected
- Correction: Nine wrong claims in one round, all one shape: a plausible file or rule named
without the probe that would settle it. NOT ONE was caught by re-reading; every
one fell to a probe down a DIFFERENT route — config-read to TOML parse, `grep -n`
to `sed -n`, `grep -rl` to `file(1)` (a "config" was a Mach-O binary), bare
basename to explicit path, reading a type to COMPILING against it, `command -v`
to an explicit path (a mise shim shadowed the real claude and answered
plausibly).

The belief overturned: that careful re-reading catches a wrong claim. It does
not. A wrong answer from the wrong instrument does not LOOK wrong — one hit, a
clean rc=1, a line that exists — so nothing invites a second look. Care is spent
reading the output, and the output is fine.

Instances 5, 7 and 8 were made AFTER the pattern had been named aloud, including
by the lane that named it. Knowing the pattern does not avoid it; changing the
instrument does. Recorded as `.claude/rules/change-the-route.md`.
