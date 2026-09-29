# Graphify CLI fork delivery specification

Status: APPROVED — user approved the three test boundaries and six-ticket dependency chain on 2026-09-22.
Date: 2026-09-22
Authority: the exact native objective in GOAL.started.txt; SHA256 e548a94f02ffeb9bfeb9304ef63051ef54c46e7b33444218edbb25105b2bd74f.
Historical parents: <https://github.com/ray-manaloto/graphify/issues/1> and <https://github.com/ray-manaloto/knowledge-base/issues/728>.
This document replaces conflicting historical delivery prerequisites for THIS attempt only. It does not change those parent issues.

## Problem Statement

The maintained Graphify fork and substantial knowledge-base adapters exist, but the fork has not been delivered against the latest qualifying upstream release with current, exact-commit acceptance evidence. Existing history includes superseded infrastructure prerequisites. Updating the fork by hand would repeat agent effort without proving reusable maintenance automation.

## Solution

Deliver a maintained subscription-CLI fork, an automated repeatable maintenance path, and verified knowledge-base integration on actual main. Reuse the existing candidate, adapters, repository tasks and research. Report exact target, publication, merge and installed identities, with every acceptance criterion linked to direct evidence.

## User Stories

1. As the maintainer, I want the latest qualifying stable release selected by publication time, so that a numerically higher or uninstalled tag cannot select the wrong target.
2. As the maintainer, I want an exact-SHA override recorded explicitly, so that a deliberate exception is reproducible.
3. As the maintainer, I want each attempt frozen to a release tag, version and commit, so that tests cannot silently change targets.
4. As the maintainer, I want a final timestamped currency check, so that "latest" has a verifiable meaning.
5. As the maintainer, I want upstream ancestry proved, so that copying changes cannot impersonate a rebase.
6. As the maintainer, I want every existing fork capability classified, so that upstream overlap does not silently drop behavior.
7. As the maintainer, I want isolated registered worktrees and preserved existing work, so that delivery cannot destroy an unfinished adapter.
8. As the maintainer, I want one skill-to-task-to-engine maintenance path, so that recurring updates require minimal agent work.
9. As the maintainer, I want clean-path execution without agent edits, so that automation claims are measurable.
10. As the maintainer, I want repeat invocation to be idempotent, so that a retry cannot duplicate changes.
11. As the maintainer, I want invalid targets rejected before mutation, so that bad input cannot damage a candidate.
12. As the maintainer, I want conflicts to stop with recoverable evidence, so that automation cannot silently resolve semantic changes.
13. As a KB user, I want Claude CLI opus/xhigh as the default, so that ordinary extraction uses my selected subscription profile.
14. As a KB user, I want explicit OpenAI CLI gpt-5.6-sol/high support, so that backend selection is deliberate.
15. As a KB user, I want conflicting selectors rejected before launch, so that ambiguous routing spends no calls.
16. As a KB user, I want metered API routes excluded from implicit selection, so that subscription requests do not incur silent API use.
17. As a KB user, I want explicitly requested fallback only after zero primary successes, so that partial success is not concealed.
18. As a KB user, I want partial and uncertain results retained and labeled, so that failure does not erase useful output.
19. As a KB user, I want bounded attempts and wall time, so that a failed extraction cannot retry indefinitely.
20. As a KB user, I want finalized structured receipts on success and failure, so that every launch is accounted for.
21. As a KB user, I want compatible warm runs to add zero extraction calls, so that replays do not repeat work.
22. As a KB user, I want incompatible execution identities separated in cache, so that one profile cannot borrow another profile's extraction.
23. As an auditor, I want original producer identity preserved on cache hits, so that a replay cannot relabel provenance.
24. As an auditor, I want requested and reported models distinct, so that configuration is not presented as observed service identity.
25. As an auditor, I want unknown usage distinguished from zero, so that missing telemetry cannot look free.
26. As a KB user, I want meaningful static raster pixels delivered on both CLIs, so that passing a path or acknowledging an attachment cannot impersonate image understanding.
27. As a KB user, I want NORMAL and DEEP extraction of real Graphify and planning-with-files subsets, so that both workflows work on relevant sources.
28. As a maintainer, I want planning-with-files registered if absent, so that its subset has a legitimate source identity.
29. As a maintainer, I want complete Linux Python and skill-generation gates green, so that baseline failures cannot waive delivery requirements.
30. As a maintainer, I want all KB dependency, source, SDK and generated identities aligned, so that the tested fork is the one actually installed.
31. As a maintainer, I want independent Standards and Spec reviews of final commits, so that implementation cannot self-certify.
32. As a maintainer, I want refreshed graph facts and provenance checked across collisions and AST refresh, so that a dependency update cannot corrupt KB knowledge.
33. As a maintainer, I want immutable publication and actual KB main integration with post-merge CI, so that an open PR cannot be called delivered.
34. As a continuing agent, I want durable criterion status and evidence, so that resume and compaction do not restart research or skip unfinished work.

