# Currency run — claude-code — 2026-07-27T23:27:09+00:00

**Verdict:** claude-code 2.1.220 → v2.1.220: 1 question(s) for review

Related: [[tool-currency-log]] · [[claude-code]]

## Step 1 — in sync?

Pinned `2.1.220` · resolved `2.1.220`

| check | status | detail |
|---|---|---|
| version | ok | claude on PATH is the reviewed 2.1.220 (/Users/rmanaloto/.local/bin/claude) |

## Steps 2-3 — upstream

- Latest (github): `v2.1.220`
- GitHub release: `v2.1.220`
- Reachable: yes

### Release notes

## v2.1.220

## What's changed

- Bug fixes and reliability improvements

## Step 4 — tracked issues and watch items

_No watch items configured for this tool._

## Step 5 — decision

Gates passed:

- ✅ latest version has a readable GitHub release
- ✅ no breaking/removal/deprecation marker
- ✅ extras unchanged
- ✅ no tracked issue moved
- ✅ step 1 currently green

### Gate: patch-level bump

**2.1.220 → v2.1.220 is not a patch bump. Adopt it?**

- Detail: Only the patch component may move unattended. Pre-1.0 projects use the MINOR slot as their breaking channel, so 0.9.x → 0.10.0 stops here.
- Recommended: Read the release notes, then decide.
- **Answer:** _not yet answered_

> **Two corrections, 2026-07-30 — neither changes an outcome.**
>
> 1. The first gate rendered as `PyPI latest has a matching GitHub tag`. Like
>    mise, `[tool.claude-code]` has no `pypi` key (`currency.toml:248-261`), so
>    that label named a lookup that never ran; `decide.GATES[1]` hardcoded the
>    PyPI wording regardless of source. The gate that ran is the GitHub-release
>    read, and it passed.
> 2. **This question should never have been asked.** `2.1.220 → v2.1.220` is one
>    release wearing two spellings. `decide()`'s early return compared raw
>    strings, so a decoration-only mismatch fell through to the gates. It now
>    compares parsed versions (`upstream.same_release`) and returns before any
>    gate runs — an already-installed release raises nothing.
>
> Both found by the cold lane, round 2.

## Step 6 — process note

This page is the immutable record of ONE run — a later run writes its own new
page rather than rewriting this one. Annotate it freely with review notes;
nothing here is regenerated.
