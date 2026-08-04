# Research artifacts — verbatim agent reports

Findings-bearing subagent reports, kept **verbatim** and **tracked**, per
`.claude/rules/agent-report-persistence.md`.

## Why these are in `docs/` and not `.agent/`

`.agent/**` is gitignored: it does not survive a fresh clone and any
`git clean -xdf` removes it. That is correct for scratch, and wrong for a
report a future session will be sent to read. Two of the artifacts here are
already cited from tracked files — `currency.toml`'s `[tool.mise]` block rests
on the v2026.7.x review — and a citation to something only one machine can open
is not a citation.

So: a report stays in `.agent/kb/reports/agents/` while the session is running
(that is where the rule says to write it at receipt), and is **promoted here
when it turns out to be load-bearing**. Promotion is a copy, not a move; the
`.agent/` original is disposable.

## What must not happen to these files

**They are not normalised, reflowed, spell-corrected, or trimmed.** They are a
record of what an agent actually reported, including its evidence tables, probe
transcripts, and command lines. Editing them to tidy a link or a typo destroys
the thing they exist to preserve.

**Annotating is different from editing, and is encouraged.** When a finding is
later refuted or superseded, add a clearly-marked caller's annotation *above*
the affected section and leave the original text beneath it — see the box at
the top of `reports/mise-path-research.md` § Q1, which records that a
well-cited recommendation was measured to be wrong for our conditions. A reader
needs to see both the claim and its refutation to judge either.

## Index

