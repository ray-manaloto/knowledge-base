# Premise verification — spec for issue #750 (bind a kb-review receipt to the observed reviewer model)

- **Verifier**: `fable-orchestrator:premise-verifier` shape, run as a teammate agent.
- **Repo**: `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base`
- **Branch/commit read**: `feat/codex-model-provenance` @ `c85b7fcb43dfae16b21cc542fffbbe6e56846b7d` (clean tree, verified `git status --short` empty).
- **Note on the issue's anchors**: issue #750 says "all four verified to exist at `3c0f5ce83096`". That is a DIFFERENT commit from the branch HEAD I was given. Every line number below was re-read at `c85b7fcb`, not inherited.
- **Status**: IN PROGRESS (written incrementally per `agent-report-persistence.md` rule 3).

---

## Per-row verdicts

### I rows (interface / signature)

| # | row | verdict | evidence |
|---|---|---|---|
| I1 | `_all_reasons(repo_root: Path, data: dict[str, Any], sha: str) -> str \| None` — review.py:413 | **CONFIRMED, exact** | `python/src/kb_setup/review.py:413` — signature matches character-for-character. |
| I2 | `def _run_review(args: argparse.Namespace) -> int` — codex_run.py:526 | **CONFIRMED, exact** | `python/src/kb_setup/codex_run.py:526`. |
| I3 | `receipt_state(repo_root, sha, *, require_base: str \| None = None) -> tuple[bool, str]` — review.py:1363-1365 | **CONFIRMED, exact** | `python/src/kb_setup/review.py:1363-1365` (3-line signature). |
| I4 | `def _tee(stream: IO[str], path: Path) -> None` — codex_run.py:235 | **CONFIRMED, exact** | `python/src/kb_setup/codex_run.py:235`. |
| I5 | `_spawn(..., tee: Path \| None = None, ...)` — codex_run.py:**266-268** | **CONFIRMED with CORRECTED ANCHOR** | The function is `def _spawn(` at `codex_run.py:261`, not 266. 266-268 are the tail of its signature (`tee: Path \| None = None` / `) -> int:` / docstring opening). Behaviour claim is right: it returns the child's own exit code, is bounded by `timeout`, and tees optionally (`codex_run.py:261-268`, docstring `:268-283`). **Cite 261 for the definition.** |

### L rows (literal / location)

| # | row | verdict | evidence |
|---|---|---|---|
| L1 | `LANES = ("standards", "spec", "cold", "silent-failure")` — review.py:110 | **CONFIRMED, exact** | `python/src/kb_setup/review.py:110`. |
| L2 | `EXEMPT_PATHS = ("graphify-out/memory/", "docs/goals/README.md")` — review.py:145 | **CONFIRMED, exact** | `python/src/kb_setup/review.py:145`. |
| L3 | `GATE_TASKS` tuple beginning "lint", "test", "brain-audit" — gates.py:173-176 | **CONFIRMED, exact** | `python/src/kb_setup/gates.py:173` `GATE_TASKS = (`, `:174` `"lint",`, `:175` `"test",`, `:176` `"brain-audit",`. Full tuple continues to `"eval"`, `"graph-size"`, `"hk-test"`, `"funnel"`, `"kb-manifest-audit"`, `"kb-graphify-catalog"` (10 gates). |
| L4 | `python/src/kb_setup/codex_review_evidence.py` does NOT exist | **CONFIRMED** | `ls` → `No such file or directory`; full `python/src/kb_setup/` listing carries no such name. |

### P rows (precedent)

