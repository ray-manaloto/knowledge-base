# #198 items 1+2 — hyperedge continuity, the assemble claim check, and the arm that corrected the source read

Round of 2026-08-07. Built against graphify **0.9.35** (installed), on `main` at
`d715d0a09477`.

## Headline

Two builds and one measurement that changed a conclusion I had already written down.

1. **Item 1 (hyperedge continuity)** — built, across **both** merge paths. The ticket
   cited one; there are two, and the one it omitted is the path on which the
   incident that motivates the ticket was observed.
2. **Item 2 (`kb-assemble`'s missing `source_file`-claim check)** — built, with
   semantics deliberately different from the ticket's literal instruction.
3. **The open lead** — resolved by a live merge that **refuted the scope of my own
   source read**. There are TWO upstream guards, not one, and the obvious
   reproduction trips the guard the real failure never touches.

## The measurement that mattered

The question: does graphify 0.9.35 cover our basename-collision loss class, making
`chunks.collision_issues` redundant?

Reading the installed source said no, because `build_merge`'s excuse predicate is
its drop predicate:

- dropped when `sf in own or _norm_source_file(sf, _replace_root) in own` — `_kept`, `build.py:1639`
- excused when `sf in own or _norm_source_file(sf, _replace_root) in own` — `_explained`, `build.py:1851`

Same test, same `new_sem_sources` set (built identically at `:1638` and `:1850`).

That reasoning was correct and **incomplete**. Ray had rejected deciding on the
source read alone; the live arm is why the write-up is right.

### The arm

Two synthetic chunks claiming one `source_file` (`ARM-COLLIDE.md`), **no id overlap**
— the id map is the wrong instrument and reported them clean throughout. Run against
the real 342,266-node graph, restored byte-identically afterwards.

| step | chunk | expected | observed |
|---|---|---|---|
| 1 | victim, 3 nodes | merges | `342266 + 3 = 342269, 0 replaced`, rc=0 |
| 2a | aggressor, **undeclared** | OUR gate refuses | refused by name, **rc=2** — control arm: the #189 gate is awake |
| 2b | aggressor, 2 nodes, declared | graphify silent | **`to_json` REFUSED** — net −1, rc=1, nothing written |
| 3 | aggressor, 5 nodes, declared | — | **nothing refused.** rc=0, 3 nodes destroyed |

**Step 2b is the trap, and it is the finding.** A toy collision that shrinks the
graph trips `to_json`'s net-count guard — a guard I had not accounted for. Had the
arm stopped there, the honest reading would have been "upstream covers this" and
item 2 would have been closed as superseded.

It does not cover it. `to_json`'s guard is count-based, and this failure mode is a
**net gain**: the aggressor adds its own nodes while destroying someone else's. The
measured PR #197 loss printed **+796 with the total rising 681** — 115 nodes replaced
under a +681 net, 72 of them belonging to a source nobody was touching. No count
guard can see that.

Step 3 reproduces that shape (5 added vs 3 destroyed, net +2) and **nothing refused**:

```
[graphify] Replaced 3 node(s) from re-extracted source file(s).
[merge] REPLACED 3 node(s): 342269 + 5 = 342274, but the graph holds 342271. ...
rc=0
```

Confirmed at the bytes, with a control on the probe itself:

| grep over the post-merge graph.json | count |
|---|---|
| `arm_victim_[0-9]` (destroyed) | **0** |
| `arm_big_[0-9]` (aggressor, CONTROL) | **5** |

The control matters: `0` alone would be indistinguishable from a grep that cannot
match anything.

**Verdict: item 2 is UNMITIGATED. `collision_issues` is load-bearing against both
upstream guards, and `assembly_overlaps` is a real gap, not a duplicate.**

## Item 1 — what the ticket under- and over-scoped

**Under-scoped: two argv builders.** The ticket cites `graphify_ops.py:221-225`
(incremental `kb-merge`). `graph._replay_doc_chunks` builds its own argv for the
`kb-build` REBUILD path and threaded `nodes` alone. Patching only the cited site
would have left the rebuild path node-only — and the #186 loss that motivates the
whole item (**11 hyperedges → 8, no nodes moved**) was observed *on a rebuild*. Both
now thread from one `_THREADED_COUNTS` table.

`_handoff_nodes` became `_handoff_counts`, returning a mapping. Forced, not
stylistic: the handoff file is **unlinked on read**, so a second
`_handoff_hyperedges` could never see it — whichever ran first would delete it and
the other would report *unknown* forever, which looks exactly like a passing check.

**Over-scoped: the node wording cannot be reused.** A doc merge has ONE way to drop
a node and FOUR ways to lose a hyperedge:

| # | channel | site | announced? |
|---|---|---|---|
| 1 | carried hyperedge whose `source_file` the chunk also names | `build.py:1735-1736` | silent |
| 2 | id collision with one the chunk re-emitted → deduped | `export.py:162-171` | silent |
| 3 | NEW hyperedge whose members resolve to no built node | `build.py:1230-1237` | stderr WARNING |
| 4 | hyperedge with a falsy `id` → skipped by `attach_hyperedges` | `export.py:167` | **silent** |

Only #1 is the node rule. The line therefore states the arithmetic and enumerates
candidates. Corpus today: 4 of 21 committed chunks carry hyperedges
(6+45+3+38 = **92**, matching the built graph exactly), none lacking an `id` — so
channel 4 is real but not live.

`attach_hyperedges` does **not** resolve endpoints, contrary to a comment in
`_merge_docs.py`; resolution happens earlier at `build.py:1219-1240`.

**Confirmed end-to-end**, which unit tests cannot do (they run under uv's python,
not graphify's bundled interpreter):

```
--prior-nodes 342269 --prior-hyperedges 92
[merge] hyperedges: arithmetic checks: 92 + 0 = 92, 0 lost
```

## Item 2 — amended semantics (Ray's call)

`assembly_overlaps` rather than a call to `collision_issues`, because that function's
semantics are void during assembly:

1. Its message describes **deletion**; assembly concatenates and deletes nothing.
2. It **excuses a declared overlap**. That excuse cannot hold here — a `supersedes`
   declaration only takes effect when the combined chunk MERGES, by which point it
   is a single chunk with nothing left to supersede, and both node sets are already
   inside it.

So every overlap refuses, declared or not. An implementation reusing
`collision_issues` passes every other arm in `tests/test_chunks.py`.

**Recorded because it looks bad otherwise:** the new gate initially failed 3 existing
`assemble` tests. Those fixtures modelled two sources via `x_`/`y_` id prefixes but
left every node at the shared default `source_file: "src.md"` — a fidelity gap no
check had ever read. The fixtures were corrected, not the gate. `kb-extract` fans out
one agent per source, so two inputs claiming one file cannot occur in a real batch.

## Mutation arms

`docs/research/reports/2026-08-07-hyperedge-continuity-arms.toml`, run via
`mise run kb-arms` (#160 — the harness is never hand-written).

**14/14 died, 1/1 control held, restore rc=0.**

This measures THE TESTS. It says nothing about the premise — the four loss channels
came from reading graphify's source, and the two-guard correction came from the live
merge, neither of which any arm here could have produced. Three previous rounds in
this repo recorded a clean sweep immediately before a real blocking defect.

## Corrections to earlier claims in this round

1. **"graphify's #479 guard is blind to this class"** — true of `build_merge`'s
   guard, incomplete as stated. `to_json` has a second, count-based guard that DOES
   fire on a net shrink. Both statements now carry their condition.
2. **"the handoff's PATH warning applies to the gates"** — narrowed. `PATH` holds
   frozen versioned install dirs under `MISE_ENV_CACHE=1`, so **bare** Bash calls
   resolve stale (uv 0.11.28, codex 0.146.1, agy 1.1.10) while `mise exec`/`mise run`
   resolve correctly (uv 0.12.2). The gates were never running on old uv.
3. **A broken probe, caught and re-run:** an `awk` range `/^def build_merge/,/^def
   [a-z_]+\(/` is self-terminating (the start line matches the end pattern), and
   reported "0 hyperedge mentions in `build_merge`". Re-run on the real range with a
   control: hyperedge **17**, `node` **45**.

## Open / not done

- #198 items **3–4** (two test-breadth gaps) — untouched.
- `mise run kb-artifacts` — still NOT RUN, carried from the previous handoff.
  `[views] NOT CHECKED` for `GRAPH_REPORT.md`, `graph.graphml`, `wiki`.
- `mise run kb-update -- agent-harness-docs` — the mirror still predates
  claude-code 2.1.224.
- A lead, not chased: `kb-currency-check` runs INSIDE a mise task, so it sees mise's
  corrected PATH and structurally cannot observe the shell-PATH drift measured above.
  It was silent today while three tools were stale on the shell's PATH. That may be a
  gap in its stated purpose ("whether the binary a shell actually reaches matches the
  pin") or a deliberate scope; not investigated.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read the installed 0.9.35 `build.py` and `export.py` to establish the hyperedge loss channels and both shrink guards.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo; issue #198.
