# Refutation lane — bot-reviews finding on PR #439 Repowise code-health disposition

CLAIM: "Repowise's code-health FAIL on PR #439 was investigated this session
(MCP registered, get_risk/get_health retrieved 14 file:line findings on the 2
flagged files) but was never actually dispositioned: no fix commit touched
tool_sync.py, no issue was filed, and the report itself declined to adjudicate
it false because the API cannot identify which 2 findings are the 'new' ones
the bot's gate failed on."

## Step 0 — primary artifact read

`.agent/kb/reports/agents/repowise-mcp-pr-verify.md` exists (15060 bytes, mtime
Aug 22 12:13). Sections 6 and 7 are present and say what the finding says they
say. Lines 195-201 verbatim:

> **The honest bound: which TWO are "new" is still not retrievable.** No finding
> carries an `introduced_in` or `new` field ... The two top-`health_impact` rows
> are the strongest candidates and are **not** asserted to be the answer.

So conjunct 4 (report declined to adjudicate) is CONFIRMED from the primary
artifact, verbatim.

Remaining conjuncts to attack: "no fix commit touched tool_sync.py", "no issue
was filed", and the overall "never actually dispositioned".

## Step 1 — DEFECT FOUND in the offered evidence: the time-window probe is blind

The finding offers:
`git log --since="2026-08-22T16:00:00" --oneline -- python/src/kb_setup/tool_sync.py` -> empty

Local time when re-run: `Sat Aug 22 13:18:37 CDT 2026`, offset `-0500`.
git parses a bare `--since` timestamp in LOCAL time. 16:00 local on 2026-08-22
HAS NOT HAPPENED YET. The window is entirely in the future.

CONTROL ARM (the probe run with no path filter at all, i.e. the loosest possible
case it could match):

    $ git log --since="2026-08-22T16:00:00" --oneline | wc -l
    0

POSITIVE CONTROL (a path that provably WAS committed this session):

    $ git log --since="2026-08-22T16:00:00" --oneline -- .mcp.json
    (empty)
    $ git log --since="2026-08-22T00:00:00" --oneline -- .mcp.json
    25cb30f7 feat(mcp): register Repowise, and refute "it has no PR-scoped tool"

So the cited probe returns empty for a file that was demonstrably committed in
the very commit the finding itself cites as evidence. It could only ever have
returned "empty". It is not evidence for anything.

Related: the finding timestamps 25cb30f7 as `2026-08-22T17:14:04-05:00`. git
says `2026-08-22 12:14:04 -0500` (= 17:14:04 UTC). The offered timestamp glues a
UTC clock time onto a -05:00 offset, i.e. it is off by five hours.