| # | row | verdict | evidence |
|---|---|---|---|
| P1 | explicit `env = {...}` for a subprocess — skillopt_contract.py:424 | **CONFIRMED, exact** | `python/src/kb_setup/skillopt_contract.py:424` is `env = {`; the dict pins `HOME`, `PATH`, all four `XDG_*`, a canary and `PYTHONDONTWRITEBYTECODE`, and is passed to `subprocess.run(argv, cwd=project, env=env, ...)` at `:435-440`. DATA-level match holds. |
| P2 | `_spawn` refuses stdin+tee rather than defaulting — codex_run.py:286-287 | **CONFIRMED, exact** | `codex_run.py:286` `if prompt is not None and tee is not None:` / `:287` `raise ValueError("_spawn cannot write stdin and tee the output stream in one call")`. Rationale documented `:280-284`. |

### E rows (emitted values)

| # | row | verdict | evidence |
|---|---|---|---|
| E1 | evidence record ← the review attempt | **PARTIALLY SETTLED — bound still absent** | *Distribution* IS bounded and the spec did not say so: `.agent/` is gitignored at `.gitignore:190`, so the record never enters git and never reaches GitHub. *Size* is unbounded and unspecified — nothing in the repo bounds a diagnostics field, though the idiom exists (`cli.py:763` `_MAX_COUNT_DIGITS = 18`, with its reason stated `:759-762`). **PII: LOW-BUT-NOT-NONE is right, and there is a sharper hazard the row misses** — the "immutable output path" points at a `_tee` file that holds the lane's **merged stdout AND stderr** (`codex_run.py:294`, `:312` `stderr=subprocess.STDOUT`), and that module's own comment (`:309-311`) records the accepted cost: *"hook warnings and MCP errors now land in the report too."* So the record must carry the **path** and never inlined content. Also: the METHOD/instructions file (`/tmp/astra-method.txt` per `.claude/agents/kb-codex-astra-reviewer.md:67`) must not be copied in. |
| E2 | receipt field ← a REFERENCE to the record | **CONFIRMED FEASIBLE** | `Receipt.as_payload()` is an explicit dict literal (`review.py:271-282`); adding a key is one line. No test pins the key SET — `tests/test_review.py:503-504` asserts only stamp stability and idempotence. So the schema change is safe. |

### A rows (assumptions)

| # | row | verdict | evidence |
|---|---|---|---|
| A1 | `turn_context.model` names the reviewer sub-agent; `source == {"subagent":"review"}` + `parent_thread_id` identifies it | **ASSUMED — report-sourced, correctly labelled, AND NARROWER THAN THE SPEC USES IT** | I did not invoke codex this session. The report's F7/F8 (`docs/research/reports/2026-09-10-codex-model-provenance-advisor.md:120-170`) is a genuine 3-arm live measurement with a control arm and a historical 2-Sol/2-Astra discriminator, which is strong. **But every arm ran `mise run kb-codex -- --review`, i.e. `codex review`.** See MISSING-1: that is not the invocation the default cold lane uses. |
| A2 | a recorded model does not prove completion | **ASSUMED (report-sourced) — and INDEPENDENTLY STRENGTHENED by code** | `_run_review` returns `_spawn(...)` unchanged (`codex_run.py:606-610`), and `_spawn` returns `_RC_TIMED_OUT` on its bound, so a truncated review already yields a nonzero rc at the collection point. Note also the #678 failure shape the module documents (`codex_run.py:243-246`): *"the flag was accepted, the run returned rc 0, and no file existed"* — so rc alone is not completion either. |
| A3 | rollout schema stable within a release, unstable across | **ASSUMED — unknowable by probe, correctly labelled** | No probe can settle it. Independent support for the *versioning* half: the plugin supervisor's own comment (`run-lane.sh:99-101`) records that *"an unknown -c key would be silently dropped, so re-verify on CLI upgrades"* — same hazard class, already bitten once. |
| A4 | `$CODEX_HOME` may differ from `~/.codex` | **CONFIRMED — upgrade this from ASSUMED, with a citation** | Not merely an invariant-derived caution: `python/src/kb_setup/skillopt_reviewed.py:824` already sets `"CODEX_HOME": str(run_root / "codex")` for a subprocess **in this repo**. And `_spawn` passes `env=os.environ.copy()` (`codex_run.py:314`), so the child sees the parent's `CODEX_HOME` — the collector must read `os.environ.get("CODEX_HOME")`, never `~/.codex`, and never a re-derived value. |

