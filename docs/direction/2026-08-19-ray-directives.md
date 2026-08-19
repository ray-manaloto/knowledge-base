# Directives — 2026-08-19 (Ray, verbatim)

**Stored verbatim**, following `docs/direction/2026-08-18-ray-directives.md`, because
this series' own first complaint is that requirements get lost between sessions.
Do not paraphrase, summarise, or "clean up" the text below — it is the artifact.
Analysis, status and open questions go in the sections *after* the verbatim block,
never inside it.

**This file must stay under `docs/direction/**`** — that path is formatter-exempt in
`hk.pkl` precisely because a spell-checker "fixing" a verbatim record edits what
someone said.

Given at `/clear-prep`, 2026-08-19, with the explicit instruction: *"copy below
verbatim in the usual durable file(s) for the next session to review/prioritize
and act upon"*.

---

## VERBATIM

> regarding statement: 'The three things I'd want you to remember from it'
> - how should our session-review workflow be updated to automate handling them
>
> i see a dirty git workspace:
> ```
> ➜  knowledge-base git:(main) ✗ git status
> On branch main
> Your branch is up to date with 'origin/main'.
>
> Untracked files:
>   (use "git add <file>..." to include in what will be committed)
>         graphify-out/memory/query_20260819_155028_what_did_the_2026_08_18_19_session_review__issue_t.md
> ```
>
> ----------
> copy below verbatim in the usual durable file(s) for the next session to review/prioritize and act upon
>
> i will restart the claude terminal session to pick up changes to 2.1.235
> - perform currency sync and release notes/feature/changes review
>
> we need to handle and understand that our process is slow and that dependencies will update while we are working on a task and handle the updates to dependencies
> - either immediately if it fixes an issue we are working on
> - on the next session after running /clear-prep (and internally the session-review worklfow)
>
> new graphify version needs to be synced with same release-notes/feature/changes review:
> - https://github.com/Graphify-Labs/graphify/releases
>
> install as a claude code marketplace plugin at project-level scope (do not modify ~/.claude and its subdirectories) and review and determine if this will help the agents working on this project find alternative ways to try and solve and tackle the work/problems in this project. if we install them then these plugins also need to become currency/critical dependencies:
> - https://github.com/UditAkhourii/adhd
> - https://github.com/dietrichgebert/ponytail
>
> the outputs of these commmand need to have zero outdated first level dependencies (these checks need to be integrated into our kb currency sweeps and have agents perform the same relese-notes/feature/changes review):
> - mise outdated -b -J
> - uv tree --outdated --show-sizes --all-groups --format json
>
> in mise.toml:
> - 'rumdl = "v0.2.52"' needs to be updated to 0.2.57
>   - NOTE: we should review if we can remove the 'v' prefix
>   - should make rumdl a critical/currency dependency
>   - perform currency sync and release notes/feature/changes review
> - github:agent-sh/agnix should be updated to version 0.49.0
>   - perform currency sync and release notes/feature/changes review
>   - should be updated to a critial/currency dependency
>
> i see these type of commands being run, the session-review workflow should have identified this as a set of manual step by step commands that should be wrapped into a modular/wrapper skill(s) -> mise task(s) -> python library module(s)/function(s)
>
> $ cd /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base; uv run python - <<'PY' 2>&1 | tail -3
> import hashlib, json, os, re, tempfile
> from pathlib import Path
> from kb_setup import graphify_semantic_corpus as gsc
> repo = Path(".").resolve()
> with tempfile.TemporaryDirectory() as td:
>     tmp = Path(td); s = tmp/"s"; pin = gsc.admit_source(repo, s); c = tmp/"p"
>     gsc.plan_source(s, c, source=pin, max_output_tokens=gsc.planned_max_output_tokens(repo, os.environ))
>     new = {k: hashlib.sha256((c/f).read_bytes()).hexdigest() for k, f in
>            (("execution_config_sha256","execution-config.json"),("plan_manifest_sha256","manifest.json"))}
> ap = Path("python/src/kb_setup/graphify_semantic_corpus_authority.py")
> t = ap.read_text()
> for k, v in new.items():
>     t2 = re.sub(rf'"{k}":"[0-9a-f]{{64}}"', f'"{k}":"{v}"', t)
>     assert t2 != t, k
>     t = t2
> ap.write_text(t)
> print("re-recorded:", {k: v[:12] for k, v in new.items()})
> PY
> rm -rf graphify-out/graphify-semantic-corpus; mise run kb-graphify-semantic-corpus plan >/dev/null 2>&1; echo "replan rc=$?"; S=/private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/773421d1-632d-44fb-a680-8117295016ad/scratchpad; uv run pytest tests/ -q > $S/tC.log 2>&1; echo "suite rc=$?"; grep -E "^(FAILED|ERROR)" $S/tC.log | head -3
>
> $ cd /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base; git log --oneline -3; echo "=== did I keep Codesmith's better exact-set assertion? ==="; grep -n "lagging == {allowed}" tests/test_currency_ref_bindings.py; echo "=== suite ==="; S=/private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/773421d1-632d-44fb-a680-8117295016ad/scratchpad; uv run pytest tests/ -q > $S/tB.log 2>&1; echo "rc=$?"; grep -E "^(FAILED|ERROR)" $S/tB.log | head -3
>
> $ cd /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base; git add -u && git commit -m "fix(currency): re-record the plan authority after the rebase moved the slice
>
> Sixth re-record, and it is the ordering rule working rather than being
> violated: resolving the rebase conflict edited a COMMENT in
> \`graphify_semantic_slice.py\`, whose digest sits inside \`execution-config.json\`
> as \`semantic_slice_sha256\`. So the authorization went stale on a comment, which
> is the exact failure the block's own note has now recorded three times.
>
> Full suite green." 2>&1 | tail -3; mise run kb-gates > /private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/773421d1-632d-44fb-a680-8117295016ad/scratchpad/g3.log 2>&1; echo "gates rc=$?"; tail -8 /private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/773421d1-632d-44fb-a680-8117295016ad/scratchpad/g3.log

---

## Provenance, and nothing more

Filed at `/clear-prep` on 2026-08-19 by the session that landed PR #347 and
PR #375. The three shell blocks Ray quotes are REAL and were run by that
session, at the times its transcript records — they are not illustrative
examples. Analysis, issue filing and prioritisation are the NEXT session's work,
per the pattern this series established on 2026-08-18.

The one thing that is NOT deferred, because Ray asked it as a direct question
rather than as a backlog item: *"how should our session-review workflow be
updated to automate handling them"*. That answer is in
`.agent/plans/session-2026-08-19.md` § the workflow amendments, and the issues
it proposes are filed.

---

## SECOND ADDENDUM — VERBATIM (Ray, same session, on PR #375's bot reviews)

> also were these pr comments reviewed: https://github.com/ray-manaloto/knowledge-base/pull/375#pullrequestreview-4974111558
>   - we need to make reviewing the pr bot comments a prioritiy (if they rate limit, then it is fine to skip them)
>   - but the graphify pr bot comments are critical since we need to understand how graphify works and how we can replicate its functionality
>
>   this should also be copied verbatim and analyzed after running /clear on the next session

## THIRD ADDENDUM — VERBATIM (Ray, same session, after the lockfile loss surfaced)

> add to the list of items to review after /clear on the next session
> - a full analysis on wht happend with 'Confirmed and serious: uv lost all 7 platform blocks — every checksum, URL and github-attestations provenance. Auditing every tool.'
>   - and how to detect and prevent it from happening again going forward
>   - the session-review workflow should try to identify this

## FOURTH ADDENDUM — VERBATIM (Ray, same session, on hand-editing config)

> instead of hand modifying mise.toml and pyproject.toml or other config files
> - review if their cli/sdk/api provide a command to run instead to prevent it from breaking due to hand coded modificatons
> - make this a requirement going forward
>   - via:
>     - AGENTS.md/CLAUDE.md
>     - hooks
>     - claude rules
>     - hk checks and pre/post commit hooks and/or builtins
>     - linter/static analyzer checks
>     - provide other suggestions

---

## The one thing already ANSWERED, because it was a live regression

The second addendum's question — *"were these pr comments reviewed"* — has a
one-word answer: **no**. It is recorded here rather than deferred because the
answer turned out to be a defect on `main`, fixed in the same session.

**Three `graphify-labs` reviews existed on PR #375** and none of their bodies was
read: `4973529378` (14:55Z), `4973713252` (15:13Z), `4974111558` (15:54Z). The PR
merged at **15:49Z**. Review `4973529378` was available for **54 minutes**;
review `4973713252` for **36 minutes**. Review `4974111558` was posted
**5 minutes after** the merge.

**Why the probe could not see them.** The bot sweep used
`gh api repos/.../pulls/375/comments` — the INLINE-comment endpoint. graphify-labs
posts its findings in the **review BODY**, which lives at
`pulls/375/reviews`. So "zero new inline comments" was true and the conclusion
drawn from it ("the bots found nothing") was false. A probe's shape decided its
answer, and the report generalised from one endpoint to "all three bots".

**What they had caught.** At 14:55Z: *"hk lock entry drops pinned artifact
checksums"*. At 15:13Z: *"fnox lock entry still records the old version"*. Both
correct. Audited per tool against `d937841d~1`:

| tool | before | after | |
|---|---|---|---|
| `uv` | 7 blocks / 7 checksums | **0 / 0** | total loss |
| `hk` | 6 / 6 | **0 / 0** | total loss |
| `doppler` | 7 / 7 | 1 / 1 | lost 6 of 7 |
| `fnox` | 7 / 7 | **14 / 14** | duplicated |

Every `checksum`, `url_api` and `provenance = "github-attestations"` line for uv
and hk was gone from a lockfile on `main`.

**And the session's own check masked it.** It verified "81 tool sections
preserved" and reported that as proof. The total stayed at 81 because fnox
DOUBLED while uv and hk emptied — a count-based guard catching corruption only
by luck. The audit that found it counts **per tool** against the pre-round file.

Fixed by `mise lock -p <all seven platforms>` with **no tool argument**: 103
platform entries updated, the stale duplicate pruned, all four restored, and
`conda:ffmpeg` (3→7) and `gh` (0→7) gained coverage they never had.

Two further findings from the same reviews were also real and are fixed: the
`antigravity-cli` `version_pattern` was bare-anchored, and the new laggard
assertion keyed its allowed set on the path alone, so two bindings in one file
collapsed to a single member.

**The durable lesson, and the reason the fourth addendum exists:** all of this
began with hand-edited `mise.toml`/`pyproject.toml` pins followed by
`mise install`. The tools ship commands for this — `mise use <tool>@<version>`,
`uv add --dev <pkg>==<version>` — which maintain the lockfile themselves.
