---
type: "query"
date: "2026-09-09T23:50:39.912962+00:00"
question: "How many derived values does a graphify pin move strand, and can they be derived without a build?"
contributor: "graphify"
outcome: "useful"
---

# Q: How many derived values does a graphify pin move strand, and can they be derived without a build?

## Answer

Seven values are stale at the graphify 0.9.57 pin, not the six #728 names.
Three were on no list: `detected_count` (471) and `extracted_count` (463), both
derived at v0.9.53 with 19 files added since; and the disposition catalog's
`uv.lock` entry, whose bytes moved (`c2e5f129…`/1015646 -> `cd961937…`/1015799).

Five of the seven derive with ZERO graphify involvement, correcting #740's
stated order: `source_manifest()` (`graphify_baseline.py:583`) is pure
git+worktree and runs at `:1798`, BEFORE `detect_checked:1809`. Only the two
COUNTS need a build.

The derivation is PROVEN and control-armed: re-running it against the OLD pin's
inputs reproduces the accepted `2a1f353a5d6ee0f087744197e56d07a8f2bcbf84bb048cfd6c8b281821bf5ac0`
exactly — the value a real 0.9.53 build produced. So the encoding
(`msgspec.json.encode(x) + b"\n"`, per `_write_json:1388-1391`) is right and the
new-pin candidates are real candidates, not artefacts.

The generalisable finding: a hand-written enumeration of DERIVED values is wrong
every time. Round f found #728's 2-value list wrong (it was 6); this round found
the 6-value list wrong (it is 7). The primitive must DERIVE the set, never read
a list.


## Outcome

- Signal: useful