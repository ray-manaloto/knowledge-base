---
type: "query"
date: "2026-08-27T16:21:51.330001+00:00"
question: "Why did mise run kb-build refuse on 56 files across 10 sources, and what actually fixed it?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did mise run kb-build refuse on 56 files across 10 sources, and what actually fixed it?

## Answer

`mise run kb-build` refused on 56 files across 10 sources. The fix was NOT a per-source
exclusion list: every one of the 56 belonged to a file CLASS — a name shape or an
extension that recurs in the next source — so the fix went into the classifier this repo
already owns, `kb_setup.graphify_sdk.classify_unclassified`.

MEASURED, file-based rc both ways:
  before  11 sources fail; {timeout: 1, unclassified-files: 10}; 56 unresolved paths
  after    0 preflight failures across 85 built sources

The load-bearing lesson, and it generalises past this fix:

A `re.match()` is anchored at position 0. `_LICENSE_NAME` was applied that way, so the six
prefixed spellings biome vendors — PRETTIER_LICENSE, ROME-LICENSE-MIT, CODESPAN_LICENSE,
RSLINT_LICENSE — could not match HOWEVER the alternation was written. No amount of editing
the pattern would have fixed it; the call site was the bug. When a regex "cannot possibly
match this", check the METHOD before the pattern.

The second lesson cost a review round. Widening that regex with a leading boundary admitted
the six licence files AND every CONTENT file with the word in a hyphenated segment:
`docs/verify-license.adoc` moved from the COUNTED class to the SILENT one, control-armed
against `docs/api.adoc` which stayed counted. A widening is never only as wide as the cases
that motivated it — ask what ELSE now matches, in the direction that loses data quietly.

Third: the extraction gate then failed closed on graphify's own routine merge narration
(`[graphify] Replaced N node(s) from re-extracted source file(s).`). Verified benign by
READING the vendor source at graphify/build.py:1724 rather than by its reassuring wording —
`_kept` only drops a node whose source_file is in the NEW chunks, and those chunks are merged
in the same build. Crucially the #479 shrink guard keeps its own `_disk_nodes` baseline across
that rebind, so approving the narration leaves the real loss detector armed. That distinction
is the whole reason the approval is safe, and #231's buried 1,024 nodes is why it had to be
checked rather than assumed.

NOT FIXED, stated because a green preflight reads like a green build: `kb-build` still exits 1.
It now dies in EXTRACTION on ast-grep (Cargo.toml zero nodes, upstream graphify #1666), which
is #417's family. #397's acceptance criterion 3 stays open behind it.


## Outcome

- Signal: useful