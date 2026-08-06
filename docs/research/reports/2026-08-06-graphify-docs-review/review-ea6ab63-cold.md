# Cold review — commit `ea6ab63` (round 2 of 2)

- **Reviewed commit:** `ea6ab630bf6063bd96f5726d06b63fa376b8e283` (`ea6ab63`), which is HEAD and is checked out in the working tree.
- **Range:** `5204e57365b66440efc3d3c1b95df9a4f4dc4d23..ea6ab630bf6063bd96f5726d06b63fa376b8e283`, excluding `docs/research/**`.
- **Lane:** cold, cross-family — GPT-5.6 Sol via `codex exec review` (codex-cli 0.146.1), read-only sandbox.
- **Diff size:** 18,039 lines total in range; **568 lines** once `sources/extractions/**` is excluded. The code batch was reviewed whole (well under the 1,500-line guard).
- **Cold discipline:** codex was given the range and the repo's house rules only. No description of what the changes were meant to achieve, and no access to the round-1 report, was provided.

---

## Part A — Mechanical verification (measured by the reviewer, not delegated)

These two claims were supplied with the review request. Both were verified directly rather than trusted. Both **hold**.

### A1. `sources/extractions/graphify-2026-08-06-docs.json` is a pure `source_file` rewrite — CONFIRMED

Method: extracted both blobs (`git show <sha>:<path>`), parsed as JSON, compared structurally with every `source_file` value replaced by a sentinel.

| Measure | at `5204e57` | at `ea6ab63` |
|---|---|---|
| top-level keys | `edges, hyperedges, input_tokens, nodes, output_tokens` | identical |
| `nodes` | 796 | **796** |
| `edges` | 1099 | **1099** |
| `hyperedges` | 45 | **45** |
| distinct `source_file` values | 16 | **16** |
| total `source_file` occurrences | 1940 | **1940** |

- **Remainder is byte-identical.** With `source_file` blanked on both sides, the two documents compare **equal** (`bo == bn` → `True`). Zero divergences anywhere else in the tree.
- **Every value gained the prefix.** All 16 distinct values moved from `X` to `graphify/X`, and the per-value occurrence counts are unchanged one-for-one (e.g. `README.md` 375 → `graphify/README.md` 375; `AGENTS.md` 24 → `graphify/AGENTS.md` 24).
- **Line-level accounting corroborates it.** `git diff --numstat` reports `1940 1940` for this file. Of the added lines, **1940 of 1941** contain `source_file` (the one remainder is the `+++` file header); identical on the removal side. So the line diff is *exactly* the `source_file` lines and nothing else.
- **No discrepancy found.** The claim is accurate as stated.

**One value deserved a second look and is correct:** `graphify/skill.md` became `graphify/graphify/skill.md` (202 occurrences). The doubled segment is not a bug — the file genuinely lives at `sources/graphify/graphify/skill.md` in the pinned clone (`v0.9.34`, commit `07b9143d`), verified by `ls`. Relative to the source root the path really does contain `graphify/graphify/`.

### A2. Deletion of `sources/extractions/graphify-docs.json` loses nothing — CONFIRMED

The deleted chunk carried **43 nodes, 33 edges, 2 hyperedges** across 8 source files, with unprefixed `source_file` values.

- **No dangling references.** Scanned every `*.json` in `sources/extractions/` for any of the 43 deleted node ids appearing as a string anywhere (including edge endpoints and hyperedge members). Result: **zero hits in zero files.** Nothing in the corpus points at the removed ids.
- **All 8 covered files survive, far more densely.** Every file the deleted chunk touched is covered by the surviving dated chunk, at roughly 10x the node count:

| source file | deleted chunk | surviving chunk |
|---|---|---|
| `AGENTS.md` | 1 | 11 |
| `ARCHITECTURE.md` | 5 | 43 |
| `BENCHMARKS.md` | 7 | 35 |
| `README.md` | 8 | 165 |
| `SECURITY.md` | 7 | 44 |
| `docs/docker-mcp-sqlite.md` | 2 | 34 |
| `docs/how-it-works.md` | 10 | 36 |
| `docs/node-summaries-rfc.md` | 3 | 39 |
| **total** | **43** | **407** |

- **Concept coverage holds.** A label-text probe reported 37 of 43 deleted labels absent from the surviving chunk — but that probe is lexical, and **its control arm passed** (6 of 43 matched, so it can produce both answers). Following it up semantically, every substantive concept from the deleted labels is present in the surviving chunk: `ssrf`, `prompt injection`, `prompt-injection`, `locomo`, `longmemeval`, `god node`, `leiden`, `tree-sitter`, `path traversal`, `sanitize` — all `True`. The 37 "missing" labels are re-phrasings at finer granularity, not lost content.

