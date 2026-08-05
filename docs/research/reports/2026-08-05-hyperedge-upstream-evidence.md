# Hyperedge survival: upstream evidence, control-armed against graphify 0.9.33

Round: #176 (Phase 2 of spec #174). Author: the architect session, 2026-08-05.
Binary: `~/.local/share/mise/installs/pipx-graphifyy/0.9.33/bin/graphify`,
resolved through `graphify_exe(REPO)` so it follows this repo's pin — never
`command -v graphify`, which reaches a raw install dir ahead of the mise shims
and more than one version is installed on this host.

Harness shape copied from `tests/test_merge_prefixes_once.py` (mise-resolved
exe, `clean_env()`, `capture_output`, temp dirs, synthetic node_link graphs) —
not restated. Probe script: `scratchpad/upstream_arms.py`.

## 0. Local measurement first (#166 step 1), before any change

`uv run` throughout — never a `mise run` log, whose redaction mangles numbers.

| artifact | nodes | hyperedges | members | dangling |
|---|---|---|---|---|
| `sources/extractions/*.json` (5 across 2 chunks) | — | 5 | 24 | 0 in-chunk |
| `graphify-out/graph.json` | 336,032 | 5 | 24 | **0** |
| `graphify-out/graph-prose.json` | 2,864 | 5 | 24 | **0** |

Both slots agree in each artifact (top-level `hyperedges` = 5, nested
`graph.hyperedges` = 5). Per-hyperedge: `three_question_memory_model` 4/4
EXTRACTED · `claude_code_memory_plan_six_stages` 6/6 EXTRACTED ·
`graphify_obsidian_self_maintaining_loop` 5/5 INFERRED · `three_pass_extraction`
3/3 EXTRACTED · `security_threat_mitigations` 6/6 EXTRACTED.

