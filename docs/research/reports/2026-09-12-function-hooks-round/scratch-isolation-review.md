# Scratchpad-isolation review — kb-codex-astra-advisor

- Lane: `kb-codex-astra-advisor` (this agent), plus fanned-out codex lanes named inline.
- Repo: `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base`
- Branch: `feat/754-plugin-types-contract`, HEAD `4cdd8bfb` at report start.
- Directive under review: Ray, 2026-09-12 — *"update whatever is necessary so each
  background task/subagent gets their own dedicated scrathpad"*.
- Status: IN PROGRESS — written incrementally per `agent-report-persistence.md` rule 3.

---

## 1. IS THE APPLIED FIX CORRECT?

### Verdict: **NO — the fix is incomplete and has two live defects.** The
### *instrument* (`mktemp -d`) is right; the *application* is not.

Three findings, each independently sufficient to send it back.

#### 🔴 P0-A — `$KB_LANE` is referenced with NO assignment in scope, at two sites

The team lead asked specifically whether a substitution landed where `$KB_LANE`
is unset. It did, twice:

| file:line | the reference | nearest assignment |
|---|---|---|
| `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agents/skills/kb-review/references/lanes.md:148` | `< "$KB_LANE/method.txt"` | **NONE anywhere in the file** |
| `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.codex/agents/kb-codex-astra-reviewer.toml:112` | `< "$KB_LANE/method.txt"` | line **208**, i.e. 96 lines AFTER the use |

Probe (control-armed — the same grep DOES find assignments in the four files
that have them, so it discriminates):

```bash
cd /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base
for f in .agents/skills/kb-review/references/lanes.md \
         .claude/agents/kb-codex-advisor.md \
         .claude/agents/kb-codex-astra-advisor.md \
         .claude/agents/kb-codex-astra-reviewer.md \
         .codex/agents/kb-codex-advisor.toml \
         .codex/agents/kb-codex-astra-reviewer.toml; do
  echo "=== $f ==="; grep -n 'KB_LANE' "$f"
done
```

