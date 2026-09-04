# Tool-currency engine — retired design rationale

Moved out of the root `CLAUDE.md` on 2026-09-03 (#697). Every fact here was
correct and load-bearing when written; none of it changes what a session should
DO, which is why it stopped earning eager context. The norms it supports live in
`.claude/rules/tool-currency-and-native-first.md`; the run log is
`docs/currency/README.md`.

## Step 1 — why an in-sync check was the new part

Bumps were already covered (Renovate, `mise outdated --bump`). What nothing
checked was whether the binary a shell actually reaches matches the pin, and
whether the *installed* version built `graphify-out/`. It caught a live defect on
day one: `MISE_ENV_CACHE=1` had a stale `pipx-graphifyy/0.9.23/bin` on PATH ahead
of the mise shims.

## Why the stamp does not key off `built_at_commit`

graphify stamps no version into its own output — `export.to_json()` writes only
`built_at_commit` — so `kb-build` writes `graphify-out/.currency-stamp.json`
recording the version that ACTUALLY RAN, never the pin, which would launder
drift. A rebuild that bypasses `kb-build` is detected via a content fingerprint
(`size:mtime_ns`) and reports *version unknown*, never a false green.

It deliberately does NOT key off `built_at_commit`: that is the git HEAD, so
every rebuild at one commit writes the same value — and rebuilding repeatedly at
one commit is the normal rhythm, which made the old check almost never able to
fire while claiming it could.

## `extra_probes` is author-chosen on purpose

Two files agreeing that `extras = ["all"]` says nothing about whether the extra
delivered anything, so the config also names packages that must be present.
`graspologic`/`leidenalg`/`igraph` auto-skip by PEP 508 marker on Python 3.14
(the accepted Louvain fallback), so demanding every extra would report drift that
is not drift.

## The three states, expanded

DRIFT (checked, disagrees) · SKIP (not applicable here) · OK. Kept distinct
because collapsing them is how every defect in this engine's review happened. A
run of nothing-but-SKIPs reports *not verifiable here*, never "in sync"; an
unreachable upstream reports *latest UNKNOWN*, never "current"; a tracked issue
whose lookup failed blocks gate 5 rather than passing it; and a binary that is
simply not installed on a host where it *should* be is DRIFT, not SKIP.

## The SessionStart hook's two exceptions

Step 5 can never live in a hook — a hook is a shell command; only the model can
call `AskUserQuestion`. The SessionStart hook therefore runs step 1 only and is
silent unless something drifted, always exiting 0, because a session must not be
blocked over a version pin. Two things it does NOT stay silent about: a missing
`currency.toml` (silence is this design's "clean", so an absent config must
announce that step 1 did not run) and an unknown `--tool` (exit 2).

## The six self-apply gates

Versions readable and moving forward · readable GitHub release · no breaking
marker · extras unchanged · no tracked issue moved · step 1 green. Fails closed.
PyPI is the installable truth; GitHub the narrative.

## GitHub repos touched

_None._ Every line above was moved verbatim from this repo's own `CLAUDE.md`.
