---
type: "query"
date: "2026-09-12T00:23:56.049853+00:00"
question: "What is this repo's guard enforcement surface, and can a dotfiles function-hooks adoption preserve it?"
contributor: "graphify"
outcome: "useful"
---

# Q: What is this repo's guard enforcement surface, and can a dotfiles function-hooks adoption preserve it?

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

- Signal: useful