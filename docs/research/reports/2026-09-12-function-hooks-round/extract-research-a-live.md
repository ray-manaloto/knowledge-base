# TRACK A (live probes) — what `gh` can pull out of GitHub issue 91870

Lane: run directly by `kb-codex-astra-advisor` in the Claude session, because a
codex `--sandbox read-only` lane has **no network egress** and cannot run any of
these. A companion lane (`extract-research-a1-gh-source`) reads gh's Go source
at the pin to answer the mechanism questions without network.

All probes run **2026-09-12**. `gh` = **2.98.0 (2026-08-20)**, pinned at
`mise.toml`. Target: `anthropics/claude-code#91870`.

## Rate-limit baseline — so no zero below can be a rate limit

Taken BEFORE the probes and re-read after each block:

```
core:    limit 5000, remaining 4903, used 97
graphql: limit 5000, remaining 5000, used 0
search:  limit 30,   remaining 30,   used 0
```

After the comment-count block: core 4899, graphql 5000. **No probe below ran
near a limit.** Every zero/short result reported here is an answer, not an
outage.

## FINDING 1 (headline) — `gh api .../comments` silently returns 30 of 161, rc 0

Control-armed four ways against the issue's own authoritative count:

| route | comments returned | rc |
|---|---|---|
| `gh api repos/anthropics/claude-code/issues/91870` → `.comments` (authoritative) | **161** | 0 |
| `gh issue view 91870 --json comments` → `.comments \| length` | **161** | 0 |
| `gh api repos/.../issues/91870/comments` (no `--paginate`) | **30** | 0 |
| `gh api repos/.../issues/91870/comments --paginate` | **161** | 0 |

**The third row is the trap**: it exits 0, prints valid JSON, and drops 131 of
161 comments with no warning. Anyone who writes the obvious command gets 18.6%
of the issue and no signal that anything is missing.

**`gh issue view --json comments` does NOT truncate at 161** — it returns the
full set without `--paginate`, because the GraphQL path paginates internally.
That refutes the natural assumption that the view command is the lossy one.

The control arm that makes this evidence rather than opinion: the same
`--jq 'length'` shape returned 30, 161 and 161 across three routes in the same
minute at the same rate-limit budget, so the shape can produce both a short and
a full answer.

## FINDING 2 — the two `--json` field sets are IDENTICAL (27 fields)

`gh issue view --json` and `gh issue list --json` accept exactly the same set at
2.98.0, derived by invoking each with a bare `--json` (which makes gh print its
accepted fields):

```
assignees author blockedBy blocking body closed closedAt
closedByPullRequestsReferences comments createdAt id isPinned issueType labels
milestone number parent projectCards projectItems reactionGroups state
stateReason subIssues subIssuesSummary title updatedAt url
```

**No field exposes attachments or uploaded assets as structured data.** Assets
exist only as markdown inside `body` and inside each comment's `body`. (Control
arm for that negative: the same enumeration DOES contain `reactionGroups` and
`closedByPullRequestsReferences`, so the listing is complete rather than
filtered — an attachment field would have appeared had one existed.)

## Issue 91870 at a glance (measured, not inherited)

```
number      91870
title       "Function Hooks - make plugins 10x more powerful"
state       open
author      poteat
created_at  2026-09-03T18:00:23Z
updated_at  2026-09-12T00:40:29Z
comments    161
reactions   141 (total_count on the issue itself)
body length 9306 characters
```

<!-- probes continue below; this file is written incrementally -->

## FINDING 3 — the asset inventory is 22 files / 50.7 MB, not "9 videos + a PDF"

**This contradicts the brief and is a finding, not a correction of wording.**
Extracted from the issue body plus all 161 comment bodies, then each URL probed
for its real type:

| type | count | total |
|---|---|---|
| `video/mp4` | **9** | 46.8 MB |
| `image/jpeg` | **9** | 0.98 MB |
| `image/gif` | 1 | 3.86 MB |
| `image/png` | 1 | 0.61 MB |
| `image/svg+xml` | 1 | 0.59 MB |
| `application/pdf` | 1 | 0.29 MB |
| **total** | **22 distinct URLs** | **50.7 MB** |

