# Cold review — commit 5204e57

**Reviewed commit:** `5204e57365b66440efc3d3c1b95df9a4f4dc4d23` (short `5204e57`, HEAD)
**Base:** `27bf69104054172d13d143ca3066a7a5f2ee1810`
**Diff scope:** `git diff 27bf69104054172d13d143ca3066a7a5f2ee1810...5204e57 -- . ':(exclude)docs/research/**'`
**Lane:** cold — external reviewer from a different model family (GPT-5.6 Sol via `codex-cli 0.146.1`),
handed the diff with no description of intent. Lane exit `EXIT: 0`, no watchdog kill.
**Working tree at review time:** `git rev-parse HEAD` = `5204e57365b66440efc3d3c1b95df9a4f4dc4d23`,
`git status --porcelain` empty — so every citation below was spot-checked against the
reviewed bytes directly, and re-verified clean after the mutation arm in F6.

## Scope measured

| file | +/- |
|---|---|
| `.claude/rules/md-size-budgets.md` | +11 / -1 |
| `.claude/rules/mise-tasks-only.md` | +1 / -0 |
| `.claude/skills/graphify/.graphify_version` | +1 / -0 |
| `.claude/skills/graphify/SKILL.md` | +8 / -0 |
| `.gitignore` | +11 / -1 |
| `currency.toml` | +49 / -2 |
| `mise.toml` | +27 / -0 |
| `python/src/kb_setup/cli.py` | +5 / -0 |
| `python/src/kb_setup/currency/apply.py` | +35 / -12 |
| `python/src/kb_setup/currency/skill.py` | +115 / -6 |
| `python/src/kb_setup/skill_refresh.py` | +73 / -0 |
| `sources/agent-harness-docs.manifest` | +1 / -1 |
| `sources/extractions/graphify-2026-08-06-docs.json` | +20128 / -0 (EXCLUDED — see UNCOVERED) |
| `tests/test_currency_skill.py` | +115 / -0 |
| `tests/test_skill_refresh.py` | +129 / -0 |

Reviewable (non-corpus) surface: **604 changed lines** — under the single-shot guard,
so it went to codex whole, in one batch, with no truncation and no file-splitting.

## Verdict

**11 findings — 3 P1 (all BLOCKING), 5 P2, 3 P3.**

