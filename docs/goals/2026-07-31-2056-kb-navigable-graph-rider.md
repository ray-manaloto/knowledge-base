# Rider — Navigable

Serves `docs/goals/2026-07-31-2056-kb-navigable-graph-goal.md`.

## Scope decision — is this one round?

**By the headline-word test, honestly: this is the widest round attempted here,
and P5 is the part that strains the word.** `Navigable` names the end state of
P1–P4 cleanly (our own library is in the graph; three peer tools are ingested; a
reusable team exists; three docs exist). P5 — the graphify version-sync tail —
is about *currency*, not navigation.

The connection that makes it one round rather than two: **a graph whose builder
version you cannot verify is not navigable in any load-bearing sense.** You can
traverse it, but you cannot cite it. P5's owed re-probes are about the tool doing
the navigating, and the dotfiles pin drift is itself the first real blast-radius
test case for what P1 builds.

**Ray folded P5 in explicitly** (2026-07-31, AskUserQuestion, "Fold in
everything") after being shown the option to defer it and the reason to. Recorded
as an informed decision, not an oversight. If the round stalls, P5 is the first
thing to split out — it is the only phase that is not a prerequisite for any
other.

**Ray also chose the full orchestrated cross-family team** after being shown the
`#67` cost lesson verbatim (2.93M tokens across five rounds, reverted). Also
informed, also recorded.

## The evaluator constraint

The `/goal` evaluator does not call tools. It reads this conversation and nothing
else. Therefore every clause in the goal is a **string a Haiku-class reader can
find**, and every one of them must be produced by a real run whose output is
pasted into the conversation. Subagent and workflow output counts only when
pasted here — which matters more this round than any previous one, because P3
stands up a team whose whole point is to work elsewhere.

## What this round answers

**Can this repo answer "what does my change break?" about its own code, and does
any of the three peer tools do something graphify cannot?**

### Banned answers — theories already retracted by measurement, 2026-07-31

Do not re-derive these. Each was believed, probed, and killed in the grilling
that produced this round. Re-proposing one without a **new pasted measurement**
is a defect, not diligence.

| Retracted claim | The measurement that killed it |
|---|---|
| "`graphify affected` is broken because our graph is undirected" | `affected.load_graph` does `raw = {**raw, "directed": True}` (#1174). End-to-end: `affected "get_relational_engine()" --depth 1` → 165 nodes with correct `file:line`, on a node with 156 `calls` predecessors counted from `graph.json`. Bogus label → no match. |
| "`multigraph: false` collapses edges" | `graphify diagnose multigraph`: raw 307,101 → post_build 307,101, `undirected_same_endpoint_collapsed_edges: 0`. |
| "graphify has no LSP/symbol-resolution anything" | `scip_ingest.py` ships a simplified SCIP subset. The first probe grepped `lsp\|pylsp\|pyright` and missed it on **spelling**. |
| "Ingesting the three tools is too expensive" | Measured expansion on graphify's own ingested source: 4.7 MB `.py` → ~6 MB graph = **1.3×**. All three ≈ 55 MB against 167 MB headroom (345 MB now, 512 MiB cap, overridable via `GRAPHIFY_MAX_GRAPH_BYTES`). Token-free. |
| "kb_setup in the aggregate graph will be drowned by 130k nodes" | `affected` seeds on an **exact** node and walks edges. Crowding applies to ranked `query`, not to blast radius. |

**What actually survives**, and is what P1 fixes:

- `python/src/kb_setup/` is **not in the graph at all** — 0 of 37 tracked files.
  Control-armed on `source_file`: `graphify/extractors/` → 429, `cognee/api/` →
  793, bogus → 0.
- `repo` attribution is collapsed: 127,929 of 130,844 nodes claim
  `repo: knowledge-base`, cognee's and graphify's included.
- `scip_ingest.py`'s own docstring: *"Not wired to the CLI in this phase."*
  Control-armed: `scip` in `cli.py` → 0, `affected` → 6.

## Preserve list

| What | Where | Why |
|---|---|---|
| `size:mtime_ns` for OUTPUTS, sha256 for INPUTS | `currency/sync.py`, `.currency-stamp.json` | measured 341 MB vs 2.4 MB, 142×; #89 falsified unifying them |
| DRIFT / SKIP / OK as three distinct states | `currency/` | collapsing them is how every defect in that engine's review happened |
| `kb-currency-check` silent when clean, always exit 0 | `currency/run.py` | a session must never be blocked over a pin |
| the `kb-review` receipt gate | `kb_setup.review`, `pr.py` | deleting it is the CHEAPEST route to the `PASS  gate` lines below, and must not be the way |
| the `no depends` ban | `hk.pkl` | Ray decided 2026-07-31 to keep it despite hk 1.53.0 fixing the deadlock |
| every existing `[tool.*]` block and its `watch` items | `currency.toml` | P5 ADDS baselines; it never prunes |
| the `#2308` mcp watch item **with its version condition** | `currency.toml` | its warning inverted rather than expired — keep, do not delete |
| verbatim reports | `docs/research/reports/**`, `.agent/kb/**` | `agent-report-persistence.md` — never normalise |
| existing memory entries | `graphify-out/memory/**` | authored, the one committed part of a derived tree |
| the four still-open tracked issues | `currency.toml` | #2101, #2086, #1653, #1824 — P5 re-probes them, never closes them unilaterally |

## Posture

- knowledge-base only. **No dotfiles commit.** P5 *measures* the dotfiles pin gap
  and writes it down; bumping dotfiles' pin is a separate PR in a separate repo.
- No `.sh`. No inline shell logic in `hk.pkl` / `mise.toml`.
- No `noqa` / `type: ignore` / `ty: ignore`.
- No bare `graphify` at a command position — `kb-*` tasks only. Read-only
  `path` / `explain` / `god-nodes` / `affected` / `diagnose` stay allowed.
- **No non-Claude LLM backend touches the corpus.** `clean_env()` stays intact.
- Branch first; never commit on `main`. Branch is
  `feat/graph-navigation-and-tool-review`.
- Ingest **all three repos, no exclusions** — Ray's call, backed by the 1.3×
  measurement. Do not quietly add a `.graphifyignore` to "save space".
- Do not delete `docs/goals/*-goal.md` bytes to satisfy a formatter; that tree is
  excluded from hk's md builtins on purpose.
- Stop after 60 turns. The bound is **soft** (Ray, 2026-07-31): at 60, flag the
  overrun and finish the phase in flight rather than stopping mid-phase.

## Phases

Each phase: depth test first where it changes code → implement → gates green →
one conventional commit. P4 and P5's re-probes produce *findings*, not code, so
they have no failing test to write first; that is stated rather than faked.

### P1 — the baseline fix (blocks everything else)

1. **Depth test first.** A test asserting `python/src/kb_setup/**` nodes exist in
   the built graph. It must FAIL at HEAD (0 of 37 files today) — paste the
   failure before implementing.
2. Index `python/` **and the root `tests/`** into the **aggregate** graph, same
   shape as `graph.py::_extract_code` + `merge-graphs`. Add
   `python/graphify-out/` and `tests/graphify-out/` to `.gitignore` in the same
   change — there is precedent for the shape in the existing
   `brain/graphify-out/` block.

   **`tests/` is in scope by Ray's decision (2026-07-31, clear-prep), widening
   what this rider originally said.** The reason is that "which tests cover this
   symbol?" is the blast-radius question with the most day-to-day value, and it
   is unanswerable from `python/` alone: 40 files and 14,090 LOC of tests sit
   outside that tree. Verify by node count that `.venv/` and `.ruff_cache/` were
   NOT walked — graphify honours VCS ignore files by default, but that is an
   assumption until a count is pasted.
3. `kb-watch` mise task wrapping `graphify watch`, which **restamps** after each
   incremental rebuild via the existing `restamp_artifacts` — otherwise the
   background rebuild changes `graph.json`'s `size:mtime_ns`, `artifact_fingerprints`
   stops matching, and the detector shipped last round reports *version unknown*
   every session. Logic in `kb_setup`, one-line seam in `mise.toml`.
4. **Narrow `do-not.md` #2 in this same change.** Its stated rationale — *"shared
   mutable machine state is non-reproducible and collides across hosts"* —
   describes `extract --global`, `global add` and `hook install`. It does not
   describe `watch`, which writes this repo's own `graphify-out/`. Narrow the rule
   to the ops its reason covers, and say in the commit body why.
5. **Both arms of `affected`** on a real `kb_setup` symbol: expected callers
   derived independently by `grep -n`, pasted next to the graph's answer; and a
   bogus symbol returning no match. A one-armed result is not reportable.

### P2 — ingest the three tools

Three `sources/*.manifest` pins (url + ref + commit SHA) + `mise run kb-build`.
No exclusions. Expect ≈55 MB of graph growth; if it exceeds 167 MB, stop and
report rather than raising `GRAPHIFY_MAX_GRAPH_BYTES` silently.

- `deusdata/codebase-memory-mcp` — C, MIT, 158 languages, vendored tree-sitter
  runtime at `internal/cbm/vendored/ts_runtime/`
- `tirth8205/code-review-graph` — Python, MIT, MCP + CLI
- `cosmtrek/mindwalk` — Go, MIT, session-log visualiser

Append all three to `sources/REGISTRY.md` (`research-repo-enumeration.md`).

### P3 — the reusable cross-family team

**The team is a deliverable, not scaffolding** (Ray: *"save this agent team for
re-use and to improve"*). It must survive the round as tracked files:

| Role | Family | Job |
|---|---|---|
| Orchestrator | Claude (this session) | plans, verifies evidence, never delegates verification |
| Curator | Claude | manifests, `kb-build`, `kb-validate-chunks`, `kb-remember`/`kb-reflect` |
| Researcher ×3 | mixed | one per tool; graph-grounded first, source second |
| Cross-family reviewer ×3 | codex / antigravity | never the same family as the doc's author |
| Adversarial verifier | Claude | control-arms every **negative** claim before it is written down |
| Synthesist | Claude | cross-tool comparison + the consolidated graphify gap list |

Saved as `.claude/agents/*.md` plus a saved `.claude/workflows/` script. Every
researcher prompt must carry the graphify-first orientation rule and the
incremental-persistence instruction (`agent-report-persistence.md` rule 3) — an
agent that dies at minute 40 holding everything in memory leaves nothing.

The **verifier is the role that must not be cut.** Every claim of the form
"graphify lacks X" is the same shape as the LSP claim that was wrong twice in one
session before a control arm caught it.

### P4 — three documents

`docs/research/reports/`, tracked (not `.agent/`, which dies on `git clean -xdf`).

- Two **retrieval gap analyses** — codebase-memory-mcp, code-review-graph: what
  graphify lacks, and what graphify has that they lack. Both directions, per Ray.
- One **harness-observability doc** — mindwalk. Its README says it reads Claude
  Code and Codex *session logs* and replays agent footprint on a 3D repo map; it
  does not index or retrieve code. Comparing it to graphify on retrieval is a
  category error. Its question instead: can it show what a `kb-review` lane or a
  `codex` implementer actually touched during a round, versus what the spec
  scoped?

Each doc ends with `## GitHub repos touched`. Each states a **refuted count** —
a gap analysis with zero refuted claims means the verifier did not run.

### P5 — the version-sync tail

Two owed re-probes, whose methods are recorded in `currency.toml` and must be
followed rather than reinvented:

- `label-communities-schema-gap` — last probed on 0.9.30. Method: diff `llm.py`;
  if it changed, grep the diff for `label` before assuming anything; run the
  42-batch probe **only if** a label-touching line moved.
- `data-only-json-produces-zero-nodes` — re-probe by counting build warnings.

Then: the four still-open tracked issues (#2101, #2086, #1653, #1824) re-checked
against the **installed 0.9.31 source**, not the issue tracker — issues stay open
after fixes ship (`probes-need-a-control-arm.md`). Seed hk and fnox upstream
baselines with a networked `mise run kb-currency` (both print *"no upstream
version has ever been recorded — NOT CHECKED against upstream (this is not a
pass)"* every session today). Measure and write down what a graphify bump
actually costs: pin + manifest + re-clone + a ~30 min full rebuild, which nothing
currently declares.

Record the dotfiles gap **as a measurement, not a fix**: its `currency.toml`
carries only `[tool.graphify]`, and its `kb-setup` pin is 26 commits behind main
(4,907 insertions across 21 modules, `currency/*` included). `#34` — the
SessionStart nudge never fires cross-repo because `CLAUDE_PROJECT_DIR` is the
other repo.

### P6 — close

`kb-remember` + `kb-reflect` → run the **`kb-review` skill** (one cold
cross-family lane, bounded at 2 rounds) → `mise run kb-review-receipt` →
`kb-goal-outcome` → commit what it wrote → `mise run kb-ship` → `mise run kb-land`.

**The round ends at `kb-land`, not at `ship: OK`** (Ray, 2026-07-31: *"why is
merging mine, we are working on a long-running multi-agent harness"*). Run
`kb-goal-outcome` BEFORE `kb-ship` and commit its output — `review.EXEMPT_PATHS`
covers `graphify-out/memory/**` and `docs/goals/README.md`, so this costs no
re-review (#66).

## Sentinel formats

Every sentinel ends `@ <sha>`, where `<sha>` is `git rev-parse --short HEAD` at
the time it is written. A sentinel without one does not count. Tool output cannot
carry a sentinel and counts only when pasted verbatim from a real run.

```text
SELF-INDEX+ @ <sha>          affected on a real kb_setup symbol, expected callers grep-derived alongside
SELF-INDEX- @ <sha>          the same command on a bogus symbol -> no match
WATCH-STAMP+ @ <sha>         kb-watch rebuild THEN kb-currency-check clean (restamp works)
WATCH-STAMP- @ <sha>         a rebuild that bypasses the restamp -> drift reported (the arm)
INGESTED: <repo> <n> nodes @ <sha>        x3, from kb-build output
TEAM-SAVED: <n> agents + <workflow> @ <sha>
GAP-DOC: <tool> — <n> verified, <n> refuted @ <sha>    x3
REPROBE: <watch-item> — <verdict> @ <sha>              x2
ISSUES-RECHECKED: 2101/2086/1653/1824 — <one line each> @ <sha>
BUMP-COST: <one sentence> @ <sha>
DOTFILES-GAP: <one sentence> @ <sha>
GOAL-BLOCKED: <blocker> — tried: <probe1>; <probe2> @ <sha>
```

## Verification — sourced from the code that PRINTS each string

Anchored to symbols, never line numbers (a line number is invalidated by any edit
above it; a symbol only by a rename, which is when the citation *should* break).

| Signal | Literal | Source |
|---|---|---|
| review receipt, before any gate | `==> review: <n> lane(s): …` | `pr.py` `ship_main` |
| any gate under `kb-ship` | `PASS  gate <name> rc=0` — **two spaces** | `pr.py` `run_gates` |
| the gates `kb-ship` runs | lint, test, brain-audit, eval | `pr.py` `GATES` |
| PR opened | `ship: OK — PR open, gates green` | `pr.py` `_open_or_update_pr` |
| merged | `land: OK — PR #N merged, main synced` | `pr.py` `land_main` |
| memory | `Saved to graphify-out/memory/<file>.md` | graphify `cli.py` |
| reflect | `Reflected N memories (...) -> ...LESSONS.md` | graphify `cli.py` |

**Three traps that make reasonable-looking conditions unsatisfiable:**

1. `mise run test` runs pytest under `-qq`, so **`"N passed"` never appears**.
   Control arm: bare `uv run pytest tests/` prints it.
2. `kb-currency-check` prints **nothing** on success, so silence is
   indistinguishable from never-ran — require an echoed, file-recorded `rc`.
3. **`kb-ship` REFUSES before running a single gate** without a `kb-review`
   receipt for the current HEAD. A condition asking for `PASS  gate` lines with
   no instruction to review first is unsatisfiable.

## Out of scope

- Wiring `scip_ingest.py` to the CLI. It is graphify's code, unwired by its own
  docstring; this round *documents* the gap. Wiring it is upstream work.
- Fixing the collapsed `repo` attribution. Real, measured, and an upstream
  id-scheme question (`knowledge-base::knowledge-base::…`) — record it, do not
  chase it here.
- Bumping dotfiles' `kb-setup` pin. Measured here, fixed in that repo's own PR.
- `#93`, `#94`, `#82`, `#81`, `#67`, `#68`, `#62`–`#65` — standing backlog,
  untouched unless one blocks a phase, in which case say so and stop.
- Any `~/.claude` or other out-of-project edit. Ever.

## Hand-back — never report these as done

- **Secret rotation.** Deferred by Ray; raise **once**, unprompted, when the
  project completes. Not this round.
- Any decision to raise `GRAPHIFY_MAX_GRAPH_BYTES` above its default.
- Any decision to close one of the four upstream tracked issues.