The brief's "9 videos and an architecture PDF" is exactly right on those ten.
What it omits is **12 image assets** — 9 jpegs (~110 KB each, near-identical
sizes, almost certainly a screenshot series), a 3.9 MB animated GIF, a 612 KB
PNG and a 591 KB SVG. The SVG in particular is text and is directly ingestible
as prose; the GIF is a screen recording in a container `transcribe.py` does not
list.

Grep control arm: the same `grep -oE 'https://…'` shape over the same corpus
returned 41 `github.com` URLs and a host histogram (`github.com` 41,
`example.com` 2, `x.com` 1, `code.claude.com` 1, `jquery.com` 1, `ftp.gnu.org`
1, `policy.internal` 1) — so the extraction shape discriminates and the 22 is
not a truncated match.

## FINDING 4 (decisive for Track B) — `assets/<uuid>` URLs carry NO file extension

Two distinct durable URL forms appear, and they behave differently:

| form | example | extension in URL? |
|---|---|---|
| `github.com/user-attachments/files/<id>/<name>.<ext>` | `.../files/31802150/EXTERNAL.Function.Hooks.Core.Architecture.pdf` | **yes** — `.pdf` |
| `github.com/user-attachments/assets/<uuid>` | `.../assets/ea09f465-d147-4884-947e-fb32c39649fa` | **no — none at all** |

21 of the 22 assets use the extension-less `assets/<uuid>` form. **Reordering
graphify's `_detect_url_type` if-chain would therefore fix only ONE of the 22
assets** (the PDF), because the other 21 have no extension for any
extension-based branch to match. The true type is discoverable only by
performing the fetch and reading `Content-Type`, or by reading the signed
redirect target's path.

## FINDING 5 — HEAD returns 403; the 403 is a probe artifact, not an answer

The first sweep ran `curl -sIL` (HEAD) over all 22 URLs and got **403 from
`github-production-user-asset-6210df.s3.amazonaws.com` for all 21 `assets/`
URLs**. Reporting that as "the assets are unreachable" would have been wrong.

Control arm, same URL, method swapped:

```
HEAD  (curl -sIL)          -> final_code=403  type=application/xml   size=0
GET   (curl -sL -r 0-1)    -> final_code=206  type=video/mp4         size=2
GET   (curl -sL -r 0-65535) -> file(1): "ISO Media, MP4 Base Media v1"
```

Cause: the S3 presigned signature covers the HTTP **method**, so a presigned-GET
URL rejects HEAD. Anything probing these with `curl -I` will read a live,
public, downloadable asset as forbidden.

## FINDING 6 — durable vs signed URL, answered

- **Durable**: `https://github.com/user-attachments/{assets/<uuid>|files/<id>/<name>}`.
  This is what is stored in the issue markdown and what survives. It is a
  redirector, and it is the form to record in the corpus.
- **Ephemeral**: the redirect target. For `assets/` it is
  `github-production-user-asset-6210df.s3.amazonaws.com/<owner-id>/<asset-id>-<uuid>.<ext>`
  carrying `X-Amz-Algorithm / X-Amz-Credential / X-Amz-Date / X-Amz-Expires=300
  / X-Amz-Signature / X-Amz-SignedHeaders` plus `response-content-type`. For the
  PDF (`files/` form) it is `objects.githubusercontent.com`, also
  `X-Amz-Expires=300`.
- **`X-Amz-Expires=300` measured on every one of the 22.** Five minutes. Never
  store a signed URL; always re-resolve from the durable one.
- Bonus: the signed path leaks the **true original filename with extension**
  (`645860106-ea09f465-….mp4`), which is a second, cheaper route to the media
  type than reading `Content-Type` — but it is only visible after following the
  redirect, so it does not help a pre-fetch classifier.
- These fetches were **unauthenticated** `curl` (no token), so the assets are
  public and no credential is needed to ingest them.

## FINDING 7 — what each route uniquely provides (measured)

Entity counts, all `--paginate`d, all rc 0:

| route | entries | bytes |
|---|---|---|
| `gh api .../issues/91870` | 1 | 12,762 |
| `gh api .../comments --paginate` | 161 | 590,177 |
| `gh issue view --json comments,body,…` | 161 | 391,661 |
| `gh api .../timeline --paginate` | **479** | 1,998,545 |
| `gh api .../reactions --paginate` | **141** | 155,706 |

