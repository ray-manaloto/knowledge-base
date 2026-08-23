# Refutation attempt — finding 19 (lane: contradicted)

**Claim (verbatim):** CLAUDE.md and do-not.md both assert only `graphify-out/memory/`
is committed, but this round tracked 106 more files under
`graphify-out/graphify-semantic-corpus-chunks/` (347 total tracked under
`graphify-out/`), per Ray's own 2026-08-23 #317 ruling documented in `.gitignore`
-- and neither doc was updated.

**Verdict: NOT REFUTED.** The contradiction is real, reproducible at HEAD, and the
finding is UNDER-stated (a third doc also contradicts). One number is wrong.

## Probes

```
$ git ls-files graphify-out/ | wc -l
     347
$ git ls-files graphify-out/ | awk -F/ '{print $2}' | sort | uniq -c | sort -rn
 237 memory
 105 graphify-semantic-corpus-chunks
   5 graphify-semantic-slice
```

Doc text at HEAD:

- `CLAUDE.md:169` — "… Committed: **only `memory/`** (authored work-memory). …"
- `.claude/rules/do-not.md:65` — "5. **Do NOT commit `graphify-out/` beyond `memory/`.**"

Tracking commit:

```
$ git log -1 --format='%H %ad' --date=iso a7ae6d7be1c0
a7ae6d7be1c0b9addeba0c5c69c56ff5db434b4c 2026-08-23 12:33:06 -0500
   chore(corpus): track the staged provider evidence, closing #317 as TRACKED
$ git merge-base --is-ancestor a7ae6d7be1c0 HEAD && echo yes
yes
$ git show --stat a7ae6d7be1c0 | grep -E 'CLAUDE.md|do-not.md|gitignore'
 .gitignore  | 19 +++++++++++++------
$ git ls-tree -r --name-only a7ae6d7be1c0 graphify-out/graphify-semantic-corpus-chunks/ | wc -l
     105
```

"Neither doc was updated" — newest commit touching each:

```
$ git log -1 --format='%h %ad %s' --date=iso -- CLAUDE.md
c4ea46a0 2026-08-23 01:28:35 -0500 session review report always (#466)
$ git log -1 --format='%h %ad %s' --date=iso -- .claude/rules/do-not.md
43a6b468 2026-08-01 19:59:38 -0500 feat/graph navigation and tool review (#102)
```

Both predate the 12:33 tracking commit. CONFIRMED.

## Control arms (the probes discriminate)

1. `git ls-files` positive/negative on the SAME tree:
   - positive: `git ls-files graphify-out/memory | wc -l` -> `237`
   - negative on a file that EXISTS but is untracked:
     `ls -la graphify-out/graph.json` -> 772120976 bytes present;
     `git ls-files graphify-out/graph.json` -> empty.
   So an empty result means "untracked", not "probe blind".
2. `git log -1 -- <path>` positive: same command on `.gitignore` returns
   `a7ae6d7b 2026-08-23 12:33:06` — i.e. it CAN report a post-tracking edit. It
   returns an earlier date for CLAUDE.md/do-not.md because none exists.

## The one real defect in the finding: the count

`106` is wrong in both readings:

- files under `graphify-out/graphify-semantic-corpus-chunks/` = **105** (at
  a7ae6d7b and at HEAD).
- tracked files under `graphify-out/` beyond `memory/` = **110**
  (105 chunks + 5 `graphify-semantic-slice`).

`347 total` is correct. Restate as: **110 tracked files beyond `memory/`, 105 of
them under `graphify-semantic-corpus-chunks/` and 5 under
`graphify-semantic-slice/`.**

## The finding is UNDER-stated: a THIRD doc contradicts, more directly

`.claude/rules/clean-git-state.md:62-67`:

> **Why that path and not an ignore rule.** `graphify-out/graphify-semantic-corpus-chunks/`
> is deliberately absent from `.gitignore` and the comment there says why: it is
> retained provider evidence for a run that cost real tokens, and whether to track
> it is the open question in #317. Ignoring it settles that question silently;
> committing it settles it just as silently the other way. **Untracked-and-visible is
> the intended state**, and a blanket add is the one command that destroys it without
> anyone deciding.

That paragraph is now false on three counts at HEAD: #317 is settled, the state is
tracked, and the rule's stated rationale for the `git add -A` DENY rests on a
premise the same round reversed. It survives because `git log -1 -- .claude/rules/clean-git-state.md`
also predates a7ae6d7b.

Also note `graphify-out/graphify-semantic-slice/` has been tracked since
**2026-08-14** (`cc6e226b`) / `98b116fd` (2026-08-15) — so `do-not.md:65` was
already false for 9 days before this round; the round widened an existing
contradiction rather than creating it.

## Contradiction with other findings this round

None. Finding 29 (CodeRabbit's 140-file skip on PR #469) CORROBORATES: a PR
carrying ~105 fresh chunk files is exactly what blows the 100-file cap. Findings
41/47 treat the chunk receipts as on-disk artifacts, consistent with tracking.
No finding asserts the chunks are untracked.

## GitHub repos touched

_None._
