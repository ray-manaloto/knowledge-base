# Triage labels

The mattpocock engineering skills speak in terms of five canonical triage roles.
This file maps those roles to the label strings this repo's tracker actually
uses. Consumed by `/mattpocock-skills:triage`, `to-tickets`, `to-spec` and `qa`.

| Role in the skills | Label here | Meaning |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate this issue |
| `needs-info` | `needs-info` | Waiting on reporter for more information |
| `ready-for-agent` | `ready-for-agent` | Fully specified, ready for an AFK agent |
| `ready-for-human` | `ready-for-human` | Requires human implementation |
| `wontfix` | `wontfix` | Will not be actioned |

The right-hand column is identical to the left because this repo had no prior
triage vocabulary to preserve. Edit the right-hand column — never the left — if
that ever changes; the left column is the skills' fixed vocabulary.

## Provenance

`wontfix` ships with every GitHub repo. The other four were **created on
2026-08-03**: `ready-for-agent` when #143 needed it, and `needs-triage` /
`needs-info` / `ready-for-human` alongside this file. Recorded because
`docs/issue-tracker.md` already carries the same note for the `wayfinder:*`
labels — a label that "should exist" and does not is otherwise indistinguishable
from a typo when a skill fails to apply it.

## These are not the only labels

`wayfinder:map` / `research` / `prototype` / `grilling` / `task` are a separate
vocabulary owned by `/mattpocock-skills:wayfinder` and documented in
`docs/issue-tracker.md`. The two sets are orthogonal: a wayfinder decision ticket
can also be `needs-info`.

## Why this file is not at `docs/agents/triage-labels.md`

Where `setup-matt-pocock-skills` would have put it. `agnix` treats any
`**/agents/*.md` as an agent definition requiring YAML frontmatter, so
`mise run lint-docs` **fails** on that path.

Re-probed 2026-08-03 against the currently pinned agnix, control-armed — the same
three-line file with no frontmatter at both paths:

| Path | `mise run lint-docs` |
| --- | --- |
| `docs/agents/probe.md` | **rc=1** — `error: Agent file must have YAML frontmatter` |
| `docs/probe-control.md` | rc=0 — `No issues found` |

The probe discriminates on path alone, so the constraint is real and current, not
inherited. See `docs/issue-tracker.md` for the same finding applied to the
tracker doc, including which skills read the `docs/agents/` path literally and
are therefore unaffected by this file's location only because they never look for
it.

## See also

- `docs/issue-tracker.md` — where issues live and how to operate on them.
- `docs/domain.md` — how skills should consume this repo's domain docs.