**Comment object field sets differ between the two comment routes** (keys read
off the first element of each):

- REST `/comments` only: `performed_via_github_app`, `pin`, `node_id`,
  `issue_url`, `html_url`, **`updated_at`**, `reactions` (counts inline),
  `minimized` (bool).
- GraphQL (`--json comments`) only: `includesCreatedEdit`, `minimizedReason`,
  `viewerDidAuthor`, `reactionGroups`, `id` (GraphQL node id, different value).

So **`updated_at` per comment is REST-only** — you cannot tell from
`gh issue view` whether a comment was edited after posting, only *that* it
includes a created-edit (`includesCreatedEdit`). Conversely `minimizedReason`
(why a comment was hidden — spam/off-topic/abuse) is **GraphQL-only**.

**`/timeline` uniquely provides** (event histogram over all 479 entries):

```
161 commented        150 subscribed      121 mentioned
 23 cross-referenced  15 unsubscribed      5 referenced
  3 labeled            1 comment_deleted
```

Three of those are reachable by no other route:
- **`cross-referenced` × 23** — every other issue/PR that links to 91870. For
  our purpose this is the highest-value unique: it is the map of where the
  function-hooks discussion continued.
- **`comment_deleted` × 1** — a comment was deleted. Neither `/comments` nor
  `--json comments` can show that a deletion happened; both simply return 161
  and look complete.
- **`referenced` × 5** — commits referencing the issue.

**`/reactions` uniquely provides per-user attribution** on the issue itself —
141 rows of `{content, user, created_at}`. The `reactionGroups` field gives
totals only. Breakdown: `+1` 95, `heart` 13, `rocket` 12, `hooray` 11, `eyes` 8,
`laugh` 2. (Comment-level reactions are inline in the REST comment objects; a
separate `/comments/{id}/reactions` call would be needed for per-user detail
there.)

## FINDING 8 — 2.99.0 adds attachment support in the WRONG DIRECTION; 2.100.0 adds nothing relevant

Release notes read from the API (`gh api repos/cli/cli/releases/tags/<tag>`),
not from memory. Both releases postdate our pin:

| tag | published | relevant to extracting an issue? |
|---|---|---|
| v2.98.0 (our pin) | 2026-08-20 | — |
| v2.99.0 | 2026-09-01 | **partially — but upload-only** |
| v2.100.0 | 2026-09-03 | **no** |

**v2.99.0's headline is `--attach`** — a repeatable flag on `gh issue
create/edit/comment` and `gh pr create/edit/comment` that **uploads** local
images and videos and rewrites local markdown references to the uploaded URL
(PRs #14177–#14184, #14289 caps a batch at 50 files). It is the write path.
**Nothing in it reads, lists or downloads an existing attachment.** So the one
release that finally teaches gh about attachments still gives us no route to the
22 assets in 91870. This is a genuine "no", and it is more useful than a
manufactured yes: upgrading gh does not solve our problem.

**One behaviour change in v2.99.0 does affect us**: `fix(view): reject
--comments with --json` (#14215). Armed on our pinned 2.98.0:

```
gh issue view 91870 --comments --json number  ->  {"number":91870}   rc=0
gh issue view 91870 --json number             ->  {"number":91870}   rc=0   (control)
```

At 2.98.0 the two flags combine **silently, with `--comments` ignored** — the
output is identical to `--json number` alone. From 2.99.0 that same command
errors instead. Either way you do not get comments from it; 2.98.0 just fails
quietly and 2.99.0 fails loudly. Anything we write should use
`--json comments`, never `--comments --json`.

**v2.100.0** adds experimental per-host `api_host` API routing, promotes a
`webhook` extension, and prints fuller help when invoked by a coding agent.
Nothing touches issues, comments, attachments or pagination.

Control arm for "2.98.0 has no `--attach`": `gh issue create --help | grep -c
attach` → **0**, while the same shape for a flag known to exist (`body-file`) →
**1**. The zero is an answer, not a broken grep.

## FINDING 9 — the REST issue object has no attachment field either

`gh api repos/anthropics/claude-code/issues/91870 --jq 'keys'` → 34 keys:

```
active_lock_reason assignee assignees author_association body closed_at
closed_by comments comments_url created_at events_url html_url id
issue_dependencies_summary issue_field_values labels labels_url locked
milestone node_id number performed_via_github_app pinned_comment reactions
repository_url state state_reason sub_issues_summary timeline_url title type
updated_at url user
```

No attachment/asset/media key. Both the REST and the GraphQL surfaces agree:
**attachments exist only as markdown text inside `body`.** Extracting them is
necessarily a parse-the-markdown-then-fetch job, by any route.

## FINDING 10 — the 23 cross-references are a source backlog, and only `/timeline` has them

Reachable by no other route we probed. Deduplicated from the 479 timeline
entries; `anthropics/claude-code#93426` is the only same-repo one:

