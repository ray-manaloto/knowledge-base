# Refuter: "corpus correctness no longer depends on PATH ordering"

**VERDICT: REFUTED** (with significant parts of the change confirmed correct).

Repo: `knowledge-base` @ `main`, staged change (`git diff --cached`), 2026-07-27.
Read-only probes only. No `kb-build`, no `kb-artifacts`, no writes to `graphify-out/`.
`git status --short graphify-out/` → empty after every probe.

---

## 0. Probe hygiene / environment facts

| fact | value |
|---|---|
| repo pin (`mise.toml:23`) | `"pipx:graphifyy" = { version = "0.9.26", extras = ["all"] }` |
| `mise which graphify` (repo cwd) | `…/installs/pipx-graphifyy/0.9.26/bin/graphify` → `graphify 0.9.26` |
| `mise which graphify` (cwd `/tmp` or `$HOME`) | `…/installs/pipx-graphifyy/**0.9.28**/bin/graphify` |
| PATH-first `graphify` in this session | `0.9.26` (this session is *clean*; the bug is not live here) |
| `python3` | 3.14.0 (mise) |

**PEP 758 note (not a defect).** `except OSError, subprocess.SubprocessError:` at
`graphify_env.py:106,127,158,204` and `currency/sync.py:229` is *valid* on Python 3.14
(unparenthesized `except`). Control arm: `py_compile` on a deliberately broken file
(`def f(`) DID raise `SyntaxError: '(' was never closed`, so the compile probe
discriminates; the staged blob compiles clean. It *is* a hard 3.14+ floor — the system
`/usr/bin/python3` (3.9.6) cannot import the module — but the repo pins 3.14.

**Sandbox gotcha that invalidated one early probe:** `/tmp` is **wiped between Bash tool
calls** here. An impostor binary created in call N is gone in call N+1, which silently
turns an impostor test into a no-op that "passes". Every impostor result below was
created *and* consumed in the same shell call, with a control arm asserting the impostor
was actually reachable (`command -v graphify` → `/tmp/fakebin/graphify`).

---

## 1. What the change genuinely FIXES (conceded, verified)

`graphify_exe()` works, and `cwd=root` is load-bearing:

```
# impostor (a real graphify 0.9.28) symlinked first on PATH:
  shutil.which('graphify') = /tmp/fakebin/graphify        (control arm: reachable, reports 0.9.28)
  graphify_exe(repo)       = …/pipx-graphifyy/0.9.26/bin/graphify   ✔ defeats it

# cwd sensitivity is real, and graphify_exe handles it:
  graphify_exe(repo_root=REPO) with cwd=/tmp → …/0.9.26/bin/graphify   ✔
```

Converted call sites (all verified present): `artifacts.py:74`, `brain.py:135,340`,
`graph.py:86,138,254`, `graphify_ops.py:69,174`. `artifacts.py` restructured its
`_ARTIFACTS` registry to argv-only so no entry *can* hard-code a bare binary — good.

**`mise.toml`'s bare `graphify` task bodies are NOT a refutation** (I expected them to be;
they are not). Measured: mise **prepends its resolved tool bin at position 8** of the
task PATH, ahead of everything, and **strips other `mise/installs/**` entries entirely**.

```
env PATH="/tmp/fakebin:$PATH" mise exec -- python -c '<scan PATH for graphify>'
   pos 8   …/installs/pipx-graphifyy/0.9.26/bin      <- wins
   pos 158 /tmp/fakebin                              <- impostor demoted
   pos 166 …/mise/shims
# control arm: the same scan on a clean PATH does NOT list /tmp/fakebin, so it discriminates.
# end-to-end: `env PATH=/tmp/fakebin:$PATH mise run kb-remember` ran the REAL graphify
# (argparse error "--question required", rc=2), not the impostor. Nothing was written.
```

So `kb-serve`(:170 `graphify-mcp`), `kb-add`(:179), `kb-remember`(:227), `kb-reflect`(:233),
`brain-update`(:243) are protected *when invoked via `mise run`*. Hooks in
`.claude/settings.json` all use `mise exec -C "$CLAUDE_PROJECT_DIR"` / `mise run -C` — also pinned.

---

## 2. REFUTATION 1 — `kb-build` runs the pinned binary but STAMPS the PATH-first one

The change converts the *invocation* and leaves the *provenance stamp* PATH-resolved.

