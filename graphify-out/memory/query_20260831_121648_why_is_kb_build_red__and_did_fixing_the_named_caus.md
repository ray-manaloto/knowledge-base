---
type: "query"
date: "2026-08-31T12:16:48.249392+00:00"
question: "Why is kb-build red, and did fixing the named cause unblock it?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why is kb-build red, and did fixing the named cause unblock it?

## Answer

# Round kb-20260830.004 — what it asked and found

**Question:** why do `next-ticket` and the active plan disagree about what is next,
and can the two files be collapsed into one?

**Answer:** they never disagreed. The tracked chain places issue #638's re-grill
BEFORE `/to-spec`, and the plan's Phase 3 *is* `/to-spec` — so the real order is
re-grill → Phase 2 → Phase 3. The plan simply never encoded the re-grill as a
checkbox, so its `## Next Step` opened one step late. Fixed by adding a Q0 item.

They cannot be collapsed. `next_ticket.py`'s own docstring states the chain file is
the tracked ORDERING while the tracker is the tracked STATUS, and that it exists
because "a plan that lives only in a session scratchpad dies with the session".
`planning-with-files` documents its plan files as working memory for one task, with
no archived state and no built-in archive step — so it structurally cannot hold
cross-round ordering. What WAS duplicated is one field: `## Next Step`, which the
plugin injects into every prompt. That field now carries no cross-round pointer and
no command name.

**Upstream graphify has an opinion on `graphify-out/` and it is the opposite of ours:**
"graphify-out/ is meant to be committed to git so everyone on the team starts with a
map", excluding only `cost.json` and optionally `cache/`. We invert that solely
because our graph is 737 MB. So a tracked purpose-named subdirectory there is the
right SHAPE; the defect is that `do-not.md` claims one exception while the repo has two.

**`kb-build` was red for neither of the two reasons anyone assumed.** Not a graphify
defect and not the `graphify_health` stderr policy: `sources/ast-grep.manifest`
documented "extraction deferred" in a COMMENT and never set the `build` key, so it
defaulted to `include`, was extracted, and its bare workspace `Cargo.toml` produced
the zero-node warning nothing had approved. A second failure was queued behind it:
commit `b2d51b53` bumped six manifests and touched `graph.py` zero times, leaving
`uv`'s registered `Cargo.toml` hash stale.

**The systemic finding behind that:** 14 sources have a pin living in TWO files — the
manifest and `graph.py`'s `_EXPECTED_METADATA_ONLY` — with no gate forcing them to
move together. `sources/graphify.manifest` already warns about exactly this shape in
its own comments; it is the only pair anyone thought to warn about.

## The build was run, and it FAILED AGAIN — the fix was incomplete

`mise run kb-build` ran to completion at 2026-08-31T12:15:42Z and **failed with the
identical error**, on a different source. Confirmed with a control arm:
`sources/biome/Cargo.toml` is a bare `[workspace]` with **0** `[package]` sections;
`grep -c 'source_name="biome"' graph.py` → **0** while the same grep for `uv` → **1**,
so biome is genuinely unregistered and the probe discriminates; and
`grep -cE '^build' sources/biome.manifest` → **0**, so it is not deferred either.

**This is the third instance of one defect, and that is the actual finding.** Fixing
`ast-grep` let extraction get *further*, to `biome`. Any source with a bare workspace
`Cargo.toml` that is neither registered in `_EXPECTED_METADATA_ONLY` nor `build`-excluded
fails the same way, one at a time, in whatever order extraction reaches them. There are
**34** `Cargo.toml` files under `sources/`; **14** sources are registered; the remainder
are unaudited.

**So the per-source fix is the wrong shape of fix.** Chasing them one build at a time
costs a full clone-and-extract cycle per instance — this one took ~55 minutes to reveal
a single name. The gate belongs upstream of that: enumerate every source's bare package
manifests once and require each to be registered or excluded, checked without a build.

**And the exit code lied.** The background task reported `exit code 0`; the run had
failed. That is `tail`'s status, because the invocation was piped — the exact
anti-pattern this repo has a rule about, committed by me while writing about it.


## Outcome

- Signal: useful