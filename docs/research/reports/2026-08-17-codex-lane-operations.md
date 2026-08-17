# Codex lane operations — what 2026-08-17 measured

Operations reference for driving the `codex` CLI as this repo's cross-family
review lane. Written after a round in which the lane **claimed to be codex and
was not**, and a subsequent real codex pass found four blocking defects a
same-family lane had passed clean.

Every claim below is either cited to where it came from, re-measured while
writing this document (marked **re-verified 2026-08-17**), or labelled
`UNVERIFIED`.

---

## 1. The headline failure: a lane that claimed codex and was not codex

A cold review was dispatched as agent type `fable-orchestrator:codex-reviewer`,
named `cold-codex-42e82f5a`. It completed, reported "no unaddressed correctness
defect", and a receipt was written recording lane **`cold:codex`**.

It was **a Claude Sonnet 5 subagent that never invoked the `codex` CLI at all.**
It disclosed this itself, unprompted, after being asked a direct status question
— *"I did NOT invoke the `codex` CLI at any point — no `codex exec` process ran.
I performed the entire review myself."*

Every commit under review was Claude-authored, so the receipt asserted a
cross-family review that never happened. The `kb-review` skill's entire reason
for the cold lane — *different weights from the author* — was not obtained.

### Root cause, stated precisely

**The agent-type name and the agent's own name are routing labels. Neither is
evidence of which model ran.** `fable-orchestrator:codex-reviewer` describes
where a request was *sent*; `cold-codex-42e82f5a` is a string the orchestrator
chose. Nothing in the path from dispatch to receipt verified that the vendor CLI
executed.

The orchestrator compounded it by reporting *"Lane is
`fable-orchestrator:codex-reviewer` (OpenAI) — checked rather than assumed."*
What had actually been checked was the **authorship of the diff** — establishing
that a cross-family lane was *warranted*. That is a different question from
whether one *ran*.

### Open question — 10 historical receipts, deliberately not rewritten

**Re-verified 2026-08-17:** `grep -l "cold:codex" .agent/kb/review/receipt-*.json`
returns **10** receipts from earlier rounds.

Whether those runs genuinely invoked codex is **UNKNOWN**. They were left
untouched on purpose: rewriting history that cannot be verified would be its own
fabrication. Anyone relying on a pre-2026-08-17 `cold:codex` receipt as evidence
of cross-family review should treat it as unconfirmed.

The two receipts written *this* round that carried the false claim were deleted,
and the current HEAD receipt reads `cold:claude-sonnet-subagent`
(**re-verified 2026-08-17** in
`.agent/kb/review/receipt-df4001df87fce22743feed7b5e85ef27546d26de.json`).

---

## 2. How to verify a codex lane actually ran

### The probe

```bash
pgrep -f "codex exec"        # CORRECT — narrow
pgrep -f codex               # WRONG — matches a dozen unrelated things
```

**Re-verified 2026-08-17**, same machine, same moment:

| probe | matches |
|---|---|
| `pgrep -f codex` | **18** |
| `pgrep -f "codex exec"` | **0** |

What the broad probe actually hits (full command lines read with `ps -o command=`):

- `~/Library/Application Support/OpenSymphony/codex-otel/otelcol-contrib` — an
  OpenTelemetry collector bundled with Codex, 6+ days uptime
- `~/.codex/plugins/cache/openai-bundled/chrome/latest/extension-host/…`
- `/Applications/ChatGPT.app/…/Codex Framework.framework/…` (×6)
- `/Applications/ChatGPT.app/Contents/Resources/codex … app-server`
- `~/.codex/computer-use/Codex Computer Use.app/…` (×5)
- `npm exec xcodebuildmcp@latest mcp` — **and its full argv contains no `codex`
  token at all** (checked with `ps -ww -o command=`; cause not established).
  Recorded because it makes the point sharper: the broad probe matched something
  whose match reason could not even be reconstructed.

So a `pgrep -f codex` liveness check **can only ever say "alive"**. It is a probe
with one face.

### Confirm, don't just match

```bash
ps -o pid,etime,command= -p "$(pgrep -f 'codex exec' | head -1)"
```

Read the command line. During the successful run this printed:

```
51886  codex exec --ephemeral --sandbox read-only -c model_reasoning_effort=high -
```