| kind | ref | what |
|---|---|---|
| IS | `goondocks-co/myco#1111` | Claude Code hook surface realignment |
| IS | `goondocks-co/myco#1172` | research appendix R01–R21 |
| IS | `jeremylongshore/tons-of-skills-marketplace#1437` | researching FH without losing model-agnosticism |
| IS | `lossless-claude/lcm#376` | `feat(hooks)`: function-hooks module, early access |
| IS | `yonatangross/orchestkit#3917` | watch thread on 91870 |
| PR | `yonatangross/orchestkit#3918` | FH-ready handler policy and gate |
| IS | `Yeachan-Heo/gajae-code#5263` | epic: capability-scoped function hooks + event middleware |
| IS | `anchorwatch-dev/anchorwatch#8` | engine module scan reachable from plugin |
| IS | `notdp/hive#80` | adopt the upstream knob once one exists |
| IS | `anthropics/claude-code#93426` | [BUG] `.in_use/<pid>` / `.orphaned_at` writes |
| PR | `davila7/claude-code-templates#867` | Function Hooks section (experimental) — 10 hooks, CLI flag, blog |
| PR | `pleaseai/honmoon#90` | claude-plugin function-hooks module with fail-c… |
| PR | `JoshuaOliphant/claude-plugins#23` | autonomous-sdlc 2.4.0 |
| PR | `makikub/kb-notebooklm-podcast#19` | FH + banked-reset asides |
| PR | `giadaf-boosha/claude-code#88` | What's new 2026-09-07 |
| PR | `thkt/dotclaude#651` | research note on workflow scripts |
| IS | `96loveslife/big_model_radar` #435 #440 #445 #456 #461 #471 | daily AI-CLI digest (6 issues) |
| IS | `junlinzhao327-oss/big_model_radar#610` | same digest, mirror repo |

Six of the 23 are one bot's daily digest and two repos mirror it, so the
distinct signal is ~15. Several are real downstream implementations of the
proposal and are candidate corpus sources in their own right
(`research-repo-enumeration.md`).

**`comment_deleted`**: one, `actor: anthropics`, `2026-09-04T10:39:14Z`. A
comment was deleted by the org the day after the issue opened. No other route
reveals that a deletion occurred.

## FINDING 11 — the four search indexes, run separately, and one is STRUCTURALLY zero

All via `gh api -X GET search/...` (never `gh search`), plus GraphQL for
discussions because **REST has no discussions-search endpoint at all**.

| index | query | total | control arm |
|---|---|---|---|
| **code** | `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` | **106**, `incomplete_results: false` | `filename:CLAUDE.md graphify` → 3,504 |
| **repositories** | `claude code function hooks` | **16** | (non-zero, self-arming) |
| **issues** | `"function hooks" repo:anthropics/claude-code` | **117**, `incomplete_results: false` | (non-zero, self-arming) |
| **discussions** (GraphQL) | `function hooks claude code` | 622, **none from `anthropics/claude-code`** | `claude code` → 28,472 |