The worst is F2: Step 5 of the regenerated graphify skill writes `GRAPH_REPORT.md`
and `.graphify_labels.json`, *then* attempts the `graph.json` export, and when that
export refuses it prints the error and falls straight through to
`print('Report updated with community labels')` at indent 0 — exiting 0 with two
sidecars describing a graph that was never written. Step 4 of the same file, twenty
lines earlier, does it correctly and its own comment names the issue (#1392) this
reintroduces.

---

## P1 — BLOCKING

### F1 (P1, blocking) — Step 5 rewrites `graph.json` through graphify's bundled interpreter, not a `kb-*` task

`.claude/skills/graphify/SKILL.md:496,502,527`

The Step 5 bash block is `$(cat graphify-out/.graphify_python) -c "…"`
(`SKILL.md:496`), and this commit adds `from graphify.export import to_json`
(`SKILL.md:502`) and a new `graph.json` write (`SKILL.md:527`):

```python
wrote = to_json(G, communities, 'graphify-out/graph.json', community_labels=labels)
```

That is a graph WRITE performed through graphify's bundled python. It bypasses the
task-layer pinned-version guard that every other writer goes through —
`cli.py:52-61`, `if cmd in _GRAPH_WRITERS: … graphify_env.assert_pinned_graphify(repo_root)`,
whose own comment says writers "destroy data" with a stale binary. It is also
precisely the invocation `kb_setup.hook_guard` denies (`mise-tasks-only.md`: "the
bundled interpreter / `_merge_docs.py` → `mise run kb-merge`").

**Adjudication (evidence gathered here, not from codex):** these bytes are
**upstream's**, not a hand-edit. The 0.9.34 installer template at
`…/pipx-graphifyy/0.9.34/…/site-packages/graphify/skill.md:517` contains the same
line. Control arm: a token known to be in that template
(`Report updated with community labels`) → 1 hit, so the probe discriminates
between present and absent. The pattern is also pre-existing throughout this file
(bundled-interpreter blocks at `SKILL.md:110,173,199,222,295,320,335,369,406,468`).

So the remedy is **not** to hand-edit the file — this commit's own central lesson is
that a hand-edit to this tree gets eaten by the next refresh. It is an `ADDENDA`
entry or an upstream report. Blocking on the grounds that the bytes are committed
and an agent following the skill will run them.

### F2 (P1, blocking) — Step 5 prints success after the export was REFUSED, leaving two sidecars describing a graph that was never written

`.claude/skills/graphify/SKILL.md:521-531`

Verified byte-exactly at `5204e57`, indentation included:

```
521  report = generate(G, communities, cohesion, labels, analysis['gods'], …)
522  Path('graphify-out/GRAPH_REPORT.md').write_text(report, encoding="utf-8")
523  Path('graphify-out/.graphify_labels.json').write_text(json.dumps(…), encoding="utf-8")
…
527  wrote = to_json(G, communities, 'graphify-out/graph.json', community_labels=labels)
528  if not wrote:
529      print('ERROR: refused to shrink graphify-out/graph.json (existing graph has more nodes; #479).')
530      print('If this shrink is intentional (you deleted files), re-run a full build with --force.')
531  print('Report updated with community labels')
```

Line 531 is at **indent 0** (confirmed with an explicit raw-bytes dump), so it runs
on the refusal path too. Two consequences:

1. `GRAPH_REPORT.md` and `.graphify_labels.json` were already written at 522-523,
   *before* the export was attempted, so on refusal they describe a graph
   `graph.json` does not contain.
2. The block exits 0 with `Report updated with community labels` as its last word.

**The file refutes itself twenty lines earlier.** Step 4, at `SKILL.md:436-444`,
has the correct shape and says why:

```
436  # Export FIRST and honor the #479 shrink-guard: to_json returns False (writing
437  # nothing) when the new graph is smaller than the existing graph.json. Only write
438  # GRAPH_REPORT.md + the analysis sidecar when the graph was actually written, so
439  # they never describe a graph that graph.json doesn't contain (#1392).
440  wrote = to_json(G, communities, 'graphify-out/graph.json')
441  if not wrote:
442      print('ERROR: …')
443      print('If this shrink is intentional …')
444      raise SystemExit(1)
```

Step 5 has no `raise SystemExit(1)`, and inverts Step 4's export-first ordering.
This is issue #1392 reintroduced one step over. Same upstream-origin adjudication as
F1 — the remedy is an addendum or an upstream report, not a hand-edit.

### F3 (P1, blocking) — tracking `.graphify_version` makes the `currency.apply` path produce a lint-failing commit

`.gitignore:76-88`, `.claude/skills/graphify/.graphify_version:1`,
`python/src/kb_setup/currency/apply.py:206-221`, `python/src/kb_setup/skill_refresh.py:61-66`

This commit un-ignores the stamp (`.gitignore`, the removed
`.claude/skills/graphify/.graphify_version` line) and commits it. Both callers of
`skill.refresh` then diverge:

- `skill_refresh.refresh` runs `mise run fmt` afterwards (`skill_refresh.py:62-66`);
- `currency.apply.apply` calls `skill.refresh(repo_root, spec)` at `apply.py:206`
  and returns at `apply.py:214-222` with **no formatting step at all**.

`currency.toml:51` sets `skill_install = ["mise", "exec", "--", "graphify", "install", "--project"]`,
so an ordinary auto-applied graphify bump takes the unformatted path.

**Independently verified at primary source, not from the author's comment.**
`install.py:229` and `install.py:860` in the installed 0.9.34:

```python
(skill_dst.parent / ".graphify_version").write_text(__version__, encoding="utf-8")
```

`__version__` is `"0.9.34"` — no trailing newline. The committed stamp at `5204e57`
*does* end in `\n` (confirmed with `od -c`), which is exactly the `mise run fmt` in
`skill_refresh.py` doing its job — direct evidence the raw installer output lacks it.

hk's `newlines` builtin is live at `hk.pkl:176`, and `.claude/skills/graphify/**`
appears in **neither** `baseExclude` (`hk.pkl:20-145`) nor `proseExclude`
(`hk.pkl:146-147`). So a `kb-currency` auto-apply bump of graphify now leaves a
tracked, newline-less file that fails `mise run lint` — the gate `kb-ship` blocks on.
Reachable on the ordinary path; introduced by this commit, because ignoring the file
is what previously made it unreachable.

### F4 (P1, blocking) — `kb-skill-refresh` exits 0 with known installer damage still in the working tree

`python/src/kb_setup/skill_refresh.py:73` (and `:56-66`)

```python
73    return 1 if result.lost_addenda else 0
```

`result.unrepaired` is **never consulted** anywhere in `skill_refresh.py`. Yet
`currency/skill.py:151-155` documents that field as:

> Paths the installer dirtied that are STILL dirty after the repair ran.
> Non-empty means damage is sitting in the working tree right now, and the
> only honest thing to do is name the files — a caller who commits after
> reading a cheerful note picks the damage up with the bump.

The refresh reaches that state on a successful install (`currency/skill.py:318`,
`repaired, unrepaired = _repair(repo_root)`), and `tests/test_currency_skill.py:144-176`
proves it is reachable — an untracked `_REPAIR` path yields
`result.unrepaired == ("CLAUDE.md",)` with `ran=True`.

The note printed at `skill_refresh.py:57` does contain `COULD NOT REVERT`, but the
task still exits **0**, and `skill_refresh.py:68` then tells the operator to go
commit. `tests/test_skill_refresh.py:5-6` states the exact principle this violates:
"every arm is about an exit code: a task that returns 0 after something went wrong is
how a broken skill reaches a commit." There is no test arm for the `unrepaired` case.

---

## P2

### F5 (P2) — an addendum destroyed by a *failing* installer is never detected

`python/src/kb_setup/currency/skill.py:297-316` vs `:318-323`

The installer-failure branch returns at `skill.py:307-316` after repairing only
`_REPAIR`. `_apply_addenda` is called at `skill.py:323`, i.e. only on the success
path. An installer that rewrites `references/query.md` and *then* exits nonzero
(the "half-finished installer" case `tests/test_currency_skill.py:194-217` says is
ordinary) therefore deletes the local paragraph while `lost_addenda` keeps its empty
default (`skill.py:150`). The caller gets `installer failed`, with no addendum-loss
warning — and `_skill_warnings` (`apply.py:126-131`) has nothing to report.

This is the same silent-loss shape the whole `ADDENDA` mechanism was built for
(`skill.py:37-51`), surviving on the one path it does not cover.

### F6 (P2) — the idempotence test cannot exhibit duplication; MUTATION-CONFIRMED

`tests/test_currency_skill.py:277-289`, fixture at `:247-261`

`_wipes` regenerates the addendum file from scratch on **every** invocation
(`:254-261`, `p.write_text(body)`), and the test runs that same installer before
both refreshes (`:283`, `:286`). The second installer run therefore deletes the first
insertion before `_apply_addenda` is reached, so `add.text in text` at
`skill.py:242` is never True and the guard is never exercised. The assertion
`body.count(_ADDENDUM.text) == 1` (`:289`) holds for an implementation that inserts
unconditionally.

**Control arm run (not asserted — measured).** I deleted the guard at
`currency/skill.py:242-243`:

```python
        if add.text in text:
            continue
```

`git diff --stat` confirmed the mutant differs at the intended lines (1 file, 2
deletions), so this is not a mis-targeted `str.replace`. Result:

- `uv run pytest tests/test_currency_skill.py -k "idempot or twice or no_addenda or live_addenda"` → **rc=0, mutation survived**
- `uv run pytest tests/test_currency_skill.py tests/test_skill_refresh.py` → **21 passed, rc=0, mutation survived**

So *nothing* in the new 244-line test surface covers `_apply_addenda`'s idempotence,
despite one test being named for it. File restored from a scratch copy; tree
re-verified clean at `5204e57` afterwards.

### F7 (P2) — the "no addenda configured" control arm returns before addendum code runs

`tests/test_currency_skill.py:321-330`

`_repo` creates only `.claude/skills/graphify` (`:25-26`), but the test passes
`_spec(skill_dir=".claude/skills/other")` (`:327`). `refresh` then returns at
`currency/skill.py:270-271`:

```python
    if not skill.is_dir():
        return SkillResult(ran=False, note=f"{spec.skill_dir} is not present — nothing to refresh")
```

`lost_addenda == ()` and `addenda == ()` (`:329-330`) are the dataclass defaults on
that early return (`skill.py:142-150`). Both assertions hold even if `_apply_addenda`
were deleted outright. The docstring claims it controls the crying-wolf direction;
the fixture never reaches the code that could cry wolf.

### F8 (P2) — `mise.toml` documents a unified-diff report that no code emits

`mise.toml:623-625`

> `# Restores are REPORTED, never silent: each protected file goes back to its`
> `# pre-install bytes AND the reverted delta prints as a unified diff, so a future`
> `# graphify that legitimately adds a hook cannot have it discarded without trace.`

No code prints a diff. `_repair` (`currency/skill.py:169-199`) runs
`git checkout --` and returns **path names only**; `skill_refresh.py` prints
`result.note` (`:57`) and the string `review \`git diff .claude/\` before committing`
(`:68`) — an instruction to the human, not a printed delta. A `grep -n "diff"` across
both modules returns only docstrings and that instruction.

The stated safety property — "a future graphify that legitimately adds a hook cannot
have it discarded without trace" — is therefore **not implemented**. A newly added
upstream hook is reverted with only the filename recorded.

### F9 (P2) — `mise.toml` claims `.claude/CLAUDE.md` is protected; it is not

`mise.toml:626-628` vs `python/src/kb_setup/currency/skill.py:86`

> `# `.claude/CLAUDE.md` is protected too and is NOT in #133's list — the installer`
> `# writes a `# graphify` block there, and that file is hand-authored and at its`
> `# `md_size_budget`, so an append breaks a gate rather than merely churning.`

But:

```python
86  _REPAIR = (".claude/settings.json", "CLAUDE.md")
```

`CLAUDE.md` is the **root** file — `currency/skill.py:88-91` and `:209` say so
explicitly ("a backup beside the ROOT `CLAUDE.md`, which is in `_REPAIR`"). The
pathspec `CLAUDE.md` does not match `.claude/CLAUDE.md`, so the file `mise.toml`
names is unprotected by `_repair`.

**Verified at primary source that the installer really does write it.** In the
installed 0.9.34 `install.py`:

- `:263` — `claude_md = project_dir / ".claude" / "CLAUDE.md"`
- `:629` — `claude_md = (project_dir / ".claude" / "CLAUDE.md") if project else Path.home() / ".claude" / "CLAUDE.md"`
- `:1708` — `target = (project_dir or Path(".")) / "CLAUDE.md"` (the ROOT one, which *is* covered)

So the installer writes **both**, and only one is in `_REPAIR`. `mise.toml`'s own
stated stakes make this the more expensive of the two: `.claude/CLAUDE.md` is
hand-authored and at its `md_size_budget`, so an installer append breaks a gate.

Not raised to P1 only because the append is marker-idempotent
(`_CLAUDE_MD_MARKER = "## graphify"`, `install.py:683`) and did not fire in this
commit — `.claude/CLAUDE.md` is absent from the diff. It fires the first time
upstream changes that block's content.

---

## P3

### F10 (P3) — absence assertion with no control arm

`tests/test_skill_refresh.py:87-88`

```python
87    src = Path(skill.__file__).read_text(encoding="utf-8")
88    assert "assert_pinned_graphify" not in src
```

A negative source grep with nothing proving the probe can produce the other answer.
It passes if `currency/skill.py` were emptied, renamed, or if the token were spelled
differently. `probes-need-a-control-arm.md` names this shape directly ("a TOKEN
SPELLING is a bound too"). Cheap fix: assert the same probe finds the token in
`skill_refresh.py`.

### F11 (P3) — the live-`ADDENDA` test asserts nothing when the mapping is empty

`tests/test_currency_skill.py:333-346`

The loop `for skill_dir, entries in skill.ADDENDA.items()` with
`if not (root / skill_dir).is_dir(): continue` (`:340-341`) executes **zero**
assertions if `ADDENDA` is empty — which is the deletion this test exists to catch.
Its own docstring says it guards "an `ADDENDA` entry whose anchor never existed in
the real file", but it does not guard the entry going missing. Add a counter and
assert it is nonzero.

Note: the arm does currently pass. I verified the live anchor and text are present in
the shipped tree — `git show 5204e57:.claude/skills/graphify/references/query.md`
carries `graphify path "NODE_A" "NODE_B"` at :197 and the addendum body at :200-202.

### F12 (P3) — `_wire` patches the stdlib `subprocess` module globally

`tests/test_skill_refresh.py:44-48`

```python
44    monkeypatch.setattr(
45        skill_refresh.subprocess,
46        "run",
47        lambda *_a, **_k: subprocess.CompletedProcess(["mise"], fmt_rc),
48    )
```

`skill_refresh` does a plain `import subprocess` (`skill_refresh.py:31`), so
`skill_refresh.subprocess` **is** `sys.modules["subprocess"]`. This replaces
`subprocess.run` process-wide for the duration, not just for the module under test.
Harmless today because the wired tests only call `skill_refresh.refresh`, but it is a
loaded gun for any future arm in the same test that needs a real subprocess —
`tests/test_currency_skill.py` runs real `git` through `subprocess.run`.

---

## Findings I checked and did NOT reproduce

- The `.gitignore` change is coherent: `.graphify_version` un-ignored and committed,
  `.claude/skills/**/.graphify_root` correctly left ignored (`.gitignore:88`). No
  broader pattern elsewhere re-ignores the stamp — the file is genuinely tracked at
  `5204e57`.
- `set_pin_version` / `_pin_line_matches` (`apply.py:60-104`) and the
  resolve-everything-before-writing ordering (`apply.py:178-192`) hold up; the
  `old != verdict.current` refusal at `apply.py:170-176` is a real TOCTOU guard.
- `_repair`'s retry-then-re-read design (`currency/skill.py:191-199`) is correct and
  is genuinely control-armed by `tests/test_currency_skill.py:144-176` plus its
  paired clean-case arm at `:179-191`. That pair is the strongest work in the diff.
- `_clear_backups`' non-recursive `_REPAIR`-parent glob (`skill.py:221-224`) does
  cover `.claude/CLAUDE.md.graphify-bak`, because `.claude/settings.json`'s parent is
  `.claude/`. F9 is about `_repair`, not about backups.
- `currency.toml`'s new `[[tool.claude-code.watch]]` block and the graphify serve-probe
  note parse fine and are internally consistent; `taplo` covers this file.

---

## UNCOVERED

### `sources/extractions/graphify-2026-08-06-docs.json` (+20,128 lines) — excluded from the codex batch, verified directly instead

Deliberately withheld from the review batch: it is corpus DATA — a
`{nodes, edges, hyperedges}` semantic extraction chunk — not executable behaviour,
and at 20,128 lines it would have blown the single-shot guard and degraded the review
of the 604 lines that *are* behaviour. It was **not** dropped silently. Verified
independently, reading the blob at the reviewed SHA
(`git show 5204e57:sources/extractions/graphify-2026-08-06-docs.json`, 814,126 bytes):

| check | result |
|---|---|
| parses as JSON | yes |
| top-level keys | `edges`, `hyperedges`, `input_tokens`, `nodes`, `output_tokens` |
| counts | 796 nodes, 1,099 edges, 45 hyperedges |
| nodes missing `id` | 0 |
| duplicate node ids | 0 |
| edges with unresolved `source` | 0 |
| edges with unresolved `target` | 0 |
| hyperedge members unresolved or empty | 0 |
| duplicate `(source, target, relation)` edges | 0 |
| self-loop edges | 0 |
| nodes with empty `label` | 0 |
| isolated nodes (in no edge and no hyperedge) | 0 |
| `_origin` stamping | `semantic` on all 796 — uniform, no unstamped node |

Every edge endpoint and every hyperedge member resolves within the file.

**Control arm — the verifier can produce the other answer.** A mutant of the same
blob (one edge target repointed to `__NO_SUCH_NODE__`, one hyperedge member set to
`__NO_SUCH_MEMBER__`, one node duplicated) run through the identical script:

```
duplicate node ids: 1 ['gfyagents_agents_md_contract']
edges w/ unresolved target: 1 [(0, '__NO_SUCH_NODE__')]
hyperedge members unresolved/empty: 1 [(0, '__NO_SUCH_MEMBER__', 'gfyagents_three_agent_rules')]
```

So the clean result above is a discriminating negative, not a probe that can only pass.

**Second, independent route — the repo's own gate.**
`mise run kb-validate-chunks -- sources/extractions/graphify-2026-08-06-docs.json`
→ `✓`, **rc=0** (read from a file, not a piped tail). Two routes agree.

No findings against the chunk.

### Nothing else uncovered

`docs/research/**` was excluded by the caller's own pathspec. Every other file in the
scoped diff went to codex in one batch. No hunk was truncated, and there are no
untracked files (the tree is clean at `5204e57`).

---

## Provenance of these findings

F1–F7 and F10–F11 originate with the codex lane (GPT-5.6 Sol), raw output at
`/var/folders/z4/0p475gq56vvczc3y4qlt60f80000gn/T/codex-review-final.XXXXXX.NcpYsf4ZDh`
(9 findings, all cited). F8, F9 and F12 are mine, found while spot-checking its
citations. Every codex citation was checked against `5204e57` and **all nine
resolved** — no phantom line numbers, no claim contradicted by the cited bytes.
Severities are my adjudication, not codex's: codex ranked F1/F2/F3/F4 as P1 and the
rest P2, and I lowered its two weakest test findings to P3 and added the
upstream-origin context for F1/F2 that changes their *remedy* without changing their
truth.

Nothing here has been refuted. The caller runs that pass.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read the installed 0.9.34 `install.py` (stamp write at `:229`/`:860`, `.claude/CLAUDE.md` writes at `:263`/`:629`, root `CLAUDE.md` at `:1708`, `_CLAUDE_MD_MARKER` at `:683`) and the `skill.md` installer template (`:517`) to establish whether the SKILL.md hunk was upstream-generated and whether the version stamp carries a trailing newline.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repository under review; commit `5204e57` against base `27bf691`.
- [jdx/hk](https://github.com/jdx/hk) — `hk.pkl` imports `Builtins.pkl` from release v1.54.0; consulted to confirm the `newlines` builtin is live and that the graphify skill tree is not excluded from it.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — named as the `github` source for the `[tool.claude-code]` currency entry whose `expected` moved 2.1.222 → 2.1.223 in this diff; its changelog claims were read only as diff content, not fetched.
