---
type: "query"
date: "2026-09-02T16:51:11.477450+00:00"
question: "Why was the graphify fork's rebase debt reported as 36 when it is 0?"
contributor: "graphify"
outcome: "corrected"
correction: "I reported the graphify fork was \"36 commits behind upstream, the rebase\ntreadmill is already accruing\" and presented it as measured fact. It was\nmeasured -- against the WRONG REF.\n\n`upstream/main` in Graphify-Labs/graphify is a DEAD BRANCH: last commit\n2026-05-14, v0.1.x era, and NOT an ancestor of v0.9.53. Upstream's real default\nis `v8`, and `upstream/v8 == v0.9.53` exactly, which is our merge base. Real\nrebase debt: 0. Rebasing onto `main` would have been destructive.\n\nThe probe was `git rev-list --count HEAD..upstream/main`. It ran fine and\nreturned a real number. Nothing about the output said \"this ref is dead\" -- a\nstale branch answers a revision count exactly as confidently as a live one.\n\nCONTROL ARM THAT WOULD HAVE CAUGHT IT, and now the habit: before counting\nagainst any remote branch, resolve what the remote's DEFAULT actually is --\n`git symbolic-ref refs/remotes/<remote>/HEAD` -- and check the candidate is an\nancestor of the tag you are on: `git merge-base --is-ancestor <ref> <tag>`.\n\"main\" is an ASSUMPTION about a remote's layout, not a fact about it.\n\nSame class as a token-spelling bound in probes-need-a-control-arm rule 3: the\nliteral command was true, the conclusion was backwards.\n"
---

# Q: Why was the graphify fork's rebase debt reported as 36 when it is 0?

## Answer

I reported the graphify fork was "36 commits behind upstream, the rebase
treadmill is already accruing" and presented it as measured fact. It was
measured -- against the WRONG REF.

`upstream/main` in Graphify-Labs/graphify is a DEAD BRANCH: last commit
2026-05-14, v0.1.x era, and NOT an ancestor of v0.9.53. Upstream's real default
is `v8`, and `upstream/v8 == v0.9.53` exactly, which is our merge base. Real
rebase debt: 0. Rebasing onto `main` would have been destructive.

The probe was `git rev-list --count HEAD..upstream/main`. It ran fine and
returned a real number. Nothing about the output said "this ref is dead" -- a
stale branch answers a revision count exactly as confidently as a live one.

CONTROL ARM THAT WOULD HAVE CAUGHT IT, and now the habit: before counting
against any remote branch, resolve what the remote's DEFAULT actually is --
`git symbolic-ref refs/remotes/<remote>/HEAD` -- and check the candidate is an
ancestor of the tag you are on: `git merge-base --is-ancestor <ref> <tag>`.
"main" is an ASSUMPTION about a remote's layout, not a fact about it.

Same class as a token-spelling bound in probes-need-a-control-arm rule 3: the
literal command was true, the conclusion was backwards.


## Outcome

- Signal: corrected
- Correction: I reported the graphify fork was "36 commits behind upstream, the rebase
treadmill is already accruing" and presented it as measured fact. It was
measured -- against the WRONG REF.

`upstream/main` in Graphify-Labs/graphify is a DEAD BRANCH: last commit
2026-05-14, v0.1.x era, and NOT an ancestor of v0.9.53. Upstream's real default
is `v8`, and `upstream/v8 == v0.9.53` exactly, which is our merge base. Real
rebase debt: 0. Rebasing onto `main` would have been destructive.

The probe was `git rev-list --count HEAD..upstream/main`. It ran fine and
returned a real number. Nothing about the output said "this ref is dead" -- a
stale branch answers a revision count exactly as confidently as a live one.

CONTROL ARM THAT WOULD HAVE CAUGHT IT, and now the habit: before counting
against any remote branch, resolve what the remote's DEFAULT actually is --
`git symbolic-ref refs/remotes/<remote>/HEAD` -- and check the candidate is an
ancestor of the tag you are on: `git merge-base --is-ancestor <ref> <tag>`.
"main" is an ASSUMPTION about a remote's layout, not a fact about it.

Same class as a token-spelling bound in probes-need-a-control-arm rule 3: the
literal command was true, the conclusion was backwards.
