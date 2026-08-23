# Refutation — bot-reviews finding 21 (all bot reviews/check-runs landed after mergedAt)

CLAIM: "Every bot PR review/check-run in the entire window (graphify-labs on all 4 PRs,
coderabbitai on #337, Repowise on all 4) landed strictly AFTER its own PR's mergedAt ...
no bot review in this window could structurally have gated its own merge."

VERDICT: REFUTED.

## The bound in the original probe
The offered evidence used `gh api .../pulls/N/reviews`. That endpoint returns only formal
REVIEW objects. It returns NOTHING for check-runs (a different endpoint,
`/commits/{sha}/check-runs`) and NOTHING for bot ISSUE COMMENTS
(`/issues/N/comments`). Repowise never files a review object at all — it posts an issue
comment plus a check-run — so the probe could not have returned "before merge" for Repowise
on any PR. The claim was universally quantified over "review/check-run"; the probe only ever
asked about reviews.

## Counterexamples (check-runs, `/commits/<headSha>/check-runs`)
merged_at re-read via REST `/pulls/N` (second route, agrees with `gh pr list`).

PR #337 merged 2026-08-18T03:43:21Z:
  Repowise / code health (repowise-bot)  completed 03:40:19Z  conclusion=failure  (-3m02s)
  Graphify Formal Verification (graphify-labs) completed 03:42:06Z conclusion=neutral (-1m15s)
  [code]smith (blacksmith-sh)            completed 03:40:43Z  conclusion=success  (-2m38s)
PR #336 merged 02:14:49Z: [code]smith completed 02:14:24Z (-25s)
PR #338 merged 04:33:31Z: [code]smith completed 04:33:23Z (-8s)
PR #339 merged 07:50:57Z: [code]smith completed 07:50:50Z (-7s)

So a bot check-run reached a terminal conclusion BEFORE mergedAt on all four PRs, and on
#337 three of the four did, including one by graphify-labs — a lane the finding names
explicitly as "all 4 after".

## Counterexamples (bot comments, `/issues/N/comments`)
#336 merged 02:14:49Z: coderabbitai 01:58:36Z (-16m13s), repowise-bot 01:58:40Z (-16m09s)
#337 merged 03:43:21Z: repowise-bot 03:40:20Z (-3m01s), coderabbitai 03:40:23Z (-2m58s)
#337's pre-merge repowise comment body contains "**❌ Health gate: failed**" and a
"**📌 Before you merge**" checklist — a substantive, terminal, failing bot verdict present
3 minutes before the merge. That is the direct negation of "could not structurally have
gated its own merge".

## Control arm (the probe discriminates)
The SAME check-runs endpoint returns after-merge rows: "Graphify" (graphify-labs)
completed 02:29:49 / 03:46:17 / 04:43:36 / 07:58:35Z, each strictly after its PR's
mergedAt. So the before/after comparison is not a one-faced coin.

## Effect on neighbours
Finding 20 (graphify-labs #336 review ran 15 min after merge) survives — 02:29:50Z vs
02:14:49Z is correct in isolation. Only the universal generalisation in 21 fails.