🔴 **The discussions zero is structural, and reporting it as "nothing was
discussed" would be wrong.** `gh api repos/anthropics/claude-code --jq
'{has_discussions}'` → **`false`**. The repo has discussions DISABLED, so the
discussions index can never return a row from it no matter what was written.
Same shape as this repo's recorded `jdx/hk` lesson. The 622 hits are all other
repos and are noise for our purpose.

**`incomplete_results: false` on both the code and issues queries** — that field
is the one that distinguishes "asked and got everything" from "asked and the
index gave up", and it survives `--jq '{...}'` because that is not a bare
projection to `.items`.

## FINDING 12 — the issues index found FOUR sibling issues the timeline did not

`search/issues` on `"function hooks" repo:anthropics/claude-code` returned 117,
of which these are directly on-topic and **none appears in 91870's timeline
cross-references**:

| issue | state | title |
|---|---|---|
| **93215** | **CLOSED** | **Add mods: sec-default, diff and telemetry** |
| 92440 | open | Function hooks: `agent.offer` doc comment and example say `offered` |
| 92533 | open | Any function-hook `tool.call` on Bash breaks Agent isolation |
| 92469 | open | `/plugin-types` omits the op events `session.authorize` and `flag.value` |
| 93831 | open | [BUG] Self-fixing leads to guardrail weakening |

**#93215 is the `mods/` the brief refers to** — the brief established that
`mods/` is 404 at our claude-code pin v2.1.258 and present at v2.1.269
(`df52d04a4e65195c1621fe6222e0564bcccb1804`, carrying README.md, diff,
sec-default, telemetry). The issues index names the issue that landed it. **No
timeline route would have found this**, because #93215 never cross-referenced
91870.

**This is the measured argument for running all four indexes**: the code index
alone would have missed every one of these, and the timeline alone would have
missed all five.

**Repositories index — 16 dedicated repos**, several of which are reference
implementations worth ingesting (`sources/REGISTRY.md` candidates):

```
ray-amjad/awesome-claude-code-function-hooks   curated list
cvuijst/cc-function-hooks-poc                  POC against the 91870 API
Monte9/claude-function-hooks                   reference impl of the "hook algebra"
productowner-ro/claude-function-hooks          JS/TS reference
scriptease/claude-code-redact-plugin           example plugin using functional hooks
fnclaude/hooks                                 strongly-typed TS wrapper
AnExiledDev/cc-changelog-plugin                unofficial changelog plugin
```

Code index repos worth noting: `davila7/claude-code-templates`,
`lossless-claude/lcm`, `yonatangross/orchestkit`, `TransmuteLabs/Catalyst` — and
**`ray-manaloto/dotfiles`**, i.e. this operator's own sibling repo already
mentions the env var.

## FINDING 13 — `gh api` CAN download an attachment. I expected it could not.

I predicted `gh api` would refuse an absolute non-API URL. It does not: given the
full durable attachment URL it follows the redirect, performs the signed GET, and
streams the raw bytes to stdout.

```
gh api https://github.com/user-attachments/assets/ea09f465-…  > vid-gh.mp4   rc=0
curl -sL                https://github.com/user-attachments/assets/ea09f465-…  -o vid1.mp4
cmp -s vid-gh.mp4 vid1.mp4   ->  IDENTICAL       (4,071,679 bytes, ISO Media MP4)
gh api https://github.com/user-attachments/files/31802150/EXTERNAL.Function.Hooks.Core.Architecture.pdf
   ->  rc=0, 291,522 bytes, "PDF document, version 1.4, 8 pages"
```

Control arm, rc read **without a pipe** (a piped rc is `head`'s, not gh's):

```
gh api .../assets/00000000-0000-0000-0000-000000000000  > out 2> err
   rc=1 · stdout "Not Found" · stderr "gh: HTTP 404"
gh api .../files/31802150/….pdf > /dev/null 2>&1
   rc=0