**Conclusion:** the deletion is a supersede, not a loss. The only thing that does not survive is the 43 opaque node **ids**, and nothing references them.

---

## Part B — Cold-lane findings on the code diff

The cold lane returned **4 findings, all P2, and it marked all four blocking.** Every citation below was spot-checked against the working tree (which is `ea6ab63`). All four citations resolve and all four premises verify.

### B1 (P2, codex: blocking) — `repair_delta` is dropped by the `currency.apply` caller

`python/src/kb_setup/currency/skill.py:427` sets `repair_delta=delta` on the success path, and `python/src/kb_setup/skill_refresh.py:69-71` prints it. The other production caller does not: `python/src/kb_setup/currency/apply.py:210-213` builds its notes from `_skill_warnings(skill_result)` plus `skill_result.note`, and **`_skill_warnings` (`apply.py:107-133`) carries only `lost_addenda` and `unrepaired`** — verified by reading it. `repair_delta` is referenced nowhere in `apply.py`.

So on an auto-applied bump the installer's bytes are destroyed by `git checkout` at `skill.py:250-251` with only filenames surviving — precisely the state the field's own docstring at `skill.py:185-189` says must not happen ("A caller that shows only `repaired` names the files and loses the bytes").

**Reviewer note on severity.** The `mise.toml` prose that motivated this fix describes the `kb-skill-refresh` task, and that entry point *does* print the delta — so the documented contract is met for the path it documents. The gap is the *second* caller. Real, and an incomplete fix rather than a wrong one.

### B2 (P2, codex: blocking) — the version stamp is normalised only on the installer-success path

`_normalise_stamp` is called at `skill.py:411`, which is reached only after the failure-path `return` at `skill.py:394-407`. Verified in the installer: `sources/graphify/graphify/install.py:229` writes the stamp with `write_text(__version__, encoding="utf-8")` — **no trailing newline, confirmed by reading the line** — and it does so *inside* skill installation, before the `.claude/CLAUDE.md` registration at `install.py:627-641` and the root-`CLAUDE.md` work at `install.py:1706+`, any of which can fail afterwards.

Because `currency.apply` deliberately keeps the pin move after a failed refresh (`apply.py:200-210`, whose own comment says "a failure is REPORTED in the note while the pin still lands"), a late installer failure can leave the **tracked** stamp without its newline and reproduce exactly the hk `newlines` failure this function was added to prevent.

### B3 (P2, codex: blocking) — the diff capture's exit code is unchecked before the destructive checkout

At `skill.py:250`, `delta = _git(repo_root, "diff", "--", *dirty).stdout`. `_git` is defined at `skill.py:205-212` with **`check=False`** (verified), so a failing `git diff` returns empty stdout indistinguishably from a genuinely empty diff. The very next line, `skill.py:251`, runs `git checkout --` and destroys the bytes. The result can then report non-empty `repaired` alongside an empty `repair_delta`, which is the contract stated in the docstring at `skill.py:237-245`.

### B4 (P2, codex: blocking) — the new Step 5 addendum has no test; deleting its registration passes the whole suite — MUTATION-CONFIRMED

This is the sharpest finding, and it is a **new defect created by this round's own fixes**: the F11 remedy (`checked > 0`) and the F1/F2 remedy (the Step 5 `Addendum`) landed together, and the former does not cover the latter.

`tests/test_currency_skill.py:364` asserts only `checked > 0`. That aggregate is already satisfied by the pre-existing `references/query.md` addendum, so it says nothing about the new registration at `skill.py:151-173`.

**I ran the mutation rather than reasoning about it:**

1. Deleted `skill.py:151-173` — the entire Step 5 `Addendum(...)` entry — leaving the shipped warning in place at `.claude/skills/graphify/SKILL.md:491-507`.
2. Proved the mutant differs at the intended lines: `git diff --numstat` → `0 23`, and the hunk header is `@@ -148,29 +148,6 @@ ADDENDA: dict[str, tuple[Addendum, ...]] = {`, removing exactly the `path=".claude/skills/graphify/SKILL.md"` entry.
3. `uv run pytest tests/test_currency_skill.py tests/test_skill_refresh.py -q` → **28 passed, rc=0.**
4. `uv run pytest tests/ -q` (the FULL suite) → **rc=0. Nothing anywhere caught it.**
5. Restored; `git status --porcelain` empty, `git rev-parse HEAD` still `ea6ab63`.