**This overturns #166's local symptom.** The capability report (§3.6) measured
every member dangling: members carried zero `::` prefixes while the nodes they
named carried one. Phase 1 (#175) removed the second prefix pass by merging the
self sub-graph inside the single N-ary `merge-graphs` call, so semantic doc
nodes now carry no prefix at all and the members match. `graph_checks.assert_composition`
refuses a dangling member on every build, so the local half of #166 is fixed
AND guarded. What remains is upstream, and it is worse than #166 described.

## 1. ARM A — `merge-graphs` orphans hyperedge members (the #166 mechanism)

Two synthetic inputs, each with three nodes and one hyperedge naming all three.

```
merged node ids        : ['alpha::a_one', 'alpha::a_two', 'alpha::a_three',
                          'beta::b_one',  'beta::b_two',  'beta::b_three']
CONTROL link endpoints : [('alpha::a_one', 'alpha::a_two'), ('alpha::a_two', 'alpha::a_three')]
nested members         : {'h_beta': ['b_one', 'b_two', 'b_three']}
-> h_beta: 0/3 members resolve in the merged graph
```

**Control arm:** the link endpoints ARE prefixed, so `prefix_graph_for_global`
demonstrably runs and demonstrably relabels what it intends to. Hyperedge
members are the omission, not a no-op run.

Source, verified at 0.9.33 (`build.py:1590-1608`): `relabel = {n: f"{repo_tag}::{n}" ...}`,
`nx.relabel_nodes(G, relabel, copy=True)`, then loops over `H.nodes` and
`H.edges` rewriting `_src`/`_tgt`. `G.graph` — where hyperedges live — is never
touched. `nx.relabel_nodes` copies graph-level attributes forward verbatim.

## 2. ARM B — `nx.compose` keeps only the LAST input's hyperedges (UNREPORTED)

Same run. Two inputs each contributed exactly one hyperedge; the merged output
holds **one**, `h_beta`, from the last input. `h_alpha` is gone.

`cli.py:2174-2175` composes with `merged = _nx.compose(merged, prefixed)` in a
loop. `nx.compose` merges graph-level attributes by `dict.update`, so each
input's `G.graph["hyperedges"]` **overwrites** the accumulated one rather than
extending it. Merging N graphs discards N−1 hyperedge sets.

This is distinct from every closed upstream issue: #1574 is `build_merge`
dropping the existing graph's hyperedges on `--update`; #1755 is
`watch._rebuild_code` evicting by `source_file`; #1561 is the `members`/`node_ids`
alias. None of them is `merge-graphs`.

## 3. ARM C — a `merge-graphs` output has NO top-level `hyperedges` key

`top-level 'hyperedges' : ABSENT`. The merged file is written with
`json_graph.node_link_data(merged)` (`cli.py:2177`), whose schema has no
top-level hyperedge slot; the list survives only inside `data["graph"]`, which
is just a serialisation of `G.graph`. `to_json` (`export.py:314`) writes BOTH —
`data["hyperedges"] = G.graph.get("hyperedges", [])` on top of node_link_data's
nested copy — so which slot a graph.json uses depends on which writer produced
it. Arm D is why that asymmetry is not cosmetic.

## 4. ARM D — `graphify label` deletes nested-only hyperedges, silently

Two arms over `graphify label .` on a four-node graph, members resolving in both:

| arm | slots before | slots after | rc | stderr |
|---|---|---|---|---|
| **control** — top-level present | top=[h_probe] nested=[h_probe] | top=[h_probe] nested=[h_probe] | 0 | none |
| nested-only | top=ABSENT nested=[h_probe] | **top=[] nested=ABSENT** | 0 | **none** |

The control arm is the load-bearing half: **the top-level restore path works at
0.9.33**. `build_from_json` does read `extraction["hyperedges"]`
(`build.py:1053-1094`), revalidates the members, and reattaches survivors. So
the loss is CONDITIONAL, and the condition is which slot the list is in.

`build.py:1053` reads `extraction.get("hyperedges", [])` — the top-level key
only. `extraction["graph"]["hyperedges"]` is never consulted. When the top-level
key is absent the `if hyperedges:` guard skips the whole block, `G.graph` never
gains the key, and `to_json` writes `[]` over the real list. No warning, no rc
change.

**Arms C and D compose into total silent loss:** `merge-graphs` writes
nested-only, and the very next `label` / `cluster-only` / `export` that
round-trips that file deletes every hyperedge in it.

## 5. ARM E — a revalidation wipeout becomes a durable `[]`

Top-level slot present, members deliberately non-resolving:

```
BEFORE top=['h_probe']   AFTER top=[]   rc=0
stderr: [graphify] WARNING: dropping hyperedge 'h_probe' — none of its members
        ['ghost_one', 'ghost_two', 'ghost_three'] match built nodes.
```

One WARNING per casualty on stderr, rc unchanged, and the emptied list is
written back over the input file. A transient id mismatch — exactly what arm A
produces — is converted into permanent data loss on the next run. The
`if kept_hyperedges:` guard at `build.py:1093` means a total wipeout does not
even set the key, which is how the nested slot disappears entirely in arm D.

**This is what this repo measured as "5 → 0" on its own aggregate.** The cause
was arm A (orphaned members) feeding arm E (revalidation wipeout), not an
unconditional loss — a correction to `hyperedges.py`'s module docstring, which
states the mechanism correctly but does not say the loss is conditional on
member resolution.

## 6. ARM F — the round's acceptance criterion, end to end

#176's acceptance: *"A chunk carrying a valid hyperedge survives assemble →
merge → label with members resolving in the final artifact (measured)."*
Real pinned binary, temp corpus root, nothing written inside the repo; the
binary and the bundled interpreter are resolved from the REAL repo so they
follow the pin, which is `test_merge_prefixes_once.py`'s `_graphify()`
reasoning applied to a second harness.

```
STEP 1 assemble  -> 4 nodes, 1 hyperedge(s): ['probe_trio']
STEP 2 merge     -> rc=0, 5 nodes, 1 hyperedge(s): ['probe_trio']
STEP 3 label     -> rc=0, 5 nodes, 1 hyperedge(s) top / 1 nested
  FINAL probe_trio: 3/3 members resolve; dangling=[]
  PROSE 5 nodes, 1 hyperedge(s), 0 dangling
ACCEPTANCE PASS
```

The prose row matters on its own: `graph-prose.json` is the surface
`kb-query --prose` reads, and it carries the hyperedge with no dangling member.

## 7. ARM G — is our own carry still load-bearing? MEASURED, not inferred

Same pipeline as arm F with `hyperedges.reattach` stubbed to a no-op:

```
STEP 3 label     -> rc=0, 5 nodes, 1 hyperedge(s) top / 1 nested
  FINAL probe_trio: 3/3 members resolve; dangling=[]
ACCEPTANCE PASS
```

**The hyperedge survives without the carry.** Arm D's control predicted this —
top-level slot plus resolving members round-trips fine at 0.9.33 — but a
predicted survival is the arm that owes the most evidence, not the least
(`probes-need-a-control-arm.md` rule 9), so it was run rather than reasoned.

So `kb_setup.hyperedges.capture`/`reattach` is **belt-and-braces on today's
build path**, not load-bearing: Phase 1 removed the second prefix pass, members
now resolve, and graphify's own restore path handles it.

**Do not remove it, and do not cite arm G when removing it.** Three reasons,
in order of strength:

1. Arm D: the nested-only shape is a **total silent loss** — rc 0, nothing on
   stderr — and arm C shows `merge-graphs` produces exactly that shape. Any
   future path that hands a raw merge output to `label`/`cluster-only`/`export`
   without an intervening `to_json` loses everything.
2. Arm E: the survival depends on every member resolving. That is currently
   guaranteed by `graph_checks.assert_composition`, which refuses a dangling
   member — but the guarantee lives in a different module from the behaviour it
   protects, so the coupling is invisible from either side.
3. The carry is what makes the outcome independent of graphify's revalidation
   and slot handling, both of which this document has just measured to be
   fragile, and both of which are free to change at 0.9.34 without a note.

## 7. Duplicate check against upstream

Searched `Graphify-Labs/graphify` for `hyperedge` (open + closed) and
`prefix_graph_for_global`. Closed and adjacent but NOT these: **#1574**
(`build_merge`/`--update` drops the existing graph's hyperedges), **#1755**
(`watch._rebuild_code` evicts by `source_file`), **#1561** (`members`/`node_ids`
alias), **#1418** (`to_json` does not relativize `source_file` on
`graph.hyperedges[]`), **#1005** (viz node limit), **#1831** (`to_graphml`
crash). Open: **#2449** (polygon self-intersection — rendering only).

