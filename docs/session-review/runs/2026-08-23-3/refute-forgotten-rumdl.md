# Refutation attempt — forgotten lane, rumdl currency dependency

## Claim under judgment
Ray's queued ask (2026-08-19T16:16:53Z) that rumdl "should be a critical/currency
dependency": half done (sources/rumdl.manifest exists), half not ([tool.rumdl]
absent from currency.toml). #383 lists it open. Handoff prose ambiguous.

## Probes run (as I go)

### P1 currency.toml [tool.*] sections (HEAD ff299734, branch clear-prep-2026-08-19b)
`grep -n "^\[tool\." currency.toml` -> 13 sections:
graphify ffmpeg mise claude-code hk fnox doppler skillopt uv ruff ty codex antigravity-cli
NO rumdl. Control: `grep -n -i ruff currency.toml` -> [tool.ruff] at 1447 (probe discriminates).
Only rumdl mention in currency.toml is line 446, prose inside another item.

### P2 sources/rumdl.manifest
EXISTS (1295 bytes). `added = 2026-08-02`, ref v0.2.57, kind=code, cites #81.
=> the manifest PREDATES the 2026-08-19 ask by 17 days.

### P3 issue #383 (gh issue view 383 --json state,body / --comments)
state = OPEN, labels P1 + directive + currency.
Body verbatim: *"it \"should make rumdl a critical/currency dependency\""*.
Comment 2026-08-19T17:31:21Z (sortakool) closes with:
  "**Promoting rumdl and agnix to tracked currency dependencies** — not done, and
   for rumdl it should wait on #358 (use-or-remove)"
=> the finding's "#383 correctly lists this as an open acceptance criterion" is
   CONFIRMED VERBATIM.

### P4 the handoff prose (.agent/plans/session-2026-08-19.md:245-252)
Heading L245: "### The `v`-prefix question has TWO answers, and both are now right"
L251-252: "The `currency.toml` machinery originally proposed for
this in #383 is **withdrawn**; nothing was needed."
L254: "### Still owed, unchanged" -> lists agnix, graphify sync, claude-code,
the two gates, #373, build stamp, the 08-18 P0 set. rumdl is NOT in it.
`grep -nE "critical|currency dependency|promot" session-2026-08-19.md` -> ONE hit,
the #380 row about bot reviews. Control: the grep returns a hit, so it discriminates.
=> the rumdl PROMOTION item appears NOWHERE in the newest handoff.

### P5 never-existed check (all refs)
`git log --all --oneline -S'[tool.rumdl]' -- currency.toml` -> 0 commits.
Control: `-S'[tool.antigravity-cli]'` -> d937841d, 0f235f52. Probe discriminates.
`mise run kb-currency-check` output names graphify + skillopt, never rumdl.

### P6 THE CITATION IS WRONG (the refutation I found)
`jq 'select(.timestamp=="2026-08-19T16:16:53.812Z")'` on the session jsonl:
  type=queue-operation, content = "instead of hand modifying mise.toml and
  pyproject.toml or other config files ..." -- that is the FOURTH ADDENDUM /
  issue #381, NOT the rumdl ask.
The rumdl ask is the /clear-prep message at **2026-08-19T16:05:07.748Z**, stored
verbatim at docs/direction/2026-08-19-ray-directives.md:59.
Control: grep -l 'rumdl a critical' over all 239 project jsonl -> only this
session's own file (which holds the prompt); 97 files contain "rumdl", so the
grep works.

### P7 "one half done" is generous, not wrong
sources/rumdl.manifest `added = 2026-08-02`, cites #81; `git log --follow` shows
only e084df70 (#136) and 482e1220. The round's only touch was c8af8beb
"fix(currency): sync sources/rumdl.manifest pin to v0.2.57" -- a pin sync, not a
promotion. So ZERO halves of the promotion ask were done in-round.

### P8 the strongest counter-route, and why it fails
Ray, queued 2026-08-19T17:28:58.653Z (and re-queued 17:29:30.127Z):
  "- we should have researched what mise provides regarding the change for prefix 'v'
   - did we try to just update rumdl = \"v0.2.52\" to rumdl = \"0.2.52\"
   - i dont think the change to currency.toml is necessary"
A BROAD reading ("no currency.toml change at all") would make the handoff's
"withdrawn; nothing was needed" accurate and the finding wrong. It fails: all
three bullets are scoped "regarding the change for prefix 'v'"; #383's only
currency.toml proposal is the `tag_prefix` field, offered for the v-prefix; and a
broad reading has Ray reversing his own 16:05:07Z directive 2h23m earlier with no
statement to that effect. The round itself read it narrowly (see P3).
This same quote is, however, exactly what makes the handoff sentence misreadable.

## VERDICT: NOT REFUTED on substance; the provenance citation IS refuted.