## Implementation Decisions

- Preserve the existing product candidate and both unfinished adapter worktrees. Recover relevant changes into new registered worktrees; keep a byte/hash preservation inventory before recovery.
- Reuse the candidate's public execution/profile/invocation/receipt interfaces and existing KB NORMAL/DEEP entrypoints. Recover the D2 adapter work by reviewing its staged and unstaged changes, without resetting its original checkout.
- Fork maintenance belongs with the Graphify fork; KB retains consumer pinning, source registration, skill refresh, build, audit and ship/land. The bounded Sol/xhigh architecture consult supports this separation. The capability manifest and immutable fork ref form the cross-repository contract. Reuse existing currency logic/patterns where suitable; do not expand delivery into dotfiles or services.
- The maintenance skill invokes a mise task; the task invokes a deterministic implementation. The engine exposes preview and explicit apply with a frozen target, input candidate and bounded allowed roots. It records target resolution, ancestry, Git state, commands and direct outcomes.
- Release resolution considers non-draft, non-prerelease GitHub releases in descending publication chronology and requires usable non-yanked PyPI distribution availability. Resolve the tag to its commit and record both evidence sources. A SHA override is an explicit user exception, never an inferred fallback.
- Recheck the release policy before integration and final delivery. A newer qualifying release invalidates the affected attempt evidence and starts a newly pinned attempt unless the user explicitly overrides. No perpetual maintenance begins after final delivery.
- Build a capability matrix from the fork delta, existing controls and upstream changes. Each entry ends as retained, equivalent upstream, superseded, or user-excluded, with evidence. Existing exclusions authorize only the corresponding excluded capabilities.
- Preserve default and explicit subscription profiles from the native objective. Validate selectors before launching. Credential/routing controls assert that an implicit metered route is never attempted.
- Existing successful primary results prohibit fallback. Fallback requires explicit request and zero primary successes. Unknown outcome or partial output is retained with uncertainty; do not turn ambiguity into an automatic replay.
- Total attempts include primary, retries and fallback. Freeze finite numeric launch, case and attempt bounds in each live-run manifest before execution, using existing supported limits where valid. An unbounded lower-level path is an implementation defect to fix before live acceptance.
- Cache compatibility includes the execution identity inputs affecting extraction. Keep original producer metadata on warm reads and distinguish replay/request identity from original production identity.
- Preserve requested/reported models and known/unknown usage as separate concepts. Full served-model certification is excluded; do not fabricate model provenance.
- Use real source subsets with version/ref, paths, bytes and hashes frozen before tests. Pin independently checkable expected concepts/relationships and omission accounting before viewing the output. A nonempty schema-valid graph alone is insufficient.
- Test static raster meaning using a source fixture with a known pixel-dependent answer, including an opposite-direction control. Path mentions, attachment acknowledgement and generic descriptions do not pass.
- Align actual KB declarations, lock, installed metadata, source ref/manifest, currency metadata, SDK contract, both skill trees/stamps and reviewed baselines to the delivered fork. Generated data is produced with owning tasks, not hand-edited.
- Complete the deterministic KB build without full paid corpus extraction. Reuse existing corpus inputs and source registration rules; intentional exclusions and absence remain visible.
- Preserve repository-specific review, graph-refresh, gate and ship/land workflows. Publish a new immutable fork ref without rewriting preserved refs.
- Sequence publication before live acceptance: first complete fork gates and independent Graphify Standards/Spec reviews, recheck the target, then publish and independently verify the immutable fork ref. Install that published identity for all eight KB cold/warm acceptance cases. Optional prepublication smoke is only risk reduction, never final acceptance. A postpublication defect creates a new immutable attempt; affected fork reviews/gates and KB evidence must be refreshed.

## Testing Decisions

Use the highest existing user-visible seams; test external outcomes and include controls that would fail if the promised behavior regressed.

### Seam A: maintenance task with real isolated Git repositories

