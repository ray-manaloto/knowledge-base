# Refutation lane: hook_guard watch-deny message cites retracted do-not rationale

Task: try to REFUTE contradicted.md finding #8 (hook_guard.py:85's watch-deny
message cites the rationale do-not.md retracted 2026-08-01, and fails to name
the kb-watch remedy). Default refuted=true unless confirmed.

## VERDICT: NOT REFUTED — CONFIRMED on every leg, by an independent route

### Anchor verification (Read, 2026-08-18)

- `python/src/kb_setup/hook_guard.py:85` verbatim:
  `"watch": "NOT ALLOWED in this repo (do-not: graphify --watch / hook install)",`
- `.claude/rules/do-not.md:31` verbatim: "**`watch` was in this list and never
  belonged to it** (narrowed 2026-08-01)"; :32-33 the `--watch` spelling "is not
  a real invocation at all"; :37-38 "A ban filed under a reason that does not
  apply is one nobody can reason about later"; :43 "Use **`mise run kb-watch`**";
  :48-49 by-hand still fails rule 3 (so the DENY stays right).
- `mise.toml:510` — `[tasks.kb-watch]` exactly there (its comment :512-519 even
  explains the graphify-watch relationship).

### Live probes (executed, not reasoned; controls named)

`uv run python` scratchpad probes calling `kb_setup.hook_guard.decide()`:

- `graphify watch .` → DENY: "Do not run `graphify watch` by hand. **Use the
  mise task: NOT ALLOWED in this repo (do-not: graphify --watch / hook
  install).** All graphify work goes through a mise task ..." — cites the
  retracted rationale, does NOT name kb-watch, and the template renders a
  self-contradictory sentence ("Use the mise task: NOT ALLOWED...").
- Controls: `graphify path 'A' 'B'` → None; `graphify query "x"` → deny naming
  the real task `mise run kb-query`. Probe two-faced; not an artifact.
- **`graphify --watch .` → None (ALLOWED).** The guard's subcommand regex
  (`[a-z][a-z-]*`, hook_guard.py:38) cannot match the very spelling the message
  cites — the cited ban is unmatchable by the guard citing it. Discriminating
  arm: `graphify watch` (real spelling) denies in the same probe run.
- Sibling row hook_guard.py:84 `add-watch` → "NOT ALLOWED — never `graphify
  watch`", also no kb-watch remedy. Same class.

### History (staleness is real, not a deliberate keep)

- `git log -S 'do-not: graphify --watch / hook install' -- hook_guard.py` →
  exactly ONE commit: `1d11f0fd` 2026-07-22 (introduction; never edited since).
- Narrowing commit `43a6b468` 2026-08-01 (PR #102) touched `.claude/rules/do-not.md`
  (27 lines) and 29 other files — hook_guard.py NOT among them (git show --stat).
- No test pins the message text: `grep -n watch tests/test_hook_guard.py` → 0
  (control: `query` → 2 in same file; `NOT ALLOWED` → 0). The eval fixture
  `eval_cases.py:85` `_D("graphify watch", _DENY, "watch is a do-not in this
  repo")` pins only the VERDICT (deny) — correct per rule 3 and untouched by a
  message fix — while its label carries the same pre-narrowing framing.

### Transcript window (mtime >= 2026-08-17; .jsonl grepped, never read)

- "do-not: graphify --watch" occurs in 11 transcripts total (unbounded count;
  an earlier 10-file list was my own `| head` display bound, caught and re-run).
  In-window: only `6b974f05` (2026-08-17), 1 hit = a line-numbered Read echo of
  hook_guard.py (`83\t...85\t...`), not a firing.
- The rendered deny 'Do not run `graphify watch` by hand' occurs ONCE ever, in
  `f6decfb0` (2026-07-28, outside window) — the eval engine's inverted
  control-arm echo ("expected ALLOW, saw DENIED (...Use the mise task: NOT )"),
  truncated. So the stale message has never fired against a real command in the
  window; the defect is latent text, exercised by eval machinery whose
  assertions never read the text.

### Directive + handoffs (ALL read in full)

`docs/direction/2026-08-18-ray-directives.md` (234 lines) and handoffs b, c, d,
e, f, g, 2026-08-18-a: zero mentions of the watch row, no ruling legitimising
the message. The sweep the directive mandates (issues as durable output) is what
this finding feeds.

### Contradicting findings in the set: NONE — two corroborations

- contradicted.md #4 (Quick start vs the install row, hook_guard.py:86) is the
  SAME `_REDIRECT` NOT-ALLOWED-row class; its refutation lane
  (refute-quickstart-install-vs-guard.md) independently confirmed it. Corroborates.
- contradicted.md "VERIFIED-CONSISTENT" already pinned `mise.toml:510`
  kb-watch exists — corroborates the remedy clause.
- No finding asserts the message is current or that watch belongs to entry 2.

### What a fix must preserve (for the issue this becomes)

Keep the DENY (rule 3 + eval fixture requires it); change only the STRING at
hook_guard.py:85 (and :84) to cite rule 3 and name `mise run kb-watch`
(kb_setup.graph.refresh_self) as the remedy; optionally update the
eval_cases.py:85 label. Template nicety: the NOT-ALLOWED rows abuse the
"Use the mise task: {task}" slot — worth a message shape that doesn't read
"Use the mise task: NOT ALLOWED".

## COVERAGE

- REACHED AND ANALYSED: hook_guard.py (full 399 lines); do-not.md:20-54;
  mise.toml:495-530; eval_cases.py:55-105; tests/test_hook_guard.py (watch/NOT
  ALLOWED/query greps); live decide() probes (5 + 2 commands, both controls);
  git history of the message string and of the narrowing commit (43a6b468
  --stat + body grep); the 2026-08-18 directive IN FULL; all 7 handoffs IN
  FULL; contradicted.md IN FULL (the findings set); the sibling
  refute-quickstart-install-vs-guard.md; transcript greps (unbounded count,
  in-window context extraction, f6decfb0 disambiguation).
- OPENED BUT NOT FINISHED: nothing.
- NEVER REACHED: the other 10 findings' own refutation lanes beyond the
  quickstart one; graphify's pinned cli.py (do-not.md's 0-vs-7 `--watch` probe
  taken as recorded, since my live decide() probe independently establishes the
  spelling is dead HERE); PR #102's review discussion on GitHub.
