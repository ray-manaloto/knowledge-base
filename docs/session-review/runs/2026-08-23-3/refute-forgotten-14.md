# Refute lane: finding [forgotten] #14 — "session-review.js's `.result.report` is null and it has no completing step calling `gh issue create`"

## Sub-claims
A. `.result.report` is null (evidence cites run 1 `wf_8af76005-9bd`)
B. session-review.js has no completing step that calls `gh issue create`
C. that diagnosis has no GitHub issue
D. (causal) B is "the root cause of most other findings never being filed"

## Probes so far

1. `.claude/workflows/session-review.js:767` — `report: synthesised.value,`
   `judge()` at :632-639: `if (first) return { value: first, ranOn: 'fable/high' }`
   ⇒ report is null ONLY if BOTH fable and opus fallback return falsy.
2. `docs/session-review/runs/2026-08-18-1/run.json` .outcome:
   `{"status":"completed","agents":23,"synthesis_ran_on":"fable/high",...}`
   `synthesis_ran_on == 'fable/high'` ⇒ `first` was TRUTHY ⇒ report NOT null for run 2.
   The 19,909-byte `session-review-synthesis.md` is that report.
3. `grep -rn "gh issue create" --include='*.js' ...` (quoted; unquoted form was
   eaten by zsh — `(eval):1: no matches found: --include=*.js`) → 0 hits in
   `.claude/workflows/*.js`; BUT 1 hit in `.claude/skills/kb-session-review/SKILL.md:123`
   ("- **issues** (`gh issue create`) for anything deferred, with the evidence;")
   i.e. the filing step EXISTS, in the skill that owns step 5 "Apply".

## THE DECISIVE PROBE — the identical jq, both runs

```
D=~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/f1d1c0cf-43e1-4aea-b777-1faefbce022c/workflows
$ jq -r '{status, agentCount, report_type:(.result.report|type), report_len:(.result.report|tostring|length)}' $D/wf_8af76005-9bd.json
{ "status": "completed", "agentCount": 78, "report_type": "null", "report_len": 4 }

CONTROL ARM — same probe, the OTHER run (the one that produced this very finding):
$ jq -r '{status, agentCount, report_type:(.result.report|type), report_len:(.result.report|tostring|length), ran_on:.result.synthesis_ran_on}' $D/wf_3d0034e1-62d.json
{ "status": "completed", "agentCount": 23, "report_type": "string", "report_len": 2381, "ran_on": "fable/high" }
```

The probe DISCRIMINATES. `.result.report` is not a property of session-review.js;
it is a property of one dead run.

## Run 1 ran a SUPERSEDED version of the file — WRONG ARTIFACT

`jq -r '.result | keys' wf_8af76005-9bd.json` -> ["confirmed","lanes",
"lanes_that_did_not_return","partial_coverage","refuted","report","unverified"]
— **no `synthesis_ran_on`, no `not_triaged`**. Those keys were introduced by
`f772f5eb` (2026-08-18 09:48:09), together with `judge()`'s fable->opus fallback:

```
$ git show 022e88f4:.claude/workflows/session-review.js | grep -n "synthesis_ran_on\|async function judge\|report:"
365:State plainly, in the report:            <- only the prose hit
$ git show f772f5eb:.claude/workflows/session-review.js | grep -n "synthesis_ran_on\|async function judge\|report:"
510:async function judge(prompt, opts) {
580:  report: synthesised.value,
583:  synthesis_ran_on: synthesised.ranOn,
```

Run 1 launched 06:10 local, i.e. against `022e88f4` (03:30) — the single-dispatch,
no-fallback synthesis. The null-report defect was FIXED at 09:48 and run 2
launched at 09:49. The finding reads a superseded artifact as current state.

Run 1's journal confirms the death, not a report-phase bug:
`grep -o '"type":"[^"]*"' journal.jsonl | sort | uniq -c` -> `31 result`, `78 started`.

## The CAUSAL claim is refuted by the round's own issue list

Finding says the null report "is the root cause of most other findings in this
round never being filed". Run 2's report was NOT null, and:

```
$ gh issue list --state all --limit 1000 --json number,createdAt,title --jq '.[]|select(.createdAt>="2026-08-18")|[.number,.createdAt,.title]|@tsv'
345 2026-08-18T16:08:03Z ...
344 2026-08-18T15:52:12Z ...
343 2026-08-18T15:26:25Z ...
342 2026-08-18T15:26:05Z ...
341 2026-08-18T15:26:04Z ...
340 2026-08-18T15:25:08Z ...
```

Run 2 finished 10:21 local = 15:21Z. Six issues were filed 4-47 minutes later.
A non-null report produced filing immediately. The synthesis itself says filing
was *"deferred by decision"* — a human decision, not a null report.

## Sub-claim B is literally true but structurally mis-framed

`grep -rn "gh issue create" --include='*.js'` -> 0 in `.claude/workflows/*.js`.
BUT `grep -n "require(\|import \|readFile\|writeFile\|execSync\|child_process\|fetch(\|Bash"`
over ALL THREE workflow files -> **0 hits** (control: the same pattern hits
`~/.claude/plugins/.../runtime-query-ids.js`; and `grep -c "agent(" session-review.js`
-> 5, so the file is readable). Workflow scripts here have NO I/O primitive at
all. #341's own body states it: *"workflow scripts have no filesystem access"*.
A `gh issue create` completing step is not expressible in the .js.
It lives where it can run: `.claude/skills/kb-session-review/SKILL.md:123`
— *"- **issues** (`gh issue create`) for anything deferred, with the evidence;"*
inside § "5. Apply — and this is the half that gets skipped".

## Contradiction with finding #7 in this round's set

#7 states run 1 died "on the session limit at 31/78 agents". That is the
mechanism the journal shows and is incompatible with #14's framing of the null
report as a tool defect in the report/synthesise phase. Two probes of one fact;
#7 is the one the artifacts support.

## VERDICT: REFUTED