**What an unset `$KB_LANE` actually does here is NOT the root-directory write the
lead feared — it is worse in one way and better in another, and the direction
matters.** Both bad sites are **input** redirections (`< "$KB_LANE/method.txt"`),
not output. Unset expands to `/method.txt`, which does not exist, so the
redirection fails and `mise run kb-codex` never runs. That is a *loud* failure —
good. But it is loud in a way that reads as **the codex lane being unavailable**,
which is precisely the false-negative class `long-running-command-hangs.md` rule
3a exists to stop ("a probe using one dies with `command not found` … and reads
in a transcript as the thing under test failing").

The lead's root-write worry IS live at the *output* sites — `"$KB_LANE/prompt.md"`,
`"$KB_LANE/verdict.md"`, `"$KB_LANE/tree-before.txt"` — but at every one of those
the assignment is present and immediately above. So: **the unset-variable defect
is real, and it is at the two sites the lead did not list.**

#### 🔴 P0-B — the `.claude/` mirror of `lanes.md` was NOT fixed

`.agents/skills/kb-review/references/lanes.md` was edited; its twin was not.

```bash
diff /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.agents/skills/kb-review/references/lanes.md \
     /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/skills/kb-review/references/lanes.md
# 148c148
# <   < "$KB_LANE/method.txt"
# ---
# >   < /tmp/astra-method.txt
```

`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/skills/kb-review/references/lanes.md:148`
still carries the fixed path. **`.claude/` is the tree Claude Code actually
loads**, so the one file a Claude session reads is the unfixed one, and the one
that was fixed is now broken by P0-A. The net effect of the edit on this pair is
that both copies are wrong, in two different ways.

Note the shape: this is `change-the-route.md` rule 4 — *a bare basename is
ambiguous across repos, and silently resolves wrong*. Here it is ambiguous across
**trees within one repo**.

#### ⚠️ P1-C — `mktemp -d` is unguessable, and something DOES need to find these files

The lead asked the right question. Answer: **for the verdict file, yes, this is a
real regression; for the prompt and the fingerprint, no.**

- `prompt.md`, `method.txt`, `tree-before.txt` — written and read by the same
  lane, within one turn. Unguessable is fine, arguably better.
- `verdict.md` — this is the artifact the lane is told to keep *because the lane
  may die*. `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/agents/kb-codex-advisor.md:48-51`
  states the reason verbatim: *"always captured to a file so a killed or idle
  turn still leaves evidence"*. A killed lane cannot tell you its `mktemp` path.
  **An unguessable path defeats the stated purpose of the file.** The repo has
  already been bitten by exactly this: memory
  `subagent-lanes-go-idle-without-reporting.md`, and the standing instruction in
  `MEMORY.md` — *"tell any advisor to write its verdict to a file BEFORE
  returning"* — is only actionable if the caller knows where.

The reviewer agent already resolves this correctly for its `--output`, and the
fix did not touch it:
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/agents/kb-codex-astra-reviewer.md:84`
keeps `--output .agent/kb/review/reports/review-<HEAD SHA>-cold.md` — a
**deterministic, findable, already-contractual** path (`agent-report-persistence.md`
makes that filename a contract `kb_setup.review` reads). That is the model the
verdict files should follow, not `mktemp`.

---

## 3. NATIVE MECHANISM — **YES, one exists, and it is better than `mktemp -d`**

### 3.1 A Claude Code subagent DOES get its own scratchpad directory

This is the finding that should change the fix. Claude Code hands every session —
**including each subagent** — a scratchpad directory:

```
/private/tmp/claude-501/<project-slug>/<session-uuid>/scratchpad
```

Evidence, measured this session by this lane:

| probe | result |
|---|---|
| this subagent's scratchpad, from its own system prompt | `…/3b921834-9839-450d-aee1-0b72d7549b50/scratchpad` |
| `[[ "$CLAUDE_CODE_SESSION_ID" == "3b921834-9839-450d-aee1-0b72d7549b50" ]]` | **MATCH** — the directory is keyed on the session id |
| the uuid the harness used for this lane's OWN background tasks | `36755013-0c2e-45ae-985a-acfe76c91278` — **a different uuid** (the parent session's) |

The third row is the decisive one. This subagent's scratchpad uuid is **not** its
parent's. A subagent therefore carries its own session id and its own scratchpad
directory, distinct from the session that spawned it.

**I got this wrong on my first pass and am correcting it here rather than
silently.** My initial inference was "per-session, not per-subagent", from a count
of 6 project-root directories with today's mtime against ~19 named lanes. That
count does not support the conclusion: directories are created lazily on first
write, so a lane that never touches its scratchpad leaves none. The count was a
real measurement of the wrong thing — `probes-need-a-control-arm.md` rule 6.

I also tried to classify directories as session-vs-subagent by whether they
contain a `tasks/` subdirectory (38 with, 40 without, 78 total, loop control-armed).
**That discriminator does not work** and I am not relying on it: a top-level
session that never backgrounds a command also has no `tasks/`. Reported only so a
later reader does not re-run it expecting an answer.

### 3.2 What the scratchpad is NOT

- 🔴 **It is not an environment variable.** Probed by `[[ -v NAME ]]` (never
  printing values), with `HOME`/`PATH`/`TMPDIR` as the control arm, all three SET:

  | SET | ABSENT |
  |---|---|
  | `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT`, `TMPDIR` | `CLAUDE_SCRATCHPAD`, `CLAUDE_CODE_SCRATCHPAD`, `CLAUDE_SCRATCH`, `SCRATCHPAD`, `CLAUDE_PROJECT_DIR`, `CLAUDE_AGENT_ID`, `CLAUDE_CODE_AGENT_ID`, `AGENT_ID`, `CLAUDE_WORKING_DIR`, `CODEX_HOME`, `CODEX_SANDBOX`, `CODEX_SESSION_ID` |

  **This is the constraint that shapes the fix.** The scratchpad path reaches an
  agent as *system-prompt text*, not as a variable a shell snippet can expand. So
  an agent definition cannot write `cd "$CLAUDE_SCRATCHPAD"` — that variable does
  not exist. It must instruct the agent to use *the scratchpad directory named in
  its environment*, which the agent then substitutes literally.

  `CLAUDE_CODE_SESSION_ID` **is** set, so a shell snippet CAN derive a
  session-unique path from it. That is the one composable native handle available.

- **It is not needed for background-task stdout.** The harness already isolates
  that natively: each `run_in_background` call gets a generated task id and its own
  output file, e.g. `…/36755013-…/tasks/bw347im01.output`. Three lanes launched
  from this agent got `bw347im01`, `bkb890ujg`, `bqxutqq63` — no collision possible.

### 3.3 The repo instruction that was already being ignored

Every session here is told, in its environment block:

> Scratchpad directory: `/private/tmp/claude-501/…/<uuid>/scratchpad` — **always use
> it for temporary files** … instead of `/tmp` or other system temp directories; it
> is session-specific, isolated from the project, and can generally be used without
> permission prompts.

The agent definitions instructed `/tmp/<agent-name>-prompt.md` — **in direct
contradiction of a standing instruction every one of those agents receives.** The
collision was not an unlucky race against an adequate design; it was the
predictable result of overriding the isolation the harness already provided.

That reframes the whole fix: this is not "add isolation", it is "stop overriding
the isolation you already have."

---

## 2. WHAT ELSE COLLIDES — the wider sweep

### 2.1 🔴 THE FIX AS APPLIED BREAKS A SHIP GATE RIGHT NOW

This outranks everything else in this section, because it is not a latent risk —
it is red on the current working tree.

```bash
cd /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base && mise run kb-skill-lint
```
```
skill-lint: 28 skill(s) checked; every instructed command is a mise task or allowed read-only
skill-lint: mirror drift: kb-review: .claude/skills/kb-review/references/lanes.md and its mirror differ
skill-lint: 1 skill(s) differ between .claude/skills/ and .agents/skills/. `.claude/` is
            authoritative — copy it onto the mirror. A lane that needs different text needs its own skill.
[kb-skill-lint] ERROR task failed
TASK rc=1
```

`skill_lint` is a declared hk step — `/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/hk.pkl:503-505`:

```pkl
["skill_lint"] = new Step {
  check = "uv run kb-setup skill-lint"
}
```

so `mise run lint` fails, so `mise run kb-ship` refuses to push. **The branch
cannot ship in this state.**

**And the gate's own remedy would REVERT the security fix.** `mirror_drift`
documents `.claude/` as authoritative —
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/skill_lint.py:220-224`:

> `.claude/` is authoritative: it is the tree Claude Code loads and the one every
> rule and task names, so a divergence is repaired by **copying it onto the
> mirror, never the other way**.

`.claude/…/lanes.md:148` still holds `/tmp/astra-method.txt`. Following the
printed remedy literally copies the fixed path back over the fix, in both trees,
and the gate then goes green. **A green gate would certify the defect restored.**

Correct order: **edit `.claude/` first (it is authoritative), then copy onto
`.agents/`.** The fix was applied to the mirror only, which is backwards.

Worth recording for the gate design in §4: `mirror_drift` compares **every file
under a skill**, not just `SKILL.md` — and it does so because a cold lane on
`a61988b2454a` caught the anchor-only version missing exactly this class
(`skill_lint.py:258-265`). That is the third time in this repo that a
`references/*.md` asset was the thing that drifted.

### 2.2 `python/src/kb_setup/**` — CLEAN, and control-armed

The code layer already does the right thing everywhere. Not one hard-coded temp
path; every one goes through `tempfile` with a descriptive prefix.

```bash
grep -rn 'Path("/tmp\|"/tmp/\|open("/tmp\|= "/tmp' python/src/kb_setup/ ; echo "rc=$?"
# rc=1   (no match)
```

**Control arms, both run, because a bare rc=1 is not an answer:**

| arm | result |
|---|---|
| same grep shape for a string I know is present (`tempfile.mkdtemp`) | 4 hits, rc=0 — the shape works |
| same tree for the *docstring* form `/tmp/out.log` | 2 hits (`eval_cases.py:196`, `check.py:13`), rc=0 — `/tmp` IS findable there |

So the negative is real: `/tmp` exists in that tree only inside prose, never as a
write target. Representative correct usage —
`tool_sync.py:137`, `mod_runtime.py:528`, `graph.py:1425`, `workflow_lint.py:178`,
`session_review_archive.py:554`, `artifact_download.py:304`,
`graphify_baseline.py:1776`.

**This is an argument about where the gate belongs (§4): the Python obeys the
rule; only the English disobeys it.**

### 2.3 Fixed paths that are CORRECT — do not "fix" these

Naming them so a later sweep does not flag them and so §4's predicate has to
accommodate them:

| path | why it is fine |
|---|---|
| `.agent/kb/review/reports/review-<sha>-<lane>.md` | a **contract** `kb_setup.review` reads; the `<sha>` and `<lane>` ARE the discriminators. `.claude/agents/kb-codex-astra-reviewer.md:84` |
| `.agent/kb/gates/gates-<sha>.json` | discriminated by `<sha>` |
| `.agent/kb/recall/<slug>.md` | discriminated by topic slug; two lanes recalling the SAME topic would collide, but the content is a pure function of the topic, so the write is idempotent |
| `/tmp/out.log` in `.claude/rules/long-running-command-hangs.md:75`, `.claude/rules/ai-cli-invocation.md:56` | **prose quoting an example**, not an instruction to this repo's lanes. A gate that flags these is worse than no gate |

### 2.4 `.agent/kb/reports/agents/<agent-name>.md` — a real but partly-mitigated collision

The lead asked about this specifically. Verdict: **the risk is real, and it is
mitigated by convention rather than by mechanism.**

`.claude/rules/agent-report-persistence.md:31` mandates the path
`.agent/kb/reports/agents/<agent-name>.md`. Two concurrently-spawned instances of
one agent type resolve `<agent-name>` identically and collide — the exact shape of
the original incident, relocated from `/tmp` into `.agent/`.

In practice the 563 existing entries are mostly discriminated by date or topic
(`2026-08-23-advisor-a922c168` — note the sha suffix, `advise-569.md`,
`754-advisor-verdict.md`), because callers assign a task-specific name. This
lane's own report is one of those: the lead named it `scratch-isolation-review.md`.

So the convention saves it, and the *rule text* does not. That gap is worth
closing in the rule regardless of §4's verdict.

### 2.5 `.claude/workflows/*.js` — no fixed shared scratch

`kb-extract.js`, `kb-tool-review.js`, `session-review.js` (287 / 271 / 1408 lines,
all readable — control arm). Their `.agent/` references are a configurable
`reportDir` (`session-review.js:281`: `cfg.reportDir || '.agent/kb/reports/agents'`)
and prose. No fixed `/tmp` write target.

### 2.6 `.codex/agents/kb-codex-astra-advisor.toml` — correctly untouched, NOT a miss

Worth stating because its absence from the changed-file list looks like an
oversight. It is the codex-side **role** — it *is* the lane, rather than
launching one — so it has no prompt-file block and no `/tmp` path to fix
(`grep '/tmp/'` → rc=1). Its instruction at line 195-196 is *"never write outside
the file you are told to write your verdict to"*, i.e. the path arrives from the
caller. Correct by construction.

### 2.7 🔴 A MISSED INSTANCE — and it is the SOURCE of the pattern

`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/rules/ai-cli-invocation.md:56`

```bash
# Capture to file (for background use):
cat prompt.md | codex exec -o /tmp/result.md -
```

This is inside a ```bash fence in the rule file that **documents the canonical
codex invocation patterns for this repo**. Every lane is pointed at it — the file
says so itself at line 186: *"The patterns above ARE the reference."* Two
concurrent lanes following it write the same `/tmp/result.md`.

This is not a peripheral instance. The agent definitions' `/tmp/<agent>-prompt.md`
convention is this pattern, copied. Fixing the agents and leaving this is fixing
the copies and keeping the original.

---

## 4. THE GATE — **YES, build it.** The evidence for it is unusually clean.

> ⚠️ This section is my own analysis. A dedicated `gpt-5.6-sol` gate-design lane
> was still running when this was written; its independent proposal is merged in
> §6 below, and where we disagree I say so rather than silently reconciling.

### 4.1 The false-positive problem — which this repo has measured as its ONLY real failure direction — is solved by fence-scoping, and I measured it

`mise-tasks-only.md` § *Extending* states the house constraint: *"a redirect that
misfires on legitimate read-only introspection erodes trust in the guard, and that
— not evasion — is the direction every measured defect has come from."*

So the question is not "can we detect `/tmp`" but "can we detect it **without**
flagging the prose that legitimately discusses it". Measured over
`lane_recording.DEFAULT_GLOBS` — `.claude/agents/*.md`, `.codex/agents/*.toml`,
`.claude/rules/ai-cli-invocation.md`:

| file:line | shape | inside a ```bash fence? | verdict |
|---|---|---|---|
| `.claude/agents/kb-codex-advisor.md:54` | `>` blockquote prose | **no** | correctly ignored |
| `.claude/agents/kb-codex-astra-advisor.md:86` | `>` blockquote prose | **no** | correctly ignored |
| `.claude/agents/kb-codex-astra-reviewer.md:71` | `>` blockquote prose | **no** | correctly ignored |
| `.claude/rules/ai-cli-invocation.md:182` | paragraph, inline backticks | **no** | correctly ignored |
| `.claude/rules/ai-cli-invocation.md:56` | fenced command | **YES** | 🔴 **TRUE POSITIVE** (§2.7) |

**Fence-scoping alone takes five candidates to one, and that one is a real
defect.** Zero false positives on the live tree — and note that the three
blockquote hits are the *warnings the fix itself just added*, i.e. exactly the
self-documentation trap `lane_recording`'s own comment records being bitten by
(`hk.pkl:522-526`: *"the mirrored kb-codex-advisor pair it scans now DISCUSSES
`--ephemeral` at length explaining why it is absent, and a literal search would
flag its own documentation"*). A fence-scoped check survives that trap by
construction.

This is the strongest argument for the gate: **it finds a real instance on day
one, and it flags nothing else.**

### 4.2 The predicate

Not "a fixed path" — that would ban `--output .agent/kb/review/reports/review-<SHA>-cold.md`,
which is correct (§2.3). The predicate is narrower and does not need the general
concept at all:

> Inside a shell-class fence, in the agent/skill/lane-rule surfaces this repo
> owns, **a write target directly under `/tmp` or `/private/tmp` is denied.**
> Remedy: use the session scratchpad named in your environment.

Three properties that make it implementable rather than aspirational:

1. **It is about a directory, not about "fixedness".** No need to decide whether
   `<SHA>` counts as a discriminator — that whole judgment is out of scope.
2. **`$TMPDIR`, `mktemp` and the scratchpad path all pass**, so the check never
   argues with the instrument chosen in §5.
3. **It is a redirect, not a ban**, matching every other guard here — it prints
   the canonical alternative.

### 4.3 Where it lives

**Extend `python/src/kb_setup/lane_recording.py` (261 lines).** It is not merely
adjacent, it is the same gate:

- it already scans **exactly the three surfaces** where this defect lives
  (`lane_recording.py:45-49`), and its comment records that omitting
  `.codex/agents/*.toml` was a P1 in cold round 2 — the same two-tree miss the
  applied fix just repeated;
- it already owns the **CommonMark fence walker** (shared with `skill_lint`) and
  `check_first`'s **shlex tokeniser** — §4.1's whole mechanism, already built and
  already tested;
- it already returns **`Rc.NOT_RUN` (127) when nothing was examined**
  (`lane_recording.py:91-100`, `:244`), which is §4.4's floor, already correct.

Building a new module would duplicate all four. The hk seam already exists.

The skill trees (`.claude/skills/**`, `.agents/skills/**`) are covered by
`skill_lint`'s own fence walk, so a second entry point there is the natural
companion — and `mirror_drift` (§2.1) already guarantees the two trees agree, so
the check only has to be right once.

### 4.4 The NOT_RUN floor

Inherited from `lane_recording.Report` — `NOT_RUN` when `scanned` is empty. A glob
that matches nothing exits 127, never 0. Already implemented; do not re-invent it.

### 4.5 The mutation arms

Per `probes-need-a-control-arm.md` rule 2, and via `mise run kb-arms -- <spec.toml>`
— never a hand-written harness.

| arm | mutation | must be |
|---|---|---|
| **control** | tree as-shipped after `ai-cli-invocation.md:56` is fixed | **green** |
| realistic-1 | restore `-o /tmp/result.md` in that fence | **red** |
| realistic-2 | reintroduce `cat > /tmp/kb-codex-advisor-prompt.md` in `.claude/agents/kb-codex-advisor.md`'s fence | **red** |
| realistic-3 | same, in the `.codex/agents/*.toml` twin only (the two-tree miss) | **red** |
| false-positive | the `>` blockquote prose at `kb-codex-advisor.md:54` | **green** |
| false-positive | `ai-cli-invocation.md:182` inline-backtick prose | **green** |
| NOT_RUN | point the glob at a directory with no matches | **rc 127**, not 0 |

Note the realistic-vs-cosmetic distinction the rule insists on: the mutation must
be the *instruction being written back*, not a renamed variable. Renaming
`KB_LANE` would leave the fence still free of `/tmp` and prove nothing.

---

## 1b. THE FIX CHANGED UNDER REVIEW — attempt 2, and it is WORSE

Between the start of this review and 13:40 the working tree was revised. §1 above
reviewed **attempt 1** (`mktemp -d`). The tree now carries **attempt 2**:

```bash
KB_LANE="${TMPDIR:-/tmp}/kb-lane-$KB_LANE_NAME"; mkdir -p "$KB_LANE"   # KB_LANE_NAME = YOUR agent name, unique per lane
```

at `.claude/agents/kb-codex-advisor.md:71`, `kb-codex-astra-advisor.md:103`,
`kb-codex-astra-reviewer.md:70,77`, `.codex/agents/kb-codex-advisor.toml:51`,
`.codex/agents/kb-codex-astra-reviewer.toml:112,209`.

### Verdict on attempt 2: it REINTRODUCES the defect

**`KB_LANE_NAME` is referenced 9 times and assigned 0 times.** Both readings fail:

| reading | result |
|---|---|
| a literal shell variable | unset → **every lane of every type** shares `$TMPDIR/kb-lane-`. Strictly worse than attempt 0, which at least separated agent types |
| a placeholder the agent substitutes | the comment says *"YOUR agent name"*. An agent reading its own definition takes its name from that file's frontmatter — `kb-codex-astra-advisor`. Five concurrent instances substitute the same string → `$TMPDIR/kb-lane-kb-codex-astra-advisor`. **The original collision, relocated** |

`${TMPDIR:-/tmp}` is not a discriminator either: `$TMPDIR` on this host is
`/var/folders/z4/0p475gq56vvczc3y4qlt60f80000gn/T/` — per **user**, not per session
or lane.

The gate-design lane reached this independently and stated the general rule:
*"Treat a static agent-type string such as `kb-codex-astra-advisor` as
non-discriminating: five concurrent instances share it."*

### What attempt 2 DID fix

**Mirror drift is resolved** — `mise run kb-skill-lint` now exits 0. §2.1's shipping
blocker is cleared.

### What attempt 2 did NOT fix — P0-A survived, and spread

`$KB_LANE` is still referenced with no assignment in scope, and now in **both**
trees:

```bash
grep -n 'KB_LANE=' .claude/skills/kb-review/references/lanes.md \
                   .agents/skills/kb-review/references/lanes.md ; echo rc=$?
# rc=1   — no assignment in either file
grep -c 'KB_LANE' <same two files>
# 1 and 1 — one reference each, at :148
```

The mirror repair propagated the broken reference into both trees instead of
fixing it. Both now agree, and both are wrong — which is what a byte-equality
gate can and cannot do for you.

---

## 5. THE RECOMMENDATION

**The caller allocates the path and hands it to the lane.** Both codex lanes
converged on this independently, from different directions, and it is the only
option whose correctness does not depend on an unresolved question.

```
.agent/kb/lanes/<run-id>/<lane-instance-name>/{prompt.md,verdict.md,method.txt}
```

Why this and not the alternatives:

| option | collision-safe | findable by a caller collecting a DEAD lane's verdict | verdict |
|---|---|---|---|
| `mktemp -d` | yes | **no** — unguessable by design, which defeats the verdict file's stated purpose | rejected |
| `$TMPDIR/kb-lane-$KB_LANE_NAME` | **no** (§1b) | yes | rejected |
| session scratchpad subdir | probably | only if the caller is told the base | rejected: the layout is **undocumented** (§3.2), and the native lane's explicit warning is *"Do not reconstruct the scratchpad path… That layout is undocumented"* |
| **caller-allocated `.agent/kb/lanes/…`** | **yes** | **yes** | **ship this** |

Three things make it right rather than merely adequate:

1. **Only the caller knows the fan-out.** An agent reading its own definition
   cannot know whether it is instance 1 of 1 or 3 of 5. The caller does. That is
   not a workaround, it is where the information actually is.
2. **You are already doing it.** This session's lanes carry distinct instance
   labels — `advisor-754`, `cold-755`, `cold-755-r2`, `impl-755-fix`, and this
   lane was named `scratch-isolation-review`. The label IS the discriminator; it
   just was not being used as one.
3. **The agent definition gets simpler, not more clever.** It should say *"write
   to the scratch path your caller gave you"* — no `mktemp`, no `$TMPDIR`, no
   session-id arithmetic, nothing the agent computes about itself.

### 🔴 Do NOT use `$CLAUDE_CODE_SESSION_ID` as the discriminator

Tempting, and both codex lanes refused to endorse it. This repo has already
measured against it —
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/context_usage.py:54-56`:

> **A session id cannot make the distinction** — measured on a live fork, whose
> `CLAUDE_CODE_SESSION_ID` is identical to the main session's, which reads the
> same transcript…

My own contrary measurement (§3.1) is about an agent **teammate**, which may be a
different mechanism from a fork or an ordinary Agent-tool subagent. Corroborating
the caution: only **4** transcripts carry today's mtime under
`~/.claude/projects/-Users-rmanaloto-…/` while ~19 named agents are active, so most
agents are *not* separate sessions (control arm: 198 transcripts total, so the
glob and the time bound both work).

**The recommendation does not depend on resolving that**, which is exactly why it
is the one to ship.

---

## 1c. ATTEMPT 3 — live on disk now, and it is BROKEN SHELL

The tree moved a third time. `KB_LANE_NAME` is gone (`grep -rn 'KB_LANE_NAME'
.claude/ .codex/ .agents/` → **rc=1**; control arm `grep -rln 'KB_LANE'` on the two
agent dirs → rc=0, 5 files, so the probe discriminates). §1b's findings are now
historical; the shell semantics quoted there remain conclusively unsafe.

What replaced it, at
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.claude/skills/kb-review/references/lanes.md:139-149`:

```bash
mise run kb-codex -- --review \
  --base <FIXED> \
  ...
  --output .agent/kb/review/reports/review-<HEAD SHA>-cold.md \
  : "${KB_LANE:?your caller must pass an absolute per-instance scratch path}"
  < "$KB_LANE/method.txt"
```

**This does not do what it looks like it does.** The `\` at the end of the
`--output` line continues the command, so `:` and the `${KB_LANE:?…}` string are
passed as **two positional arguments to `kb-codex`** — not executed as a shell
guard. Three consequences:

1. **The guard never fires.** `${KB_LANE:?…}` in an argument position expands (or
   errors) but never gates anything; the reassuring error message is decorative.
2. **The method file is never piped in.** `< "$KB_LANE/method.txt"` lands on its
   own line as a bare redirection with no command. The lane runs its review with
   **no instructions at all** — and `--review` will happily proceed.
3. `kb-codex` receives two junk positional args.

The `.codex` twin is worse still —
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.codex/agents/kb-codex-astra-reviewer.toml:104-115`
splices `mkdir -p "$KB_LANE"` *between* the continued invocation and the orphan
redirect.

**Attempt 2 collided; attempt 3 does not run.** Neither is shippable. The failure
also has the same signature as §1's P0-A: it reads as the codex lane misbehaving,
not as a broken recipe.

The intent — *"your caller must pass an absolute per-instance scratch path"* — is
exactly §5's recommendation, and is right. Only the shell is wrong. Correct form:

```bash
: "${KB_LANE:?your caller must pass an absolute per-instance scratch path}"
mkdir -p "$KB_LANE"

mise run kb-codex -- --review \
  --base <FIXED> \
  ...
  --output "$KB_LANE/review.md" \
  < "$KB_LANE/method.txt"
```

— the guard on its own line, *before* the invocation, and the redirect attached to
the command it feeds.

---

## 6. SYNTHESIS LANE — where it corrected ME

A fourth `gpt-5.6-sol` lane cross-checked the three verdicts against this report.
It found six errors of mine. All six are accepted; the sections above were written
before it ran and are corrected here rather than silently edited.

### 6.1 🔴 My §3.1 headline was WRONG — I measured a TEAMMATE, not a subagent

I claimed *"a Claude Code subagent DOES get its own scratchpad directory."* That
overgeneralises from my own case. The mechanisms are three, not one:

| mechanism | session id | evidence |
|---|---|---|
| ordinary Agent-tool subagent | runs **inside** the parent session; transcript nests at `{sessionId}/subagents/agent-{agentId}.jsonl` | `sources/claude-code-docs/content/en/docs/claude-code/sub-agents.md:994,1021,1051` |
| in-session forked subagent (`/subtask`) | **identical** to the parent's | `python/src/kb_setup/context_usage.py:54,267`; `sub-agents.md:1078,1113` |
| **agent-team teammate** | its own — *"a separate Claude Code instance and full, independent Claude Code session"* | `sources/claude-code-docs/content/en/docs/claude-code/agent-teams.md:175,229` |

**I am a teammate**, which is why my id and transcript are my own. The synthesis
lane found the live team config naming my instance (`scratch-isolation-review`)
separately from my agent type (`kb-codex-astra-advisor`) —
`/Users/rmanaloto/.claude/teams/session-36755013/config.json:298`.

So: *no documented per-subagent scratch exists*, the native lane was right within
its scope, and my §3.1 claim is withdrawn. **§5's recommendation is unaffected** —
it was written not to depend on this.

### 6.2 I rejected a count, then reused it

At §3.1 I correctly discarded a directory-mtime count as non-discriminating, then
at §5 reused essentially the same count ("4 transcripts vs ~19 agents") as
corroboration. It is not corroboration: ordinary subagent transcripts are *nested*,
so they could never appear in that top-level count. **Withdrawn.** The `context_usage.py:54`
citation carries §5's caution on its own.

### 6.3 I contradicted myself on `ai-cli-invocation.md:56`

§2.3 listed it under "fixed paths that are CORRECT"; §2.7 called it a true
positive. **§2.7 is right and §2.3's row is wrong** — strike it. The file labels
the command *"for background use"* (`:55`), prescribes it for background tasks
(`:178`), and declares the patterns authoritative (`:185`). It is a live shared-writer
instruction and belongs in the gate's scope.

One thing I *did* overstate there: I called it "the SOURCE of the pattern" the
agent definitions copied. That is a causal claim I did not establish. It is a real
instance; whether it caused the others is **UNVERIFIED**.

### 6.4 "Extend `lane_recording`" — architecturally wrong, and I accept the correction

My §4.3 argued for extension on **parser reuse**. The synthesis lane's counter
decides it: **invariant ownership**. `lane_recording` enforces exactly one policy —
*do not restore `--ephemeral`* (`python/src/kb_setup/lane_recording.py:2`, `hk.pkl:506`).
Folding a second, unrelated invariant into it makes its command name and its
success message dishonest.

**Revised: build `python/src/kb_setup/lane_scratch.py`** — its own `Report`, CLI
verb, hk step and mutation arms — while *reusing* `lane_recording`'s fence and
continuation walkers and `skill_lint.command_lines()`. Shared machinery, separate
policy. §4.1/§4.2/§4.4/§4.5 stand; only the host changes.

Scope is wider than my §4.3 said: **both agent trees, both `lanes.md` copies, and
`.claude/rules/ai-cli-invocation.md`.**

### 6.5 `review-<sha>-<lane>.md` is NOT concurrency-safe

I listed it in §2.3 as correct "because it is a contract." That conflates two
things. `python/src/kb_setup/review.py:633` strips the `:variant` and returns one
deterministic path per SHA+lane, so two concurrent reviews of one SHA collide. A
consumer contract explains the *filename*; it does not create *writer isolation*.
It is still the right shape for findability — but it needs a writer discriminator,
not an exemption.

### 6.6 My §2.5 "workflows have no fixed shared scratch" is FALSE

I probed the workflows for `/tmp` and found none, then reported the wrong
conclusion — a token-spelling bound (`probes-need-a-control-arm.md` rule 3). The
sweep lane found them under `.agent/`:

- `.claude/workflows/session-review.js:281` (one default `reportDir` per run),
  `:354` (`${reportDir}/<lane>.md`), `:393` (`refute-<lane>.md`), `:995` (all
  refuters concurrent), `:1183` (fixed synthesis name)
- `.claude/workflows/kb-tool-review.js:216` (`peer-tool-synthesis-<joined-keys>.md`)
- `.claude/workflows/kb-extract.js:235,257` (`${scratchDir}/${s.key}.json`), `:275`
  (all sources parallel, **no uniqueness check on `sources[].key`**)

### 6.7 My rejection of `mktemp -d` was too broad

Accepted. `mktemp -d` is correct for **disposable intermediates** whose recovery
does not matter. It is wrong only where a caller must find the file after the lane
dies — i.e. `verdict.md`, and nothing else.

---

## 7. THE FULL COLLISION INVENTORY — 13 classes

From the sweep lane, verbatim file:line, independently reported. I have spot-checked
the `.claude/skills/kb-review/references/lanes.md` and `skill_lint` claims directly;
the rest are **as reported by that lane** and are marked so.

1. the agent-definition scratch paths (§1, §1b, §1c)
2. `.agent/kb/reports/agents/<agent-name>.md` — `agent-report-persistence.md:29,31,94`; restated at `kb-tool-researcher.md:80`, `kb-codex-advisor.md:100`, `kb-codex-astra-advisor.md:177` and the `.codex` twins
3. **`.agent/notepad.md` — every concurrent findings lane appends to ONE file**; `notepad-enforcement.md:3,8,40`. Ordinary Write/Edit is a read-modify-write, so this loses content
4. `.agent/kb/review/reports/review-<sha>-<lane>.md` + `receipt-<sha>.json` — `review.py:510,603,633` (§6.5)
5. `session-review.js` — `:281,354,393,995,1183`; the skill path adds only a date, so same-day runs collide (`kb-session-review/SKILL.md:262`). `mise.toml:1692` already documents real overwrites
6. `kb-tool-review.js` — `:54,100,216`; concurrent same-type verifiers at `:129`
7. `kb-extract.js` — `:54,235,257,275`; no uniqueness check on `sources[].key`
8. the generated `/graphify` skill — one cwd-wide namespace; `.claude/skills/graphify/SKILL.md:96,100,117,273,302,312,443,449`, and `cost.json` read-modify-write at `:630,644`, cleanup that can delete another run's intermediates at `:649`
9. `.claude/rules/ai-cli-invocation.md:55,178` — `/tmp/result.md` (§2.7, §6.3)
10. `.agent/kb/recall/<slug>.md` — `recall_work.py:227,1127,1331`; the slug truncates to 60 chars, so distinct topics can normalise to one filename
11. `gates-<sha>.json` / `outcome-<task>-<sha>.json` — `gates.py:346,384,774,781`, `pr.py:158`; `mise.toml:374,375` and the comment at `:364` already record a hand-run lint mixing evidence with `kb-gates`
12. `.agent/brain-audit.md` (`settings.json:181`, `brain.py:651,670`), the `graph_first` session marker (`graph_first.py:114,168`, idempotent), `.agent/kb/reflect/<session>.md` (`settings.json:186`, `session_reflect.py:817,843`)
13. `.agent/kb/native-extract` default (`graphify_native_extract.py:237,419,864`) and `extract-census-YYYYMMDD-HHMMSS.md` at second resolution (`extract_census.py:360,362,364`)

**Correctly excluded as prose, not instructions** (so a later sweep does not
re-flag them): `/tmp/out.log` at `long-running-command-hangs.md:71`,
`mise-tasks-only.md:42`, `mise.toml:710,1617`; `/tmp/lint.log` in both
`goal-engineering/references/rubric.md:62`; the new `>` blockquote warnings at
`kb-codex-advisor.md:54`, `kb-codex-astra-advisor.md:86`,
`kb-codex-astra-reviewer.md:71`; `graphify_ops.py:621`; the `eval_cases.py` guard
fixtures; `hk.pkl:150,436`.

---

## 8. COULD NOT ESTABLISH

- **Whether two concurrent instances of one agent TYPE receive distinct
  `CLAUDE_CODE_SESSION_ID`s.** I sent a sibling-probe request to the `fh-source-sweep`
  teammate asking for its scratchpad path; **no reply had arrived when this report
  was finalised**. Reported as the open item rather than filled in with reasoning.
  §5 is deliberately independent of the answer.
- **The construction and cleanup contract of `/private/tmp/claude-501/…/<id>/scratchpad`.**
  Undocumented. `CLAUDE_CODE_TMPDIR` (`env-vars.md`, verified directly) explains the
  `/tmp` + `claude-{uid}` prefix; the `<project-slug>/<session-id>/scratchpad` tail
  is not documented anywhere I could find.
- **Whether `ai-cli-invocation.md:56` CAUSED the agent definitions' pattern.** A real
  instance; the causal claim is unverified (§6.3).
- **Graph evidence from the codex lanes.** All three reported `mise run kb-query`
  failing before graphify ran (`mise WARN tool purgatory cleanup failed: Operation
  not permitted`, mise 2026.9.5). They correctly did not substitute a direct
  `graphify` call. My own `kb-query --prose --idf` from this session DID run
  (11,330 nodes indexed); its top hits were about subagent isolation generally and
  did not bear on the scratch-path question.
- **No implementation or mutation-arm run exists.** §4 is a design verdict only.
- **Citation offsets:** the native lane cited `agent-view.md:731` for `CLAUDE_JOB_DIR`;
  the line is **:742**. I verified the text independently. Treat every line number
  in a relayed citation as navigation, not evidence (`change-the-route.md` rule 5).

### Lanes that ran, and what produced what

| lane | model | rc | produced |
|---|---|---|---|
| sweep | gpt-5.6-sol / xhigh / read-only | 0 | §7's 13 classes |
| native-mechanism | gpt-5.6-sol / xhigh / read-only / **--network** | 0 | §3.2, §5's scoring table |
| gate-design | gpt-5.6-sol / xhigh / read-only | 0 | §4's predicate and arms |
| synthesis cross-check | gpt-5.6-sol / xhigh / read-only | 0 | §6's six corrections |

**No lane went idle without reporting, and no lane refused.** All four wrote their
verdicts to disk before returning.

---

## GitHub repos touched

- [openai/codex](https://github.com/openai/codex) — `sources/codex/`, read for per-thread scratch and the `CODEX_SESSION_ID`/`CODEX_THREAD_ID` distinction (`shell_environment.rs:6,145`, `exec_env.rs:30`, `spawn.rs:698,715`, `multi_agents.rs:53`, `recorder.rs:1635`, `seatbelt.rs:26`, `home-dir/src/lib.rs:5`), as reported by the native lane.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — `sources/claude-code/`, `sources/claude-code-docs/`; `sub-agents.md`, `agent-teams.md`, `env-vars.md`, `agent-view.md` for the subagent/fork/teammate distinction and `CLAUDE_JOB_DIR`/`CLAUDE_CODE_TMPDIR`. Both already have manifests.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — this repo's core dependency; `mise run kb-query --prose --idf` was run against the corpus it builds. Already pinned via `sources/graphify.manifest`.

_No new source needs adding to `sources/REGISTRY.md`: all three are already tracked._
---

## 9. 🔴 THE SIBLING PROBE CAME BACK — §3 IS REFUTED, NOT MERELY NARROWED

§8 listed the sibling-distinctness question as the one thing I could not establish.
It has since been answered, and the answer **refutes** §3.1 outright rather than
narrowing it the way §6.1 did.

**Two concurrently-running teammates report the SAME scratchpad directory, byte for
byte.**

| lane | scratchpad, verbatim |
|---|---|
| `scratch-isolation-review` (this lane) | `/private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/3b921834-9839-450d-aee1-0b72d7549b50/scratchpad` |
| `fh-source-sweep` (concurrent, different agent type) | **identical string** |

Both also reported the same `tasks/` namespace, `36755013-0c2e-45ae-985a-acfe76c91278`.

**The echo control, which is what makes this evidence rather than an anecdote.**
My probe message deliberately described the target as *"a path ending in
`<uuid>/scratchpad`"* and never contained a uuid or a full path. A matching uuid
therefore cannot be my own value parroted back. `fh-source-sweep` also flagged the
right caveat unprompted — it read `CODEX_COMPANION_SESSION_ID`, not
`$CLAUDE_CODE_SESSION_ID`, so its *variable* evidence corroborates shape only. The
**path** it quoted is direct, verbatim, and is the load-bearing fact.

### What this overturns

§3.3 said the agent definitions were *"overriding the isolation the harness already
provided"* and framed the whole fix as *"stop overriding the isolation you already
have."* **That framing is wrong and I withdraw it.** Had the definitions written to
`<scratchpad>/prompt.md` instead of `/tmp/<agent-name>-prompt.md`, five concurrent
advisor lanes would have collided in exactly the same way. The harness provided no
isolation at this level to override.

So the corrected picture across all three of my passes:

| claim | status |
|---|---|
| §3.1 "each subagent gets its own scratchpad" | **refuted** |
| §6.1 "…but a *teammate* does" | **also refuted** — two teammates share one |
| §5 "do not use `$CLAUDE_CODE_SESSION_ID` as a discriminator" | **confirmed, and now on direct evidence** rather than on `context_usage.py:54` alone |

My `$CLAUDE_CODE_SESSION_ID` is `3b921834…`, which is the *shared* uuid. So the
session id is shared across concurrent teammates, and using it as a discriminator
would have produced precisely the original collision — the shape `context_usage.py:54`
warned about and that both codex lanes refused to endorse without a sibling probe.
**The gate lane's refusal was correct and my measurement was the unreliable half.**

### What it confirms

§5's recommendation is unchanged and is now the only option standing. Every
harness-derived identity available to a lane — `$TMPDIR`, the scratchpad path,
`$CLAUDE_CODE_SESSION_ID` — has now been measured shared. **Nothing a lane can read
about itself discriminates it from a concurrent sibling.** Only the caller knows.

One incidental confirmation worth recording: this lane's own artifacts survived the
review only because I happened to write them to
`<scratchpad>/astra-scratch-isolation/` — a subdirectory named after my *instance*.
Four prompts and four verdicts sat in a directory `fh-source-sweep` was writing to
at the same time. The pattern §5 recommends is the one that accidentally saved this
report.

