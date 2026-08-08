---
type: "query"
date: "2026-08-08T08:31:37.291329+00:00"
question: "What did the 2026-08-08 tool-currency round teach about bumping tools and about my own fixes?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the 2026-08-08 tool-currency round teach about bumping tools and about my own fixes?

## Answer

A full tool-currency round (PR #247, 2026-08-08) bumped six tools, advanced seven source manifests, closed #242, rebuilt the graph under graphify 0.9.36 (357,217 -> 358,756 nodes, 876,064 -> 880,924 links, 122 hyperedges), and re-probed all 13 local watch items. What it actually taught is about the WORK ON TOP of a bump, not the bump.

SIX OF ELEVEN COLD-REVIEW FINDINGS WERE DEFECTS IN MY OWN FIXES OR MY OWN RECORDS, not in the original commit. Two were code: #242's fix was DEAD CONFIG because `sync.check_sync` returns out of `_check_self_managed` before `_check_manifest` is reachable, so a `manifest` key on an `expected`-based row is parsed and never read - for exactly the two tools (mise, claude-code) #242 was about. Armed: `sources/mise.manifest` reverted THREE releases reported silence, while the identical mutation on mise-managed `hk` fired, so the silence was the checker's. The second: `apply()` passed an empty `mise_key` into the pin editor, raising a bare KeyError instead of the clean refusal this fail-closed engine produces everywhere else. Two more were FALSE CLAIMS I wrote into committed run reports - gate answers saying re-probes had been "appended to currency.toml" when `grep 290` and `grep superseded` both returned 0 against a control of 9. The claim was written; the append was not done.

AN INHERITED "THIS WAS REFUTED" NOTE IS SCOPED TO THE FUNCTION IT WAS MEASURED ON. My memory records that #235 refuted an annotated-tag drift bug, and round 2's P2 looked like that settled claim resurfacing. It was not: #235 concerns `manifest.latest_commit`, which passes an EXACT ref to `git ls-remote` and therefore gets only the tag-object line, so that compare is genuinely fine. `sync._tag_commit` is a different function reading a LOCAL CLONE with `git rev-list -n1`, which PEELS. Constructed the reaching case rather than reasoning about it - a real clone with `.git` at v2026.8.3 gives manifest `dd76a503e34e` vs rev-list `e6d9aed080ef` -> DRIFT on a manifest pinned exactly right. Control: uv's `0.12.3` is a LIGHTWEIGHT tag (one SHA), so uv and ruff cannot exhibit it. Filed as #246 rather than fixed, because which side is wrong depends on what `kb-build` checks out, and normalising both sides until they agree would bury that question.

A FALSE DRIFT IS WORSE THAN A SKIP; AN HONEST UNKNOWN IS NEITHER. codex tags releases `rust-v0.147.0`, which the engine cannot parse. Declaring `[tool.codex].manifest` made it report "the corpus describes code we do not run" about a manifest pinned exactly right, so that key was removed - a line that cries wolf every session trains the reader to ignore it. Its VERSION row was kept, because `latest UNKNOWN` is rendered under "NOT CHECKED against upstream (this is not a pass)": silence about a question, not a wrong answer to it. Engine gap is #245.

THE STALE-PATH SKEW IS LIVE AND NOW AFFECTS THREE TOOLS AT ONCE. After `mise install`, `mise which` reported the new versions while a bare `hk`/`uv`/`graphify` reported the old ones - `MISE_ENV_CACHE=1` with stale install dirs at PATH positions 4, 5 and 8, ahead of the shims. `mise exec --` and `mise run <task>` resolve correctly, confirmed by `kb-build` stamping "built by graphify 0.9.36". The engine's own `resolution` check reported all three independently, which is a second probe agreeing. mise 2026.8.3's new `not_found_system_fallback` is a THIRD near-miss on this surface and does not retire the workaround: it governs a shim whose tool is ABSENT, while ours is a stale dir ahead of a PRESENT tool's shim.

A WEDGED PROCESS SURVIVED A KILL THE PREVIOUS SESSION CALLED VERIFIED. Three processes from the 3h06m hk incident were still alive at 4h42m: two `sh` wrappers at 0% CPU reparented to launchd, and the real `typos` worker at 100% CPU, chewing a `.graph.json.<rand>.tmp` that no longer existed. Three lessons: kill the process GROUP rather than the PIDs you know about; `pgrep hk` is structurally blind because the command line names `typos` and `sh`, not the tool that spawned them; and the wedge was SPINNING hot, not idling - the recorded "0.0% CPU" had been read off the wrapper.

A DOCS FINGERPRINT EARNS ITS KEEP BY FINDING WHAT NO CLAIM LIST WOULD. All four tracked claude-code doc claims held verbatim, but `goal.md:106` had gained "the turn count, timer, and token-spend baseline all reset on resume". A goal's TEXT survives a `--resume` while the counter it bounds returns to zero, so a bounded condition reads bounded and is not. `goal-engineering` carried turn bounds in its rubric and mentioned resume ZERO times (control: `4,000` -> 1). Patched before the baseline was rolled - rolling first is how a finding gets silently discarded.

## Outcome

- Signal: useful