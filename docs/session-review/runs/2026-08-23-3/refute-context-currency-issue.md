# Refute lane: "Currency gate CARRIED 3 rounds; NO GitHub issue exists to force it"

## Probe 1 — full issue-title sweep (unbounded, state=all)
`gh issue list --state all --limit 400 --json number,title,state,labels,createdAt` -> 210 rows.
Control arm: `grep -ic graphify` = 30, `grep -ic review` = 19 (probe discriminates).

Grep `-iE 'pin|bump|version|stale|drift|outdated|upgrade'` returned, among others:

- **#184 OPEN 2026-08-05 "Upgrade every pinned dependency in mise.toml and pyproject.toml, deliberately and in one round"**
- #225 OPEN "13 manifests declare 'this pin MUST track the version we actually run'; nothing enforces it, and 5 are drifted"
- #226 OPEN "Redirect bare `mise outdated` to `--bump`"
- #329 OPEN "datamodel-codegen version check reads an UNPINNED mise pipx install, not the 0.72.4 pin"
- #287 OPEN "Redesign reviewed currency apply as an atomic verified transaction"

=> The "no GitHub issue exists" half looks REFUTED pending a read of #184.

## Probe 2 — #184 read in full (primary artifact, 2 routes)
`gh issue view 184` and `gh api repos/ray-manaloto/knowledge-base/issues/184`
-> `#184 open closed_at=null | Upgrade every pinned dependency in mise.toml and
pyproject.toml, deliberately and in one round` (filed 2026-08-05T21:39:06Z).

Body carries explicit Acceptance criteria:
- "Every pin in `mise.toml` and `pyproject.toml` is either advanced or has a recorded reason it was held."
- "`mise run kb-currency` is run for the deep-tracked tools rather than hand-bumping them"
and states "Not started — it is a round of its own".

That IS an open issue whose acceptance criteria force the carried currency work.

## Probe 3 — controls
- negative control: `grep -ic 'zzqxnotatoken'` -> **0** (probe can return zero)
- positive control: `grep -ic 'currenc'` -> **11**; `graphify` -> 30; `review` -> 19
- body-level sweep (titles-only would be a bound): `gh issue list --state open --limit 400
  --jq 'select(body+title | test("currenc|8 pins|pins behind|kb-currency";"i"))'`
  -> 37 OPEN issues, incl. #184, #287, #225, #226, #329, #195, #188, #151.

## Probe 4 — the handoff's own wording
`.agent/plans/session-2026-08-18-d.md:186-189` (Currency bullet) does **not** say
"no issue". The *adjacent* bullets do, explicitly: `:191-193` Roster — "No issue
filed"; `:194-196` "Four addendum items with NO issue"; `:197` "MAX_ITERATIONS
still prose-only, no issue". The finding generalised those to Currency, which the
source it cites deliberately did not.

## Verdict: REFUTED
The "carried three rounds / zero work" half holds (docs/currency/runs/ newest =
`2026-08-17-graphify.md`; nothing on 08-18). The load-bearing half — "no GitHub
issue exists to force the next round to address it" — is false.

## Contradiction with another live finding
Finding 10 ([forgotten]) says "the closest (#225) explicitly proposes a
non-blocking surfacing mechanism" — i.e. it CONCEDES currency-pin issues exist and
scopes its claim to the *blocking enforcement mechanism*. Finding 19 states the
unqualified "no GitHub issue exists". Two probes of one fact disagree; #184 + #225
settle it against 19.
