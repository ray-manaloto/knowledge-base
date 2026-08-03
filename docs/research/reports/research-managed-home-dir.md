# Research: one managed directory for a distributable `init` workflow

**Status:** COMPLETE (written incrementally)
**Date:** 2026-08-02
**Question:** How should a tool's `init` workflow provision and lay out ONE managed
directory that holds everything it and its wrapped tools generate?

## Method log

- [x] step 0 — query this repo's own graph (`kb-query --prose --idf`) — **miss, control-armed**
- [x] read `CLAUDE.md` + `.claude/rules/agent-artifact-conventions.md`
- [x] read INSTALLED graphify 0.9.31 source: where does it decide to write?
- [x] comparators: uv, mise, git, chezmoi, ollama, cargo measured on host; pnpm,
  terraform documented-only (absent from this host, marked as such)
- [x] derive proposed layout + migration path

---

## 0. The graph does not know the answer (control-armed)

Two `mise run kb-query -- … --prose --idf` runs (2,817 indexed prose nodes):

| query | top hits |
|---|---|
| "where does the tool write its output directory, project-local vs home directory, XDG base directory, managed state layout" | Claude Code hook *scope* (`~/.claude` vs `.claude/`), Agent SDK session state as JSONL, "Home: the knowledge-base repo" |
| "XDG_DATA_HOME XDG_CACHE_HOME base directory specification" | same cluster; nothing about XDG at all |

**Control arm:** the same command shape returned dense, on-topic, high-IDF hits for
the *hook-scope* question (16.39 / 15.22 top scores, correct sources), so the query
path discriminates. The corpus genuinely has **no material on tool state layout /
XDG / managed home directories** — it is a corpus gap, not a query miss. The single
closest node is `sources/media/framework-plan-ladybug.md` § "Home: the
knowledge-base repo", which is about *this program's* home, not a directory spec.

**Actionable:** the XDG spec, and the layout docs of uv/mise/cargo/pnpm, are absent
from the corpus and are ingestion candidates (`sources/REGISTRY.md`).

---

## 1. graphify 0.9.31 — how it decides where to write (INSTALLED source)

Read at `/Users/rmanaloto/.local/share/mise/installs/pipx-graphifyy/0.9.31/graphifyy/lib/python3.14/site-packages/graphify/` (38,640 LOC of Python).

### 1a. The single source of truth is `paths.py`

```python
GRAPHIFY_OUT = os.environ.get("GRAPHIFY_OUT", "graphify-out")   # paths.py:26
GRAPHIFY_OUT_NAME = os.path.basename(os.path.normpath(GRAPHIFY_OUT))
def out_path(*parts) -> Path: return Path(GRAPHIFY_OUT, *parts)
def default_graph_json() -> str: return str(out_path("graph.json"))
```

Design facts worth stealing wholesale:

1. **One env var, accepting BOTH a relative name and an absolute path.**
   `"graphify-out-feature"` (per-worktree) or `"/shared/graphify-out"` (shared).
   `Path(GRAPHIFY_OUT, *parts)` resolves both without a branch.
2. **Read ONCE at import time**, documented as such — "set `GRAPHIFY_OUT` before
   the process starts". A deliberate simplicity trade, not an oversight.
3. **`GRAPHIFY_OUT_NAME` is a separate export**: the bare directory *name* even when
   the override is absolute. It exists because two different consumers need it —
   the path guards that walk parents looking for the output dir, and the `detect`
   scan-exclude so **a custom output dir is never re-ingested as source**. That
   second one is the trap: a managed dir that lives inside the scanned tree will be
   re-ingested by the next extraction unless the scanner is told its own name.
