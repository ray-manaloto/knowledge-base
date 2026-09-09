---
type: "query"
date: "2026-09-09T00:38:26.847622+00:00"
question: "Is restoring .codex/config.toml from HEAD a safe recovery from the #710 import rewrite?"
contributor: "graphify"
outcome: "corrected"
correction: "A check's REMEDY is part of the check, and it gets less review than the\ndetection. The tripwire's detection logic had 12 tests and three verdict arms;\nits printed advice had none, so the advice could be — and was — wrong on arrival\nand stayed wrong through a cold review that rated the module NO P0/P1.\n\nTwo further specifics worth carrying:\n\n1. **The advice fix passed every gate with NOTHING going red.** The render\n   asserted the recovery command and the issue number and never the guidance. A\n   green suite over a changed message is not evidence; it is the absence of a\n   question. Two arms (A2, A3) now pin both halves.\n\n2. **A schedule claim died on its fourth data point.** The message asserted\n   \"~03:29\", true of the 2026-09-05 and 09-06 events — three occurrences within\n   two seconds of one clock minute, which is precisely what makes a fixed-timer\n   claim persuasive enough to write into code. The fourth was 22:21:10Z and the\n   fifth 00:37Z. A schedule this repo neither owns nor observes is not a fact it\n   should assert. Removed, and pinned by an arm so it cannot be re-added.\n\nThe general form: when you write a remedy into a tool's output, ask what state\nthe remedy LEAVES BEHIND, not just whether it undoes the damage.\n"
---

# Q: Is restoring .codex/config.toml from HEAD a safe recovery from the #710 import rewrite?

## Answer

# The #710 tripwire's own recovery advice was arming the rewrite it detects

Shipped on 2026-09-08 morning: a SessionStart check that diffs
`.codex/config.toml` against its committed copy and, on CHANGED, prints
`git stash push … -- .codex/config.toml` as the recovery.

Two codex research lanes then read the importer's own source. It is not opaque:
`openai/codex`'s `external-agent-migration` crate, driven by the ChatGPT desktop
app through `externalAgentConfig/import`.

**A category writes only when the merge finds something ABSENT** — `import_config`
needs a missing value (`service.rs:590-595`), `import_mcp_server_config` a missing
server NAME (`:633-635`). `HEAD` deliberately carries no
`[mcp_servers.graphify]`. So restoring the committed copy RE-CREATES the exact
gap the next import fills, and the whole-file `toml::to_string_pretty` +
`fs::write` (`config_values.rs:77-80`) takes the comments with it again.

The check was therefore detecting a defect and, in the same breath, arming its
next occurrence.


## Outcome

- Signal: corrected
- Correction: A check's REMEDY is part of the check, and it gets less review than the
detection. The tripwire's detection logic had 12 tests and three verdict arms;
its printed advice had none, so the advice could be — and was — wrong on arrival
and stayed wrong through a cold review that rated the module NO P0/P1.

Two further specifics worth carrying:

1. **The advice fix passed every gate with NOTHING going red.** The render
   asserted the recovery command and the issue number and never the guidance. A
   green suite over a changed message is not evidence; it is the absence of a
   question. Two arms (A2, A3) now pin both halves.

2. **A schedule claim died on its fourth data point.** The message asserted
   "~03:29", true of the 2026-09-05 and 09-06 events — three occurrences within
   two seconds of one clock minute, which is precisely what makes a fixed-timer
   claim persuasive enough to write into code. The fourth was 22:21:10Z and the
   fifth 00:37Z. A schedule this repo neither owns nor observes is not a fact it
   should assert. Removed, and pinned by an arm so it cannot be re-added.

The general form: when you write a remedy into a tool's output, ask what state
the remedy LEAVES BEHIND, not just whether it undoes the damage.
