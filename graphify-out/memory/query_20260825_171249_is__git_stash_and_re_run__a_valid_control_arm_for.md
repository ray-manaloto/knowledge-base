---
type: "query"
date: "2026-08-25T17:12:49.574889+00:00"
question: "Is 'git stash and re-run' a valid control arm for whether this session caused a test failure?"
contributor: "graphify"
outcome: "corrected"
correction: "\"Stash and re-run\" is only a control arm when HEAD predates the change under\ntest. In a session that has already committed, HEAD is your own work, so\nstashing compares your edits against your edits and CANNOT produce the other\nanswer — the exact shape `probes-need-a-control-arm.md` forbids.\n\nThe rule: when arming \"did I cause this?\", the baseline must be a commit from\nBEFORE the session, named explicitly (`git show <pre-session-sha>:<file>`), never\n`HEAD` and never a stash. Write the pre-session SHA down at session start; by the\ntime you need it you will have committed over it.\n\nThis is the second failure this session from the same root — hand-editing. The\nprose I wrote broke a test, and the arm I ran could not see it because I had\nalready committed the prose.\n"
---

# Q: Is 'git stash and re-run' a valid control arm for whether this session caused a test failure?

## Answer

No. `test_skillopt_contract` failed with a tomllib "Cannot overwrite a value".
I ran `git stash push` on my uncommitted files, re-ran the test, saw the SAME
failure, and reported it as pre-existing.

The arm could not discriminate: HEAD was `e5bfa961` — MY OWN commit from earlier
in the same session — which already contained the change that caused the failure
(a fnox comment rewrite mentioning `[tools]` twice in prose). Stashing reverted
to my edits, not to the pre-session state.

`git show 0a997094:mise.toml | grep -c '\[tools\]'` returned 1; the working tree
returned 3. That settled it: I caused it. The fixture used
`.replace("[tools]", ...)` with no count, so it injected one `skillopt` pin per
occurrence and produced a duplicate key.


## Outcome

- Signal: corrected
- Correction: "Stash and re-run" is only a control arm when HEAD predates the change under
test. In a session that has already committed, HEAD is your own work, so
stashing compares your edits against your edits and CANNOT produce the other
answer — the exact shape `probes-need-a-control-arm.md` forbids.

The rule: when arming "did I cause this?", the baseline must be a commit from
BEFORE the session, named explicitly (`git show <pre-session-sha>:<file>`), never
`HEAD` and never a stash. Write the pre-session SHA down at session start; by the
time you need it you will have committed over it.

This is the second failure this session from the same root — hand-editing. The
prose I wrote broke a test, and the arm I ran could not see it because I had
already committed the prose.
