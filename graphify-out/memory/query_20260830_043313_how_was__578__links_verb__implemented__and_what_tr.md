---
type: "query"
date: "2026-08-30T04:33:13.127505+00:00"
question: "How was #578 (links verb) implemented, and what tripped it up?"
contributor: "graphify"
outcome: "useful"
---

# Q: How was #578 (links verb) implemented, and what tripped it up?

## Answer

Shipped #578, the links verb, as PR #627 (merged eedc0142). The command shape was the hard part: a bare URL passed to lychee as a positional argument is treated as a page to scrape for links inside it, not as a link to check itself, and a URL that itself 404s in that form panics the whole process with empty stdout. Two full rounds of live premise-verification against the real lychee 0.24.2 binary were needed before dispatch — the first round found this bug plus eight others (the -v flag being required for lychee to report successes at all, the real JSON field names, no safe source for a checked count, lychee's own built-in excludes independent of any user config, and more); the second round, checking only the fix, found two more (redirect_map double-counting an entry already present elsewhere, and an incomplete migration of has_issues/has_discussions read sites). The corrected form writes URLs one-per-line to a temp file and points lychee at that file instead.

Separately, the codex-implementer dispatch itself misfired: the spawned agent had full Write/Edit tool access and wrote the diff directly rather than driving the actual codex CLI, despite being dispatched under that subagent_type. It self-reported this the moment asked. The diff was still fully correct and gate-verified, so it shipped as a Claude-authored diff with codex-reviewer as the cross-family lens (grok is not installed in this repo) rather than being discarded and redone.

The review found one real gap: the new verb had no dedicated mise task, unlike its sibling kb-research-trackers, breaking this repo's own mise-tasks-only convention. Fixed as a one-line follow-up commit, reviewed as its own fix-round report, and shipped in the same PR.


## Outcome

- Signal: useful