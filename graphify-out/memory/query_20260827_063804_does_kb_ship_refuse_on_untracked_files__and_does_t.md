---
type: "query"
date: "2026-08-27T06:38:04.985704+00:00"
question: "Does kb-ship refuse on untracked files, and does the funnel gate really force the eli5-visual artifact collision #536 describes?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does kb-ship refuse on untracked files, and does the funnel gate really force the eli5-visual artifact collision #536 describes?

## Answer

`mise run kb-ship` REFUSES on a dirty tree, and "dirty" includes UNTRACKED
files — not just modified tracked ones. On 2026-08-27 it refused with
`ship: refusing — working tree is dirty; commit or stash first` over two
untracked HTML files under `docs/artifacts/` that were being deliberately
held back pending issue #536.

The recorded precedent is stash -> ship -> restore, and it works:
`git stash push --include-untracked -m "<why>" -- docs/artifacts/`, then
`mise run kb-ship`, then `git stash pop`. The files come back untracked and
the pending decision is preserved exactly.

THE NEW FACT, and it changes what #536 is choosing between. #536 was filed
because the `eli5-visual` output style makes every explanation an artifact
under `docs/artifacts/`, while the `funnel` ship gate fails a branch that
touches `docs/artifacts/**` with no `sources/**` delta and no
`Funnel-exempt:` trailer. That framing assumed the artifact commit would
arrive ALONE.

It does not have to. `funnel` keys on whether the SAME branch carries a
`sources/**` delta — not on which commit carries it. So an artifact
committed onto a branch that also touches `sources/**` reports `funnelled`,
not `drift`, and ships with no exemption trailer at all. Branch
`fix/plugin-count-and-codex-pin` was exactly that shape (it modified
`sources/codex.manifest`), so the two held-back artifacts could have ridden
along legitimately and the gate would have passed.

That is a third option #536 did not have when it was written: neither
"exempt `docs/artifacts/**`" nor "require a trailer every time", but
"land an explainer on a branch that also funnels something". It is not a
general answer — a pure-docs branch still collides — but it means the
collision is narrower than the ticket states.

Also worth knowing: this is the live edge of #530, which Ray ruled a DECLARED
BOUND rather than a bug — the funnel gate cannot see uncommitted research, so
the stash-for-the-push move means the gate's PASS never examined those files.
The gate was green about a tree that did not contain them.


## Outcome

- Signal: useful