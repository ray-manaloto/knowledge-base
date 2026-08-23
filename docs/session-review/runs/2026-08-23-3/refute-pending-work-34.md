# Refutation attempt — pending-work #34 (corpus-gate-bundle-0821 has no PR and no remote backup)

Verdict: NOT REFUTED (substance holds on 3 independent routes). One number is stale: ahead is now 6, not 5.

## Route 1 — PR existence (gh), control-armed
    gh pr list --head corpus-gate-bundle-0821 --state all --json number,state,url,title  -> []
    CONTROL gh pr list --head graphify-corpus-0947 --state all ...                       -> [{"number":422,"state":"MERGED",...}]
Second route, no --head filter (guards against a fork/head-filter bound):
    gh pr list --state all --limit 300 --json number,state,headRefName | grep -i -e bundle -e 0821 -> rc=1 (no match)
    CONTROL same listing | grep -i 0947 -> "422 MERGED graphify-corpus-0947"; total PRs listed = 146

## Route 2 — do the commits exist on origin at all? (GitHub API)
    gh api repos/ray-manaloto/knowledge-base/commits/a67cbac4 -> HTTP 422 "No commit found for SHA"
    ... c720f1c9 -> 422 ; ... 964fb112 -> 422
    CONTROL ... 8929d47f -> 8929d47f434c359d82adff03c94ce392ee77055d (200)

## Route 3 — live remote refs
    git ls-remote origin '*corpus-gate*' '*0821*' -> no refs (162 refs total on origin)
    CONTROL git ls-remote origin | grep refs/heads/main + issue-299 -> both present
    git branch -r --contains a67cbac4 -> empty ; CONTROL --contains 8929d47f -> origin/HEAD, origin/main

## Upstream ref
    git for-each-ref refs/heads: "corpus-gate-bundle-0821||964fb112" (empty upstream field)
    git config --get-regexp '^branch\.corpus-gate-bundle-0821\.' -> rc=1 (nothing)
    CONTROL git config --get-regexp '^branch\.main\.' -> branch.main.remote origin / branch.main.merge refs/heads/main

## Correction to the finding (drift, not refutation)
    git rev-list --left-right --count origin/main...corpus-gate-bundle-0821 -> 0  6
Tip is now 964fb112 "fix(corpus): answer cold review of #414..." committed 2026-08-21T10:33:16-05:00 (15:33Z),
i.e. AFTER the review window (main transcript ends 15:10:59Z) — by the still-running lane of finding #9.
git show --stat 964fb112: 7 files, +505/-71, incl. graphify_semantic_corpus.py +206 and
tests/test_graphify_semantic_corpus.py +273 — exactly the deltas finding #33 reported as uncommitted.
So #33 ("sits only in the working tree") is now FALSE; #34's "5 commits / ahead=5" is now "6 commits / ahead=6".
Neither changes #34's claim: still no PR, no upstream, nothing on origin.

## Weak arm noted (do not reuse)
    git cherry -v origin/main <merged-branch> printed '+' for all three commits of the SQUASH-merged #422,
    so `git cherry` cannot detect squash-merged content and is useless as a "already upstream" probe here.

## Residual, unverified
"exists on exactly one machine" is unfalsifiable from inside this machine (Time Machine / another clone / a
mirror cannot be probed from here). What IS verified is the git-operational form: not on origin, no PR, no upstream.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — PR list, commit existence API