- Exercise skill instructions through the registered mise entrypoint and engine.
- Frozen source/release fixtures cover publication chronology, prerelease/draft exclusion, yanked/missing distributions and SHA override.
- Apply a clean nonconflicting fork delta with zero executing-agent file edits; verify target ancestry and retained behavior.
- Repeat the same invocation: unchanged delivered tree/ref and no duplicated commits or dirty output.
- Invalid/unresolvable target: nonzero exit, zero candidate/ref/file mutations.
- Deliberate conflict: nonzero stopped result, conflicted paths and recovery information retained, no automatic resolution or destructive reset.
- Record all manual preparation/repair separately. It cannot count as clean-path automation evidence.

### Seam B: actual KB NORMAL and DEEP entrypoints through the public Graphify SDK

Exactly eight cold acceptance cases:

| Source subset | Backend | Mode |
| --- | --- | --- |
| Graphify | claude-cli opus/xhigh | NORMAL |
| Graphify | openai-cli gpt-5.6-sol/high | NORMAL |
| Graphify | claude-cli opus/xhigh | DEEP |
| Graphify | openai-cli gpt-5.6-sol/high | DEEP |
| planning-with-files | claude-cli opus/xhigh | NORMAL |
| planning-with-files | openai-cli gpt-5.6-sol/high | NORMAL |
| planning-with-files | claude-cli opus/xhigh | DEEP |
| planning-with-files | openai-cli gpt-5.6-sol/high | DEEP |

- Every cold case uses real installed fork code and actual subscription CLI execution, with a valid graph containing its predeclared expected evidence, zero unaccounted input omissions, and finalized receipts.
- Replay all eight with the same compatible identity; each replay adds exactly zero extraction calls. Prove incompatible profiles cannot reuse the extraction cache.
- Keep deterministic failure tests at the same task/SDK seam and real-process boundary. Cover missing/invalid credentials, selector conflict, API routing refusal, allowed/forbidden fallback, bounded retry/timeout, retained partial output and labels, receipt finalization, provenance and raster controls for both backends.
- A fake external process may isolate a deterministic negative test. It never establishes live backend success.
- Prior art: the recovered adapter's execution, ingest and native-extract tests, real-process timeout/partial-output tests, and candidate execution/profile/cache controls.

### Seam C: exact-commit repository and delivery gates

- Full Linux Python 3.10, 3.12, 3.13 and 3.14 suites: zero failures and errors on every version. Explain existing skips; zero new skips/xfails that hide failures.
- All five skill-generation checks: generated output, coverage audit, schema singleton, monolith roundtrip, always-on roundtrip.
- Applicable upstream CI and isolated fresh install/import/help checks pass. Matching upstream failure is not a pass.
- KB locked environment passes lock check, clean locked installation and installed direct-URL identity checks, including local/editable override detection.
- Complete deterministic KB build, manifest audit, graph baseline/SDK checks and repository gates pass on delivered input identities.
- Refresh required graphs after code changes; verify collision identity, facts and provenance survive AST refresh.
- Standards and Spec reviewers independently accept exact final commits. Repairs/rebases invalidate affected review/test evidence and require revalidation.
- Publish immutable fork identity; use KB ship/land to actual main; verify merged commit, post-merge CI and pinned/installed identity. A wrapper exit of zero does not establish these facts.

## Acceptance Evidence

Each criterion is PENDING, RUNNING, PASS or FAIL with evidence path(s), exact relevant commit(s), input/config hashes, command argv, direct exit code, separately retained stdout/stderr, timestamps and receipt/artifact references. Missing required evidence cannot yield PASS.

Maintain one index mapping every native-goal criterion and every capability classification to evidence. Frozen attempts have separate directories. Preserve failures and superseded evidence with their status; never overwrite them into apparent success.

A completion report includes the final release check timestamp, frozen upstream tag/version/SHA, ancestry evidence, immutable published fork ref/SHA, KB main merge commit and CI run identities, and remaining limitations (none may violate a required gate).

## Out of Scope

AgentsView/M1 prerequisites; services/platform work; full paid corpus rebuilds; full served-model certification; scheduler activation/autopromotion; Cursor; OCR; animation; changing unrelated or user-global configuration. Existing research is reused rather than broadly rerun.

## Further Notes

- Prior work and test results are leads, not current acceptance evidence.
- Historical control plans include superseded AgentsView/M1 prerequisites and elapsed deadlines. They are not prerequisites for this objective.
- Do not close or modify historical parent issues as a planning side effect.
- New implementation tickets are published in the configured GitHub tracker after the test-boundary and breakdown check. Use native dependencies and parent links.
- Bind approved bytes by absolute path and SHA256 before implementation dispatch. Amendments require a new binding and explicit evidence impact assessment.
