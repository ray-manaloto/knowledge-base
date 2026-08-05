# graphify capability expert report — 0.9.32 (installed) → 0.9.33 (upstream)

**Agent:** graphify-capability-expert · written incrementally, verbatim.
**Question (Ray, 2026-08-04):** *"tell me how we can utilize graphify to understand
our codebase and the research we are ingesting."*

**Method.** Every behavioural claim is read from the INSTALLED source at
`/Users/rmanaloto/.local/share/mise/installs/pipx-graphifyy/0.9.32/graphifyy/lib/python3.14/site-packages/graphify/`
(cited as `GX/<file>:<line>`), from this repo's `python/src/kb_setup/`, from
`mise.toml`, or from `gh api` against `Graphify-Labs/graphify`. **No `graphify`
subcommand was executed.** Measurements I ran myself are marked MEASURED with the
command shape. Anything else is labelled UNVERIFIED.

---

## 0. Three corrections to standing lore, up front

### 0a. `graphify --help` does NOT trigger a build

`GX/__main__.py:506-703` is a pure `print(...)` block ending in `return` at
`__main__.py:703`. No graph load, no build.

What DOES build is the **path-redirect fallthrough**, `GX/cli.py:3878-3884`:

```python
elif Path(cmd).exists() or cmd in (".", "..") or cmd.startswith(("./","../","/","~")):
    sys.argv.insert(2, sys.argv[1]); sys.argv[1] = "extract"; _reenter_main()
```

`graphify <anything-resolving-as-a-path>` silently becomes `graphify extract <path>`
— a full build. The recorded incident is consistent with that, not with top-level
`--help`. Two adjacent traps:

- `GX/__main__.py:694-700`: a universal help guard makes `-h/--help/-?` *after* the
  command print one line and stop — **except** for
  `_FREE_TEXT_CMDS = {"query","explain","path","save-result","install","uninstall"}`.
  So `graphify explain --help` treats `--help` as the concept to explain.
- `graphify install --help` was historically destructive (`#821`, comment at
  `__main__.py:693-696`).

**The "never run graphify by hand" invariant is unchanged** — but the reason to
avoid `--help` is the fallthrough, and the *help text itself is readable from
source*, which is where §1 below comes from.

### 0b. graphify's own hook is fighting this repo's hook

Every Bash call this session returned
`MANDATORY: graphify-out/graph.json exists. You MUST run graphify query …`.
That string is graphify's, not the harness's: `GX/cli.py:578-586` (`_SEARCH_NUDGE`),
with `_READ_NUDGE` (`cli.py:588-604`) and a **hard deny** `_READ_DENY`
(`cli.py:610-628`, `permissionDecision: "deny"`, once per session, gated by
`_hook_strict_enabled` / `GRAPHIFY_HOOK_STRICT`, `cli.py:425-433`). It instructs an
agent to run exactly the raw `graphify query` that `kb_setup.hook_guard:72` DENIES.
Two guards in direct contradiction; this repo's wins (`mise run kb-query`). Worth
knowing it is a vendored string, not a system opinion.

### 0c. The 512 MiB cap is already raised here — but only inside mise

`GX/security.py:32` sets `_MAX_GRAPH_FILE_BYTES = 512 * 1024 * 1024`;
`check_graph_file_size_cap` (`security.py:357-383`) rejects anything larger.
**MEASURED:** `graphify-out/graph.json` is **552,462,397 bytes** — 15.8 MB over the
default cap. `mise.toml:137` sets `GRAPHIFY_MAX_GRAPH_BYTES = "1GB"` (parsed as
1 GiB, `security.py:42`), so every mise-launched graphify subprocess is fine.
**Control arm:** the same grep over `python/ mise.toml CLAUDE.md .claude docs` also
returned `.claude/agents/kb-corpus-curator.md:39` and six `docs/` hits, so the probe
discriminates.

Consequence worth recording: **a graphify invocation that does not inherit
`mise.toml`'s `[env]` will refuse to read this graph.** That is a second, independent
reason `mise run kb-query` is the only path, and it silently changes behaviour in
0.9.33 (§4.2).

---

## 1. Complete command + flag surface (0.9.32)

Dispatch: `GX/cli.py:713-3887` (`dispatch_command`); install dispatch via
`dispatch_install_cli` (`__main__.py:705`); the authoritative flag list is the help
block at `__main__.py:506-703` **cross-checked against each command's real arg loop**
(flags found only in the arg loop are marked ⚠ **undocumented**).

Legend — **USED** (call site cited) · **NOT USED** · **FORBIDDEN**.

### 1.1 Query & analysis

| Command | `cli.py` | Real flags | Status |
|---|---|---|---|
| `query "<q>"` | 852-971 | `--dfs`, `--context C` (repeatable), `--budget N` (default **2000**), `--graph PATH`; `=`-forms at 866-889 | **USED** — `mise.toml:301-330` → `kb_setup/cli.py:70` → `graphify_ops.py:288`; also `brain.py:340`, `eval_cases.py:401` |
| `affected "<X>"` | 972-1031 | `--relation R` (repeatable), `--depth N` (2), `--graph PATH` | **NOT USED** — no task, no call site. Allowed direct (`hook_guard.py:86`) |
| `god-nodes` / `god_nodes` | 1032-1086 | `--top N` (10), `--graph PATH`, `--json` | **NOT USED**; allowed direct (`hook_guard.py:85`) |
| `path "A" "B"` | 1175-1301 | `--graph PATH` | **NOT USED**; allowed direct |
| `explain "X"` | 1302-1435 | `--graph PATH` | **NOT USED**; allowed direct |
| `diagnose multigraph` | 1436-1529 | `--graph`, `--json`, `--max-examples N` (5), `--directed`, `--undirected` (mutually exclusive, 1478-1495), `--extract-path` | **USED only in the eval harness** — `eval_cases.py:419` |
| `benchmark [graph.json]` | 2524-2540 | positional only | **NOT USED** |
| `tree` | 1983-2039 | `--graph`, `--output`, `--root`, `--max-children N` (200), `--top-k-edges N` (12), `--label NAME` | **USED** — `artifacts.py:32` |

**Direction semantics differ per command and are not configurable:**
`query` forces **undirected** (`cli.py:909-916` — so BFS reaches callers *and*
callees); `path` forces `directed=True, multigraph=True` (`cli.py:1201-1207`);
`explain` forces `directed=True` (`cli.py:1323-1324`); `cluster-only`/`label` follow
the file's own flag (`cli.py:1680-1681`) — and our `graph.json` says
`"directed": false` (MEASURED, `head -c 1200 graphify-out/graph.json`). This is the
mechanism behind the standing memory *"graphify's CLI overrides the directed flag"*.

### 1.2 Build / ingest