4. **It was born from a duplication bug (#1423).** The constant was copy-pasted into
   `__main__`, `cache`, and `watch`, while `security` and `callflow_html` hardcoded
   the literal `"graphify-out"` and **silently ignored the override**. Centralising
   was the fix. A managed-dir design that does not have exactly one resolver function
   will grow this bug.
5. **Atomic writes are in the same module** (`_atomic_replace` → `write_text_atomic`,
   `write_json_atomic`): temp file in the SAME directory, `os.replace`, symlink
   resolved first *so a shared-output symlink is written THROUGH, not replaced*, and
   the destination's mode is preserved so an atomic replace never silently tightens
   permissions. Path resolution and durable write are one concern, co-located.

### 1b. `--out` names the PARENT, not the directory

From `graphify --help` (`extract`):

```
--out DIR, --output DIR   output dir (default: <path>); writes <DIR>/graphify-out/
```

So `--out` is a *root* and graphify still appends its own well-known name. That is
the right shape for a managed dir: the user picks WHERE, the tool owns the NAME.
(`--output` is an accepted alias only because dropping it silently was a shipped bug,
#2004.)

Per-command `--out`/`--graph`/`--output`/`--dir`/`--memory-dir` overrides exist on
`clone`, `merge-graphs`, `merge-chunks`, `add`, `tree`, `callflow-html`, `query`,
`path`, `explain`, `affected`, `god-nodes`, `save-result`, `reflect`, `diagnose`.
**Every read command takes `--graph`**, which is exactly what lets this repo pin the
MCP server to an absolute path (tension (d)).

### 1c. graphify has NO XDG support — control-armed

| probe (same command shape, same corpus) | hits |
|---|---|
| `grep -rn "XDG" … --include="*.py"` | **0** |
| control: `grep -rn "GRAPHIFY_OUT" …` | 75 |
| control: `grep -rn "Path.home()\|expanduser" …` | 37 |

The probe discriminates. graphify never reads `XDG_DATA_HOME`, `XDG_CACHE_HOME`,
`XDG_STATE_HOME`, or `XDG_CONFIG_HOME`.

> Note on method: an earlier probe for a `graphify init` subcommand used
> `grep '"init"'` with `grep '"serve"'` as the control — **the control also returned
> no dispatch hits**, so that probe was unarmed and its result was discarded. The
> armed answer comes from `graphify --help`, which enumerates ~60 commands
> (`install`, `clone`, `add`, `extract`, `watch`, `update`, `cluster-only`, `label`,
> `query`, `affected`, `god-nodes`, `save-result`, `reflect`, `check-update`, `tree`,
> `global add|remove|list|path`, `benchmark`, `export`, `hook install`, plus 20
> per-platform `<platform> install|uninstall` pairs) and **contains no `init`**.
> `serve` is also absent from `--help` despite `serve.py` existing — an undocumented
> command, consistent with this repo's recorded `kb-serve` defect.

### 1d. What graphify DOES put in `$HOME` (all hardcoded, none XDG)

| path | written by | nature |
|---|---|---|
| `~/.graphify/global-graph.json` | `global_graph.py:11` | derived, cross-project aggregate |
| `~/.graphify/global-manifest.json` | `global_graph.py:12` | index (repo tag → source path + hash) |
| `~/.graphify/providers.json` | `llm.py:223` | **authored config** (custom LLM providers) |
| `~/.graphify/repos/<owner>/<repo>` | `cli.py:679` (`clone`) | **big binary-ish blobs** — full git clones, `--depth 1`, `git pull` on re-run |
| `~/.cache/graphify-queries.log` | `querylog.py:30` | opt-in query log |
| `~/.cache/graphify-rebuild.log` | `hooks.py:226` | rebuild log |

Two observations that matter for the recommendation:

- **`~/.cache` is spelled literally**, not `XDG_CACHE_HOME`. It happens to equal the
  XDG default on Linux, and is *wrong* on macOS (should be `~/Library/Caches`) — this
  is "accidental XDG", the most common state in the wild.
- **`~/.graphify/` already mixes all four kinds**: authored config (`providers.json`),
  derived data (`global-graph.json`), an index (`global-manifest.json`), and a large
  blob cache (`repos/`). That is precisely the trap this repo hit with
  `graphify-out/memory/`, reproduced one level up. graphify's own `uninstall --purge`
  deletes `graphify-out/` — so **an authored `memory/` inside a tool-purgeable
  directory is a data-loss bug waiting on a flag.**

- **The query log's opt-in reasoning is a design precedent worth copying**: it is OFF
  by default because it writes plaintext questions "under `~/.cache` — **outside any
  repo's `.gitignore`/retention**". Moving state out of the repo moves it out of every
  policy the repo has.

### 1e. The AST cache is namespaced by tool version; the semantic cache is not

`cache.py`: AST entries live under `cache/ast/v{version}/` and entries from other
versions are swept on first use, because "AST cache entries are the output of
graphify's own extractor code, so they are only valid for the version that wrote
them". The semantic (LLM) cache is **deliberately NOT versioned** — invalidating it
per release would re-bill extraction.

**Generalised rule for the managed dir: namespace by producer-version anything a
release can invalidate, and never namespace anything that cost money to produce.**

---

## 2. What this repo has today, measured

Measured 2026-08-02 on this host (`du -sh`):

| path | size | nature | committed? |
|---|---|---|---|
| **repo total** | **8.4 G** | | |
| `graphify-out/` | **4.4 G** | derived, EXCEPT `memory/` | only `memory/` (308 K) |
| ├ `obsidian/` | 600 M | derived view | no |
| ├ dated backups `2026-07-22`…`2026-08-02` (7 dirs) | **~2.4 G** | graphify's own backups | no |
| ├ `graph.json` | 382 M | derived aggregate | no |
| ├ `.base-graph.json` | 359 M | derived | no |
| ├ `graph.graphml` | 334 M | derived view | no |
| ├ `cypher.txt` | 229 M | derived view | no |
| ├ `study-graph.json` | 128 M | derived, scope=study | no |
| ├ `graph.svg` | 40 M | derived view | no |
| ├ `wiki/` | 18 M | derived view | no |
| ├ `cache/` | 16 M | derived cache (AST version-namespaced + semantic) | no |
| ├ `GRAPH_TREE.html` | 9.1 M | derived view | no |
| ├ `graph-prose.json` | 4.0 M | derived-from-derived | no |
| ├ **`memory/`** | **308 K** | **AUTHORED work-memory** | **YES** |
| ├ `reflections/` | small | derived from `memory/` | no |
| `sources/` | **3.6 G** | manifests (authored) + clones (derived) + media (authored) + extractions (authored) | mixed |
| `raw/` | 110 M | fetch landing zone, input, transient | no |
| `.agent/` | 5.2 M | session scratch | no |
| `brain/` | 528 K | authored vault + its own `graphify-out/` | notes yes |

**The headline number in the brief is stale in the safe direction.** `graph.json` is
382 M; the *managed footprint* is **4.4 G under `graphify-out/` alone and 8.4 G for
the repo**. More than half of `graphify-out/` (2.4 G) is graphify's own dated backup
directories, which `.gitignore` already dismisses as "redundant with git history" —
i.e. a retention policy the repo *documents* but does not *enforce*, because nothing
prunes them.

### 2a. The four collisions in one directory

`graphify-out/` today holds all four of the tensions the brief names, interleaved:

| tension | where it bites here |
|---|---|
| (a) derived vs authored | `memory/` (authored, committed) sits inside a tree the tool's own `uninstall --purge` deletes and every doc calls "derived, safely deletable". `.gitignore` needs **19 separate negative rules** to express "ignore this dir except one subdir", each one a place to forget a new output filename. The `.gitignore` itself admits this: the `python/graphify-out/` and `tests/graphify-out/` blocks get a *wholesale* directory rule "unlike the root and brain/ blocks above, and the difference is the point: those two trees each contain an authored `memory/` that must survive". |
| (b) blobs vs text | 3.9 G of blobs (graphs, graphml, cypher, svg, obsidian, backups) share a parent with 308 K of authored JSON notes. Any `du`, backup, sync, or `git clean -xdf` treats them alike. |
| (c) machine-local vs committed | `.currency-stamp.json`, `.base-graph.sha256`, `graph.json.refresh` are explicitly per-clone and reasoned about individually in `.gitignore` comments — each was a separate discovery, one of them (`.currency-stamp.json`) added only after the first run that produced it. |
| (d) multi-project collision | already hit: CLAUDE.md invariant 4, "One MCP server per graph. The server binds to an ABSOLUTE `graph.json` path (`mise run kb-serve`), so multiple graphify projects on one host never collide." The mitigation exists **because the default is CWD-relative**. |

### 2b. `sources/` has the same disease, mirrored

`sources/` mixes four natures under one directory with an ignore-list expressing the
policy:

```gitignore
sources/*/            # clones: derived, re-fetched from a pinned SHA
!sources/extractions/ # authored, expensive (real Claude tokens)
!sources/media/       # authored, non-refetchable
sources/media/*.m4a   # …except audio, which is derived-ish
sources/media/*.pdf.txt # …and pdf text, regenerable via pypdf
```

Four `!`-toggles to say "these are different kinds of thing". **A layout that needs a
negation to express its own policy is the wrong layout** — the natures should be
different directories.

### 2c. `.agent/` is a third, parallel convention

`.claude/rules/agent-artifact-conventions.md` establishes `.agent/` (gitignored) vs
"durable artifacts are TRACKED and live in the repo proper". It was renamed from
`.omc/` in 2026-07-25 after a control-armed check that Claude Code neither claims nor
reserves `.agent/`. Its rules 4 and 5 are the ones a managed-dir design must preserve:

- rule 4: "a finding that should outlive the session goes in the GRAPH
  (`mise run kb-remember`) … not in `.agent/`";
- rule 5: skills live in `.claude/skills/**` — Claude Code's loader scans nowhere else.

**That second one is a hard constraint on any consolidation**: `.claude/**` cannot
move into a managed dir, because the loader is not configurable. Any `init` that
tries to unify *everything* will break skill loading. The managed dir can hold what
the *tool* generates; it cannot hold what the *harness* loads.

---

## 3. Comparators — measured on this host unless marked

All sizes `du -sh`, 2026-08-02, this Mac. XDG env on this host is fully set
(`XDG_CACHE_HOME=~/.cache`, `XDG_DATA_HOME=~/.local/share`,
`XDG_STATE_HOME=~/.local/state`, `XDG_CONFIG_HOME=~/.config`), so any tool
*ignoring* XDG here is doing so by choice, not by absence.

| tool | root(s) | split policy | relocation knob | "safe to delete" contract |
|---|---|---|---|---|
| **mise** | `~/.config/mise` 453 M · `~/.local/share/mise` **48 G** · `~/.local/state/mise` 157 M · `~/.cache/mise` 279 M | **full 4-way XDG split**, and `mise doctor` PRINTS a `dirs:` block naming all five (incl. `shims`) | `MISE_*_DIR` (docs; not in `--help`) | `mise cache clear`; `state/env-cache` 154 M is regenerable |
| **uv** | cache `~/Library/Caches/uv` (platform-native, **not** XDG on macOS) · `~/.local/share/uv/{python,tools}` · `.venv` project-local | global cache + global toolchains + **per-project venv** | `UV_CACHE_DIR`, `UV_PROJECT_ENVIRONMENT`, `--project`, `--directory` | `uv cache dir \| clean \| prune \| size` — a **complete four-verb lifecycle** |
| **git** | `.git/` project-local, 24 M here | one opaque dir: `objects/` content-addressed + packs, `refs/` index, `config`+`hooks/`+`info/exclude` authored | `GIT_DIR` (4 hits in the 1,639-line `git(1)`), and a worktree's `.git` is a **file** pointing elsewhere | `git gc` / `git prune` |
| **cargo** | `~/.cargo` 1.2 G (`registry/` 1.2 G, `git/` 11 M, `bin/` 11 M, `config.toml`, `env`) + `~/.rustup` 2.1 G; build output in project `target/` | **global cache in home, derived build output in the project** | `CARGO_HOME`, `CARGO_TARGET_DIR` | `cargo clean` (project `target/` only) |
| **ollama** | `~/.ollama` **42 G**: `models/blobs/sha256-<hex>` (flat, content-addressed, 42 G) · `models/manifests/<registry>/<ns>/<name>/<tag>` (24 K, human-navigable index) · `logs/` · `cache/` · **`id_ed25519`(+`.pub`) — the precious identity key** | content-addressed blobs + path-shaped manifest index | **`OLLAMA_MODELS` relocates ONLY the models dir** — the knob is on the big part, not the whole home | `OLLAMA_NOPRUNE` (prune is **on by default** at startup) |
| **chezmoi** | config `~/.config/chezmoi/chezmoi.toml` 260 K · source state = **a user-chosen git repo** (`~/dev/.../macos-development-environment/home`) · dest `~` | three roots, none nested; source of truth is an ordinary repo the user owns | `--source`, `--config`, `--destination` | n/a — nothing derived is kept |
| **terraform** | `.terraform/` project-local (providers/modules, derived) · `terraform.tfstate` project-local **and precious** | — | `TF_DATA_DIR`, `TF_PLUGIN_CACHE_DIR` | **not measured here** (terraform ABSENT on this host) |
| **pnpm** | global content-addressed store + hardlinks into project `node_modules/` | store global, links local | `PNPM_HOME`, `store-dir` | `pnpm store prune` |
| **node_modules** | project-local, wholly derived, reproducible from a lockfile | — | — | `rm -rf` is the contract |

> **Not measured, marked as such:** pnpm and terraform are ABSENT on this host
> (probe: `command -v` returned absent for both, PRESENT for cargo/ollama/chezmoi/git
> — so the probe discriminates). Their rows are from documentation/recall, not
> measurement, and should be re-derived before being quoted as evidence.

> **Probe honesty note.** For `GIT_DIR` I first used `GIT_CONFIG` as the control arm
> and it returned **0** — a *bad control*, because `GIT_CONFIG` is documented in
> `git-config(1)`, not `git(1)`. The armed evidence is instead: `git help git` yields
> 1,639 lines and 4 `GIT_DIR` hits at lines 155/1005/1025/1027, so the page is being
> read and the term is genuinely there.

### 3a. Four transferable patterns

**P1 — The relocation knob goes on the BIG part, separately.** ollama's
`OLLAMA_MODELS` moves 42 G of blobs to another disk without moving the identity key,
the logs, or the config. cargo splits `CARGO_HOME` from `CARGO_TARGET_DIR`. uv splits
`UV_CACHE_DIR` from `UV_PROJECT_ENVIRONMENT`. **A single "move everything" env var is
the option nobody actually wants**, because the reason people relocate is disk
pressure, and disk pressure is always about one subtree.

**P2 — Content-addressing is the collision answer.** ollama, pnpm, git and cargo's
registry all solve "N projects on one host" by making the shared part
content-addressed, so two projects wanting the same bytes *converge* instead of
colliding. This repo currently solves collision by pinning an absolute path
(CLAUDE.md invariant 4) — correct, but it is avoidance, not convergence: every
project still keeps its own 382 M copy of overlapping corpus.

**P3 — A "deletable" directory needs a command that deletes it.** uv ships four verbs
(`dir/clean/prune/size`), git ships `gc`, ollama prunes on startup by default, pnpm
ships `store prune`. This repo's `graphify-out/` is *documented* deletable and has
accumulated **2.4 G of dated backup dirs** with nothing pruning them. **A retention
policy stated only in a `.gitignore` comment is not a retention policy.**

**P4 — Enumerate your roots as a first-class command.** `mise doctor` prints a `dirs:`
block; `chezmoi doctor` names config-file / source-dir / dest-dir / working-tree;
`chezmoi source-path` and `uv cache dir` print one root each. **You cannot migrate,
back up, or debug what you cannot enumerate** — and an `init` that creates roots
without a `where`/`doctor` that prints them leaves the user with no way to find them.

### 3b. Two anti-patterns, both measured on this host

**A1 — a relocation with no migration leaves an orphan.** `UV_CACHE_DIR` is set to
`~/Library/Caches/uv`, and `~/.cache/uv` still holds **10 GB** that nothing will ever
read or reclaim. The relocation knob worked perfectly and the data was abandoned.
Any `init`/`export` that can change a root must own the move, or at minimum detect
and report the orphan.

**A2 — a config dir with no contract accretes non-config.** `~/.config/mise` is
453 M, of which **259 M is a directory literally named `$HOME`** (a shell-quoting
accident that created the literal string as a path) and **194 M is `node_modules`**.
mise's four-way split is excellent and nothing enforces it, so junk landed in the
smallest, most-precious root. **The split is only as good as the resolver that
everyone is forced through.**

---

## 4. The decisive local finding: there is no resolver, and there are 56 literals

```
graphify-out literals in python/src/kb_setup/**.py : 56
"sources"    literals                              :  7
.agent       literals                              :  4
graphify-out mentions in mise.toml                 :  6
graphify-out rules in .gitignore                   : 41
```

There is **no `kb_setup/paths.py`**. Every module computes `repo_root /
"graphify-out" / "graph.json"` for itself — `artifacts.py:52`, `graph.py:188/272/369/
424/506`, `graphify_ops.py:53/269`, `eval_cases.py:338/630`, `evals.py:473`,
`brain.py:53-55`, `chunks.py:102`, `_merge_docs.py`, plus the sub-graph paths
`sources/<name>/graphify-out/graph.json` and `python|tests/graphify-out/`.

**This is graphify issue #1423 reproduced inside this repo, at 3× the scale.**
graphify had the same constant copy-pasted into four modules while two others
hardcoded the literal and *silently ignored the override*; the fix was `paths.py`.
Here the equivalent silent-ignore is guaranteed: any directory move done by
find-and-replace across 56 sites will miss one, and the missed site will keep writing
to the old path **without failing** — the exact failure class this repo's memory
already records twice (`a task that exits 0 passes every check`, `a fix can survive
inside its own fix`).

**Therefore: the resolver is step 0 of the migration, and it must land and be proven
BEFORE any bytes move.**

---

## 5. RECOMMENDATION

### 5.1 Shape: hybrid — a project-local managed root plus a host-shared blob store

Not pure-XDG, not pure project-local:

- **Project-local root `.kb/`** for everything whose meaning is *this corpus*: the
  manifests, the extractions, the graph, the learnings. This is git's, terraform's
  and node_modules' answer, and it is what makes tension (d) — multi-project
  collision — structurally impossible rather than avoided by an absolute-path pin.
- **Host-shared store `~/.local/share/kb/store/`** (XDG data, honouring
  `XDG_DATA_HOME`) for bytes that are *identical across projects*: git clones of
  pinned SHAs, fetched raw pages, downloaded audio. Content-addressed, so two
  projects converge (P2) instead of each keeping a copy. This is cargo's registry /
  pnpm's store / ollama's blobs.

Rejected alternatives, with the reason:

| option | rejected because |
|---|---|
| everything under `~/.local/share/kb/<project-hash>/` (pure XDG) | the authored parts (manifests, extractions, memory) must be **committed with the repo** — CLAUDE.md invariant 3, reproducibility. Moving them out of the repo moves them out of every policy the repo has (graphify's own query-log comment makes exactly this argument about `~/.cache`). |
| everything project-local, no shared store | keeps the 3.6 G of `sources/` clones per-project; N projects on one host pay N× for identical pinned SHAs. |
| keep `graphify-out/` and just document harder | it is documented today, in `.gitignore` (41 rules, 4 `!` negations), in CLAUDE.md, and in a rule file — and `memory/` is still one `graphify uninstall --purge` from deletion. |

### 5.2 Layout — top-level split by LIFECYCLE, never by producer

```
.kb/                              # the ONE managed root; KB_HOME overrides
├── kb.json                       # layout_version, created_by, created_at, roots  [COMMITTED]
│
├── state/                        # AUTHORED + PRECIOUS. Committed. No tool command deletes this.
│   ├── sources/*.manifest        #   github pins (url + ref + SHA)                — was sources/*.manifest
│   ├── extractions/*.json        #   host-agent chunks (cost real Claude tokens)  — was sources/extractions/
│   ├── media/                    #   vendored non-refetchable (transcripts, PDFs) — was sources/media/
│   └── memory/                   #   work-memory / "learnings"                    — was graphify-out/memory/
│
├── derived/                      # REGENERABLE + FREE. `kb clean` rm -rf's this whole subtree.
│   ├── graph/                    #   ← GRAPHIFY_OUT points HERE. graph.json, graph-prose.json,
│   │                             #     manifest.json, .graphify_*, wiki/, obsidian/, *.graphml,
│   │                             #     *.svg, cypher.txt, GRAPH_REPORT.md, dated backups
│   ├── reflections/              #   LESSONS.md — derived FROM state/memory/
│   └── subgraphs/<name>/         #   per-source + self-extraction sub-graphs
│
├── cache/                        # REGENERABLE but EXPENSIVE. `kb clean` does NOT touch this;
│   ├── ast/v<graphify-version>/  #   only `kb cache clean` does. Version-namespaced per graphify's
│   └── semantic/                 #   own rule; semantic cache deliberately NOT versioned (it cost money).
│
└── local/                        # MACHINE-LOCAL, non-precious, not free to lose.
    ├── clones/<name> -> store    #   symlink/hardlink into the shared store
    ├── raw/                      #   kb-add fetch landing zone (was ./raw)
    ├── stamps/                   #   .currency-stamp.json, .base-graph.sha256
    ├── logs/
    └── agent/                    #   session scratch, review receipts + reports (was .agent/)

~/.local/share/kb/store/          # host-shared, content-addressed (XDG_DATA_HOME honoured)
├── blobs/sha256-<hex>            #   clones + fetched pages, deduped across projects
└── manifests/<owner>/<repo>/<sha>#   human-navigable index → blobs   (ollama's shape exactly)
```

**`.gitignore` becomes three lines with zero negations:**

```gitignore
.kb/derived/
.kb/cache/
.kb/local/
```

versus 41 `graphify-out` rules + 4 `!` toggles under `sources/` today. **That single
diff is the proof the layout is right**: a layout that needs a negation to express its
own policy is the wrong layout, and this one needs none.

#### Rationale per directory

| dir | why it exists as a SEPARATE top-level child |
|---|---|
| `kb.json` | the only file that makes migration mechanical rather than archaeological. Records `layout_version` and the tool version that created it. Without it, a future move is a hand-audit — the 10 GB orphaned `~/.cache/uv` on this host is what "no layout version" costs. |
| `state/` | **the trap this design exists to kill.** Today `memory/` is authored, committed, and lives inside a tree that graphify's own `uninstall --purge` deletes and every doc calls "safely deletable". Hoisting it to a sibling means no `--purge`, no `kb clean`, no `rm -rf derived/` can ever reach it. Same fix ollama needs for `~/.ollama/id_ed25519` and hasn't made. |
| `derived/` | must be safe to `rm -rf` **at any moment, with no allowlist**. That property is the whole design. It also gets the retention command it lacks today (P3) — 2.4 G of dated backups here have never been pruned. |
| `cache/` | separated from `derived/` because the two have different *prices*, not different natures. graphify already encodes this distinction internally (AST cache version-namespaced and swept; semantic cache deliberately not, "invalidating them on every release would re-bill extraction"). Generalised: **namespace by producer-version anything a release invalidates; never namespace anything that cost money.** |
| `local/` | machine-local and gitignored like `derived/`, but *not free to lose*: `.currency-stamp.json` records which graphify version actually built the graph, and its absence must read as "rebuild pending", never as a false green. Deleting `derived/` must not silently reset that provenance. |
| `~/.local/share/kb/store/` | (b) big blobs live once per host, not once per project. Content-addressed so N projects converge. `KB_STORE` relocates it independently (P1) — the knob goes on the 3.6 G part. |

### 5.3 The env-var surface — copy graphify's shape exactly

```python
# python/src/kb_setup/paths.py — the ONLY module that names a directory
KB_HOME  = os.environ.get("KB_HOME", ".kb")        # relative name OR absolute path
KB_STORE = os.environ.get("KB_STORE", xdg_data_home() / "kb" / "store")
KB_HOME_NAME = os.path.basename(os.path.normpath(KB_HOME))   # for scan-exclude

def kb_root() -> Path: ...
def state(*p) -> Path: ...
def derived(*p) -> Path: ...
def cache(*p) -> Path: ...
def local(*p) -> Path: ...
def graph_json() -> Path: return derived("graph", "graph.json")
```

Four properties, each taken from graphify's `paths.py` for a stated reason:

1. **Accepts a relative name or an absolute path** in one variable; `Path(KB_HOME, *p)`
   resolves both. Relative → per-worktree isolation; absolute → shared output.
2. **Read once at import**, documented as such. Simplicity over live reconfiguration.
3. **`KB_HOME_NAME` exported separately** — the bare directory name even when the
   override is absolute. graphify needs this for its `detect` scan-exclude "so a
   custom output dir is never re-ingested as source"; **this repo needs it for the
   same reason and does not have it.** `.kb/` sits inside the tree that gets
   extracted, so its name must also land in `.graphifyignore`.
4. **Atomic writers live in the same module** (`write_json_atomic`,
   `write_text_atomic`), with graphify's symlink-resolution behaviour preserved so a
   shared-output symlink is written *through*, not replaced.

**`GRAPHIFY_OUT` is what makes this possible without forking graphify.** Set
`GRAPHIFY_OUT=<abs>/.kb/derived/graph` and all 75 graphify call sites honour it — the
`kb-*` tasks already funnel every graphify invocation through `kb_setup.graphify_env`,
which is the natural place to inject it (it already strips non-Claude backend
triggers, so a second env contract there is free). Corollaries:

- `graphify add`'s `--dir` must point at `local/raw/` (its default is `./raw`).
- `graphify save-result`'s `--memory-dir` must point at `state/memory/`, **which is
  outside `GRAPHIFY_OUT`** — its default is `graphify-out/memory`, so this override is
  mandatory, not cosmetic. Likewise `reflect --memory-dir` + `--out`.
- `graphify clone`'s `--out` must point into the shared store (default is
  `~/.graphify/repos/<owner>/<repo>`, an uncontrolled second home).

### 5.4 What `kb init` must do

1. **Create the four children + `kb.json`**, idempotently. Refuse (don't merge) if
   `kb.json` exists with a *newer* `layout_version` than this binary understands.
2. **Write the three `.gitignore` lines** if absent, and `.kb` into `.graphifyignore`.
3. **Print every root it resolved** — `mise doctor`'s `dirs:` block, verbatim in
   spirit (P4). Include the shared store and note whether it came from a default or an
   env var, because "which knob is in force" is the question every later debug asks.
4. **Detect and report orphans** — an existing `graphify-out/`, `sources/`, `raw/`,
   `.agent/`, or a store at a *different* path than the one now in force. Report; do
   not silently adopt or delete. (A2.)
5. **Not touch `~/.claude`, `.claude/**`, `.git/`, `mise.toml` or `pyproject.toml`.**
   `.claude/**` is a **hard constraint, not a preference**: Claude Code's loader scans
   `.claude/skills`, `.claude/rules`, `.claude/agents` and nowhere else, and it is not
   configurable — so any "one directory for everything" that swallows `.claude/` breaks
   skill loading silently. **The managed dir holds what the TOOL generates; it cannot
   hold what the HARNESS loads.**

Companion commands, each earning its place from a comparator:

| command | precedent |
|---|---|
| `kb where` / `kb doctor` | `mise doctor` `dirs:`, `chezmoi doctor`, `chezmoi source-path`, `uv cache dir` |
| `kb clean` (rm -rf `derived/`) | `cargo clean`, `git gc`, `rm -rf node_modules` |
| `kb cache clean \| prune \| size` | `uv cache clean/prune/size` — the four-verb set, adopted whole |
| `kb gc` (prune dated backups + orphaned store blobs) | `git prune`, `pnpm store prune`, ollama's default-on startup prune |
| `kb export --to <dir>` | see below |

### 5.5 Export / migration (tension (e))

**`kb export` must emit the reproducible INPUT set, not a copy of derived bytes.**
Concretely `state/**` + `kb.json` — measured today that is ~308 K of memory plus
`sources/media` + `sources/extractions` + manifests, against **4.4 G of `derived/`
that `kb build` reproduces for free** (deterministic, no LLM). Copying `derived/`
would be copying the thing whose entire contract is "regenerable".

Two hard requirements:

- **`kb.json` carries `layout_version`.** A future layout change is then a numbered
  migration, not archaeology. This is the field whose absence produced the 10 GB
  orphaned `~/.cache/uv` on this very host.
- **`kb import` / `kb init --from <bundle>` must be the inverse**, and the round-trip
  must be *proven* by a control arm: export → fresh dir → import → `kb build` →
  the graph node/edge counts match. Anything less is two commands agreeing with each
  other.

### 5.6 Migration path from today — ordered, each step independently verifiable

**Step 0 (MUST be first, and shippable alone): introduce `kb_setup/paths.py` and
route all 56 literals through it, changing NO directory.** Every path resolves to
exactly where it does today. Gate: `mise run lint && mise run test`, then a grep
proving `graphify-out` appears in `paths.py` and nowhere else in `python/src/kb_setup/`
— and prove the FAIL direction by deleting one call site's import and confirming the
grep gate goes red. Until this lands, any move is 56 chances to silently miss one.

**Step 1: `.kb/` skeleton + `kb.json` + the three `.gitignore` lines.** Nothing moves;
the tree is created and `kb where` prints it. Verify `.kb` is excluded from extraction
(`KB_HOME_NAME` in the scan-exclude and in `.graphifyignore`) — control-arm it by
confirming a marker file under `.kb/` does **not** appear as a node after `kb build`.

**Step 2: move the PRECIOUS things first, while everything still works.**
`graphify-out/memory/` → `.kb/state/memory/`; `sources/*.manifest`,
`sources/extractions/`, `sources/media/` → `.kb/state/`. These are `git mv`s of
committed files — reviewable, revertible, and they immediately kill the
`--purge`/`rm -rf` trap. Two couplings must move in the same commit:
`kb_setup.review.EXEMPT_PATHS` (`graphify-out/memory/**` → `.kb/state/memory/**`) and
`brain.py`'s `_MEMORY_SUBPATH`/`_LESSONS_SUBPATH`.

**Step 3: point `GRAPHIFY_OUT` at `.kb/derived/graph` in `graphify_env`,** plus the
`--memory-dir` / `--dir` / `--out` overrides §5.3 lists. Then `mise run kb-build` from
a clean tree and confirm it reproduces from committed inputs alone — that is the only
honest arm, per `clean-git-state.md`. Delete the old `graphify-out/` only after that
passes.

**Step 4: `local/`** — `raw/` → `.kb/local/raw/`, `.agent/` → `.kb/local/agent/`,
stamps → `.kb/local/stamps/`. Update `agent-artifact-conventions.md` in the same
commit. Note `.omc/` cannot be moved (it is recreated by a USER-level statusline hook
this repo does not edit) and must stay in `.gitignore`.

**Step 5 (separable, ship last): the shared store.** `~/.local/share/kb/store/` +
content-addressing + `KB_STORE`. This is the only step with real new machinery, it is
the only one that touches `$HOME`, and everything above works without it — so it
should not block the rest.

**Docs to change in the same commits (not after):** `CLAUDE.md` (the Layout table,
invariants 3/4/5, and the two-verbs section), `.claude/rules/agent-artifact-conventions.md`
(both tables + rule 4), `docs/graphify-reference.md`, `currency.toml`'s `artifact`/
build-stamp paths, and every `kb-*` task in `mise.toml`. Per
`tool-currency-and-native-first.md` rule 5, a layout change with stale describing docs
leaves two files asserting opposite things.

---

## 6. What this CHANGES versus the written-down current design

| today (CLAUDE.md / agent-artifact-conventions.md) | after | why |
|---|---|---|
| `graphify-out/` is "DERIVED … only `memory/` is committed" | `derived/` is derived with **no exceptions**; memory lives in `state/` | an exception inside a purgeable tree is a data-loss bug waiting on a flag; it also forces 41 gitignore rules |
| `sources/` mixes manifests (authored) / clones (derived) / media (authored) / extractions (authored), expressed with 4 `!` negations | split across `state/` (authored) and `local/clones` → shared store | a layout needing a negation to state its own policy is the wrong layout |
| `raw/` at repo root, "an INPUT, gitignored" | `.kb/local/raw/` | one root, not three |
| `.agent/` at repo root | `.kb/local/agent/` | same; the `.agent/`-vs-`.omc/` rename rationale (vendor-neutral, control-armed) is preserved, just re-parented |
| MCP server pinned to an **absolute** `graph.json` to avoid cross-project collision | still absolute, but now derived from `paths.graph_json()` | keeps invariant 4; removes the hand-maintained literal |
| no path resolver; 56 literals | `kb_setup/paths.py`, 1 literal | graphify #1423, already-solved upstream |
| retention stated in a `.gitignore` comment | `kb gc` / `kb cache prune` | 2.4 G of unpruned backups is the measurement |

Unchanged and deliberately so: `.claude/**` stays where the loader looks; `graphify-out`
remains graphify's *own* default name (we set `GRAPHIFY_OUT`, we do not patch graphify);
committed-inputs reproducibility (invariant 3) is strengthened, not relaxed.

---

## 7. What I could NOT determine

1. **Whether `GRAPHIFY_OUT` is honoured by every graphify write path in 0.9.31.**
   `paths.py` is the documented single source of truth and 75 call sites reference it,
   but #1423 records that `security.py` and `callflow_html.py` once hardcoded the
   literal and silently ignored the override. I did **not** run the control arm that
   would settle it: set `GRAPHIFY_OUT` to a temp dir, run a build, and assert nothing
   lands in `./graphify-out`. **Do that before step 3.** It is cheap and it is the
   single load-bearing assumption of the whole recommendation.
2. **Whether `graphify serve` / `graphify-mcp` honours `GRAPHIFY_OUT`.** `serve` is not
   in `--help` at all, so its contract is undocumented; this repo pins an absolute
   `--graph`, which sidesteps the question but does not answer it.
3. **pnpm and terraform rows are unmeasured** — both absent from this host.
4. **Whether `.kb` collides with any tool's reserved name.** `.agent/` was adopted only
   after a control-armed check against Claude Code's full docs corpus (`.agent/` → 0,
   `CLAUDE.md` → 439). **`.kb` deserves the same check before it is chosen**, and I did
   not run it.
5. **The right name.** `.kb/` (dot = tool-owned, per `.git`/`.terraform`) vs `kb/`
   (no dot, since `state/` is hand-edited and committed — chezmoi's source dir is a
   plain visible repo). I lean `.kb/` because the majority of the bytes are tool-owned,
   but this is a judgement call for the owner, not a finding.
6. **Whether the shared store should hardlink or symlink** into `.kb/local/clones/`.
   pnpm hardlinks (cheap, but a project write mutates the store); git worktrees use a
   pointer *file*. Not probed.
7. **Cross-repo blast radius.** `kb_setup.currency` and `kb_setup.md_budget` are
   consumed by the sibling **dotfiles** repo as pinned git deps. Whether any of their
   path assumptions cross the boundary was not checked, and a layout change that breaks
   a downstream consumer would surface only in that repo's CI.

---

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read the INSTALLED 0.9.31 source (`paths.py`, `global_graph.py`, `cli.py`, `cache.py`, `querylog.py`, `hooks.py`, `install.py`) and `graphify --help`; the primary analogue for output-dir resolution, `GRAPHIFY_OUT`, and the `~/.graphify` home state.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo: `CLAUDE.md`, `.gitignore`, `.claude/rules/agent-artifact-conventions.md`, `.claude/rules/md-size-budgets.md`, `mise.toml`, `python/src/kb_setup/**`; the layout being redesigned.
- [jdx/mise](https://github.com/jdx/mise) — `mise doctor` `dirs:` block and the measured 4-way XDG split; source of the "enumerate your roots" pattern.
- [astral-sh/uv](https://github.com/astral-sh/uv) — `uv cache dir/clean/prune/size` four-verb lifecycle; `UV_CACHE_DIR` platform-native default and the measured 10 GB orphaned cache.
- [ollama/ollama](https://github.com/ollama/ollama) — measured content-addressed blob store + manifest index, `OLLAMA_MODELS`, `OLLAMA_NOPRUNE`, and the identity key sitting inside 42 G of deletable blobs.
- [rust-lang/cargo](https://github.com/rust-lang/cargo) — measured `CARGO_HOME` (registry/git/bin/config) vs project-local `target/`; the global-cache + local-output hybrid.
- [twpayne/chezmoi](https://github.com/twpayne/chezmoi) — measured three-root split (config / user-chosen source repo / dest) and `chezmoi doctor` / `source-path` root enumeration.
- [git/git](https://github.com/git/git) — `.git/` as the canonical one-managed-directory; `GIT_DIR` in `git(1)`; worktree `.git`-as-a-file pointer.
- [pnpm/pnpm](https://github.com/pnpm/pnpm) — content-addressed store + hardlinks (**documented, NOT measured — pnpm absent on this host**).
- [hashicorp/terraform](https://github.com/hashicorp/terraform) — `.terraform/` derived vs precious state, `TF_DATA_DIR` (**documented, NOT measured — terraform absent on this host**).