That — the real `codex` binary observed in the process table — is what
"verified cross-family" should mean.

### The ambiguity that cost time

**A `codex exec` count of 0 is ambiguous between "not running right now" and
"never ran".** During the failed lane it was read as *"the lane is dead"* when it
actually meant *"the lane is not codex"*. Two different conclusions, one
observation.

Resolve it by asking the agent directly (it answered honestly when asked) or by
waiting for the harness's own completion signal, which is the authority. A
process probe cannot distinguish *dead* from *thinking*.

---

## 3. The doctor is the setup check — and it was green the whole time

```bash
bash "/Users/rmanaloto/.claude/plugins/cache/fable-orchestrator/fable-orchestrator/1.21.0/scripts/doctor.sh"
```

Also reachable as the `fable-orchestrator:doctor` skill.

**Re-verified 2026-08-17**, output unchanged:

```
codex lanes (implementer, reviewer: gpt-5.6-sol; fast mode: off; effort: high)
  ok   CLI present: codex-cli 0.147.0
  ok   auth + gpt-5.6-sol access confirmed (tier: standard, effort: high)

5 ok, 2 warnings, 0 failures
```

**No setup was needed. Nothing was broken.** Record this so a future round does
not go hunting for a `codex login` or a config fix that was never the problem.

The two warnings are unrelated to codex:

- `timeout` binary absent — affects the doctor's own live checks only; lanes ship
  their own pure-bash watchdog.
- `grok` CLI not installed — already recorded in `.claude/rules/ai-cli-invocation.md`
  ("`grok` is NOT installed — do not write a fallback that assumes it"), which
  makes codex the only viable cross-family lane on this machine.

One note the doctor prints that matters for lane honesty: *"pinned Claude models
are resolved by Claude Code and fall back to the session model **SILENTLY** if
unavailable."* Silent fallback is the same class of problem as this round's
mislabelled lane.

---

## 4. The invocation that worked

```bash
cat prompt.md | codex exec --ephemeral --sandbox read-only \
  -c model_reasoning_effort="high" - > /tmp/codex-review.log 2>&1
echo "CODEX_RC=$?" >> /tmp/codex-review.log
```

The prompt goes in a **file** piped to stdin. This repo has a standing lesson
(`prose-to-a-cli-goes-via-a-file`, recorded three times across three tools);
`ai-cli-invocation.md` states the same reason — avoid `ARG_MAX` on large prompts.
The trailing `-` is what makes codex read stdin.

### Cross-check against `.claude/rules/ai-cli-invocation.md`

**No drift.** The rule documents each piece; what worked is a composition of two
of its lines:

| rule line | used |
|---|---|
| `codex exec --ephemeral --sandbox read-only -` | yes |
| `codex exec --ephemeral -c model_reasoning_effort="high" -` | yes |
| `cat prompt.md \| codex exec --ephemeral -o /tmp/result.md -` | **no — see below** |

The rule's WRONG-pattern list (`codex -p`, positional `codex exec "prompt"`,
`--full-context`) was not tripped.

### One improvement the rule already offered and this round did not take

**Re-verified 2026-08-17** against `codex exec --help`:

```
  -o, --output-last-message <FILE>
      --json
      --output-schema <FILE>
```

The run used a shell redirect (`> /tmp/codex-review.log`), so **~1.09 MB of
streamed reasoning trace and the final findings landed in one file** and the
answer had to be recovered by searching backwards for the last
`Blocking findings found.` marker.

**Use `-o <FILE>` for the answer** and let the redirect capture the trace
separately. `--json` is available if a machine-readable transcript is wanted.

---

## 5. Operational characteristics measured this round

Task: cold review of `origin/main...HEAD`, 47 files, +3,839/−281, at
`model_reasoning_effort=high`.

| metric | measured |
|---|---|
| tokens used | **282,779** (reported by codex itself) |
| output log | **1,092,947 bytes** (~1.09 MB) — **re-verified 2026-08-17** |
| shell commands codex ran | **74** `exec` blocks — **re-verified 2026-08-17** |
| exit code | `CODEX_RC=0` |
| wall clock | long — tens of minutes; not precisely instrumented (`UNVERIFIED`) |

### Byte-count plateaus are NOT a stall

The log sat at an unchanging size for many consecutive polls — `983543` bytes for
roughly ten checks in a row, then jumped. This was nearly misread as a hang.

