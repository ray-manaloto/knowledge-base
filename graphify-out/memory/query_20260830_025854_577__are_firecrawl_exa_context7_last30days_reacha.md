---
type: "query"
date: "2026-08-30T02:58:54.995813+00:00"
question: "#577: are firecrawl/exa/context7/last30days reachable headlessly, one shape or several?"
contributor: "graphify"
outcome: "useful"
---

# Q: #577: are firecrawl/exa/context7/last30days reachable headlessly, one shape or several?

## Answer

## Question

#577 (parent #568, aggregated-research build order position 4/5, "breadth"):
are the aggregated-research plugin's four declared dependencies (firecrawl,
exa, context7, last30days) reachable from a headless, non-Claude-session
process, and does one transport/record shape serve all four — which sizes
whether `breadth` is one adapter ticket or more.

## Answer

All four sources are headlessly reachable, but split into three distinct
transport classes rather than one: an installed-CLI-binary class (firecrawl,
context7 — env-var auth and stored-login auth respectively), a direct-HTTP
class (exa — `x-api-key` header, no CLI on PATH at all), and a
vendored-script-subprocess class (last30days — no CLI, not published on
PyPI, only present because a Claude Code plugin clone happens to sit on
disk). Every reachability claim was control-armed (real vs. bogus query/key/
topic on the identical transport shape) and independently spot-checked by
the architect (`firecrawl --status`, `ctx7 whoami`, a PyPI 404 for
`last30days-skill` against a known-good package control) before shipping.

The dispatch spec's own premise (L4: "last30days has no CLI, reachable only
via a Claude session") was checked with `command -v last30days` alone, which
tests for a named PATH binary only. The report corrected this: absence of a
PATH binary is not absence of headless reachability — last30days ships a
runnable vendored Python script, reachable via `uv run <path> ...` with zero
MCP/session dependency, but with a real, unresolved packaging gap (no
installable artifact a standalone `breadth` CLI could depend on).

Verdict: `breadth` must be split into more than one adapter ticket — at
minimum a CLI-subprocess adapter (firecrawl + context7, pending a future
check that their *record* shapes, not just transport, converge), a
direct-HTTP adapter (exa, reusing #568's `httpx2` decision), and a
higher-risk third path for last30days that needs its packaging question
resolved before any ticket can commit to depending on it.

Full report: `docs/research/reports/2026-08-30-breadth-source-reachability.md`
(PR #624, merged `072910a5`).


## Outcome

- Signal: useful