**Control arm, so the survival claim is precise.** I then broke the addendum's `anchor` string instead (`"### Step 5 - Label communities\n"` → `…MUTANT\n"`, a one-line change at `skill.py:153`) and re-ran the same test: **rc=1**, `AssertionError: .claude/skills/graphify/SKILL.md: anchor missing from the shipped file`. So the test *can* fail — it discriminates on content mismatch but is blind to deletion of the registration.

**Why it matters:** an unregistered addendum is silently erased by the next `mise run kb-skill-refresh`, because the skill tree is regenerated. The warning would vanish from `SKILL.md` with no test, no gate, and no diff signal that a local note was dropped — the exact failure `lost_addenda` exists to catch, arriving through the one door it does not watch.

---

## Part C — Reviewer-found finding (not from the cold lane)

### C1 (P3, not blocking) — a comment labelled `CONTROL ARM` that asserts nothing

`tests/test_currency_skill.py:448` reads `# CONTROL ARM: the installer really did write it without one.` — but no assertion follows that checks the fixture actually produced a newline-less stamp. The test writes it via `printf '0.9.34' > …` at `tests/test_currency_skill.py:444-446` and then asserts only the post-condition at `:452`.

**Mutation-checked, and the test is genuinely live:** neutering `_normalise_stamp`'s body (`skill.py:303-304` → `return`) makes it **fail, rc=1**, with `+ 0.9.34` in the assertion diff. So this is not a dead check today.

The defect is narrower and forward-looking: because the fixture's no-newline property is never asserted, anyone later editing that `printf` to include `\n` silently converts a live check into one that can only pass, with a comment still claiming a control arm is present. Under this repo's own `probes-need-a-control-arm.md` rule 5 ("say which arm you ran"), a stated control arm that is not asserted is the thing the rule warns about. One line — asserting the stamp lacks its newline immediately after the installer runs and before normalisation is observed — would make the label true.

---

## Part D — House-rule sweep (reviewer-run)

- **Inline lint suppressions:** none. Swept `noqa` / `type: ignore` / `ty: ignore` / `nosec` across all four changed python files — zero hits.
- **Zero-bash-logic in `mise.toml`:** the changed task's `run` is `run = "uv run kb-setup skill-refresh"` (`mise.toml:646`) — a single command, no loop, conditional, or `&&` chain. The 24-line change to that block is comment prose only. Compliant.
- **graphify through `kb-*` tasks:** the added `SKILL.md` addendum actively *strengthens* this invariant — it redirects Step 5 away from graphify's bundled interpreter to `mise run kb-label`.
- **`_normalise_stamp` path resolution** (not flagged by codex; checked because a wrong path would make the fix a silent no-op): `repo_root / spec.skill_dir / ".graphify_version"` with `skill_dir = ".claude/skills/graphify"` (`currency.toml:41`) matches the installer's `skill_dst.parent / ".graphify_version"` (`install.py:229`). The shipped file is tracked and currently reads `b'0.9.34\n'` — correct.

---

## Verdict

**4 findings from the cold lane (all P2, all marked blocking by it) + 1 reviewer-found P3. No P1.**

The one I would not ship without is **B4** — it is mutation-confirmed against the full suite, and it is a defect this round's own fixes introduced. B1/B2/B3 are all the same shape: a round-1 fix applied correctly at one of two call sites or one of two code paths. None of them is wrong where it was applied; each is incomplete.

C1 is advisory and should not block.

---

## Provenance

- Cold lane: GPT-5.6 Sol via `codex exec review`, codex-cli **0.146.1**, `model_reasoning_effort=high`, `sandbox_mode="read-only"`, standard service tier. Exit marker `EXIT: 0`; watchdog did not fire.
- The lane was given the commit range, the repo's house rules, and a test-quality standard — and **no** description of what the changes were meant to achieve, and no access to `review-5204e57-cold.md`.
- Round-1 report consulted only AFTER findings were formed, and only to check whether a fix introduced a new defect. That check is what frames B4.
- All mutations were run by the reviewer (the codex lane is read-only and cannot mutate). Tree verified clean at `ea6ab63` after every arm.

## UNCOVERED

- `sources/extractions/graphify-2026-08-06-docs.json` — excluded from the codex batch by instruction; **verified directly instead**, see Part A1. Nothing about it is unreviewed.
- `sources/extractions/graphify-docs.json` (deleted) — verified directly, see Part A2.
- `docs/research/**` — excluded from the range by instruction.
- Nothing else. The 568-line code diff was reviewed whole, in a single batch.

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read `graphify/install.py` at the pinned `v0.9.34` (`07b9143d`) to verify the stamp write at `:229`, the `.claude/CLAUDE.md` registration at `:627-641`, and the root-`CLAUDE.md` path at `:1706+`; also confirmed `graphify/graphify/skill.md` exists, validating the doubled path prefix.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repository under review.
