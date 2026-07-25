# Retry Once on a Transient Network Failure — Don't Triage It as a Defect

> **Name kept for cross-repo parity.** In the sibling dotfiles repo this rule is
> about the `persistence` gate inside `verify-local`, a devcontainer flow that
> does not exist here. What ports is the *diagnosis*: this repo's expensive
> tasks are network-sensitive in ways that are not obvious from the task
> definition, and a transient DNS blip looks exactly like a corpus defect in the
> first-pass log.

## Which tasks are network-sensitive, and why it isn't obvious

| Task | The hidden network call |
|---|---|
| `mise run kb-build` | re-clones **every** `sources/*.manifest` at its pinned SHA from GitHub |
| `mise run kb-update -- <name>` | resolves upstream HEAD, then fetches |
| `mise run kb-add -- <url>` | fetches the page/video into `raw/` |
| `mise install` / a first `uv run` | resolves `pipx:graphifyy`, `conda:ffmpeg`, and the PyPI deps |
| `mise run kb-currency` | queries PyPI + GitHub for latest versions and tracked issues |

A single flaky resolution in any of these aborts the task with the graph bytes
perfectly healthy and every committed input unchanged.

## Retry-once heuristic

Before triaging a failure as a real defect:

1. **Confirm the failure mode is environmental.** Look for
   `getaddrinfo ENOTFOUND` / `dial tcp: lookup ... no such host` /
   `Could not resolve host` / `Connection reset` / an HTTP 5xx from
   `github.com`, `pypi.org`, or `ghcr.io`. That is the network signature.
   A real defect looks different — see the table below.
2. **Check host DNS** before retrying:
   `dscacheutil -q host -a name github.com` should return an `ip_address`;
   `curl -sI -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/ --max-time 10`
   should return `200`.
3. **Re-run the SAME task** — do not escalate. Do not `kb-artifacts`, do not
   rebuild from scratch, do not re-run the extraction fan-out. The inputs are
   unchanged; the expensive work is not what failed.
4. If the retry passes, log the transient and move on. If two consecutive runs
   fail with the same network signature, triage host DNS / VPN / proxy before
   changing project code.

## Failure-mode signatures

| Signature | Class | Action |
|---|---|---|
| `getaddrinfo ENOTFOUND` / `Could not resolve host` | environmental | retry once per the heuristic above |
| `dial tcp: lookup … no such host` | environmental | retry once |
| HTTP 429 / 5xx from PyPI or GitHub | environmental (rate limit) | wait, then retry once |
| `fatal: reference is not a tree: <sha>` | **real defect** — the pinned SHA was force-pushed away or the manifest is wrong | fix the manifest; `mise run kb-update -- <name>` |
| a chunk merges but adds ~0 nodes | **real defect** — extraction produced nothing | `kb-validate-chunks`; re-run extraction |
| `kb-currency-check` reports *version unknown* | **real defect** — the graph was rebuilt outside `kb-build` | rebuild via `mise run kb-build` |
| a query returns code symbols for a prose question | **known gap**, not a transient | do not retry; it will not change |

**The middle rows are the point.** A transient wastes one retry; misreading a
real defect as a transient wastes every retry after it, and misreading a
transient as a defect wastes the expensive rebuild the heuristic exists to
avoid.

## Applies to

`mise run kb-build`, `kb-update`, `kb-add`, `kb-currency`, `mise install`, and
any future task that resolves an upstream ref or fetches a URL.

## See also

- `local-devcontainer-first.md` — the sibling: don't reach for the expensive
  run when a cheap probe answers the question.
- `probes-need-a-control-arm.md` — a timeout is not a "no"; distinguish
  "answered no" from "never asked".
- `verify-before-advancing.md` — a retried-green run still owes its evidence.
