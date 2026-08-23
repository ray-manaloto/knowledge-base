# Adversarial verification — lane `forgotten`, finding: issue #446's premise is half false

**Verdict: NOT REFUTED (refuted=false).** Every clause of the finding survived an
attempt to break it, and the strongest form of the finding is stronger than what
was claimed.

## The claim under test

> Issue #446's premise ('neither [source] is in the corpus') is confirmed false for
> the fable-orchestrator half, flagged as needing amendment in two consecutive
> handoffs, and still uncorrected (0 comments, body unedited).

## How the original probe could have been wrong (and was not)

The offered evidence was `ls sources/*.manifest` — manifest *presence*. That is a
weaker probe than the ticket's own claim, which is about the **graph** ("Control-armed
2026-08-21: `fnox` returned 0 nodes…"). A manifest can exist while the source is
absent from `graph.json` (`build = skip`, a RED `kb-build` per #417, a clone advanced
past its pin). So I re-asked at the graph, which is where #446 makes its claim.

### Probe 1 — is the mar3co repo actually IN the graph?

```
uv run python -  # against graphify-out/graph-prose.json (6.9 MB, 4,868 prose nodes)
  nodes with source_file == 'fable-orchestrator.md'   -> 38
  nodes with 'antigravity-for-claude-code' in source_file -> 0
```

**Control arm, same probe, same shape, in the same file:** the antigravity half
returns **0** while the fable half returns **38**. The probe discriminates; the
0 is a real absence and the 38 is a real presence.

Node ids are `forch_*` (`forch_codex_reviewer`, `forch_fable_orchestrator`,
`forch_model_resolution_order`, `forch_codex_implementer`, …), `_origin=semantic`,
`captured_at=2026-07-22`, communities 9394/9395/10249 ("Fable 5 architect session",
"Cross-vendor CLI lanes", "Cold review of a behavior-bearing diff").

Same string in the 772 MB aggregate graph:

```
LC_ALL=C grep -o -F '"fable-orchestrator.md"' graphify-out/graph.json | wc -l   -> 70
LC_ALL=C grep -o -F 'antigravity-for-claude-code' graphify-out/graph.json | wc -l -> 0
```

(A `grep -o -F 'sources/fable-orchestrator/'` on graph.json returns 0 — but that is a
**token-spelling bound**, not evidence: AST `source_file` values are repo-relative
(`crates/vfox/src/plugin.rs`), never `sources/<name>/`-prefixed. I did not report that 0.)

### Probe 2 — the ticket's own worked example is refuted too

#446 says the corpus gap is why "#445 is blocked in practice: *what model and effort do
the reviewer lanes run at* is a question the graph should be able to answer." The graph
already answers it, from those 38 nodes:

- `forch_codex_implementer` — *"GPT-5.6 Sol at `model_reasoning_effort=high`; correctness-critical implementation lane"*
- `forch_fable_advisor` — *"Read-only skeptic (model: fable, tools Read/Grep/Glob) giving a second opinion at commitment boundaries"*
- `forch_model_resolution_order` — *"CLAUDE_CODE_SUBAGENT_MODEL env var → per-invocation…"*

So the premise is false on presence **and** on the consequence the ticket draws from it.

### Probe 3 — provenance and dating (could the manifest be a later fix?)

```
cat sources/fable-orchestrator.manifest
  url = https://github.com/mar3co/fable-orchestrator      # EXACT url #446 asks for
  commit = cd43e27691e83a9c6239d33efd93cabf45aa8aac
  kind = code ; added = 2026-07-22

git log --diff-filter=A -- sources/fable-orchestrator.manifest
  0013075edfad81e5f4ee512c8913d27cf01ae212  2026-07-22  feat(kb): code-layer ingest of 11 orchestrator sources…
```

Added **2026-07-22**, 31 days before #446 was filed (2026-08-22T13:56:02Z). Not a
later fix. `sources/REGISTRY.md:35` row 9 records
`mar3co/fable-orchestrator | repo | T1 | prose | Fable orchestrator. Code + prose extracted 2026-07-22.`
Two of #446's three acceptance criteria are therefore **already satisfied** for that half.

The clone is on disk (`sources/fable-orchestrator/`, 18 files) and the 38 nodes are
committed corpus input in `sources/extractions/orchestrator-repos-docs.json`
(`source_file = fable-orchestrator.md`, 38 of its 261 nodes) — i.e. reproducible from
committed inputs, not a working-tree artifact.

### Probe 4 — "0 comments, body unedited"

```
gh issue view 446 --json … -> {"n":446,"created":"2026-08-22T13:56:02Z",
                               "updated":"2026-08-22T13:56:02Z","ncomments":0,"state":"OPEN"}
```
`updated == created` ⇒ body never edited. **Control arm:** the same command on #441
returns `{"created":"2026-08-21T20:44:53Z","updated":"2026-08-22T16:37:42Z","ncomments":1}`
— so the probe can return "edited/commented" and did not here.

### Probe 5 — "two consecutive handoffs", exact anchors

- `.agent/plans/session-2026-08-22.md:67` (under `## 5. Owed and not done`, header at :62):
  *"**Amend #446** (confirmed finding): it claims \"Neither is in the corpus\", but `sources/fable-orchestrator.manifest` exists and `sources/REGISTRY.md` row 9 records it extracted 2026-07-22."*
- `.agent/plans/session-2026-08-22-b.md:68` (under `## 3. Issues`, header at :58):
  *"**#446** (needs amending — it claims \"neither is in the corpus\" but `sources/fable-orchestrator.manifest` exists)"* — plus `:136` (owed) and `:165` (**CARRIED**).

The finding's own section citations (§5 and §3) are exact.

## Free defect found while arming this (not part of the finding)

#446's stated control arm — *"`fnox` returned **0** nodes against a **955**-node `graphify`
control"* — does not reproduce: `grep -o -F 'fnox' graphify-out/graph.json | wc -l` → **35,232**,
and `sources/fnox.manifest` was added 2026-08-19 (3 days before #446 was filed). The ticket's
supporting measurement is at best stale/scoped-differently and was carried into the ticket
without its condition. Worth folding into the same amendment.

## Contradiction check against the other live findings

None. Items **9** and **16** of this round's set assert the same fact from the same two
routes (manifest + REGISTRY row 9) and agree with this one; item 16 adds "3+ prior handoffs"
where I could verify exactly two by name (08-22, 08-22-b) — the 08-22 handoff's §6
reconciliation implies earlier carriage but I did not verify a third by `file:line`, so
treat "two" as the measured figure and "3+" as unverified.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issue #446/#441 metadata via `gh`, local source of record.
- [mar3co/fable-orchestrator](https://github.com/mar3co/fable-orchestrator) — the source whose corpus presence is in dispute; read only via the pinned local clone + manifest, not fetched.
- [yuting0624/antigravity-for-claude-code](https://github.com/yuting0624/antigravity-for-claude-code) — the control-arm half (genuinely absent: 0 nodes).