```

So gh **discriminates**: rc 1 + `gh: HTTP 404` on a bad asset, rc 0 on a good
one. This matters for the recipe — a download loop can read a real exit code and
does not need to sniff output. (My first pass reported `rc=0` for the 404 case
because I had piped it into `head`; that rc was head's. Re-measured unpiped.)

**Practical consequence**: the extraction pipeline needs no second tool. `gh` is
sufficient for metadata *and* for assets. `curl` remains fine and is equivalent
byte-for-byte; gh's advantage is that it reuses existing auth for private repos
and gives a real rc.

## FINDING 14 (cross-lane) — every asset fits UNDER graphify's fetch cap, so nothing errors

Combining this track's measurements with lane B2's source reading:

- `sources/graphify/graphify/security.py:22` — `_MAX_TEXT_BYTES = 10_485_760`
  (10 MiB), the cap `safe_fetch_text` passes down (`:302`).
- `sources/graphify/graphify/security.py:294` — exceeding it raises
  `OSError("… exceeds size limit …")`.
- `sources/graphify/graphify/security.py:308` — under it, the bytes are
  `.decode("utf-8", errors="replace")`.

My measured largest asset is **9,789,851 bytes = 9.34 MiB**. **All 22 assets are
under the 10 MiB cap.**

So the failure is the quiet one, not the loud one: graphify would fetch all
50.7 MB, decode every byte of MP4/JPEG/PDF/GIF as UTF-8-with-replacement,
markdownify the mojibake, keep the first 12,000 characters
(`ingest.py:144`) and **raise nothing**. Neither lane could see this alone —
B2 established the cap and correctly refused to assert an unbounded-buffering
failure; only the measured sizes say which side of the cap we actually land on.

## Method notes / what I could not establish

- **Every probe above ran from the Claude session, not a codex lane**, because a
  codex `--sandbox read-only` lane has no network egress. A companion lane read
  gh's Go source at the pin to answer the mechanism questions.
- **UNVERIFIED**: whether `gh`'s GraphQL comment path would truncate on an issue
  with *far* more than 161 comments. 161 came back complete without
  `--paginate`; I did not find the ceiling, and lane A1 is reading the `first: N`
  literal from source to answer it.
- **UNVERIFIED**: whether the `--paginate` REST path would silently stop on a
  much longer thread. It returned exactly 161/161 here, matching the
  authoritative count, but 161 is only ~6 pages.
- **UNVERIFIED**: whether a *private* repo's user-attachments URLs behave the
  same. All probes here were against a public repo and ran unauthenticated for
  the asset fetches.
- **NOT ATTEMPTED**: transcribing any video. `curl`/`gh` → local `.mp4` is armed
  end-to-end (byte-exact, correct container per `file(1)`); the transcription
  step itself was not run.
- I did not read gh's Go source; that is lane A1's scope and its answers should
  be preferred over any inference here.

## GitHub repos touched

- [anthropics/claude-code](https://github.com/anthropics/claude-code) — issue 91870, its 161 comments, 479 timeline entries, 141 reactions and 22 attachments are the extraction target; also the sibling issues #93215/#92440/#92533/#92469/#93831 found via the issues index.
- [cli/cli](https://github.com/cli/cli) — `gh` itself: pinned clone at v2.98.0, plus the v2.99.0 and v2.100.0 release notes read from the API.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — our fork; `security.py` fetch caps cross-checked against measured asset sizes.
- [ray-amjad/awesome-claude-code-function-hooks](https://github.com/ray-amjad/awesome-claude-code-function-hooks) — repositories index; curated function-hooks list, corpus candidate.
- [cvuijst/cc-function-hooks-poc](https://github.com/cvuijst/cc-function-hooks-poc) — POC against the 91870 API, corpus candidate.
- [Monte9/claude-function-hooks](https://github.com/Monte9/claude-function-hooks) — reference implementation of the proposed hook algebra, corpus candidate.
- [productowner-ro/claude-function-hooks](https://github.com/productowner-ro/claude-function-hooks) — JS/TS reference, corpus candidate.
- [scriptease/claude-code-redact-plugin](https://github.com/scriptease/claude-code-redact-plugin) — example plugin using functional hooks.
- [fnclaude/hooks](https://github.com/fnclaude/hooks) — typed TS wrapper for hook entry points.
- [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) — PR #867 adds a Function Hooks section; code + timeline hit.
- [yonatangross/orchestkit](https://github.com/yonatangross/orchestkit) — issue #3917 / PR #3918, an FH handler policy and gate.
- [lossless-claude/lcm](https://github.com/lossless-claude/lcm) — #376, a function-hooks module for early access.
- [Yeachan-Heo/gajae-code](https://github.com/Yeachan-Heo/gajae-code) — #5263, capability-scoped hooks epic.
- [goondocks-co/myco](https://github.com/goondocks-co/myco) — #1111/#1172, hook-surface research appendix.
- [jeremylongshore/tons-of-skills-marketplace](https://github.com/jeremylongshore/tons-of-skills-marketplace) — #1437, model-agnosticism concern.
- [anchorwatch-dev/anchorwatch](https://github.com/anchorwatch-dev/anchorwatch) · [notdp/hive](https://github.com/notdp/hive) · [pleaseai/honmoon](https://github.com/pleaseai/honmoon) · [JoshuaOliphant/claude-plugins](https://github.com/JoshuaOliphant/claude-plugins) · [makikub/kb-notebooklm-podcast](https://github.com/makikub/kb-notebooklm-podcast) · [thkt/dotclaude](https://github.com/thkt/dotclaude) · [giadaf-boosha/claude-code](https://github.com/giadaf-boosha/claude-code) — cross-referencing repos from the timeline.
- [96loveslife/big_model_radar](https://github.com/96loveslife/big_model_radar) · [junlinzhao327-oss/big_model_radar](https://github.com/junlinzhao327-oss/big_model_radar) — a bot's daily AI-CLI digest; 7 of the 23 cross-references, low signal.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — appeared in the code index for `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS`; this operator's own sibling repo.

## FINDING 15 — lane A1's source claim, armed LIVE from this track: THREE silent truncations, not one

Lane A1 (reading `cli/cli` at `a255baf71d13fe5947a4eb7ad521ffd412d64cee`)
predicted from source that `gh issue list --json comments` silently caps each
issue's comments at 100, because `issue list` requests `comments(first: 100)`
and — unlike `issue view` — never calls the comment preloader, while its
exporter drops the `totalCount`/`pageInfo` that would reveal the truncation.

I armed that prediction live against the same issue:

```
gh issue list --search '91870 in:number' --json number,comments  ->  91870  comments=100
gh issue view 91870                      --json number,comments  ->  91870  comments=161
gh api repos/anthropics/claude-code/issues/91870 --jq .comments  ->         161
```

**Confirmed exactly, rc 0 throughout.** A source reading and a live probe from
two different lanes agree, which is worth more than either alone.

So there are **three distinct ways to silently lose comments on this issue**, all
exiting 0 with valid JSON:

| command | returns | loses |
|---|---|---|
| `gh api .../issues/91870/comments` | **30** | 131 (no `--paginate`) |
| `gh issue list --json comments` | **100** | 61 (no preloader; `pageInfo` discarded by the exporter) |
| `gh issue view --comments` (non-TTY) | all *except minimized* | A1: `pkg/cmd/pr/shared/comments.go:38-50`; gh's own test has 6 comments and expects 5 rendered (`pkg/cmd/issue/view/view_test.go:460-510`) |

**The only route that returned all 161 with no flag gymnastics is
`gh issue view --json comments`**, and A1 gives the mechanism: the preloader at
`pkg/cmd/issue/view/view.go:152` loops `comments(first: 100, after: $endCursor)`
until `hasNextPage` is false (`pkg/cmd/issue/view/http.go:11-53`). 161 comments =
two pages.

Citations spot-checked by me against the pinned clone, all resolve:
`api/query_builder.go:314` is `var sharedIssuePRFields = []string{` (so the field
set is **hand-written, not generated from struct metadata** — that refutes the
premise I put in A1's own prompt); `pkg/cmd/issue/list/list.go:113` sets
`--limit` default 30 and `:120` passes the identical `api.IssueFields`;
`pkg/cmdutil/errors.go:35` is `// SilentError is an error that triggers exit code 1`.

**A1's rate-limit answer, which mine could not reach**: a throttled or errored
page produces `gh: <message>` on stderr and `SilentError` → **exit 1**
(`errors.go:34-35`, `internal/ghcmd/cmd.go:42-50`, `cmd/gh/main.go:9-12`), so a
limit is distinguishable from a zero. **But gh streams each page to stdout before
requesting the next**, so a failure mid-`--paginate` leaves partial valid JSON on
stdout alongside the non-zero rc. The ingestion rule that follows: **require
rc 0 and discard stdout entirely on any non-zero** — never keep what arrived.

A1 also found a **silent early stop with rc 0** in GraphQL pagination:
`findEndCursor` returns `""` rather than an error on malformed JSON or a missing
`pageInfo` (`pkg/cmd/api/pagination.go:39-47`), so a 200 response with broken
pagination metadata terminates the loop successfully.

And the finding that explains my own unauthenticated-fetch result:
**gh deliberately does not forward auth across a redirect to a different host**
(`api/http_client.go:151-169`). That is why the S3 leg works with no credential —
and it flags that a *private* repo's attachments may behave differently, which
remains UNVERIFIED.