- `graph.py:213` → `sync.observed_version(spec.binary)`
- `currency.toml:16` → `binary = "graphify"`
- `currency/sync.py:222` → `found = shutil.which(binary)`  ← **PATH order**
- `git diff --cached --name-only` → **`currency/` is not touched by this change** (0 files)

Measured, both probes in one process under one polluted PATH:

```
  currency.toml binary  = 'graphify'
  BUILD actually runs   = …/pipx-graphifyy/0.9.26/bin/graphify
  BUILD actual version  = graphify 0.9.26
  STAMP records version = 0.9.28
  >>> DIVERGENT
# CONTROL ARM (clean PATH, same two probes): BUILD = 0.9.26 | STAMP = 0.9.26 | consistent
```

This is precisely the failure the change's own docstring calls unabsorbable
(`graphify_env.py:86-89`): *"a graph built by one version and stamped another is
unfalsifiable afterwards — the one failure this repo cannot absorb."* Before the change
both sides read PATH and therefore **agreed** (both would say 0.9.28). The change makes
them **disagree**. `sync.observed_version`'s own docstring states the intent it now
violates: *"the honest answer is 'whatever actually ran'"* — it no longer is.

**Reachability — stated honestly.** Under `mise run kb-build` this does NOT reproduce
(mise's pos-8 prepend makes `shutil.which` find 0.9.26 too; verified for both an
arbitrary-dir impostor and the docstring's own stale-`mise/installs` scenario). It
reproduces on any invocation that does not inherit mise's env, e.g. `uv run kb-setup build`.
That such invocations are real and shipped is proven by `.claude/settings.json:33`, which
runs `uv run --project … kb-setup hookguard` with **no mise wrapper at all**.

Note the corollary: *the same condition bounds the original bug.* Under `mise run`,
neither the old nor the new code was PATH-vulnerable. The change therefore only alters
behaviour on the non-mise surface — and on exactly that surface it converts an agreeing
pair into a disagreeing one.

## 3. REFUTATION 2 — `graphify_python()` omits `cwd=root` (kb-build / kb-merge / kb-artifacts)

`graphify_env.py:146-153` calls `mise where pipx:graphifyy` **without** `cwd=root`, unlike
`graphify_exe` which passes `cwd=root` (`:104`). `mise where` is cwd-sensitive — proven:

```
mise where pipx:graphifyy   (cwd = repo) → …/pipx-graphifyy/0.9.26
mise where pipx:graphifyy   (cwd = /tmp) → …/pipx-graphifyy/0.9.28
```

So the function ignores the `repo_root` it was given:

```
graphify_python(repo_root=REPO), cwd=REPO  → …/0.9.26/graphifyy/bin/python
graphify_python(repo_root=REPO), cwd=/tmp  → …/0.9.28/graphifyy/bin/python   <-- WRONG VERSION
graphify_exe   (repo_root=REPO), cwd=/tmp  → …/0.9.26/bin/graphify           <-- correct (contrast)
```

Its last resort (`:161`) is `shutil.which("graphify")` → **PATH-ordered**, and its
first (`:140`) is a marker file `graphify-out/.graphify_python` that outranks everything
(absent on this machine, so `mise where` is the live path).

This is on corpus-**writing** paths, all named in or reached by the claim:
`graph.py:143` (kb-build's committed-doc-extraction replay), `graphify_ops.py:44`
(**kb-merge**, `build_merge` + Louvain re-cluster), `graphify_ops.py:297`,
`artifacts.py:56 → ensure_runtime_deps → graphify_python` (**kb-artifacts**).

## 4. REFUTATION 3 — `kb-label` still aborts on a PATH check

`graphify_ops.py:65`: `if not shutil.which("graphify"): … return 2` — a **PATH-ordered gate
in front of the PATH-independent invocation** added two lines below it (`:69`). Measured
with mise reachable but graphify absent from PATH:

```
  shutil.which(mise)     = /Users/rmanaloto/.local/bin/mise
  shutil.which(graphify) = None     <- gate fires, kb-label returns 2, nothing runs
  graphify_exe(repo)     = …/pipx-graphifyy/0.9.26/bin/graphify   <- would have worked fine
```

So the claim's "`kb-label` … now invokes the binary `mise which graphify` names" is false
in the case where PATH holds no graphify: it invokes nothing.

## 5. REFUTATION 4 — the fallback is SILENT and fully restores the old behaviour

`graphify_env.py:116`: `return shutil.which("graphify") or "graphify"`. With no mise on
PATH, measured:

```
  shutil.which('mise')     = None
  shutil.which('graphify') = None
  graphify_exe(repo)       = 'graphify'      <- a BARE name, PATH-resolved, no warning
```

`except …: pass` (`:106-107`) emits nothing to stderr, sets no flag, and the corpus-writing
callers do not distinguish a resolved absolute path from a bare name. `mise which` failing
is not exotic — a missing/failed `mise`, a 30s timeout, a not-yet-installed tool, or a
non-zero rc all land here (`check=True`). The degradation is invisible in the build log.

## 6. Un-converted call sites (outside the claim's five tasks — reported, not overclaimed)

Still bare `["graphify", …]`, PATH-resolved: `evals.py:302`, `eval_cases.py:389, 407,
**429** (`graphify --version`), 646, 709`. These are the eval/measurement surface, not
corpus writes, so they do not refute the claim as worded — but `eval_cases.py:429`
records a version by PATH, the same laundering shape as §2.

**Control arm for "no other call sites".** The enumeration regex was run repo-wide over
`*.toml *.json *.pkl *.js` and all of `python/src/`, and it **did** re-find known-present
sites (`mise.toml:179, 227, 233, 243`; every converted `graphify_exe` site). Declared
bound: the pattern `graphify(-mcp)?\s+[a-z-]` missed `mise.toml:170`
(`graphify-mcp {{config_root}}…`, followed by `{`), which I found instead via the explicit
`grep -n graphify mise.toml` full listing. Both listings were used.

## 7. Tests

`tests/test_graphify_env.py` covers `graphify_exe` well (mise-wins-over-PATH, absent-mise
fallback, bad-path answer, empty output, bare-name last resort). **Nothing tests** the
build↔stamp agreement (§2), `graphify_python`'s missing `cwd` (§3), or the `kb-label` gate
(§4). Every defect above is in the untested gap.

---

## Bottom line

Sentence 2 of the claim holds for `kb-query` and `kb-update`, and for the *primary*
invocation inside `kb-build` / `kb-artifacts` / `kb-label`. Sentence 1 — "the correctness
of the knowledge corpus no longer depends on PATH ordering" — is **false**: on the
non-mise invocation surface the change *introduces* a build-vs-stamp version divergence
(§2) that the repo's own doctrine calls the one unabsorbable failure, `kb-build`/`kb-merge`/
`kb-artifacts` still reach a cwd-resolved interpreter that can be the wrong version (§3),
`kb-label` still gates on PATH (§4), and the fallback restores full PATH ordering without
saying so (§5).

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the pinned tool; installed 0.9.26/0.9.28 binaries and `save-result --help` probed locally.

_None fetched over the network; all evidence is local file:line + command output._

---

# ADDENDUM — team-lead's three prioritised questions (2026-07-27)

## Q1. Do the bare `graphify` evals break the claim? — **No, but the rationale is only 1/3 sound**

**Verdict on the claim: does NOT break it.** None of these write the corpus, and none is
among the five named tasks. Reported as a real design gap, not as a refutation.

The choice is *documented and argued* in-code (`eval_cases.py:379-397`, `evals.py:305-308`),
so it is not an oversight. Judged on its own terms, splitting the three call kinds:

| site | kind | bare resolution defensible? |
|---|---|---|
| `evals.py:302` (canary "a graph that exists must ANSWER") | measures the ENVIRONMENT | **Yes** — a canary pinned to the resolver cannot detect a broken session env |
| `eval_cases.py:429` `_corpus_stamp` → `graphify --version` | measures the ENVIRONMENT | **Yes** — the point is which binary this session has |
| `eval_cases.py:389` `_retrieval` → recall numbers | produces RESULTS | **No — self-undermining, see below** |
| `eval_cases.py:407` `_node_count` → `graphify diagnose` | reads the GRAPH | **No — no rationale exists, and none is possible** |

**(a) The ecological argument is self-undermining after #40.** The docstring's premise is
that `graphify_exe` answers *"the binary the pin names"* while the eval must ask *"the
binary a session actually runs"*. That premise was true before this change and is false
after it: a session's retrieval goes `mise run kb-query` → `graphify_ops.query` →
`graphify_exe` (`graphify_ops.py:174`) → **the pinned binary**. So `_retrieval` now measures
a binary that no operational retrieval path uses. It has become the hypothetical arm and
`graphify_exe` the ecological one — precisely the inversion the docstring claims to prevent.

**(b) `eval_cases.py:407` is not covered by the rationale at all.** `_node_count` reads
`graph.json` via `graphify diagnose`. Node count is a property of the *graph*, not of the
session; resolving that reader by PATH order can only add noise, never signal. The
docstring at `:379-397` argues only for `_retrieval` and does not reach this call.

**(c) The cited falsifiability mechanism does not do what is claimed.** *"Falsifiability is
preserved instead by `_corpus_stamp`, which records the version that ACTUALLY RAN alongside
every number."* Reading it (`:431-450`): it records the **query** binary's version, plus each
graph's **mtime** (`_built`, `:454-456`). It never records which binary BUILT the graph.
Combined with §2 above — where the build stamp can itself record a PATH-first version that
diverges from what actually ran — there is **no path** by which an eval number can be tied
to its builder version. The claim overstates the function.

**(d) The external check agrees with the lead, not the author.** dotfiles
`docs/specs/graphify-autonomous-queue.md` §5a treats this exact line as a *hazard*:

> **The real precondition is the BINARY, and all four arms share it.** `unscoped` and
> `prose` shell out to bare `graphify query` (`eval_cases.py:389`), which resolves
> differently under `mise run eval` than under a bare `uv run`. So: decide the pin,
> rebuild, re-baseline **all four arms together**, and only then quote a new number.

A property that forces all four arms to be re-baselined together is being managed as a
liability, not harvested as a measurement. **Sound for `:429` and `evals.py:302`;
rationalisation covering a real gap for `:389` and `:407`.**

## Q2. mise task bodies + hooks — **they go around the fix, and it does NOT matter for corpus correctness**

They are literally bare (`mise.toml:170,179,227,233,243`) and never touch `graphify_exe`.
But measured (§1 above), they are not PATH-vulnerable: mise prepends the pinned bin at
**PATH position 8** and strips every other `pipx-graphifyy/*/bin` entry; the end-to-end
impostor test through `mise run kb-remember` ran the real 0.9.26. Hooks use
`mise exec -C "$CLAUDE_PROJECT_DIR"` / `mise run -C` (`.claude/settings.json:13,23,33,42,51`)
— also pinned. **Convenience/consistency issue only. Not a refutation.**

One loose end worth naming: `kb-serve` invokes **`graphify-mcp`**, and `graphify_exe`
resolves only `graphify` — there is no resolver for that binary at all. Still fine via mise.

## Q3. The `shutil.which` fallback — **SILENT, and the hazard is materially live on this machine**

Silent: `except …: pass` (`graphify_env.py:106-107`) writes nothing to stderr, sets no flag,
and callers cannot distinguish an absolute path from the bare name returned at `:116`.

Live-machine facts measured just now:

```
this session's raw PATH:  exactly ONE pipx-graphifyy entry — 0.9.26/bin at pos 8  (CLEAN)
MISE_ENV_CACHE=1                                            (the freezing mechanism)
installed pipx-graphifyy versions: 43, incl. 0.9.25, 0.9.27, 0.9.28
```

So the #40 hazard is **not live in this session**, but 43 stale dirs are available to be
frozen into a session env cache — and spec §5a records `0.9.25/bin` at PATH **position 32**
in a real session measured **today**.

Precision, against my own interest: in that frozen-PATH scenario `mise` is still present, so
`graphify_exe` *succeeds* and the fallback never fires. The fallback is therefore a
lower-probability silent path (mise absent / 30s timeout / tool not installed / non-zero rc
under `check=True`). **The live exposure is §2 (stamp) and §3 (`graphify_python`), not §5.**

## Line of attack 4 — **covered, not skipped**

The offer to skip the bundled-interpreter path was not taken: it is §3 above, and it is the
second-strongest finding (`graphify_python` ignores its `repo_root`, returning the 0.9.28
interpreter for a repo pinned to 0.9.26, on the `kb-merge` / `kb-build` / `kb-artifacts` paths).

## Probe correction

The "control arm" in the live-PATH scan was **invalid**: `PATH=… awk … <<< "$PATH"` expands
`$PATH` in the *parent* shell, so the injected entry never reached the scanned string. The
mise-env scan in §1 *was* validly control-armed (it did find `/tmp/fakebin`), and that is
the one the conclusions rest on.

## Verdict (unchanged)

**REFUTED** — on §2 (build/stamp version divergence), §3 (`graphify_python` ignores
`repo_root`), §4 (`kb-label`'s PATH gate). **Not** on the evals (Q1) or the mise task
bodies (Q2), both of which I tested and found not to refute the claim.