**A static output size means codex is reasoning, not that it is stuck.** Check
liveness with `pgrep -f "codex exec"`, not with output growth. Better still,
wait for the completion notification rather than polling; this round burned a
great many turns on polling that told it nothing.

### The sandbox limits that shaped its evidence — read this before trusting a codex review

Under `--sandbox read-only`, codex **could not write to any temp directory**.
Exact errors from the log:

```
git: warning: confstr() failed with code 5: couldn't get path of
     DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-nUfMUnRg'
     (errno=Operation not permitted)
```

and, in its own closing statement:

> *"The required graph query could not start: `mise` failed with
> `Operation not permitted` while creating `/var/folders/.../T/.tmph722Bq`
> (version `2026.8.6`). I'm treating the graph as unavailable and using the
> pinned source diff as fallback authority."*

Consequences, which the reviewer stated rather than concealed:

- **`mise` could not run** → no `kb-query`, no graph. Source was fallback authority.
- **`pytest` could not collect** → it never ran the suite. Its findings were
  demonstrated by **direct function calls and constructed probes** instead.

That is a real bound on the evidence. It does not weaken what it demonstrated by
construction, but a codex review under this sandbox has **not** run your tests,
and should never be read as if it had.

### Granting a writable temp dir — options, both UNTESTED

- `-s workspace-write` — advertised in `--help`
  (`--sandbox <SANDBOX_MODE>`). Would permit temp writes, but **loses the
  read-only guarantee**: pair it with an explicit "do not modify tracked files"
  instruction and check `git status --short` afterwards. (The failed same-family
  lane *did* mutate and restore files cleanly, so a mutating reviewer is
  workable — it just has to be verified.)
- `-c 'sandbox_permissions=[…]'` — the `--help` example shows
  `["disk-full-read-access"]`, which is a **read** permission and would not fix
  temp writes.
- A `writable_roots`-style key is **not advertised in `--help`**
  (**re-verified 2026-08-17**: zero matches). Do not assume it exists; probe
  before relying on it.

Whichever is chosen, **probe it with a throwaway run before a real review** —
discovering the sandbox blocked your tests after a 280k-token pass is expensive.

---

## 6. What codex was measurably good at — the case for using it

On the **same diff** where the same-family lane reported **0 blocking**, codex
returned **8 findings, 4 High (blocking), all demonstrated by construction**:

| sev | finding |
|---|---|
| **High** | Existing stage directories trusted without verification — an empty/corrupt/symlinked stage counts as `resumed`/`repaid` and the run exits **0**. *Demonstrated:* substituted an unrelated directory for every stage → "58 resumed, 0 failed, success." |
| **High** | Callback guard checks index **range**, not ordinal **uniqueness** — duplicate callbacks conceal an unvisited chunk, and the `skipped` clamp hides the negative. *Demonstrated:* 58 callbacks over 57 unique indices → `resumed=58, skipped=0, failed=0`, success. |
| **High** | "Warm" resumption never reads graphify's cache — `extract_corpus_parallel` has `_checkpoint_chunk` (a writer) and **no cache-load call**, so real existing chunks are *always* repaid, and the test manufactured a cache hit by omitting metadata. *Independently re-confirmed* by AST walk, with a control proving the probe discriminates. |
| **High** | Adaptive retries inert for truncation — the adapter rejects `stop_reason=max_tokens` as `stop-reason-invalid` before graphify can see `finish_reason=length`. |
| Medium | Staging `OSError` bypasses the callback's `except (TypeError, ValueError, msgspec.DecodeError)` and still aborts `execute()` — the exact gap that fix claimed to close. |
| Medium | Skill stamps still `0.9.44` against a `0.9.45` pin — a 13th restatement of the revision; `mise run kb-skill-refresh`. |
| Low | A test named for the unset-vs-mismatch distinction never calls `verify_plan`. *Demonstrated:* replaced `verify_plan` with a raiser; the test still passed. |
| Low | A comment written that same day asserts the control canary "keeps the default" timeout while it passes `timeout=30`. *Independently re-confirmed.* |

### The lesson — it is METHOD, not vendor

Codex **constructed inputs and watched behaviour**: it substituted a stage
directory, drove 58 callbacks over 57 indices, built a `max_tokens` envelope,
injected an `OSError`, and swapped `verify_plan` for a raiser. It did not merely
read the diff.