---

## MISSING — premises the spec does not list

Ordered by how much they change the design.

### 🔴 M1 — the collection point covers ONE lane variant, and NOT the default one

This is the finding that most threatens the design. The spec puts **collection** at
`codex_run.py:526` (`_run_review`) and **enforcement** in `_all_reasons`, which gates
*every* receipt. Those two scopes do not match.

`_run_review` is reached only when `--review` is passed (`codex_run.py:657-658`,
`if args.review: return _run_review(args)`). Who passes it:

| receipt lane | who runs it | actual command | reaches `_run_review`? |
|---|---|---|---|
| `cold:codex-astra` | `.claude/agents/kb-codex-astra-reviewer.md:71-79` | `mise run kb-codex -- --review …` → `codex review` + `-c review_model=` | **yes** |
| `cold:codex` (**the default**) | `fable-orchestrator:codex-reviewer` plugin agent → `run-lane.sh start codex-review` | **`codex exec review --model <X> … --json`** (`~/.claude/plugins/marketplaces/fable-orchestrator/scripts/run-lane.sh:112-113`) | **no** |
| `cold:antigravity` | `antigravity:review` (agy/Gemini) | no codex process at all | **no** |
| `cold:claude-fallback-…` | Claude Opus subagent — the documented terminal fallback (`review.py:107-109`) | no codex process at all | **no** |

The routing table that picks between them is `.claude/skills/kb-review/SKILL.md:126-129`,
and its middle row says a **codex-authored** branch routes to `antigravity:review` —
which `.claude/CLAUDE.md` makes the declared default for orchestrator-driven work
(`fable-orchestrator: implementation lane = codex`).

Four consequences:

1. **Enforcement in `_all_reasons` would refuse three of the four cold variants outright**, including the default one, because no evidence record can exist for them. That is not "fail closed", it is a shipping outage for the ordinary path.
2. **The join key is invocation-specific.** `source == {"subagent":"review"}` was measured under `codex review`. Whether `codex exec review` produces the same `session_meta` shape is **UNMEASURED** — plausible (same underlying review task) but I did not probe it, and the spec treats it as universal.
3. **The default lane already has a different, possibly better observable**: `--json` makes its `LOG` a JSONL event stream (`run-lane.sh:104-106`). The advisor's F6 (*"`codex review` has no `--json`"*) is true and correctly scoped, but the spec inherits it as if it covered every review path. It does not.
4. **The default lane's model channel is a different flag** — `--model` on `codex exec` (`run-lane.sh:112`), not `-c review_model=`. The `-c review_model=` measurement does not transfer.

**Ask before dispatch**: is #750's scope "the astra lane only" or "every cold lane"? The spec reads as the latter and the anchors implement the former.

### 🔴 M2 — `--output` is load-bearing, and the spec names only `--ephemeral`

The resolver needs "the UUID from that invocation's own banner". `_run_review` can only
see the banner if a tee exists: `tee=Path(args.output) if args.output else None`
(`codex_run.py:607-610`), and `_spawn` sets `stdout=subprocess.PIPE if tee is not None
else None` / `stderr=subprocess.STDOUT if tee is not None else None`
(`codex_run.py:294`, `:312`). With `--output` omitted — and it **defaults to `None`**
(`codex_run.py:636-642`) — both streams are inherited by the terminal and the python
process never sees a byte, so the parent UUID is unobtainable.

`--ephemeral` gets a paragraph in the issue; `--output` gets none, and is the same class
of silently-load-bearing flag.

### 🟠 M3 — `mise` redaction would mangle the UUID; `raw = true` is the undeclared dependency