RE-DERIVED, unbounded (the honest probe):

    $ git log --format='%h %ad %s' --date=iso -- python/src/kb_setup/tool_sync.py
    e0b06045 2026-08-21 15:39:59 -0500 tool sync 0821 (#439)
    07fb595b 2026-08-13 13:12:55 -0500 Add transactional tool synchronization (#288)

=> the CONCLUSION ("no fix commit touched tool_sync.py") survives re-derivation;
the EVIDENCE offered for it does not.

## Step 2 — SECOND DEFECT: the issue probe's stated result is factually wrong

Finding offers: `gh issue list --search "created:>=2026-08-22"` -> only #450, unrelated

Re-run verbatim, twice:

    $ gh issue list --search "created:>=2026-08-22" --json number --jq '[.[].number]|@csv'
    452,451,450,449,448,447,446,445,444,443
    $ gh issue list --search "created:>=2026-08-22" --json number --jq 'length'
    10

NEGATIVE CONTROL (proves the probe discriminates rather than always returning
rows):

    $ gh issue list --search "created:>=2027-01-01" --json number --jq 'length'
    0

Seven of the ten (#443-#449) were created 13:55-14:29Z on 2026-08-22, i.e. HOURS
BEFORE the repowise commit 25cb30f7 (17:14:04Z). The probe could not have
returned "only #450" at any point in the session.

Unbounded re-derivation of the substantive question (all states, limit 500):

    $ gh issue list --state all --limit 500 --search "tool_sync"    -> []
    $ gh issue list --state all --limit 500 --search "\"code health\"" -> []
    $ gh issue list --state all --limit 500 --search "repowise"     -> 8 issues
      (#450, #441, #407, #380, #367, #355, #332, #301 - none about #439's health gate)
    CONTROL: --search "graphify" -> 5+ rows. Probe discriminates.

=> "no issue was filed" survives; "only #450" does not.

## Step 3 — THE REFUTATION: there IS a standing, committed, tested disposition

`python/src/kb_setup/pr.py:94`

    _ADVISORY_CHECKS = frozenset({"CodeRabbit", "Repowise / code health"})

`python/src/kb_setup/pr.py:75-93`, verbatim:

> `Repowise / code health` joined 2026-08-17 on Ray's ruling, and it is a
> DIFFERENT argument from CodeRabbit's ... Repowise is advisory because of what
> it MEASURES. Its verdict on PR #336 was "AI-authored files account for the
> larger share of this PR's regression (-0.5 vs -0.0 human)": a delta on a
> composite score, attributed by authorship rather than by defect. That is a
> signal worth reading and not a statement that anything is wrong, and **a gate
> whose failure names no defect cannot be actioned - only appeased.**
> THE COST, stated rather than discovered later: no PR blocks on code health
> again. A real complexity regression now has to be caught by review or by the
> `C901`/`PLR0915` ruff rules, which are binding

Pinned by `tests/test_pr.py:1040 test_repowise_health_is_advisory_but_still_reported`,
WITH a control arm at :1066 (`test_a_binding_check_still_blocks_alongside_an_advisory_failure`).

Ray's own words, `docs/direction/2026-08-21c-ray-directives.md:67-68`:

> Asked how to treat **Repowise's advisory code-health FAIL on PR #439** (its two
> findings live only on a JS report page).

The directive's asks (lines 87-92) are: fresh shell -> confirm the variable by
COUNT only -> mcp2cli against the endpoint -> **read PR #439's findings** ->
**decide on a project-scoped `.mcp.json` entry**. The verb "decide" attaches to
the `.mcp.json` entry, not to the findings. Both were done: findings read (§7,
14 rows with file:line) and the entry committed (25cb30f7).

The binding backstop the ruling names is live: `pyproject.toml:110 select=["ALL"]`
(includes C901/PLR0915), `:184-185 [tool.ruff.lint.mccabe] max-complexity = 10`,
and `tool_sync.py` is NOT in per-file-ignores for C901 (only `cli.py:172` is).
`mise run lint` -> rc 0 on this branch.

The policy is observably in force on this very PR:

    $ gh pr view 439 --json state,mergedAt,mergeCommit
    {"state":"MERGED","mergedAt":"2026-08-21T20:39:59Z","mc":"e0b06045..."}
    $ gh pr checks 439
    Repowise / code health   fail   ...
    Graphify                 pass
    CodeRabbit               pass   Review rate limited

#439 merged WITH the health gate failing. That is not an omission; that is
`_ADVISORY_CHECKS` working.

## Step 4 — the prior round already ruled this NOT an omission

`.agent/kb/reports/agents/bot-reviews.md:157-176` (previous round's own lane):

> ### 7. Repowise `[bot]` - FAIL status, genuinely un-dispositioned, but
> user-scoped forward (not an omission)
> ... Per the review brief's own exception clause, this is the user deferring
> forward inside the reviewed window, not the round skipping it - so it is
> reported here as a still-open item with FAIL status, **not flagged as an
> omission**.

A peer refutation lane reached the same place independently:
`.agent/kb/reports/agents/refute-repowise-advisory-docs.md` - "handoff g:39:
'Repowise / code health made advisory so kb-land could merge.'"

## VERDICT: REFUTED

The two factual atoms survive (no commit touched tool_sync.py since e0b06045
2026-08-21; the report explicitly declined to name which 2 findings are new).
Everything the finding builds on them does not:

1. The git probe is blind by construction - 0 commits repo-wide, including the
   commit the finding itself cites.
2. The issue probe's stated result is wrong by a factor of ten and was never
   obtainable.
3. "Never actually dispositioned" is false. The disposition is committed
   (`pr.py:94`), tested with a control arm (`test_pr.py:1040`, `:1066`), ruled by
   Ray on 2026-08-17, restated by Ray in the 08-21c directive as "Repowise's
   ADVISORY code-health FAIL", exercised on #439 (merged with the gate red), and
   already adjudicated "not an omission" by the prior round's own lane.

The absence of a fix commit and of an issue is the POLICY-PRESCRIBED OUTCOME for
this check, not evidence of a dropped obligation.

## Contradiction with the rest of the set

Findings 32 (httpx2 typosquat) and 33 (musl lockfile) concern `graphify-labs[bot]`,
which is NOT in `_ADVISORY_CHECKS`. This finding (31) applies the same
"un-dispositioned" frame to Repowise, which IS. The set treats three bot signals
uniformly where the repo's own tracked code distinguishes them; 32/33 stand,
31 does not.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; PR #439, issues #443-#452
- [repowise-dev/repowise](https://github.com/repowise-dev/repowise) — the bot whose check is at issue