Nothing covers `merge-graphs` (arms A/B/C) or the nested-slot read gap (arm D).
Arm E's wipeout is the behaviour #1916 deliberately introduced; the report
frames it as a durability question, not a request to revert the validation.

A second sweep before filing, over `merge-graphs`, `compose`, `build_from_json
hyperedges` and `graph-level attributes`, found nothing overlapping either. The
nearest miss is **#2261** (closed) — `merge-graphs silently rewires import edges
to the importing file's own node`: same command, different structure, and it is
about edges rather than graph-level state.

## 8. FILED

- **[Graphify-Labs/graphify#2484](https://github.com/Graphify-Labs/graphify/issues/2484)**
  — `merge-graphs`: arms A + B + C under one root cause (the merge treats
  `G.graph` as pass-through). Ray's call was to fold the unreported `nx.compose`
  clobber into this issue rather than file it separately, because the three
  share a fix.
- **[Graphify-Labs/graphify#2485](https://github.com/Graphify-Labs/graphify/issues/2485)**
  — `build_from_json`: arms D + E, the nested-slot read gap and the durable `[]`.

Cross-linked, because #2485 is what converts #2484's orphaning into permanent
loss. Both carry a self-contained repro and its control arm, so a maintainer
needs nothing from this repo to reproduce.

Recorded on our own tickets: **#166** (local half resolved by #175 and guarded;
upstream link) and **#171** (the mechanism CORRECTION — that issue said
`build_from_json` "never attaches" hyperedges, which 0.9.33 contradicts).
The `kb-merge` restamp inconsistency the cold lane surfaced is
**knowledge-base#181**.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the
  installed 0.9.33 package read as the authority for every mechanism claim
  (`build.py`, `cli.py`, `export.py`); the issue tracker searched for duplicates.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) —
  this repo; `graphify-out/graph.json` and `sources/extractions/*.json` supplied
  every §0 figure, `tests/test_merge_prefixes_once.py` supplied the harness.
