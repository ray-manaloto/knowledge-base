# Refutation lane: bot-reviews finding (PR #469 graphify-labs review absence)

## Claim
"graphify-labs' review has not posted on PR #469 as of 18:10:39Z (7.5 min after PR open);
NOT yet distinguishable from 'still running' ... 3-29 min for prior PRs."

## Probe 1 (re-run of the original, later clock)
```
$ date -u   -> 2026-08-23T18:20:07Z
$ gh pr view 469 --json createdAt -> 2026-08-23T18:03:08Z
$ gh api repos/ray-manaloto/knowledge-base/pulls/469/reviews \
    --jq '[.[]|{login:.user.login,state:.state,submitted_at:.submitted_at}]'
[{"login":"graphify-labs[bot]","state":"COMMENTED","submitted_at":"2026-08-23T18:16:58Z"}]
```
=> The review DID post, at 18:16:58Z = 13m50s after open. Inside the finding's own 3-29 min band.

## Probe 2 — the ROUTE bound (the decisive one)
The original probe read only `/pulls/469/reviews`. graphify-labs posts by more than one route.

```
$ sha=$(gh pr view 469 --json headRefOid --jq .headRefOid)   # 24d11e49c946e13a9ff1f610d3ab1ac7f8d3abd4
$ gh api repos/ray-manaloto/knowledge-base/commits/$sha/check-runs \
    --jq '[.check_runs[]|{name,app:.app.slug,status,started_at,completed_at,conclusion}]'
[{"app":"graphify-labs","completed_at":"2026-08-23T18:16:57Z","conclusion":"success","name":"Graphify",...},
 {"app":"graphify-labs","completed_at":"2026-08-23T18:09:35Z","conclusion":"neutral","name":"Graphify Formal Verification","started_at":"2026-08-23T18:09:35Z","status":"completed"},
 {"app":"repowise-bot",...,"18:03:46Z"},{"app":"blacksmith-sh",...,"18:03:11Z"}]
```
graphify-labs COMPLETED a check run at **18:09:35Z — 64 seconds BEFORE** the finding's
18:10:39Z observation. So "graphify-labs has not posted" was already false when written,
on any reading broader than "no object at the /reviews endpoint".

## Probe 3 — latency table re-derived (control arm; proves the probe discriminates)
```
$ for n in 410 422 439 453 459 463 466 469; do created=$(gh pr view $n --json createdAt --jq .createdAt);
  first=$(gh api .../pulls/$n/reviews --paginate --jq '[.[]|select(.user.login=="graphify-labs[bot]")][0].submitted_at'); ...
```
| PR | created | graphify-labs 1st review | latency | posted by 7.5 min? |
|---|---|---|---|---|
|410|15:26:12|15:32:00|5m48s|yes|
|422|03:05:28|03:11:12|5m44s|yes|
|439|19:05:27|19:14:33|9m06s|**no**|
|453|20:32:20|20:48:17|15m57s|**no**|
|459|23:41:22|23:44:08|2m46s|yes|
|463|02:22:43|02:51:46|29m03s|**no**|
|466|05:55:20|06:17:36|22m16s|**no**|
|**469**|18:03:08|**18:16:58**|**13m50s**|**no**|

Control arm: the identical command shape returned non-empty `submitted_at` for all 7 prior
PRs (so the login spelling `graphify-labs[bot]` is right and the probe can return a positive),
and now returns non-empty for 469 too. The 18:10:39Z zero was a TIME bound, not an absence.
4 of the 7 comparison PRs were also silent at the 7.5-min mark — i.e. the probe at that clock
was a coin whose majority face is "absent".

## Verdict: REFUTED
- The review landed at 18:16:58Z, 13m50s after open — inside the finding's own 3–29 min band
  (true min 2m46s, max 29m03s), i.e. entirely ordinary.
- A graphify-labs check run had already completed at 18:09:35Z, before the observation.
- Nothing to report: the finding is a snapshot of a bot that was still running, and it
  resolved to the benign branch 6 min later.

## Cross-check against the other findings
- Finding 29 (CodeRabbit skipped on #469): CORROBORATED, not contradicted. `issues/469/comments`
  shows coderabbitai[bot] at 18:03:19Z with "Review skipped / Too many files! ... 140 files,
  which is 40 over the limit of 100". Caveat for that lane: the same comment ALSO says
  "This review couldn't start because sufficient usage credits or metered capacity aren't
  available", so file-count is not the sole stated cause.
- Same defect class in both bot-reviews findings: `/pulls/N/reviews` under-reports bot activity.
  CodeRabbit left no review either, yet it posted an issue comment; graphify-labs left no review
  at 18:10, yet it had posted a check run.