`.claude/skills/kb-review/SKILL.md` already records this from earlier
measurement — *"What actually predicted a blocker was **method** (a lane that
mutated code to test its claim) rather than lane identity … give the one lane a
mutating instruction before adding a second lane back."* This round is a second
data point for that claim, on a diff where the non-mutating lane found nothing.

Note the honest caveat: the same-family lane *did* run two mutation arms and both
died. It was not lazy. It simply did not construct the adversarial states codex
did — and it shared the author's blind spots about what states were worth
constructing.

---

## 7. Recommendations for future rounds

### Invoking

```bash
cat prompt.md | codex exec --ephemeral --sandbox read-only \
  -c model_reasoning_effort="high" \
  -o /tmp/codex-answer.md - > /tmp/codex-trace.log 2>&1
echo "CODEX_RC=$?" >> /tmp/codex-trace.log
```

- Prompt via **file → stdin**, trailing `-`.
- **`-o` for the answer**, redirect for the trace. Do not conflate them.
- Run it in the background and **wait for the completion notification**. Do not
  poll output size; plateaus are normal and polling taught this round nothing.
- Budget for it: ~280k tokens and tens of minutes on a 47-file diff at high
  effort.

### Verifying the lane actually ran

1. `pgrep -f "codex exec"` — never bare `codex`.
2. Read the matched pid's `command=` to confirm it is the real binary and the
   flags you intended.
3. Record the observation. **A receipt should rest on a process observation, not
   on an agent type name.**
4. If you cannot observe it, do not write a `cold:<vendor>` receipt. Record the
   lane you can actually defend.

### What to put in the review prompt

Each of these earned its place this round:

- **The mutating instruction** — "do not only read; construct inputs and watch
  what the code does; restore anything you mutate and say so." This is what
  produced every High finding.
- **`file:line` citation required**, and *"if you cannot cite it, label it
  `unverified` rather than dropping or promoting it."*
- **Demonstrated-vs-reasoned marked per finding.** Codex complied precisely; the
  one `REASONED` finding was correctly the weakest.
- **The commit SHA must appear in the report body** — `kb-review`'s receipt gate
  (#56) refuses a report that does not name its commit.
- **Write the report incrementally** so a watchdog kill leaves evidence.
- **State coverage limits explicitly** — what was opened, what was not, and what
  could not run. Codex did this unprompted and it is the reason its sandbox
  limitation is known at all.
- **Warn about the AWS env vars**: this repo's semantic preflight refuses when
  `AWS_*` is set (`do-not.md` #4, Bedrock trigger). Tell the lane to re-run with
  `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_REGION -u AWS_DEFAULT_REGION`.

### Before trusting any review receipt

- Does a **process observation** back the lane it names?
- Did the lane state what it **could not** run? Silence is not coverage.
- Are findings marked **demonstrated vs reasoned**?
- Does the report **name the commit**?
- For a `cold:` lane: is the reviewer genuinely a **different family than the
  author**? Check `git log --format='%an %s'` over the range *and* the lane.

### The structural fix, not yet built

A receipt records the lane the orchestrator **intended**. Nothing verifies which
model ran. Closing that means `kb-review-receipt` requiring evidence for a
`cold:<vendor>` claim — a process observation or a CLI-emitted artifact — and
refusing the claim otherwise. Filed as a recommendation here; **not implemented**.

---

## Related

- `.claude/rules/ai-cli-invocation.md` — the invocation patterns; consistent with
  what worked, and it already offered the `-o` flag this round did not use.
- `.claude/skills/kb-review/SKILL.md` — the lane-routing table, the two-round
  bound, and the prior measurement that method beats lane identity.
- `.claude/skills/orchestrator-routing/SKILL.md` — the three-lane doctrine.
- `.agent/kb/review/reports/review-df4001df…-cold-codex.md` — the full codex
  findings, verbatim (gitignored; this document is the durable summary).

## GitHub repos touched

- [mar3co/fable-orchestrator](https://github.com/mar3co/fable-orchestrator) — the
  plugin providing the codex lane and the `doctor.sh` re-run for this document
  (v1.21.0, read from the local plugin cache).
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the
  pinned dependency whose `extract_corpus_parallel` was AST-inspected while
  confirming codex's write-only-cache finding.