| Artifact | Date | What it settles |
|---|---|---|
| [`reports/mise-currency.md`](reports/mise-currency.md) | 2026-07-27 | Every published `v2026.7.x` mise release reviewed (13 of them; 7.8–7.10 were never published). Groups them by whether they could have changed behaviour under us, breaking changes with applicability, regressions introduced-and-fixed inside the line, task features worth adopting, and what mise offers for detecting that it changed underfoot. Underpins `currency.toml` `[tool.mise]` and `mise.toml`'s `min_version` floor. |
| [`reports/mise-path-research.md`](reports/mise-path-research.md) | 2026-07-27 | Whether mise exposes the caller's pre-mise `PATH`. **Read the annotation box first** — its headline `get_env(name='PATH')` recommendation is correct under `env -i` and wrong under an activated shell, where `PRISTINE_ENV` strips the very install dirs a drift check hunts. Also settles `__MISE_DIFF`'s secret exposure as expected upstream behaviour with no fix pending. |
| [`reports/refuter-exe.md`](reports/refuter-exe.md) | 2026-07-27 | Adversarial verification of the `graphify_exe` / launcher work (earlier session, PRs #43/#45). |
| [`reports/refuter-tmux.md`](reports/refuter-tmux.md) | 2026-07-27 | Adversarial verification of the tmux `PATH`-inheritance mechanism (earlier session, #40/#45). |
| [`reports/2026-07-28-receipt-exempt-artifacts/`](reports/2026-07-28-receipt-exempt-artifacts/README.md) | 2026-07-28 | Ten lane reports across four review passes over #66 (PR #69). Underpins `.gitleaks.toml`'s allowlist scoping and `hk.pkl`'s `exclude`/`proseExclude` split — both rest on measurements taken here, including that **`gitleaks dir` ignores its path arguments once there is more than one**. Round 1 found three live credentials in a work-memory file that every gate was green over; its SHA is deliberately unreachable, the reports are not. |
| [`reports/2026-07-31-hk-currency.md`](reports/2026-07-31-hk-currency.md) | 2026-07-31 | What tracking hk requires (#87). **Read the annotation box first** — five of its claims are corrected there, including a flatly wrong one (`kind = "issue"` is NOT impossible for hk; a PR number resolves at 200) that `currency.toml` already disproves. What survives: **hk 1.53.0 (#1099) fixed the deadlock** behind this repo's `no depends` ban, so the ban is now a choice rather than a workaround — though the deadlock needed a `depends` edge this repo never had, so it could not have fired here. Also that `hk_version_parity` does not port (one `.pkl` here, three in dotfiles), and that the hk version is written **three times across two files**. |
| [`reports/2026-07-31-size-mtime-false-drift.md`](reports/2026-07-31-size-mtime-false-drift.md) | 2026-07-31 | Whether `size:mtime_ns` can fingerprint the corpus INPUTS (#89, a `Fluent` frontier ticket). It cannot: three ordinary git operations that leave the bytes identical move it, and on that class of operation it fires on every row — a probe that can only say DRIFT. sha256 discriminates on all eight cases and costs **1.8 ms** over 2.4 MB, against the 341 MB of outputs whose size is the whole reason the OUTPUT stamp uses a stat. Also settles that a fresh clone must short-circuit to *never built* before any input is compared, and that `git hash-object` is ~480x slower here than in-process `hashlib`. Corrects a locked map Note. |
| [`reports/2026-08-04-kb-session-state-mutation-arms.md`](reports/2026-08-04-kb-session-state-mutation-arms.md) | 2026-08-04 | The mutation evidence for `kb-session-state` (#144). **18 of 18 arms died**, control green, restored green. Its headline is a correction, not a discovery: the `__pycache__` `(mtime, size)` defect recurred for the **THIRD** time, and the #146 report had already predicted it — *"if a third harness is written, it should import this one rather than restate it"*. A third was written, in a scratchpad, and restated it. The remedy "write it down" has now failed twice running, so the fix is structural (a `kb_setup` module with a test), filed not built. Also: a rename fixture that **could not exhibit its own harm** (the un-consumed origin field yields a spurious entry while the later path still parses, so the intuitive assertion passes with the bug present), and mise redaction measured on both transports — it mangles **SHAs and PR numbers**, not just the branch, which is what four disclosure sites originally understated. |
| [`reports/2026-08-04-kb-gates-mutation-arms.md`](reports/2026-08-04-kb-gates-mutation-arms.md) | 2026-08-04 | The mutation evidence for `kb-gates` (#146). **20 of 20 arms caught, after two probes lied in opposite directions.** One arm SURVIVED honestly — `GateResult.passed` accepting a never-ran gate is unreachable end-to-end, because `stopped` is only set after a failure, so the property was a dead detector with a confident docstring; it is now pinned on the dataclass rather than deleted. The other SURVIVED falsely: this harness was written without the `__pycache__` invalidation the #145 harness already had, so a same-size mutation was served the previous arm's bytecode. A regression of a written-down lesson, not a discovery. |
| [`reports/2026-08-04-kb-handoff-check-mutation-arms.md`](reports/2026-08-04-kb-handoff-check-mutation-arms.md) | 2026-08-04 | The mutation evidence for `kb-handoff-check` (#145, extended to 45 arms by #154), with the harness itself so the table can be re-derived rather than believed. **45 of 45 discriminated, row 0 a no-op CONTROL** that must leave the suite green. **Read the "declared no-op" section first** — for two rounds this said 41 of 42, with one arm recorded as unreachable *by construction* from a chain of true premises that never asked whether a known extension ends in a DIGIT. `mp3` does, so `foo.mp:3` repaired to `foo.mp3` and the guard was live all along; the arm had merely been pointed at a fixture that could not exhibit the harm. That guard has since been retired — an alphanumeric-extension rule subsumes it, and two guards for one property mask each other's mutations — but the lesson is the durable part: **"unreachable by construction" is a claim needing an arm like any other.** Rows 0–31 were re-asserted against the harness's own `MUTATIONS` list rather than retyped, and all 32 agreed — without it a harness broken in any uniform way (a bad path, an unresolvable `uv run`) reads as total success, which is how four arms in an earlier round "died" at once to zsh word-splitting. Clears every `__pycache__` per arm because CPython invalidates on `(mtime, size)`, so a line-swap mutation is otherwise served stale bytecode and reports a false pass. |
| [`reports/2026-08-04-silent-failure-extension-typo.md`](reports/2026-08-04-silent-failure-extension-typo.md) | 2026-08-04 | The silent-failure lane over #154, promoted because **#158 rests on its control-armed probe** and a tracked issue may not cite evidence only one machine can open. Its subject is deliberate silence, which is that feature's core mechanism, and it found **5 defects in code two prior review rounds had already passed** — including that the `` (absent) `` marker had become UNFALSIFIABLE for the new check while the tool printed *"the marker is checked both ways"* beside it, and that three of the four were the OPPOSITE of the risk the design argued about: the module reasons carefully about under-reporting and where it went wrong it **over**-reported, asserting `no file named X` about tokens its own index could resolve. Also worth reading for what it CLEARED with control arms — the two extractors are disjoint over 386 files, non-vacuously. Its F6 is the pre-existing defect filed as #158. |
| [`reports/2026-08-04-kb-handoff-gate-claims-mutation-arms.md`](reports/2026-08-04-kb-handoff-gate-claims-mutation-arms.md) | 2026-08-04 | The mutation evidence for #147's gate-claim verification — the second checker in `kb-handoff-check`, and the one that reads a RECORD rather than the filesystem. **19 arms, 17 caught by single-site mutation.** The two that SURVIVED are the report's subject rather than its footnote: they are **one property guarded at two sites**, so each mutation alone is a no-op and only mutating both at once demonstrates the property is armed — a bare count would have scored defended code as unarmed. Four further arms first reported SURVIVED and were each traced to the PROBE, not the code. Both tables are **generated from the harness's own `ARMS` list** and asserted row-for-row against the run log, per `probes-need-a-control-arm.md` rule 8. Indexed here by #157; it landed tracked in #156 but was never added to this table. |

## See also

- `.claude/rules/agent-report-persistence.md` — when to write one, and why verbatim.
- `.claude/rules/research-repo-enumeration.md` — every report ends with its
  `## GitHub repos touched` section; those repos feed `sources/REGISTRY.md`.
- `docs/currency/` — the tool-currency run log, which is engine-generated rather
  than agent-authored and therefore lives separately.