| Command | `cli.py` | Flags | Status |
|---|---|---|---|
| `extract <path>` | 2597-3694 | `--backend`, `--model`, `--mode deep`, `--force`, `--max-workers`, `--token-budget` (60000), `--max-concurrency` (4), `--api-timeout` (600), `--out/--output`, `--google-workspace`, `--no-gitignore`, `--no-cluster`, `--code-only`, `--postgres DSN`, `--cargo`, `--global`, `--as <tag>` (`__main__.py:600-627`) | **USED, restricted** — `graph.py:88`, `graph.py:212-227` use exactly `extract <path> --code-only --force [--out DIR]`. `--backend/--model` **FORBIDDEN** for non-Claude (`do-not.md` #4); `--global`/`--as` **FORBIDDEN** (`do-not.md` #2) |
| `update <path>` | 1902-1957 | `--force` (or `GRAPHIFY_FORCE=1`), `--no-cluster` | **USED** — `graph.py:845` |
| `add <url>` | 1530-1564 | `--author`, `--contributor`, `--dir` | **USED** — `mise.toml:366-374` |
| `clone <url>` | 2193-2216 | `--branch`, `--out` | **NOT USED, correctly** — `_clone_repo` (`cli.py:679-757`) does `--depth 1` into shared `~/.graphify/repos/`, then `git pull`; a manifest pins a SHA, so `graph.py:51` uses raw `git clone --quiet --branch` instead |
| `watch <path>` | 1565-1577 | positional only — no `--out` | **NOT USED, correctly** — `graph.py:259-281` records the measurement: it rebuilds only `<path>/graphify-out/graph.json`, has no merge target and no post-rebuild hook. `mise run kb-watch` replaces it |
| `cluster-only <path>` | 1578-1901 | `--no-viz`, `--graph`, `--no-label`, `--backend[=]`, `--model[=]`, `--max-concurrency[=]` (4), `--batch-size[=]` (100), ⚠ `--resolution R` (1.0, 1616-1619), ⚠ `--exclude-hubs P` (1620-1623), ⚠ `--min-community-size=N` (3, 1592-1593), ⚠ `--timing` (1587) | **USED** — `artifacts.py:31` runs `cluster-only . --no-label` |
| `label <path>` | 1578-1901 (`force_relabel = cmd == "label"`, 1581) | as above + `--missing-only` | **USED** — `graphify_ops.py:170`, deterministic/no-LLM |
| `merge-graphs <g1> <g2> …` | 2095-2192 | `--out PATH` | **USED** — `graph.py:531` (N-ary), `graph.py:682` (self-merge) |
| `merge-driver <base> <cur> <other>` | 2040-2094 | — | **NOT USED** (graph.json is gitignored) |
| `merge-chunks` | 3755-3835 | — | **NOT USED** |
| `merge-semantic` | 3836-3877 | `--out` (required) | **NOT USED** |
| `cache-check` | 3695-3754 | — | **NOT USED** |
| `check-update <path>` | 1975-1982 | — | **NOT USED** |

⚠ **`--resolution` and `--exclude-hubs` are the four highest-value undocumented
flags in the tool** and are the direct lever on community quality — see §2.

### 1.3 `export <subtype>` (`cli.py:2217-2523`)

| Subtype | `cli.py` | Status |
|---|---|---|
| `callflow-html` | 2347-2438 | **USED** — `artifacts.py:33` |
| `html` | 2377, 2439-2456 | NOT USED directly (graph.html comes from `cluster-only`) |
| `obsidian` | 2457-2466 | **USED** — `artifacts.py:37` |
| `wiki` | 2467-2484 | **USED** — `artifacts.py:36` |
| `svg` | 2485-2490 | **USED** — `artifacts.py:38` |
| `graphml` | 2491-2495 | **USED** — `artifacts.py:34` |
| `neo4j` | 2496-2509 | **USED** — `artifacts.py:35` |
| `falkordb` | 2510-2523 (`FALKORDB_PASSWORD`, 2262) | **NOT USED** |

### 1.4 Memory / feedback

| Command | `cli.py` | Flags | Status |
|---|---|---|---|
| `save-result` | 1087-1117 | `--question`, `--answer`, `--type query\|path_query\|explain`, `--nodes …`, `--outcome useful\|dead_end\|corrected`, `--correction`, `--memory-dir` | **USED** — `brain.py:134-136` |
| `reflect` | 1118-1174 | `--memory-dir`, `--out`, `--graph`, `--analysis`, `--labels`, `--half-life-days` (30), `--min-corroboration` (2) | **USED** — `brain.py:688` |

### 1.5 FORBIDDEN here

| Command | Why |
|---|---|
| bare `install` | mutates `~/.claude` — `do-not.md` #1 |
| `hook install/uninstall/status` (835-851) | machine-global git hooks — `do-not.md` #2 |
| `global add/remove/list/path` (2541-2596) | `~/.graphify/global-graph.json` shared mutable state |
| `extract --global` / `--as` | same |
| `provider list/show/add/remove` (715-831) | registers a non-Claude LLM provider — `do-not.md` #4 |
| `extract --backend gemini\|openai\|…` | `graphify_env.clean_env()` strips every trigger; a flag would fight it |
| `hook-check` / `hook-guard` (1958-1974) | graphify's own PreToolUse guard — §0b |
| any raw `graphify <sub>` | `hook_guard` PreToolUse **deny**; allowlist = `path`, `explain`, `god-nodes`, `affected`, `diagnose` (`hook_guard.py:85-87`) |

### 1.6 The MCP surface — bigger than the CLI

`mise run kb-serve` starts `graphify-mcp`. Its tools (`GX/serve.py`):

`query_graph` (1349) · `get_node` (1369) · `get_neighbors` (1378) · **`get_community`
(1391)** · `god_nodes` (1403) · `graph_stats` (1408) · `shortest_path` (1413) ·
`list_prs` (1426) · `get_pr_impact` (1441) · `triage_prs` (1457).

Resources (`serve.py:1806-1811`): `graphify://report`, `://stats`, `://god-nodes`,
**`://surprises`**, **`://audit`**, **`://questions`**.

**`get_community`, `://surprises`, `://audit` and `://questions` have NO CLI
equivalent.** They are reachable only over MCP or by reading `GRAPH_REPORT.md`. This
repo sets no `KB_MCP_TOOLS` allowlist (`mise.toml:350-364`, `mcp_serve.py:83`), so
all ten tools are already exposed — we simply never call the interesting four.

---

## 2. What we are NOT using that we should be

Ranked by value against Ray's two goals: **(a) understand OUR OWN codebase**,
**(b) understand the RESEARCH CORPUS**.

### Tier 1 — highest value, zero cost, available today

**1. `affected` — blast radius on our own code (goal a).**
`kb_setup/graph.py:230-240` says this in so many words: `affected` was the question
`refresh_self` exists to make answerable, and 41 sources are now indexed. There is
**no `kb-affected` task and no call site** — the capability was built and never
wired to a verb. `GX/affected.py:1-273`, reverse traversal over
`DEFAULT_AFFECTED_RELATIONS`.
Shape: `graphify affected "<symbol>" --depth 3 --graph graphify-out/graph.json`
(allowed direct, `hook_guard.py:86`) → wrap as `mise run kb-affected -- <symbol>`.
Buys: *"which tests and callers break if I change this"* — the one question
`kb-query` structurally cannot answer, because query is forward BFS.

**2. `--resolution` / `--exclude-hubs` on `cluster-only` (goals a+b).**
⚠ Undocumented (`cli.py:1616-1623`). **MEASURED:** the corpus currently has **9,330
communities** over ~334k tagged nodes — an average of ~36 nodes each, which is
shredded, not clustered. `--resolution` below 1.0 produces coarser communities;
`--exclude-hubs P` drops the top-P-percentile degree nodes before Leiden, which is the
standard fix for hub-collapse. Neither has ever been tried here (`artifacts.py:31`
passes only `--no-label`).
Shape: `mise run kb-artifacts` after adding `--resolution 0.6 --exclude-hubs 0.99` to
`artifacts.py:31`. Buys: community labels that name a *topic* instead of a fragment —
which is what makes `kb-label`'s deterministic hub labels legible.

**3. The four MCP-only reads: `://surprises`, `://questions`, `://audit`,
`get_community` (goal b).**
`surprising_connections` (`GX/analyze.py:133-164`) ranks edges by a composite surprise
score (`_surprise_score`, `analyze.py:203-275`) that explicitly rewards
`semantically_similar_to` (×1.5, line 261), cross-file-type (code↔paper, +2, line 246),
cross-directory (+2, line 251) and peripheral→hub (+1, line 265). **That is exactly the
"show me the non-obvious connections in the research" question**, already computed, and
we read it nowhere. `://audit` gives the EXTRACTED/INFERRED/AMBIGUOUS breakdown — the
provenance quality metric this repo claims as a differentiator and never reports.
Shape: `mise run kb-serve`, then read the resources; or lift `analyze.surprising_connections`
into a `kb-surprises` task.

**4. `god-nodes` — but NEVER on the aggregate (goals a+b).** `GX/analyze.py:109-131`
excludes file/concept/JSON-key nodes and **not AST nodes**, so on the aggregate it
returns third-party Rust (§3B.1). Two shapes that work, and one that does not:

```
graphify god-nodes --top 40 --json --graph graphify-out/graph-prose.json   # concepts
graphify god-nodes --top 40 --json --graph graphify-out/graph.json         # DON'T — drowned
```

plus a per-source split on the ID prefix, which needs a `kb_setup` helper — there is
no `--repo`/`--source` flag (`cli.py:1032-1086`). Buys: `ToolVersion` for mise,
`LintContext` for rumdl, `HookOptions` for hk — each tool's real core abstraction,
invisible on the aggregate. Full measurements in §3B.

### Tier 2 — real value, small wiring cost

**5. `explain "X"` and `path "A" "B"` (goals a+b).** Both allowed direct, both
force `directed=True` (`cli.py:1201-1207`, `1323-1324`) — so unlike `kb-query` they
render true caller→callee direction. The standing memory *"a SYMBOL question needs
`graphify explain`, not `kb-query --idf`"* is exactly this, and there is still no
task making it the default reflex.

**6. `GRAPH_REPORT.md` already contains import cycles and we never read it.**
`find_import_cycles` (`analyze.py:640`) is called only from `report.generate`
(`GX/report.py:198-199`). `mise run kb-artifacts` regenerates it every time.

**7. `diagnose multigraph` outside the eval harness.** `eval_cases.py:419` runs it,
but nothing reports it. It measures same-endpoint edge collapse — i.e. how much of the
graph's relational detail the undirected simple-Graph representation is destroying.
Given `merge-graphs` *forces* `nx.Graph` (`cli.py:2151-2161`), this number is
structurally large here and nobody has looked at it.

**8. `benchmark [graph.json]`** (`cli.py:2524-2540`) — measures token reduction vs a
naive full-corpus read. That is the headline claim of this whole repo and it has never
been measured with the tool's own instrument.

### Tier 3 — evaluate, don't adopt blindly

**9. `export falkordb` / `neo4j --push`.** We already emit `cypher.txt`
(`artifacts.py:35`) and never load it. At 552 MB the graph is past the point where a
JSON file is a good query surface; a graph DB is the native scale answer and
`use-tool-builtins.md` already names it.

**10. `extract --cargo` / `--postgres`.** Irrelevant to this corpus (no Rust
workspace, no live DB). Named for completeness.

**11. NOT AVAILABLE: node summaries.** `sources/graphify/docs/node-summaries-rfc.md`
is an RFC. **Control-armed:** `grep -rn 'node_summary|node-summaries|summarize_node'`
over `GX/*.py` → **0 hits**, while the same command shape for `suggest_questions`
returned 9. Not implemented in 0.9.32.

**12. NOT AVAILABLE HERE: anything LLM-backed.** `label --backend`,
`cluster-only --backend`, `--mode deep` semantic extraction, `_llm_tiebreak`
(`GX/dedup.py:657`). `clean_env()` strips every non-Claude trigger, and graphify's
`claude-cli` backend is broken (#2076). **Any recommendation resting on graphify's own
LLM backend is unavailable — including LLM community naming.** The host-agent
Workflow is the only LLM path.

---

## 3. Cross-source connectivity — THE central question

### 3.1 MEASURED, independently re-derived this session

Streaming scan of `graphify-out/graph.json` (a Python line-state-machine over the
pretty-printed `"nodes"` / `"links"` arrays; source graph = the live 552 MB file):

| Quantity | Value |
|---|---|
| Links scanned | **816,538** |
| **Cross-source links** | **0** |
| Distinct source prefixes recoverable from node IDs | **41** |
| Communities | **9,330** |
| Communities whose members span >1 source prefix | 171 |

Top prefixes: `codex` 90,797 · `deer-flow` 28,526 · `cognee` 22,394 ·
`basic-memory` 21,025 · `uv` 20,524 · `mise` 19,651 · `rumdl` 18,804 · `pkl` 16,910 ·
`OpenSymphony` 10,987 · `ecc` 9,901 · `graphify` 9,812 · `agnix` 9,714 ·
`last30days-skill` 9,102 · `taplo` 8,013 · `codegraph` 6,390 · `pensyve` 4,963 ·
`typos` 3,422 · `.self-graph` 3,235 · `knowledge-base` 2,864 · `fnox` 2,687 ·
`skillopt` 2,587 · `hk` 2,131 · … (41 total, tail includes `ty` 36,
`fable-orchestrator` 18, `awesome-harness-engineering` 15).

**Three independent probes now agree, and the partition matters.** The lead's first
probe partitioned by the `repo` attribute — which §3.2 shows has only 2 values, so it
could only ever return 0; that one is discarded. Two survive:

| Probe | Partition | Attributed | Cross-source |
|---|---|---|---|
| lead (re-run) | `source_file` → owning `sources/<name>/` clone on disk | 634,497 of 816,538 | **0** |
| mine | node-ID prefix segment (`id.split("::")[1]`) | **816,538 of 816,538** | **0** |

Mine has full coverage (every node ID carries the prefix, so nothing is skipped);
the lead's is independent of the ID scheme. Different routes, same answer.

**Control arm — my probe was missing one, so I ran it.** Same scan, same run, same
edge-walking code, partitioned instead by the first path component of `source_file`:
**23,978 crossings**, top pairs `src`↔`tests` 10,202 · `graphify`↔`tests` 4,054 ·
`__tests__`↔`src` 975 · `pkl-core`↔`pkl-parser` 850 · `cognee`↔`examples` 780. The
machinery is demonstrably not blind to a crossing — and every crossing it finds is
**inside one source**. (My count is lower than the lead's 191,755 because I read only
the first `source_file` line per node block and so skipped 167,777 links with an
unattributable endpoint. The *direction* is what the arm establishes, and both agree
on the same top pairs.)

### 3.2 CORRECTION: per-source provenance IS recoverable — just not from `repo`

The brief stated provenance "is not even recoverable from the tag". Half right. The
`repo` attribute really does carry only 2 values — but **every node ID carries a
double prefix**, and the *second* segment is the original per-source tag.
**MEASURED:** of 11,262 sampled IDs, 11,257 have exactly two `::` separators and 5
have none; the second segment resolves to the 41 source tags above.

Mechanism, exactly:

1. `graph.py:531` calls the **N-ary** `merge-graphs <src1> … <srcN> --out <out>`.
   `distinct_repo_tags` (`GX/build.py:1611-1636`) derives one tag per input from
   `p.parent.parent.name` — i.e. `sources/<name>/graphify-out/graph.json` → `<name>`.
   Every node gets `"<name>::"` and `repo="<name>"`.
2. `graph.py:678-686` then runs the **2-input** self-merge
   `merge-graphs <out> <self-sub> --out <out>`. The accumulator's own path is
   `<repo_root>/graphify-out/graph.json`, so its tag is `knowledge-base` — and
   `prefix_graph_for_global` (`GX/build.py:1590-1606`) **re-prefixes and re-tags
   every node it already held**:

   ```python
   relabel = {n: f"{repo_tag}::{n}" for n in G.nodes}
   H = nx.relabel_nodes(G, relabel, copy=True)
   for node, data in H.nodes(data=True):
       data["repo"] = repo_tag          # ← overwrites the per-source tag
   ```

   The ID keeps both prefixes; the `repo` attribute keeps only the last one.

**So `repo` has 2 values because the final self-merge flattens it, while the ID
retains full provenance.** Anything that needs per-source facts should split
`node["id"]` on `::` and take index 1 — not read `repo`. That is a one-line change
wherever we currently give up.

### 3.3 Why 0 cross-source edges is guaranteed, not accidental

`GX/cli.py:2166-2172` is the entire merge:

```python
repo_tags = _repo_tags(graph_paths)
merged = _nx.Graph()
for G, repo_tag in zip(graphs, repo_tags):
    prefixed = _to_simple(_prefix(G, repo_tag))
    merged = _nx.compose(merged, prefixed)
```

`nx.compose` unifies nodes **by ID equality only**. Prefixing guarantees disjoint ID
sets, so no node is ever identified across two inputs, and no edge can span them.
`distinct_repo_tags`' docstring (`build.py:1613-1622`) confirms the intent is
adversarial: colliding prefixes were treated as the **defect** (#1729 — "silently
merges unrelated entities and **invents cross-runtime edges**").

**`merge-graphs` cannot ever produce a link between two pinned sources. No flag
changes this.** Any plan that waits for merge to connect the corpus is waiting for
something the code forbids.

### 3.4 Mechanism-by-mechanism verdict

| Mechanism | Can it produce a cross-source link? | Evidence / what would have to be true |
|---|---|---|
| `merge-graphs` prefixing + `nx.compose` | **NO — by construction** | `cli.py:2166-2172`, `build.py:1598` |
| `distinct_repo_tags` | **NO — it exists to PREVENT it** | `build.py:1611-1636`, #1729 |
| `global add` / global graph | **NO** — same `prefix_graph_for_global` call (`global_graph.py:117`); also FORBIDDEN | `do-not.md` #2 |
| Label normalisation / dedup (`norm_label`, `deduplicate_entities`) | **NO as we run it** | `GX/dedup.py:320-560` runs *inside* one `extract`/`build` pass over one root. `merge-graphs` never calls it. Would need: a dedup pass over the merged graph, which no CLI surface offers |
| Community detection (Leiden/Louvain) | **NO** | `cluster(G, …)` (`cli.py:1685`) is edge-derived; with 0 cross edges every community is inside one source. **MEASURED:** 171 of 9,330 community IDs appear under two prefixes — but with 0 connecting edges these are **ID collisions**, not bridges. `remap_communities_to_previous` (`GX/cluster.py:272-315`) greedily reassigns new cids to old cids by overlap, which can land two disconnected communities on one integer. (That remap is the likeliest source; UNVERIFIED whether Leiden id reuse also contributes.) **Do not read a shared community id as a relationship.** |
| `surprising_connections` | **NO** | `analyze.py:277-340` iterates `G.edges(data=True)`. No edge → no candidate. Its cross-repo bonus (`_surprise_score`, line 251, `_top_level_dir(u_source) != _top_level_dir(v_source)`) is *designed* for exactly the link we don't have |
| `god_nodes` | **NO** | `analyze.py:109-131` is per-node degree; it ranks, it does not relate |
| `semantically_similar_to` edges | **YES, conditionally** | It is an LLM-extraction relation (`GX/llm.py:478` prompt schema; scored ×1.5 at `analyze.py:261`). It can only be emitted **inside one extraction pass**. Would have to be true: a single host-agent extraction chunk contains material from two sources, and the agent is told to relate them |
| Hyperedges | **YES in principle — but ours are BROKEN today, see §3.6** | Same path — `llm.py:478` `"hyperedges":[{…,"nodes":[…]}]`, `relation: participate_in\|implement\|form`. **MEASURED:** the live graph holds exactly **5** hyperedges, all intra-source, and **all 5 dangle** |
| `path "A" "B"` / `query` / `affected` | **NO — they consume edges, they do not create them** | `cli.py:1247-1270`, `cli.py:906-971`, `affected.py` |
| **Single-root AST extraction + the cross-file resolver** | **YES — this is the real mechanism** | see §3.5 |

### 3.5 The one mechanism that actually works: ONE `extract` over ONE root

> **REFUTED IN PART, 2026-08-05 — carried, not deleted.** A sibling agent found that
> **`resolve_cross_file_raw_calls` is never called.** Control-armed: the same grep
> shape finds a live caller for `resolve_bash_source_edges` at `extract.py:5282`, so
> the probe discriminates. My citation of `extract.py:4778` named
> `_augment_symbol_resolution_edges`, which is a *different* function; I did not
> follow the call from there into `resolve_cross_file_raw_calls` and should have.
>
> What survives: the **inline** cross-file pass at `extract.py:5288-5290` is live and
> does operate over one invocation's nodes, so single-root extraction really can
> produce cross-directory edges. What does not survive is the value: the same agent
> sized what it would join on — **4,910 labels shared across sources, topped by
> `main()` in 36 of them**, plus `path`, `run()`, `config`. That is noise, and the
> resolver's uniqueness guard would suppress most of it anyway.
>
> **The one-root pilot (§5 step 4) is WITHDRAWN.** The mechanism is real; the yield
> is not. §3.7's bridge-chunk path is the surviving answer.

The original analysis follows, for the mechanism it still describes correctly.

`resolve_cross_file_raw_calls` (`GX/symbol_resolution.py:307-376`) is called from
`extract.py:4778` (`_augment_symbol_resolution_edges(paths, all_nodes, all_edges, root)`)
with **`all_nodes` = every node in the extraction run**. It builds
`label_index = build_label_index(all_nodes)` (`symbol_resolution.py:321`, defined at
:57-70) — a global label→id map across the whole scanned tree — and emits
`relation: "calls", confidence: "INFERRED", confidence_score: 0.8`
(`symbol_resolution.py:361-372`) wherever a bare call name resolves to exactly one
candidate.

**graphify itself confirms this reaches across directories**, in the code that tries to
*suppress* it (`GX/analyze.py:224-231`):

> *"label-matching fires across language families in monorepos, and code→doc 'calls'
> edges are extraction artefacts"*

So: **the way to get cross-source edges is to extract several sources under a single
root in a single `graphify extract` run**, not to merge their separately-extracted
graphs. Guardrails that come free: member calls skipped, ambiguous labels skipped
(`disambiguate_ambiguous_candidates`, `symbol_resolution.py:345-353`), only unique
candidates emitted, and only `file_type == "code"` nodes are eligible callees
(`node_is_resolvable_symbol`, `symbol_resolution.py:35-55`).

**Honest cost and risk, stated plainly:**

- It is **label matching, not real linkage.** A `run()` in `uv` and a `run()` in
  `mise` are different functions; the resolver's uniqueness guard suppresses that
  particular case (two candidates → skipped) but it also suppresses many *true*
  links. Expect precision to be mediocre and recall to be low.
- Every such edge is `INFERRED`, which is exactly what this repo's provenance model
  is for — they are visibly second-class and filterable.
- The blow-up risk is real: one root over all 41 sources is a very large single
  extraction, and #120 (the 33%-duplicate-prefix incident) is the standing warning
  about doing arithmetic on this corpus casually.

**Therefore the recommendation is a bounded pilot, not a re-architecture** — see §5
step 4. Pick the 8-ish *toolchain* sources Ray actually asked about (`uv`, `ruff`/`ty`,
`mise`, `hk`, `graphify`, `taplo`, `rumdl`, `typos`), extract them under one root into
a **separate** `toolchain-graph.json`, and measure the cross-source edge count before
touching the aggregate. If it is 0, label matching does not bridge these repos and the
answer is documentation-level linking instead. If it is non-trivial, we have the
connectivity Ray asked for at zero LLM cost.

### 3.6 NEW DEFECT FOUND: every hyperedge in the corpus dangles

**MEASURED.** The live `graph.json` contains exactly **5 hyperedges**, and
`sources/extractions/*.json` contains exactly **5** (`graphify-docs.json` 2 +
`media-docs.json` 3) — so none are being *lost*. But none of them *resolves*:

| hyperedge member id (as stored) | matching node id in the graph |
|---|---|
| `claude_code_memory_plan_bootstrap` | `knowledge-base::claude_code_memory_plan_bootstrap` |
| `yt_9ciowbmokdu_memory_storage` | `knowledge-base::yt_9ciowbmokdu_memory_storage` |

Probe: stream every `"id"` in the `nodes` array and suffix-match the hyperedge
members. **Control arm:** the probe *found* both nodes — it returned a prefixed ID
rather than nothing, so it discriminates between "absent" and "present under a
different key". The member IDs carry **zero** `::` prefixes while the nodes they name
carry one.

**Mechanism.** Hyperedges are a **graph-level attribute**, not nodes:
`data["graph"]["hyperedges"]` (visible in the first 1,200 bytes of `graph.json`).
`prefix_graph_for_global` (`GX/build.py:1590-1606`) relabels nodes and rewrites edge
`_src`/`_tgt` — and **never touches `G.graph`**. So when `graph.py:678-686` runs the
final self-merge, the doc nodes gain `knowledge-base::` and the hyperedges naming them
do not.

**Consequences.** Anything resolving a hyperedge member to a node gets nothing. Note
`_stamped_manifest_files` (`GX/cli.py:100-119`) treats a hyperedge as valid extraction
output for manifest stamping (#1920) — so this failure is *silent by design upstream*:
extraction is stamped complete while the artifact is unusable.

**Fix direction (do not apply blind):** this is another symptom of the
double-prefixing in §3.2 and step 3 of §5 — merging the self sub-graph inside the
N-ary call would remove the second prefix pass entirely, but it would *not* fix the
first one. A durable fix rewrites `G.graph["hyperedges"][*]["nodes"]` through the same
`relabel` map inside `prefix_graph_for_global` — which is an **upstream** change
(`build.py`), i.e. a graphify issue to file, not a `kb_setup` patch. **UNVERIFIED**
whether upstream already tracks it.

### 3.7 Why semantic edges cross FILES but never SOURCES — and what would change

The lead is right that `GRAPH_REPORT.md:8041-8052` lists `semantically_similar_to`
edges spanning two files (`claude-code-memory-plan.md` → `yt-9CiOwbmOKdU-memory.md`),
both under `sources/media/` — one source. Verified in the code, the scoping is
**three layers deep, and all three are OURS, not graphify's**:

**Layer 1 — the prompt gives each agent exactly one file.** `.claude/workflows/kb-extract.js`
`commonPrompt(s)` builds one `agent()` per source over a single `s.path`, and states
the rule twice:

> `source, target : node ids that BOTH exist in this chunk's nodes.`
> `Rules: only connect nodes that exist in THIS chunk;`

Every node it emits carries that one file's `source_file`/`source_url` and an id
forced to start with `"${s.key}_"`. An agent that never sees a second source cannot
relate to it.

**Layer 2 — the validator makes it machine-enforced.** `kb_setup/chunks.py:87-104`
(`_edge_issues`) rejects any edge whose endpoint is not in the chunk's own id set —
`dangling source` / `dangling target`. `graphify_ops.merge_chunk` (`graphify_ops.py:70-79`)
**refuses the whole chunk** on any issue, rc=2. So even a well-intentioned
cross-source edge would be thrown away at the door.

**Layer 3 — but the escape hatch already exists, and is already load-bearing.**
`chunks.validate(chunk, *, known_ids=...)` (`chunks.py:140-180`) widens endpoint
resolution beyond the chunk, and `resolvable = ids | (known_ids or set())`
(`chunks.py:178`). Its docstring says why it had to exist:

> *"`build_merge` loads the nodes already in the graph, prepends them as a base
> chunk, and resolves endpoints against the COMBINED set … Without this,
> `validate_files` reported four real cross-chunk relationships in
> `goal-and-skills-workflow-docs.json` as dangling; acting on that report DELETED
> them."*

**So a cross-source semantic edge is already representable and already validatable.
What is missing is only that no agent is ever shown two sources at once.**

**What would have to change — small, and none of it in graphify:**

1. `kb-extract.js`: add a *bridge* source kind whose prompt is handed **two** chunks'
   node inventories (id + label + rationale) and asked for **only** cross-source
   edges — `conceptually_related_to`, `shares_data_with`, `contrasts_with`,
   `semantically_similar_to` (the relation vocabulary graphify's own prompt uses,
   `GX/llm.py:478`). It emits `{"nodes": [], "edges": [...]}` — no new nodes.
2. `merge_chunk`: pass `known_ids` when merging a bridge chunk (the union of the two
   source chunks' ids), exactly as `kb-assemble` already does. This is the one code
   change, and `chunks.py:150-162` was written for it.
3. Ordering: the bridge chunk merges **after** both source chunks, so its endpoints
   resolve against nodes already in the graph.
4. `merge_chunk`'s `src_root` is a single path (`_merge_docs.py:6,20`) used only for
   path relativization. A bridge chunk creates no nodes, so it has no `source_file`
   to relativize — moot, but worth asserting rather than assuming.

Nothing about graphify blocks this. The constraint was our prompt, and our validator
faithfully enforcing our prompt.

### 3.8 The other honest answer: prose is where cross-tool linkage belongs

Cross-*tool* understanding (`uv` vs `mise` vs `hk`) is not a call-graph question — the
repos genuinely do not call each other. The relation is conceptual, and the corpus
already has the right relation names for it: `conceptually_related_to`,
`shares_data_with`, `semantically_similar_to` (`GX/llm.py:478`). Those come from the
**host-agent extraction**, which is Claude and which we control completely. A single
extraction chunk that reads *two* tools' docs together and is explicitly asked to relate
them will produce genuine cross-source edges — and because it is one chunk, the node IDs
land in one namespace. **This is the only path that produces high-precision cross-source
links, and it costs Claude tokens rather than CPU.**

---

## 3B. God nodes: does the AST mass drown tool-level concepts?

**Short answer: yes on the aggregate — and `--prose` fixes the drowning but still
cannot answer Ray's question, because the tools' concepts were never ingested at all.
That second half is the load-bearing finding.**

### 3B.1 The aggregate: drowned, exactly as the lead read it

`god_nodes` (`GX/analyze.py:109-131`) is pure degree ranking with three exclusions —
file nodes, concept nodes, JSON-key nodes (`_is_file_node`, `_is_concept_node`,
`_is_json_key_node`). **It does not exclude AST nodes**, and nothing weights by
source. With ~49% of the graph third-party AST, the top of the list is whatever
third-party Rust has the most call sites. `GRAPH_REPORT.md:8029-8039` is that list.

### 3B.2 `--prose` completely removes the AST mass — MEASURED

`graph-prose.json` is 2,864 nodes / 3,747 edges, `_origin` histogram **100%
`semantic`**, `file_type` = concept 2,574 · rationale 271 · code 10 · document 8 ·
image 1. Its degree-ranked top is **entirely concept-level, zero AST symbols**:

| deg | label | source |
|---|---|---|
| 72 | Anthropic "Keep Claude Code goals…" docs page | `claude-code-goal-docs.md` |
| 41 | Orchestration | `marketplace-235-relevant.txt` |
| 38 | Harness / Workflow | `marketplace-235-relevant.txt` |
| 33 | Domain-Specific | `marketplace-235-relevant.txt` |
| 30 | Claude Code "What's new" weekly digest | `code.claude.com_docs_en_whats-new.md` |
| 29 | Memory | `marketplace-235-relevant.txt` |
| 24 | Claude Code Hooks reference | `code.claude.com_docs_en_hooks.md` |

Command shape (allowed direct — read-only, `hook_guard.py:85`):

```
graphify god-nodes --top 40 --json --graph graphify-out/graph-prose.json
```

### 3B.3 …but the toolchain contributes ZERO prose nodes

**MEASURED**, prose nodes grouped by `source_file`'s first component — the entire
2,864: **no `uv`, no `mise`, no `hk`, no `ruff`, no `ty`, no `taplo`, no `rumdl`, no
`typos`.** The only tool-doc prose in the corpus is **graphify's own repo docs**
(`CHANGELOG.md` 72 · `plugins.md` 47 · `SKILL.md` 39 · `hooks.md` 13 ·
`README`/`SECURITY`/`BENCHMARKS`/`ARCHITECTURE` 8/7/7/5) plus `deer-flow.md` 28,
`skillopt.md` 25, `codex-orchestration.md` 24. Everything else is Claude Code /
agent-orchestration research.

The cause is by design and documented in each manifest, e.g. `sources/uv.manifest`:

> `kind = code: AST extraction only, no LLM, no cost. NOTE this extracts the SOURCE
> and skips every .md by design — the tool's DOCS are a separate kind = docs mirror
> (#123), not this manifest.`

So `--prose god-nodes` de-drowns perfectly and still returns nothing about `uv` vs
`mise`, because **that material is not in the corpus in either tier.** This is
`toolchain-docs-absent-from-corpus` (#81) reaching its consequence: the tools are
ingested as *implementations*, never as *tools*.

### 3B.4 Per-source `god-nodes` on the aggregate: better, but still symbols

**MEASURED** — top-degree nodes restricted to each toolchain source's ID prefix:

| source | top nodes (degree) |
|---|---|
| `uv` | `Result` 4692 · `PackageName` 781 · `PathBuf` 453 · `pip_compile.rs` 395 |
| `mise` | **`ToolVersion` 439** · `cask.rs` 297 · `Result` 211 · `PlatformTarget` 168 |
| `rumdl` | **`LintContext` 496** · `md013_line_length/tests.rs` 383 · `Rule` 286 |
| `pkl` | `VmClass` 471 · `ExpressionNode` 407 · `VmTyped` 375 |
| `hk` | `file.bash` 58 · **`HookOptions` 41** · `HookContext` 39 · `Config` 37 |
| `gitleaks` | `Rule` 239 · `main()` 225 · `Validate()` 222 |
| `graphify` | `extract()` 388 · `extract.py` 382 · `test_languages.py` 364 |
| `typos` | `main.json` 500 · `typos/src/tokens.rs` 81 |
| `taplo` | `js/.yarn/releases/yarn-4.0.2.cjs` **2661** (vendored build artefact) |
| `ty` | `find_ty_bin()` 10 — 36 nodes total, effectively a stub |
| **`ruff`** | **nothing — 0 nodes, see 3B.5** |

Partitioning **does** de-drown: `ToolVersion`, `LintContext`, `HookOptions` are each
their tool's real core abstraction and were invisible under `Result`. So this answers
*"what is mise's central abstraction"* well.

It does **not** answer *"how does mise relate to uv"* — these are implementation
symbols, and §3.3 already proved no edge connects them. Two side-effects worth
noting: `taplo`'s hub is a vendored yarn bundle (a `.graphifyignore` candidate), and
`typos`' is `main.json` (a data blob).

**No `--repo`/`--source` filter exists** on `god-nodes` (`cli.py:1032-1086`: only
`--top`, `--graph`, `--json`), so per-source ranking means splitting on the ID prefix
ourselves — a `kb_setup` helper, not a graphify flag.

### 3B.5 NEW DEFECT: `sources/ruff` is pinned, cloned, and contributes ZERO nodes

**MEASURED, control-armed:**

| probe | result |
|---|---|
| `grep -c '::ruff::' graphify-out/graph.json` | **0** |
| `grep -c '::uv::' graphify-out/graph.json` (CONTROL) | **127,902** |
| `du -sh sources/ruff` | **399M** (clone present, *larger* than uv's 289M) |

`sources/ruff.manifest` is byte-for-byte the same shape as `sources/uv.manifest` —
same owner (`astral-sh`), `kind = code`, `added = 2026-08-02`, no `scope` — and uv
produced 20,524 nodes. So the probe discriminates, the clone is on disk, and the
source is simply absent from the graph.

**Why nobody noticed:** `graph.py`'s `_extract_code` deliberately swallows a non-zero
status — its sibling `_extract_self` documents the contrast: *"Emptiness is NOT
tolerated here, unlike `_extract_code`. That function swallows a non-zero status
because a pinned upstream source may legitimately be prose-only."* A tolerance meant
for prose-only sources silently absorbed a total failure on a `kind = code` one. It
is also the exact failure class 0.9.33 fixes upstream (#2444/#2445 — a crashed worker
substituted an empty result with rc=0), which makes the bump in §5 step 1 more urgent,
not less.

**This is a corpus-integrity defect independent of everything else in this report.**
`ruff` is a tool this repo runs on every lint. Recommended gate: `kb-build` should
assert a **non-zero node count per `kind = code` manifest** and fail loudly, which is
one comparison and would have caught this on the day it happened.

---

## 4. Version delta 0.9.32 → 0.9.33

Source: `gh api repos/Graphify-Labs/graphify/releases`, published **2026-08-05T00:42:01Z**;
`gh api …/compare/v0.9.32...v0.9.33` → **11 files changed**: `CHANGELOG.md`,
`graphify/cli.py` (+89/-0), `graphify/extract.py` (+210/-30), `graphify/install.py`
(+3/-0), `graphify/watch.py` (+89/-1), `pyproject.toml`, and 5 test files.

### 4.1 What changes for us

| Change | Issue | Impact here |
|---|---|---|
| **`graphify update` no longer drops member-call / `indirect_call` edges from a changed file into an unchanged target.** `_callable`/`_callable_class` markers now persist to `graph.json` like `_origin` | #2437, #2438 | **Directly hits `mise run kb-update -- <name>`** (`graph.py:845`). On 0.9.32 every incremental refresh of a source **silently loses cross-file call edges** into unchanged files. This is a live data-loss bug in a task we run routinely |
| **`extract` no longer silently substitutes an empty result when a worker crashes.** `BrokenProcessPool` → sequential fallback; a failed file is retried sequentially; a whole-pass AST failure on a fresh build now **exits non-zero** instead of writing a zero-node graph. New **`--allow-partial`** opts back in | #2444, #2445 | **Directly hits `mise run kb-build`** (`graph.py:88`, `graph.py:212-227`). On 0.9.32 a crashed worker produced a quieter, smaller graph with rc=0 — the exact "green gate, wrong artifact" failure `verify-before-advancing.md` is about. `graph.py`'s `_extract_self` already uses `check=True`, so it would newly *fail loudly* rather than under-produce |
| C# `partial class` merge now keys on assembly | #2411 | No C# in this corpus — no effect |
| `install` prints a one-time hosted-platform pointer | — | Cosmetic; irrelevant (we never run bare `install`) |
| `watch.py` +89/-1 | #2406 twin | We do not use `watch` (`do-not.md` #2 narrowed) — no effect |

### 4.2 One caveat nobody will notice until it bites

The new incremental-resolution context calls
`check_graph_file_size_cap(existing_graph_path)` and wraps the whole block in
`except Exception: _ctx_nodes, _ctx_edges = [], []` (patch to `cli.py:3091+`). So on
an **oversized graph the #2437/#2438 fix silently fails open to the old, lossy
behaviour** — no warning, no rc change. With `GRAPHIFY_MAX_GRAPH_BYTES = "1GB"`
(`mise.toml:137`) and a 552 MB graph we are fine today; at ~1 GiB the fix disappears
without saying so. Worth a line in `docs/graphify-reference.md`.

### 4.3 Nothing in §§1-3 changes

No file under `graphify/skills/` appears in the 11-file diff. No change to
`merge-graphs`, `build.prefix_graph_for_global`, `distinct_repo_tags`, `analyze.py`,
`cluster.py`, `dedup.py`, `symbol_resolution.py` or `security.py`. **Every §3 verdict
holds unchanged at 0.9.33.**

### 4.4 What regenerating `.claude/skills/graphify` at 0.9.33 would change: nothing

`gh api …/git/trees/v0.9.32` and `…/v0.9.33`, filtered to `graphify/skills/claude`:
**every sha identical**, including the directory sha `b9a67ca7ad11e61d6fa570aa170dc8703e04fe0b`
and `references/extraction-spec.md` = `388df7674f2d25e83f87041864bbe7635aa15e75`.
`graphify/skill.md` is `d98865cc…` at both tags.

**Control arm:** the same query shape returns *different* shas for sibling files
(`skill-aider.md` `4f03ccba…` vs `skill.md` `d98865cc…`), and the compare endpoint
lists 11 genuinely changed files — so the probe discriminates between "unchanged" and
"never asked".

**Conclusion: a 0.9.33 skill regeneration changes only the `.graphify_version` stamp
(`0.9.32` → `0.9.33`).** The eight `references/*.md` and `SKILL.md` are byte-identical
upstream. (Our on-disk copies differ from the package only by blank-line insertions —
`diff` shows pure `>` empty-line adds — i.e. this repo's markdown formatter, not
content drift.)

---

## 5. Recommended plan — 10 operations in dependency order

Each is a `kb-*` task per `mise-tasks-only.md` and `zero-bash-logic.md`.

**0. FIX `ruff` FIRST — it is 0 nodes in the graph (§3B.5).** Before any of this,
re-run its extraction and find out why it produced nothing, then add the gate:
`kb-build` asserts a non-zero node count per `kind = code` manifest and fails loudly.
Buys: a tool this repo runs on every lint stops being invisible to the corpus, and
the class of failure stops being silent. Nothing else on this list is worth doing on
a corpus that is quietly missing a pinned source.
*Gate:* `grep -c '::ruff::' graphify-out/graph.json` > 0, against the `::uv::` control.

**1. Bump to 0.9.33 first.** Two real data-loss fixes in tasks we run
(`kb-update`, `kb-build`). Path: `mise run kb-currency -- --tool graphify`, then the
pin. Buys: `kb-update` stops silently dropping cross-file call edges; `kb-build`
stops turning a crashed worker into a quiet, smaller graph.
*Gate:* `mise run kb-build` + `mise run kb-currency-check` must show the stamp move.

**2. `mise run kb-affected -- <symbol> [--depth N]`.** ~15 lines in
`kb_setup/graphify_ops.py` + a task. Wraps `graphify affected` (`GX/affected.py`).
Buys: the reverse-dependency question about our own code — the one `refresh_self`
exists to enable and that nothing currently asks.
*Gate:* control-arm it — a symbol that exists must return callers; a nonsense symbol
must return the "no unique node match" string, or the probe cannot discriminate.

**3. Fix provenance at the source, not at the reader.** Wherever we need per-source
facts, read `node["id"].split("::")[1]`, not `node["repo"]` (§3.2). Better: stop the
final self-merge from re-prefixing by merging the self sub-graph **inside** the N-ary
call at `graph.py:531` instead of as a second 2-input merge at `graph.py:682`.
Buys: one prefix per node instead of two — smaller file, honest `repo` tags, and it
retires the last remnant of the #120 double-prefix class.
*Caution:* `refresh_self` depends on the current ordering (base snapshot taken before
our code, `graph.py:668-676`). This is a real change, not a tidy-up — spec it.

**4. Toolchain connectivity pilot — `mise run kb-toolchain-graph`.** ONE
`graphify extract <staged-root> --code-only --force --out toolchain-out` over a
symlink/copy root containing just `uv`, `ruff`, `ty`, `mise`, `hk`, `graphify`,
`taplo`, `rumdl`, `typos`. Writes `toolchain-graph.json`, **never** the aggregate.
Then count cross-source edges the same way §3.1 did.
Buys: the direct answer to Ray's question, at zero LLM cost — and a falsifiable one.
*Stop rule:* if cross-source edges ≈ 0, label matching does not bridge these repos;
go to step 5 instead of enlarging the root.

**4b. INGEST THE TOOLS' DOCS — this is the actual blocker (§3B.3).** Every toolchain
manifest is `kind = code` and says so: *"this extracts the SOURCE and skips every .md
by design — the tool's DOCS are a separate `kind = docs` mirror (#123)."* Result:
**zero prose nodes for uv/mise/hk/ruff/ty/taplo/rumdl/typos.** Until the docs are in,
neither `--prose god-nodes` nor any semantic edge can say anything about these tools,
because the material does not exist in the corpus.
Buys: the precondition for steps 5 and 7. This, not graphify, is why Ray cannot see
connections between the tools.

**5. Cross-source BRIDGE chunks — the high-precision path (needs 4b).** Not "read two
docs in one chunk": add a **bridge** kind to `.claude/workflows/kb-extract.js` that is
handed two already-extracted chunks' node inventories and asked for **only**
cross-source edges (`conceptually_related_to`, `shares_data_with`, `contrasts_with`,
`semantically_similar_to` — `GX/llm.py:478`), emitting zero new nodes. Then merge it
with `known_ids` = the union of both chunks' ids.
**The validator already supports this** — `chunks.validate(..., known_ids=...)`
(`chunks.py:140-180`) exists precisely because strict per-chunk resolution once
deleted four real cross-chunk relationships. The one code change is passing
`known_ids` through `merge_chunk`. Full mechanism and the four required changes in
§3.7.
Buys: *"how does `mise` relate to `uv`"* answered from the graph, with EXTRACTED /
INFERRED provenance on every link.
*Cost:* real Claude tokens, but far less than re-extraction — a bridge agent reads
inventories, not sources. Start with ONE pair, validate with
`mise run kb-validate-chunks`, then decide.

**6. Tune clustering: `--resolution` + `--exclude-hubs` in `artifacts.py:31`.**
9,330 communities is over-partitioned. Sweep resolution 0.4/0.6/0.8 and
`--exclude-hubs 0.99`, compare community count and `score_all` cohesion
(`cli.py:1699`).
Buys: `kb-label`'s deterministic hub labels start naming topics instead of fragments,
which is what makes the wiki and `kb-query --prose` legible.

**7. `mise run kb-insights` — surface what we already compute.** Read
`graphify://surprises`, `://questions`, `://audit` from `kb-serve` (or lift
`analyze.surprising_connections` + `suggest_questions` directly). All zero-LLM.
Buys: the ranked non-obvious connections across the research corpus, plus the
EXTRACTED/INFERRED/AMBIGUOUS provenance audit this repo claims and never prints.

**8. `mise run kb-benchmark` + `diagnose multigraph` in the report.**
`GX/cli.py:2524-2540` and `1436-1529`, both already installed, neither reported.
Buys: the token-reduction number this whole repo's thesis rests on, measured by the
tool's own instrument rather than asserted; and a number for how much relational
detail the forced-undirected-simple-Graph merge is costing us.

**Explicitly NOT recommended:** anything using graphify's own LLM backend (labels,
`--mode deep`, `_llm_tiebreak`) — `clean_env()` strips it and `claude-cli` is broken
(#2076); `global add` and `hook install` (`do-not.md` #2); `watch` (`graph.py:259-281`
records why); and waiting for `merge-graphs` to connect sources (§3.3 — it cannot).

---

## 6. BUILD SPEC 1 — `mise run kb-insights`

**Verdict up front: take neither route the lead proposed.** `kb-artifacts` already
computes and persists the entire payload. The cheapest honest route is **read the
sidecar `cluster-only` writes**, with a python lift as the fallback for freshness.

### 6.1 What each resource actually returns (from `serve.py`)

All three handlers are in `read_resource` (`GX/serve.py:1814-1863`). All return
**plain text**, not JSON — the MCP route would need re-parsing.

| Resource | `serve.py` | Backing call | Output shape |
|---|---|---|---|
| `graphify://surprises` | 1826-1837 | `analyze.surprising_connections(G, communities, top_n=10)` | `"Surprising cross-community connections:"` then one line per hit: `  {source} <-> {target} [{relation}]` — **the `score` and `why` fields are computed and then thrown away** |
| `graphify://audit` | 1838-1848 | inline; no helper | 4 lines: `Total edges: N`, then `EXTRACTED/INFERRED/AMBIGUOUS: n (p%)` |
| `graphify://questions` | 1849-1862 | `analyze.suggest_questions(G, communities, community_labels, top_n=10)` | `"Suggested questions:"` then `  - {question}` — **the `type` and `why` fields are discarded** |
| `get_community` (tool) | 1587-1604 | none — reads `communities` dict directly | `"{header} (N nodes):"` then `  {label} [{source_file}]`, truncated to `token_budget` (default 2000) |

The MCP layer is **lossy on two of the three**: `surprising_connections` returns
dicts carrying `score` and `why` (`GX/analyze.py:203-275` builds `reasons`), and
`suggest_questions` returns `{type, question, why}` (`analyze.py:428-436`). The
resource handlers render one field each. **That alone disqualifies the MCP route** —
we would be paying a subprocess to discard the most useful fields.

### 6.2 Sidecar and label dependencies — the answer to "does `kb-build` delete them?"

- **`communities` needs NO sidecar.** `serve._communities_from_graph`
  (`serve.py:68-75`) reconstructs it from the `community` attribute already on each
  node. Same for `cluster-only`'s `previous_node_community` (`cli.py:1688-1692`).
- **`surprises` needs NO labels.** `surprising_connections(G, communities, top_n)` —
  `communities` only.
- **`questions` DOES take labels**, via `_load_community_labels()`
  (`serve.py:1793-1800`): reads `.graphify_labels.json` beside graph.json, falling
  back to `{cid: f"Community {cid}"}`. Degraded, never fatal.
- **Nothing in `kb_setup` deletes either sidecar.** Probed `graph.py`, `artifacts.py`,
  `graphify_ops.py` for `unlink`/`rmtree`/`graphify_labels`/`graphify_analysis`: the
  only `unlink` is `_clear_stamp` on the *currency stamp* (`graph.py:712-726`) and the
  only `rmtree` is a source clone dir (`graph.py:48`). So the premise in the ask —
  "labels that `kb-build` deletes at cleanup" — **does not hold**; the sidecars
  survive a build.
- **One real caveat, upstream:** `cluster-only` refuses to persist
  `.graphify_labels.json` when the labels are placeholder-only
  (`cli.py:1866-1868`, #2073). `artifacts.py:31` passes `--no-label`, so **the
  artifacts path does not write the labels sidecar** — only `mise run kb-label`
  (`graphify_ops.py:170`) does.

### 6.3 THE FINDING: `.graphify_analysis.json` already contains the whole payload

`cli.py:1850-1861`, on the `cluster-only`/`label` path — i.e. every
`mise run kb-artifacts` and every `mise run kb-label`:

```python
analysis = {
    "communities": {str(k): v for k, v in communities.items()},
    "cohesion":    {str(k): v for k, v in cohesion.items()},
    "gods":        gods,
    "surprises":   surprises,      # FULL dicts — score + why intact
    "questions":   questions,      # FULL dicts — type + question + why intact
}
(out / ".graphify_analysis.json").write_text(json.dumps(analysis, indent=2, ...))
```

Written **unconditionally** — no placeholder gate, unlike the labels sidecar. It is
on disk right now at **41,286,244 bytes** (mtime 2026-08-02 15:02); `.graphify_labels.json`
is 178,616 bytes (15:03).

So `surprises`, `questions`, `gods` and `cohesion` need **no MCP server, no python
lift, and no recomputation** — just a JSON read. `://audit` is 4 lines of arithmetic
over `G.edges(data=True)` and is the only thing that must be computed.

**The trap, and it is the reason this needs a task rather than a `cat`:** the sidecar
is written by `kb-artifacts`, while `graph.json` is written by `kb-build`/`kb-merge`/
`kb-label`/`kb-watch`. **Nothing stamps or cross-checks them.** As of this read the
sidecar is 2026-08-02 15:02 and `graph.json` was 2026-08-03 11:15 — the sidecar is
**a day stale against the graph**, and a naive reader would report yesterday's
surprises as today's. `kb-insights` must compare mtimes and say so.

### 6.4 Recommended route

**Route C — read the sidecar, verify freshness, compute audit live.** Reasons:
zero LLM, zero subprocess for 4 of 5 outputs, keeps the `score`/`why`/`type` fields
the MCP layer discards, and it is a pure read so it cannot damage `graphify-out/`.

Implementation sketch — `python/src/kb_setup/insights.py` + a `kb-insights` task:

1. `analysis = json.loads((repo_root/"graphify-out"/".graphify_analysis.json").read_text())`
   → `surprises`, `questions`, `gods`, `cohesion`, `communities`.
2. **Freshness gate.** Compare `.graphify_analysis.json` mtime against `graph.json`.
   Older ⇒ print `STALE — regenerate with mise run kb-artifacts` and keep going with
   the figure labelled stale. Never render a stale sidecar as current
   (`probes-need-a-control-arm.md` — a "could not check" is not a green).
3. **Audit, computed live.** Do NOT go through the MCP server (§6.5). Stream
   `graph.json`'s `links` array and count `confidence` — the same line-state-machine
   §3.1 used. This avoids loading a 552 MB graph into networkx entirely.
4. Optional `--community <cid>` reproducing `get_community` from `analysis["communities"]`
   plus node labels.

Route B (python lift via `graphify_python(repo_root)`) stays the **fallback**, and is
the right answer if the sidecar is stale and you want the numbers *now* without a
`kb-artifacts` run. Its call shapes, verbatim:

```python
from graphify.analyze import surprising_connections, suggest_questions, god_nodes
surprises = surprising_connections(G, communities, top_n=10)          # analyze.py:133
questions = suggest_questions(G, communities, labels, top_n=10)       # analyze.py:428
gods      = god_nodes(G, top_n=10)                                    # analyze.py:109
```

⚠ **Cost warning on `suggest_questions`, and I am flagging it because a sweep would
hit it blind:** it calls `nx.betweenness_centrality(G, k=min(100, n), seed=42)` when
`n > 1000` (`analyze.py:459-461`). That is 100 single-source shortest-path sweeps over
a ~334k-node graph — expensive, and the reason the sidecar route is preferable.
I have **not measured** it here (no builds permitted this session): **UNVERIFIED**
runtime.

### 6.5 What `://audit` would say today — and why the answer is structural

**It would report `AMBIGUOUS: 0 (0%)`, and it always will, by our own construction.**

- `kb_setup/chunks.py:24`: `_CONFIDENCE = ("EXTRACTED", "INFERRED")`, enforced at
  `chunks.py:102-103` — **our validator REJECTS an AMBIGUOUS edge**, and
  `merge_chunk` refuses the whole chunk on any issue (`graphify_ops.py:70-79`).
- `.claude/workflows/kb-extract.js` `commonPrompt` offers agents only
  `"EXTRACTED"` / `"INFERRED"`. An agent is never told AMBIGUOUS exists.
- AST extraction never emits it either. **Control-armed:** `extract.py` appears in
  the `INFERRED` file list and **not** in the `AMBIGUOUS` one, so the probe
  discriminates; `AMBIGUOUS` occurs only in consumers (`analyze`, `report`, `serve`,
  `wiki`, `export`, `callflow_html`, `validate`, `detect`, `watch`) and in the
  extraction *prompt schema* `llm.py:478` — the LLM path we do not use.

So the lead's measured 0-in-816,538 is not a corpus accident and not a graphify
property: **we designed AMBIGUOUS out.** Two consequences to decide on before
building:

1. **`suggest_questions` category 1 is dead code for us.** Its first generator is
   "every AMBIGUOUS edge → an unresolved-relationship question" (`analyze.py:446-457`).
   With 0 AMBIGUOUS it contributes nothing, permanently. Expect questions from the
   bridge-node, god-node and isolate generators only.
2. **`://audit` as a differentiator is currently a two-value split**, not three. If
   the three-tier provenance claim matters, the fix is to admit AMBIGUOUS into
   `_CONFIDENCE` and the extraction prompt — a deliberate product decision, not a bug
   fix. Worth Ray's call rather than mine.

⚠ **One more caveat that will make the numbers disagree with the lead's.**
`serve._load_graph` forces `data = {**data, "directed": True}` (`serve.py:37`), and
our file is `multigraph: false` — so the MCP server builds a **DiGraph**, collapsing
parallel same-direction edges. `cluster-only` builds an **undirected Graph**
(`cli.py:1680-1681`, our file says `"directed": false`), collapsing harder still.
**`Total edges` from `://audit` will therefore be LOWER than 816,538, and the
percentages are over survivors.** Streaming the file (step 3 above) is the only route
that reports the real distribution — another reason not to use MCP here.

---

## 7. BUILD SPEC 2 — the clustering flags, before you sweep

### 7.1 Real semantics, from `GX/cluster.py`

**`--resolution R`** → `cluster(G, resolution=R)` (`cluster.py:134-138`) → `_partition`
(`cluster.py:22-77`) → Leiden's `resolution` kwarg if graspologic is installed
(`cluster.py:50-51`), else networkx Louvain's (`cluster.py:70`).

- Type `float`, parsed by bare `float()` at `cli.py:1616-1619` — **no range
  validation**, a bad value raises `ValueError` and traces out.
- Direction, stated twice in graphify's own docstrings (`cluster.py:28-29`,
  `cluster.py:148-149`): **`> 1.0` → more, smaller communities; `< 1.0` → fewer,
  larger.** So **lower coarsens** — sweep 0.4/0.6/0.8, which matches the plan.
- ⚠ **Leiden may ignore it.** `_partition` passes `resolution` only
  `if "resolution" in lsig` (`cluster.py:50`), inspected from the installed
  graspologic's signature. And `CLAUDE.md` records that
  `graspologic`/`leidenalg`/`igraph` **auto-skip by PEP 508 marker on Python 3.14**,
  so this repo is on the **Louvain fallback** — which does take `resolution`
  (`cluster.py:70`). Net: it applies here, but via Louvain, not Leiden. **Arm this
  before trusting a flat sweep** — a no-op arm and a real-but-small effect look
  identical.

**`--exclude-hubs P`** → `exclude_hubs_percentile` (`cluster.py:162-169`):

```python
degrees = sorted(d for _, d in G.degree())
idx = max(0, int(len(degrees) * exclude_hubs_percentile / 100) - 1)
threshold = degrees[idx]
hub_nodes = {n for n, d in G.degree() if d > threshold}
```

- P is a **percentile 0-100 of the degree distribution**, and exclusion is
  **strictly greater than** the threshold degree.
- **Answering the lead's question directly: the nodes are NOT dropped.** They are
  held out of partitioning only, then **reattached by majority-vote neighbour
  community** (`cluster.py:191-207`), with a fresh single-node community as the
  fallback when no neighbour has one. Every node still lands in a community and
  still appears in `graph.json`.
- ⚠ **Two failure modes worth naming.** (a) In a heavy-tailed degree distribution
  with mass at low degrees, `d > threshold` can exclude far fewer than `(100-P)%` —
  ties at the threshold all survive. (b) At a *low* P the threshold is a small degree,
  so a large fraction is excluded and then grouped by **majority vote, not Leiden** —
  a materially different algorithm. Keep P high (99, 99.5) unless you intend that.

### 7.2 The thing that will make a blind sweep look like a failure

**`--resolution` cannot reach the splitters, and the splitters are what produced
9,330 communities.** Three post-partition stages run *after* `_partition` and are
hardcoded — no flag, no env var:

| Stage | `cluster.py` | Constant |
|---|---|---|
| Split any community > 25% of nodes | 209-216 | `_MAX_COMMUNITY_FRACTION = 0.25`, `_MIN_SPLIT_SIZE = 10` |
| **Re-split any community ≥ 50 nodes with cohesion < 0.05** | 219-227 | `_COHESION_SPLIT_THRESHOLD = 0.05`, `_COHESION_SPLIT_MIN_SIZE = 50` |
| **Every isolate becomes its own single-node community** | 185-189 | — |

The cohesion splitter is the binding constraint at our scale.
`cohesion_score = actual_edges / (n·(n−1)/2)` (`cluster.py:256-265`). At n=50 the
denominator is 1,225, so clearing 0.05 needs **61 intra-community edges among 50
nodes**. A sparse AST community essentially never does. **So almost every community
that resolution would have made larger gets split straight back down.**

**Prediction, and I am labelling it a prediction:** a `--resolution` sweep will move
the count far less than expected, and the residue will be dominated by isolates and
cohesion-splits. **UNVERIFIED** — I ran no clustering (build in flight). Test it
cheaply first: count single-node communities in the existing
`.graphify_analysis.json["communities"]`. If that share is large, resolution was never
the lever and the honest fix is upstream constants or a filtered input graph.

### 7.3 Interactions the lead asked about

**Shrink guard: does NOT apply.** `_check_shrink` is defined at `watch.py:786` and
called only from `watch.py:1255` and `watch.py:1449`. **Control-armed:** the grep
returned real callers, so it discriminates — and none is on the `cluster-only`/`label`
path, which writes via a bare `to_json(G, communities, str(out/"graph.json"), community_labels=labels)`
at `cli.py:1868`, **unguarded**.

⚠ **Therefore `cluster-only` OVERWRITES `graphify-out/graph.json` in place with no
shrink guard, on every sweep arm.** Combined with `--no-viz` deleting `graph.html`
(`cli.py:1877-1879`) and the unconditional `.graphify_analysis.json` rewrite
(`cli.py:1855`), a sweep is **destructive to the aggregate**. There is a partial
mitigation — `export.backup_if_protected(out)` at `cli.py:1849-1850` — but I have
**not read what it protects**: **UNVERIFIED**. Sweep against a **copy**, via
`--graph <copy>` (`cli.py:1605-1606`), never the live aggregate.

**`remap_communities_to_previous`: it will corrupt cross-arm comparison.**
`cluster-only` calls it whenever the graph carries prior `community` values
(`cli.py:1687-1694`), and it greedily rewrites new cids onto old ones by overlap,
assigning fresh ids to the unmatched (`cluster.py:272-315`). So **community IDs are
not comparable between sweep arms**, and `.graphify_labels.json` labels follow the
remap onto possibly-different memberships. Compare arms on **count, size
distribution, and `score_all` cohesion** (`cluster.py:268-269`) — never on cid
identity. `community_member_sigs` (`cluster.py:110+`) is the honest identity check if
you need one.

### 7.4 Suggested sweep shape

1. Copy `graphify-out/graph.json` to a scratch path. Never sweep the live aggregate.
2. Baseline: from the existing `.graphify_analysis.json`, record community count,
   the **single-node community share**, and the cohesion distribution. If single-node
   dominates, stop — resolution is not the lever (§7.2).
3. Arms: resolution ∈ {1.0 control, 0.8, 0.6, 0.4}, each `--graph <copy> --no-label
   --no-viz`, then `--exclude-hubs 99` on the best.
4. **Control arm for the flag itself:** confirm 1.0 and 0.4 differ at all. If they do
   not, `resolution` is not reaching the partitioner and every other number is noise.
5. Compare on count / size distribution / cohesion. Never on cid.

---

## 8. BUILD SPEC 3 — the converged extraction prompt (#168)

Built on `.claude/skills/graphify/references/extraction-spec.md` (byte-identical to
upstream v0.9.32 **and** v0.9.33 — sha `388df767…`, §4.4) with DEEP_MODE on, keeping
all five local additions. Where the spec and a local rule conflict, the conflict is
named and resolved below rather than silently.

### 8.1 Conflicts resolved before the draft

**(a) Node ID format — LOCAL RULE WINS, and this must not be "converged" away.**
The spec (`extraction-spec.md:61`) mandates `{stem}_{entity}` where stem is the full
repo-relative path, *"This must match the ID the AST extractor generates — using just
the filename … will create orphan ghost-duplicate nodes."* That rationale is
**AST-coalescence**, and it does not apply to us: our chunks are pure prose from
`kind = docs` / media / URL sources with **no AST counterpart to coalesce with**.
Meanwhile the `<key>_` prefix is load-bearing here — `chunks.assemble`'s docstring
says *"extraction prefixes ids per source, so a collision is a bug"* and its collision
check (`chunks.py:250-252`) is meaningless without it.
→ **Keep `<key>_<slug>`. Adopt the spec's charset rule and its no-suffix rule**, both
of which are compatible and both of which we currently lack.

**(b) `source_file` — LOCAL RULE WINS.** The spec (`:66`) demands the verbatim
absolute FILE_LIST path. Ours uses `basename(s.path)`, and all 18 committed chunks do
too; `_merge_docs.py` takes a `src_root` argument for relativization
(`_merge_docs.py:6,20`), which is a different merge path from the one the spec's rule
protects. Switching now would make every new chunk inconsistent with every committed
one. → keep basename. *(The exact downstream consequence inside `build_merge` is
**UNVERIFIED** — I did not read it this session.)*

**(c) Relation vocabulary — UNION.** The spec's list is code-oriented
(`calls|implements|references|cites|conceptually_related_to|shares_data_with|semantically_similar_to|rationale_for`);
ours is doc-oriented and the direction table depends on it. Nothing validates
relation names — `_EDGE_REQUIRED` (`chunks.py:23`) requires the *key*, never a
vocabulary — so the union is free. Keep ours, add the spec's cross-cutting ones.

**(d) Hyperedges — DO NOT EMIT YET. Two independent defects, one of them new.**

1. **#166 / §3.6** — `prefix_graph_for_global` (`GX/build.py:1590-1606`) relabels
   nodes and edge `_src`/`_tgt` but never `G.graph["hyperedges"]`, so members are
   orphaned at merge. All 5 hyperedges in the live corpus dangle.
2. **NEW, found while answering Q1** — `chunks.assemble` **hardcodes
   `"hyperedges": []`** (`chunks.py:266`) and never reads `chunk.get("hyperedges")`
   at all; its loop concatenates `nodes` and `edges` only (`chunks.py:247-254`). **So
   `mise run kb-assemble` silently discards every hyperedge an agent emits.**

   Control arm: `_hyperedge_issues` (`chunks.py:107-137`) *does* validate them, and
   its docstring documents a real case (`graphify_pipeline_stages`, 7 members, none
   resolving) — so hyperedges are validated on the way in and dropped on the way out.
   That also explains the corpus: the only 5 that exist came from chunks committed
   directly, never through `assemble`.

→ **The prompt below emits `"hyperedges": []` and says so.** Turning the clause on
before both are fixed spends tokens on output that is discarded (assemble path) or
orphaned (direct path). The exact spec clause to paste in afterwards is kept in
§8.4 so nothing is lost.

### 8.2 The draft — ready-to-paste replacement for `commonPrompt`

Drop-in for `.claude/workflows/kb-extract.js`. Same signature, same closure variables
(`scratchDir`, `capturedAt`), same `SCHEMA`/StructuredOutput contract, so `promptFor`,
`inventoryPrompt` and `KIND_NOTE` are untouched.

```js
function commonPrompt(s) {
  const file = basename(s.path)
  return `You are a graphify extraction subagent for a knowledge-base KB. Read the ENTIRE file at:
  ${s.path}
(use the Read tool; read ALL of it — it may be long).${s.note ? `\nContext: ${s.note}` : ''}

Produce a graphify DOC-EXTRACTION CHUNK: a JSON object
  { "nodes": [...], "edges": [...], "hyperedges": [], "input_tokens": 0, "output_tokens": 0 }

CONFIDENCE TIERS — three, not two. Do NOT omit an uncertain relationship:
  EXTRACTED  relationship explicit in the source (stated verbatim, quoted, cited).
  INFERRED   reasonable inference you made across concepts.
  AMBIGUOUS  uncertain — FLAG IT FOR REVIEW, DO NOT OMIT IT. An edge you are
             unsure about is more valuable tagged AMBIGUOUS than dropped: the
             corpus can filter on confidence, but it cannot recover what you
             never emitted.

confidence_score is REQUIRED on every edge — never omit it, never use 0.5 as a default:
  EXTRACTED edges: confidence_score = 1.0 always
  INFERRED edges: pick exactly ONE value from this set — never 0.5:
    0.95  direct structural evidence (shared data structure, named cross-file reference).
    0.85  strong inference (clear functional alignment, no direct symbol link).
    0.75  reasonable inference (shared problem domain + similar shape, requires interpretation).
    0.65  weak inference (thematically related, no shape evidence).
    0.55  speculative but plausible (surface-level co-occurrence only).
  Models follow discrete rubrics better than continuous ranges; the bimodal
  distribution observed in production (>50% at 0.5, >40% at 0.85+) shows the
  range guidance is being collapsed to a binary. If no value above fits, mark
  the edge AMBIGUOUS rather than picking 0.4 or below.
  AMBIGUOUS edges: 0.1-0.3

DEEP MODE IS ON: be aggressive with INFERRED edges — indirect deps, shared
assumptions, latent couplings. Mark uncertain ones AMBIGUOUS instead of omitting.

NODE object (exact keys):
  id          : globally-unique slug, MUST start with "${s.key}_" then a short concept
                slug. Charset is strictly lowercase [a-z0-9_] — no dots, no slashes,
                no hyphens, no uppercase. Never reuse an id.
                CRITICAL: never append a chunk number, sequence number, or any suffix
                (no _c1, _c2, _chunk2). An id must be deterministic from the label
                alone — the same entity must always produce the same id.
  label       : short human name of the concept/entity.
  _origin     : "semantic"   <- EXACTLY this literal on EVERY node. Not optional.
  file_type   : "concept" for a named entity or concept; "rationale" for a
                concept-like node (an idea, principle, mechanism, or design pattern).
                Those are the only two values valid for this corpus.
  source_file : "${file}"
  source_url  : "${s.url}"
  captured_at : "${capturedAt}"
  author      : the author name if the doc states one, else null
  contributor : null
  rationale   : 1-3 sentences of SUBSTANCE — the actual claim/definition/decision,
                self-contained and faithful to the source.

WHY (design intent, trade-offs, why a decision was made) goes in the \`rationale\`
ATTRIBUTE of the relevant node. Do NOT create a separate rationale node or a
fragment node for it. Only create a node for something that is itself a named
entity or concept.

EDGE object (exact keys):
  source, target   : node ids that BOTH exist in this chunk's nodes.
  relation         : snake_case verb. Prefer one of:
                     enables, requires, part_of, contrasts_with, mitigates, defines,
                     verifies, routes_to, references, cites, conceptually_related_to,
                     shares_data_with, semantically_similar_to, rationale_for
  confidence       : "EXTRACTED" | "INFERRED" | "AMBIGUOUS" (see the tiers above).
  confidence_score : per the rubric above. Never 0.5.
  source_file      : "${file}"
  weight           : 1

SEMANTIC SIMILARITY: if two concepts in this chunk solve the same problem or
represent the same idea without any structural link (no import, no call, no
citation), add a \`semantically_similar_to\` edge marked INFERRED with a
confidence_score reflecting how similar they are (0.6-0.95). Examples:
- Two mechanisms that both validate the same input but are never connected
- A concept in one section and a concept in another that describe the same algorithm
- Two failure modes handled differently
Only add these when the similarity is genuinely non-obvious and cross-cutting.
Do not add them for trivially similar things.

EDGE DIRECTION — read every edge aloud as the sentence "<source> <relation> <target>".
If that sentence is FALSE, you have the edge backwards. Emit it in the direction
that makes the sentence true. The rules that decide it:
  part_of                  : MEMBER -> CONTAINER. "retry_policy part_of http_client",
                             NEVER "http_client part_of retry_policy". This is the one
                             most often inverted — a previous run emitted all 22 of its
                             part_of edges backwards — so check each one individually.
  requires / depends_on    : DEPENDENT -> DEPENDENCY. "cache requires redis".
  enables / defines /
  mitigates / verifies /
  routes_to / rationale_for: the ACTOR -> the thing it acts on. "gate verifies receipt".
  references / cites       : CITING -> CITED. "spec cites rfc9110".
  contrasts_with /
  semantically_similar_to /
  conceptually_related_to /
  shares_data_with         : symmetric in meaning — emit exactly ONE edge, not both.
Do NOT flip a whole relation type at the end as a batch. Direction is decided per
edge from the source text; a blanket flip breaks the ones that were already right.

HYPEREDGES: emit \`"hyperedges": []\` — an empty array — for now. Do not populate it.
Two open defects discard or orphan them (kb-assemble hardcodes an empty array; the
merge never relabels hyperedge members), so any you emit would be silently lost.

WHY \`_origin: "semantic"\` IS MANDATORY: graphify 0.9.32+ decides a node's tier from
\`_origin\` when present, and otherwise GUESSES from shape — a \`source_location\` that
looks like \`L<line>\` is read as AST. Extraction agents have emitted \`source_location\`
values like "L5" unprompted (this prompt never asked for the field), and that guess
silently deleted **629 nodes** from the prose graph in one build, with no error. The
literal marker makes the guess unreachable. \`mise run kb-validate-chunks\` REJECTS a
chunk whose nodes lack it.

Rules: only connect nodes that exist in THIS chunk; prefer faithful EXTRACTED edges;
mark reasoned links INFERRED honestly with a real score from the rubric; flag genuine
uncertainty AMBIGUOUS rather than dropping it; never invent facts not in the source.

After building the chunk, WRITE it (Write tool) to this exact absolute path (no
relative paths — Write resolves relative paths against an undefined cwd and the file
will be silently lost):
  ${scratchDir}/${s.key}.json
Then your FINAL output is ONLY the StructuredOutput {key:"${s.key}", wrote:true, node_count, edge_count, notes (any quality caveat, e.g. paywalled/partial/truncated)}.`
}
```

**What changed vs. today, itemised:** three-tier confidence + the "do not omit"
wording (spec `:15`); the discrete `confidence_score` rubric verbatim (spec `:47-59`)
replacing `confidence_score : 1 for EXTRACTED, 0.5 for INFERRED` at
`kb-extract.js:130`; DEEP_MODE verbatim (spec `:29-30`); the semantic-similarity
clause with its restraint sentence (spec `:32-36`); `file_type` widened to
`concept|rationale` with the rationale-as-attribute rule (spec `:19`); the id charset
+ no-suffix rules (spec `:61`); relation vocabulary unioned, with the direction table
extended to cover the new symmetric and citing relations; hyperedges explicitly
suppressed with the reason.

**What is preserved verbatim:** the `_origin` block and its 629-node reason; the
`<key>_` id prefix; the whole edge-direction block including the 22-backwards-edges
sentence; the Write-to-`scratchDir` + StructuredOutput contract; `source_url` /
`captured_at` / `author` / `contributor`. The `capturedAt` no-default guard (#93) is
JS-side at `kb-extract.js:79-87` and is untouched by this replacement.

### 8.3 Q1 — what exactly changes in `chunks.py`

**Required (1 line):**

```python
_CONFIDENCE = ("EXTRACTED", "INFERRED", "AMBIGUOUS")   # chunks.py:24
```

The check at `chunks.py:102-103` needs no edit — it reads the tuple.

**Nothing else is required.** But four things assume two tiers or assume less than
the new prompt promises, and you asked for all of them:

| # | Site | Finding |
|---|---|---|
| 1 | `_EDGE_REQUIRED` `chunks.py:23` | `confidence_score` is required to be **PRESENT** and its **VALUE IS NEVER VALIDATED** — no range, no type, no rubric check anywhere in the module. So the 0.55-0.95 rubric arrives completely unenforced, and an agent regressing to 0.5 is invisible. **This is new work, not a change** — and it is the one that matters, because filterability is the whole reason the extra AMBIGUOUS/INFERRED edges are safe. Suggested: EXTRACTED ⇒ `== 1.0`; INFERRED ⇒ in `{0.95,0.85,0.75,0.65,0.55}`; AMBIGUOUS ⇒ `0.1 <= x <= 0.3`. |
| 2 | `_hyperedge_issues` `chunks.py:107-137` | validates member resolution only — **never checks `confidence`**. The spec's hyperedge schema (`:64`) allows only `EXTRACTED\|INFERRED`, so widening `_CONFIDENCE` would silently start permitting an AMBIGUOUS hyperedge that graphify's own schema forbids. Moot while hyperedges are suppressed; do not forget it when they are enabled. |
| 3 | `_NODE_REQUIRED` `chunks.py:22` | requires `file_type` to be **present**, never checks its value. The spec (`:19`) says it *"MUST be one of exactly these six values … Any other value is invalid and will be rejected."* Nothing here rejects it. If the prompt now offers two values, a check is cheap insurance. |
| 4 | `assemble` `chunks.py:266` | hardcodes `"hyperedges": []` — see §8.1(d). Independent of this change; file it separately. |

Neither `validate`, `_node_issues`, nor `_edge_issues` branches on the tier anywhere
else — the only tier-aware line in the module is `:102`.

*(Aside, harmless: `chunks.py:190` uses PEP 758 unparenthesized `except OSError,
json.JSONDecodeError:`. Verified it parses — Python 3.14.0, control-armed against a
py2 `print` statement which correctly raises SyntaxError. It is 3.14-only syntax; the
sibling handler at `:213` uses the parenthesized form.)*

### 8.4 Q2 — batching, and how the id prefix survives a multi-file chunk

**Answer: one key PER FILE, never per chunk.** graphify's 20-25-files-per-agent
grouping is about token efficiency, not identity, and nothing in the id rule requires
one prefix per agent.

Concretely, the change to `kb-extract.js` is in the fan-out, not in the id scheme:
each `agent()` receives a **FILE_LIST of `{key, path, url}` triples** instead of a
single `s`, and the prompt's id rule becomes *"MUST start with the `key` of the file
this node came from"*, with `source_file`/`source_url` taken per file rather than from
one closure variable. Ids stay `<file-key>_<slug>`, so:

- **global uniqueness** holds exactly as today — the key namespace is per-file and
  already unique across the corpus;
- **traceability** holds — the id prefix and `source_file` continue to agree, which a
  per-chunk key would break (you could no longer tell which of 25 files a node came
  from by its id);
- **`assemble`'s collision check** (`chunks.py:250-252`) keeps working, and keeps
  meaning what its docstring says.

⚠ **The hard constraint on batching, and it is easy to miss:** `assemble` calls
`validate(chunk, label=p.name)` at `chunks.py:246` **without `known_ids`** — the
strict per-chunk reading. `validate_files` passes `known_ids` (`chunks.py:208`), but
`assemble` does not. So:

- edges **within** a multi-file chunk are fine (all endpoints are in that chunk) —
  batching is safe, and in fact batching *increases* the reachable edge set, since an
  agent holding 20 files can relate concepts across all 20;
- edges **between** chunks are still rejected at assemble time. Batching does not
  change that, and it is the same constraint §3.7 identified for bridge chunks.

**Recommended batch key:** group by source, not by directory. graphify says "grouped
by directory" because its corpus is a repo tree; ours is a set of independent
documents. Grouping N files of the SAME source per agent maximises the cross-file
edges the batch can find while keeping every id inside one source's namespace.

### 8.5 Q3 — what breaks for the 18 committed chunks: nothing

**Widening `_CONFIDENCE` is purely additive** — `("EXTRACTED","INFERRED")` →
`(…,"AMBIGUOUS")` only ever accepts more. Every existing edge keeps validating.

Field by field:

| Existing state | Verdict |
|---|---|
| no AMBIGUOUS edges | fine — the tier is permitted, never required. No code path asserts an AMBIGUOUS edge exists |
| flat `confidence_score: 0.5` | fine **today**, because the value is never validated (§8.3 #1). ⚠ **If you add the rubric check, all 18 chunks fail** — 0.5 is exactly the value the rubric forbids. That check must be gated to new chunks, or the old ones re-scored, or it must warn rather than refuse. **This is the one real backward-compatibility hazard in the whole change** |
| `"hyperedges": []` | fine — `_hyperedge_issues` returns `[]` for an empty list, and `None` is also accepted (`chunks.py:121-122`) |
| `file_type: "concept"` only | fine — `concept` stays valid; `rationale` is added, not substituted |
| no `rationale_for` / `semantically_similar_to` relations | fine — relation names are never validated |

**Nothing requires a new field.** `_NODE_REQUIRED` and `_EDGE_REQUIRED` are unchanged
by this spec, and every new instruction in the prompt widens what an agent *may*
produce rather than what a chunk *must* contain. The only forward-incompatible step
is the optional `confidence_score` rubric check, and the mitigation is above.

---

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the installed
  0.9.32 package read as the authority for every behavioural claim; release notes and
  the v0.9.32→v0.9.33 tree/compare diff read via `gh api`.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the
  consuming repo; `python/src/kb_setup/**` and `mise.toml` supplied every USED /
  NOT USED call site, and `graphify-out/graph.json` supplied every MEASURED figure.
