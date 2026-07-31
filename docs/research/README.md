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
| [`reports/2026-07-31-size-mtime-false-drift.md`](reports/2026-07-31-size-mtime-false-drift.md) | 2026-07-31 | Whether `size:mtime_ns` can fingerprint the corpus INPUTS (#89, a `Fluent` frontier ticket). It cannot: three ordinary git operations that leave the bytes identical move it, and on that class of operation it fires on every row — a probe that can only say DRIFT. sha256 discriminates on all eight cases and costs **1.8 ms** over 2.4 MB, against the 341 MB of outputs whose size is the whole reason the OUTPUT stamp uses a stat. Also settles that a fresh clone must short-circuit to *never built* before any input is compared, and that `git hash-object` is ~480x slower here than in-process `hashlib`. Corrects a locked map Note. |

## See also

- `.claude/rules/agent-report-persistence.md` — when to write one, and why verbatim.
- `.claude/rules/research-repo-enumeration.md` — every report ends with its
  `## GitHub repos touched` section; those repos feed `sources/REGISTRY.md`.
- `docs/currency/` — the tool-currency run log, which is engine-generated rather
  than agent-authored and therefore lives separately.
