# Refutation: "Nine plugins" vs "ten enabled plugins" vs settings.json's 10

Claim under test (lane `contradicted`, finding 19): `.claude/CLAUDE.md` says nine,
`.claude/rules/md-size-budgets.md` says ten, and `.claude/settings.json`'s **live**
`enabledPlugins` "actually has 10 entries".

## VERDICT: REFUTED (the third leg is wrong; the live count is 8)

### The two doc quotes are verbatim true
- `.claude/CLAUDE.md:46` — `**Nine plugins are enabled in / total**, which is what \`md-size-budgets.md\` § the skill-listing budget is about.`
- `.claude/rules/md-size-budgets.md:109` — `with seven project skills plus **ten** enabled plugins' skills`

### The third leg is a WRONG-ARTIFACT probe
`len(json.load(open('.claude/settings.json'))['enabledPlugins'])` counts *declarations in one
settings file*, not enabled plugins. It never reads `.claude/settings.local.json`, which is
HIGHER precedence and disables two of them:

```
$ cat .claude/settings.local.json
  "enabledPlugins": {
    "claude-md-management@claude-plugins-official": false,
    "mise@brentmitchell25": false
  }
```

Primary doc (ingested corpus, `sources/agent-harness-docs/docs/claude-code/settings.md:54-57`):
"3. **Local**: overrides project and user settings"; and at :816 —
"To opt out of a project-enabled plugin on your machine, set it to `false` in
`.claude/settings.local.json` instead."

### Live probe — the tool's own answer
`claude plugin list` → 210 unique plugin ids, **8 unique ENABLED**:
antigravity@antigravity-for-claude-code, astral@astral-sh, codex@openai-codex,
fable-orchestrator@fable-orchestrator, mattpocock-skills@mattpocock,
plugin-eval@claude-code-workflows, pr-review-toolkit@claude-plugins-official,
skill-creator@claude-plugins-official.

CONTROL ARM (the probe can return the other answer):
`claude-md-management@claude-plugins-official -> {'disabled'}` and
`mise@brentmitchell25 -> {'disabled'}` — exactly the two the local file turns off.
Second control: the same count one-liner over history returns 5 at `cd93801b`,
10 at `a8ce533b`, 11 at `a2ef5d88` — it is not stuck on 10.
`~/.claude/settings.json` contributes 0 (`enabledPlugins` == {}).

### So BOTH docs are wrong, and so is the finding
live = 8; CLAUDE.md says 9; md-size-budgets says 10; finding says 10.

### Two more inaccuracies in the finding
- "same 2026-08-03 date": `git log -S'Nine plugins are enabled' -- .claude/CLAUDE.md`
  → `7c9d62c4 2026-08-13`. The md-size-budgets "ten" is `76654672 2026-08-03`, and it was
  CORRECT then (`git show a8ce533b:.claude/settings.json` → 10). The dates are 10 days apart.
- "three of which are never named anywhere in CLAUDE.md's plugin section":
  `astral` → 0 hits in `.claude/CLAUDE.md` (holds); `mattpocock` → hit at `.claude/CLAUDE.md:10`;
  `codex` → hits at lines 32, 37, **40 (inside the plugin section)**, 61.
  Control: the same grep returns hits for `codex`/`mattpocock`, so the 0 for `astral` is real.

### md-size-budgets disclaims its own number
`.claude/rules/md-size-budgets.md:112-115`: "**Re-measure rather than trusting this number**
… A count in prose is stale the moment someone enables a plugin."

### Contradiction with other findings this round
None. No other listed finding states a plugin count. Finding 20 (native graphify hook-guard
wired in `.claude/settings.json`, firing this session) is consistent with what I observed —
the MANDATORY graph-first nudge fired on every Bash call here.

## GitHub repos touched
_None._