`CLAUDE.md` states that any figure `mise run` prints may be mangled by redaction (a
no-word-boundary literal replace). `[tasks.kb-codex]` carries `raw = true`
(`mise.toml:1152`), and `[tasks.kb-serve]`'s comment records that `--raw` is what
disables that line-based redaction. So the UUID survives **only because of a flag set
for an unrelated reason** (stdin connection). Dropping or forgetting `raw` would corrupt
the resolver's join key silently. Nothing states this dependency; a test should pin it.

### 🟠 M4 — `_run_review` has no repo, no HEAD, and no notion of the reviewed SHA

The evidence record is specified to hold "reviewed SHA and base ref". `_run_review`
receives an `argparse.Namespace` with `base`, `title`, `model`, `effort`, `sandbox`,
`output`, `timeout` and nothing else; `kb-codex` is a **general-purpose lane runner**,
not a review-aware one. It must compute HEAD itself. That opens a binding question the
spec does not raise: the receipt is written for **HEAD at receipt time**
(`cli.py:775`, `sha = review.head_sha(repo_root)`, with a deliberate no-`--sha`-override
comment at `:769-774`), while evidence is captured at **review time**. If HEAD moves in
between — which the receipt design already treats as invalidating — the binding must
detect it rather than silently accept a record for another commit.

### 🟠 M5 — enforcement placement collides with a documented ruling in the same file

`_reviewer_pin_gap`'s docstring (`review.py:346-356`) states, in bold, the opposite
placement rule: *"Runs from here (the WRITER) only — never from `_all_reasons`, which
`receipt_state` (the reader) also shares. A live-host comparison re-run at
`kb-ship`/`kb-land` time would refuse an already-honest receipt…"*

The spec's snapshot design is *compatible in principle* (a snapshot is not a live-host
comparison). But the snapshot lands in `.agent/` — gitignored (`.gitignore:190`) — so
the reader now depends on a second machine-local artifact. `kb-ship`/`kb-land` already
depend on the receipt and the lane report being on the same machine, so this is
consistent rather than novel; it does multiply the surface a single `git clean -xdf`
destroys. Worth one sentence in the spec that this was considered, not discovered later.

### 🟡 M6 — `_CHECKS` cannot host the new check; the signature is wrong

`_CHECKS = (_check_identity, _check_range, _check_lanes, _check_blocking)`
(`review.py:936`) and each is called as `check(data, sha)` (`review.py:946-947`) — no
`repo_root`. An evidence check needs the repo root, so it belongs beside `_evidence_gap`
inside `_all_reasons` (`review.py:418`), not in `_CHECKS`. A minor placement fact that
an implementer will otherwise discover by breaking a type.

### 🟡 M7 — a new receipt flag must join `_RECEIPT_FLAGS` or the repeated-flag guard misses it

`_RECEIPT_FLAGS` (`cli.py:757`) drives the duplicate-flag refusal, and the comment at
`:781-785` records why: `_opt` returns the FIRST occurrence, so a repeated flag silently
picks one. An `--evidence` flag added without a `_RECEIPT_FLAGS` entry inherits exactly
that defect on the field that gates.

### 🟡 M8 — the completion half is PARTLY enforced already; the spec proposes it as new

`_evidence_gap` → `_report_gaps` (`review.py:423`, `:716`) already refuses a receipt whose
claimed lane left **no non-empty report** at `review-<sha>-<lane>.md`. That is a real,
shipped "the review produced output" check. The spec's "terminal review result" should be
specified as what it *adds* over that (a terminal outcome and the subprocess rc), not as a
greenfield requirement — otherwise two overlapping checks drift apart, which is the exact
failure `_all_reasons`' own docstring (`review.py:414-418`) exists to prevent.

### 🟡 M9 — 173 legacy receipts exist on disk, and the ancestor-receipt path inherits the problem

