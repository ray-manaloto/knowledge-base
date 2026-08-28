---
type: "query"
date: "2026-08-28T03:56:07.157426+00:00"
question: "lychee-py spike: did the binding earn its keep over the CLI spawn, and what did the bench lie about first"
contributor: "graphify"
outcome: "useful"
---

# Q: lychee-py spike: did the binding earn its keep over the CLI spawn, and what did the bench lie about first

## Answer

The lychee-py PyO3 spike (declared, verify-only) answered its two soundness questions YES on macOS (tokio→asyncio bridge works; 5/5 clean exits after an awaited check, -X dev clean) and refuted one API premise (lychee-lib 0.24 Response has no request_uri(); into_body only). The latency bench, armed against the local server's own GET count after two lying runs (the CLI silently read the repo's lychee.toml from cwd and EXCLUDED every URL; `--no-cache` and `--include-loopback` are not 0.24.2 flags — cache and loopback-exclusion are opt-in there), measured CLI 38 ms/url on a 50-url 200/404 mix (23 ms all-200; each 404 ~54 ms more, cause not established) vs binding 0.5 ms sequential / 3 ms gathered. Ray chose A: stop — the CLI stays in hk; the 10–80× is against localhost and the real check is network-bound. Lesson: a lychee CLI run in a directory with a lychee.toml is configured by it silently — pin `--config` in any bench or probe, and read `excludes` before believing `total`.


## Outcome

- Signal: useful