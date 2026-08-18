# Refutation attempt — lane `tooling-gap` (agy cold lane has no wrapper)

CLAIM: "The cross-family cold-review lane (`agy`) is invoked by hand-constructing its
full CLI flag string every time, with no mise task or kb_setup module wrapping it --
the invocation, timeout choice, and scratch-file naming are all re-derived per call."

## Probe 1 — the offered control arm is BOUNDED (confirmed defect in the probe)

    grep -rn agy python/src/kb_setup/*.py mise.toml

`python/src/kb_setup/*.py` is a depth-1 glob. Re-derived:

    $ find python/src/kb_setup -name '*.py' | wc -l          -> 90
    $ find python/src/kb_setup -name '*.py' -mindepth 2 | wc  -> 20+ (currency/, generated/)

So the control arm could not see `kb_setup/currency/**` at all. UNBOUNDED re-run:

    $ grep -rn "agy" python/
    python/src/kb_setup/eval_cases.py:44:DECLARED_LANES = ("codex", "agy", "grok")

Control (same shape, token known present): `grep -rn "codex" python/` -> 20+ hits across
skill_lint.py, review.py, skillopt_reviewed.py, graphify_sdk.py. Probe discriminates.
=> The bound did NOT change the answer. That half of the finding survives.

## Probe 2 — mise task list, re-derived unbounded

    $ mise tasks --no-header | wc -l                       -> 78
    $ mise tasks --no-header | grep -iE "review|cold|lane|agy|anti"
      brain-remember / eval / kb-graphify-* / kb-land / kb-review-receipt / kb-ship /
      kb-skillopt-* / kb-tool-sync
    (no task invokes agy)
=> That half survives too.

## Probe 3 — TOKEN SPELLING. The wrapper is not spelled `agy`.

    $ grep -ril "antigravity" . (excl graphify-out/sources/.git/raw/.venv)
    -> .claude/rules/ai-cli-invocation.md, .claude/settings.json (enabledPlugins),
       brain/lane-antigravity.md, .claude/skills/orchestrator-routing/SKILL.md, ...

`.claude/settings.json:81`  "antigravity@antigravity-for-claude-code": true  (ENABLED)

The enabled plugin ships an executable wrapper family, on PATH:

    $ which agy-delegate
    /Users/rmanaloto/.claude/plugins/cache/antigravity-for-claude-code/antigravity/0.23.0/bin/agy-delegate
    rc=0
    $ ls ~/.claude/plugins/marketplaces/antigravity-for-claude-code/bin/
    agy-cost-compare agy-delegate agy-doctor agy-job agy-media agy-migrate agy-trace ...

Control arm for that `which`: `which agy-delegate` returns rc=0 with a real path; a
bogus name returns rc=1 (see probe 3b below).

The wrapper owns EXACTLY the three things the finding says are re-derived per call
(~/.claude/plugins/marketplaces/antigravity-for-claude-code/skills/antigravity/SKILL.md):

- L88-95  invocation shape: `agy-delegate [options] "the task prompt"`;
          "The wrapper handles agy's quirks (prompt is the value of `-p`; non-TTY stdout
          drop via `< /dev/null`)"  -> INVOCATION is wrapped.
- L93     `--timeout 10m`                                   -> TIMEOUT CHOICE is a flag.
- L105    `--print-command` (dry run: show the resolved `agy` call)
- L118+   `AGY_USAGE_LOG=/path/to/log` — "A named file cannot be truncated by a pipe."
- L147    `agy-job status`/`result`                          -> SCRATCH/RESULT NAMING is
          owned by the wrapper, not re-derived.
- L138-145 structured exit codes 10 quota / 11 auth / 12 timeout / 13 agy-missing /
          14 model-unavailable / 15 permission-denied.

And this repo's OWN rule already says to use it:
  .claude/rules/ai-cli-invocation.md — "Drive it through the `antigravity` plugin's
  skills ... rather than hand-rolling flags — the plugin owns the invocation shape and
  the cost discipline."

=> The finding's premise ("no wrapper -- all re-derived per call") is REFUTED as stated.
   A wrapper exists, is installed, is enabled, is on PATH, and is mandated by a rule
   already in this repo's eager context. What is true is the NARROWER claim: no *mise
   task / kb_setup module*, and the session did not USE the wrapper it had.

## Probe 4 — the DECISIVE arm: dry-run the existing wrapper

    $ agy-delegate --print-command --tier flash --timeout 30m --mode plan --dir "$PWD" "cold review probe"
    agy --model Gemini\ 3.5\ Flash\ \(High\) --print-timeout 30m --add-dir /Users/.../knowledge-base --mode plan -p cold\ review\ probe
    rc=0

CONTROL ARM (the probe must discriminate, i.e. not emit a constant string):

    $ agy-delegate --print-command --tier pro --timeout 5m "other prompt"
    agy --model Gemini\ 3.1\ Pro\ \(High\) --print-timeout 5m -p other\ prompt
    rc=0
    $ which agy-nonexistent-control  -> "not found", rc=1   (so `which` discriminates)

The wrapper emits the SAME `--print-timeout <N>m / --mode plan / --add-dir / -p` shape the
session hand-typed 8 times. Timeout and model are FLAGS it resolves, not values re-derived.

## Probe 5 — the finding's own recommendation is a reinvention

tooling-gap.md L73-80 proposes `kb_setup.cold_lane` + `mise run kb-cold-review` doing
(a) version check (b) fixed flags (c) derived report filename (d) uniform rc (e) gotcha
comment. Every one already exists in the enabled plugin:

| proposed | already shipped |
|---|---|
| (a) verify `agy --version` vs pin | `agy-doctor`; SKILL.md L63-68 — on agy ≥1.1.11 it asks agy via `-p /model` which model it would actually run |
| (b) fixed flags | `--tier/--mode/--yolo/--dir`, resolved by `agy-delegate` (probe 4) |
| (c) derived report filename | `agy-job.sh:15` — "Jobs live under ${ANTIGRAVITY_JOBS:-~/.antigravity-jobs}/<id>/ (out, err, rc, meta)"; plus `AGY_USAGE_LOG` |
| (d) uniform rc | SKILL.md L138-145 — exits 10 quota/11 auth/12 timeout/13 missing/14 model-unavailable/15 permission-denied, from the structured envelope |
| (e) `--mode plan` gotcha | SKILL.md L98-101 documents `--mode accept-edits\|plan` semantics |

`use-tool-builtins.md` is the rule this recommendation walks into: research the existing
tool BEFORE writing custom code. The finding never probed the plugin it names nowhere.

## Probe 6 — evidence-count inconsistency (minor)

The finding says "8 distinct full invocations at lines 6,7,11,13,66,211,332,1129,1457,1769"
— that is TEN line numbers for a count of eight. Re-derived with `grep -n "\bagy\b"`:
lines 5,6,7 are liveness/`--help` probes, 208 is `agy --version`/`agy models`, 339/2065/2067
are prose. The 8 real lane invocations are 11,13,66,211,332,1129,1457,1769. Count correct,
cited line list wrong.

## What SURVIVES (do not over-read this refutation)

- No mise task (`mise tasks | wc -l` -> 78, none agy-shaped) and no kb_setup module. TRUE.
- The session did hand-construct 8 times with drifting flags (20m/20m/20m/40m/40m/30m/30m/25m;
  `--effort high` present at 13,66 and absent after; `mise exec --` prefix only from 208 on).
  TRUE.
- Residual gap the wrapper does NOT close: pin verification against `mise.toml`.
  `which -a agy` -> mise install 1.1.11 FIRST in this shell, but `~/.local/bin/agy` is also
  present (the shadow mise.toml:116-127 documents), and `agy-delegate` execs bare `agy`.
  `mise which agy` -> .../antigravity-cli/1.1.11/agy — note this is 1.1.11, while the
  recorded pin is 1.1.13.

## VERDICT: refuted = true

The claim as worded ("no ... wrapping it -- the invocation, timeout choice, and scratch-file
naming are all re-derived per call") is false. An installed, enabled, PATH-resolved wrapper
(`agy-delegate` 0.23.0, plus `agy-job`, `agy-doctor`, `agy-cost-compare`) owns all three, and
this repo's own eager rule `.claude/rules/ai-cli-invocation.md` already mandates using it.
The true finding is narrower and different in kind: **an existing wrapper was not used**, not
**no wrapper exists** — and the remedy is "use `agy-delegate`", not "build `kb_setup.cold_lane`".