`ls .agent/kb/review/receipt-*.json | wc -l` → **173**. "Legacy receipts must not silently
qualify" is stated; what is not stated is that the **`EXEMPT_PATHS` ancestor fallback**
(`review.py:1385-1390`, `_covering_candidates`) lets an *older* receipt cover HEAD. An
ancestor receipt written before this lands carries no evidence, so the #66 round-closing
path (`kb-remember` / `kb-goal-outcome` commits) breaks on the first branch that needs it.
Decide explicitly whether the evidence requirement is keyed to receipt schema version.

### 🟡 M10 — two review rounds, one receipt: which attempt binds?

The kb-review skill is bounded at **two rounds** (`.claude/skills/kb-review/SKILL.md`
description; round-2 prompt file `cold-prompt-r2.txt` exists in `.agent/kb/review/`). Two
invocations produce two evidence attempts against one receipt. The spec says "a failed
attempt can never inherit another attempt's success" but never says which *successful*
attempt is authoritative, or whether round 1's evidence still binds after round 2.

### ⚪ M11 — a dead flag path inside the exact function being extended

`_review_argv` gates the title on `if spec.title and spec.commit:` (`codex_run.py:412-413`),
`_run_review` hardcodes `commit=None` (`codex_run.py:552`), and **no `--commit` flag exists
in the parser** (verified: `grep -n 'add_argument' codex_run.py` lists `--print-argv`,
`--review`, `--base`, `--title`, `--model`, `--output`, `--timeout`, `--write`, `--network`,
`--effort`, `--sandbox` — no `--commit`). So `--title` can never apply from `_run_review`;
its own help string says *"needs --commit to apply"* for a flag that is not there. Not a
#750 defect, but it is a structurally-dead branch in the function an implementer is about
to extend, and copying the pattern would add a second one.

### ⚪ M12 — the default lane runs an UNPINNED codex

`run-lane.sh` calls a bare `codex` (`:97`, `:112`), not `mise exec -- codex`. `mise.toml`'s
own `[tasks.kb-codex]` comment records a measured split: *"`mise exec -- codex` resolved
0.152.1 while a bare `codex` on the same PATH resolved 0.152.0."* The plugin's review-lane
comment was verified against **0.144.1** (`run-lane.sh:99`), while the advisor measured
**0.154.0**. An adapter "qualified per codex release" must therefore be qualified against
*two* possibly-different codex versions, one of which this repo does not control.

---

## Corrections to flag back into the spec

1. `_spawn` is at **`codex_run.py:261`**, not 266 (266-268 is its signature tail).
2. **A4 is CONFIRMED, not assumed** — cite `skillopt_reviewed.py:824` and `codex_run.py:314`.
3. **A1 is report-sourced AND scope-limited to `codex review`.** The spec applies it to all cold lanes.
4. E1's "bounded?" is half-answerable now: distribution bounded (`.gitignore:190`), size unbounded.

## Control arms run

- **A suspicious line was NOT reported as a defect.** `review.py:360` reads `except OSError, TypeError, ValueError:`, which is a `SyntaxError` on Python ≤3.13. Armed with a real parse (`ast.parse` over the whole file) → **AST PARSE OK**; `import kb_setup.review` also succeeded and returned `LANES`. It is valid under PEP 758 (unparenthesised except groups). Reporting it without the arm would have been a false P1.
- **`_run_review` reachability was not inferred.** I read the plugin agent (`agents/codex-reviewer.md:44,74-84`) and then its supervisor (`scripts/run-lane.sh:112-113`) to see the literal `codex exec review` command, rather than concluding from the agent prose.
- **Graph-first**: `mise run kb-query` was run before any repo-wide search; it returned rc 3 (truncation guard, 678 nodes found, 58 shown) — a truncation, not an absence, and not used as evidence either way.

## GitHub repos touched

- [openai/codex](https://github.com/openai/codex) — named as the pinned source in the advisor report I was asked to grade (`rust-v0.154.0`); I read no codex source myself this session, only the report's citations of it.

_None other._
