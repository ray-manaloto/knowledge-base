# RESULT — lychee-py spike (declared spike, caller-run §5), 2026-08-28

Spec: knowledge-base/.agent/plans/spec-2026-08-27-lychee-py-spike.md (advisor-amended: codex wrote the sources offline, the caller built and ran).
Host: macOS (Darwin 25.6.0), cargo/rustc 1.98.0, maturin 1.15.0 via `uv tool run`, uv venv in the spike dir.
Pins actually built: pyo3 0.29 · pyo3-async-runtimes 0.29 (tokio-runtime) · lychee-lib 0.24 · tokio 1 (see Cargo.toml / Cargo.lock beside this file).

## Finding 1 — the API premise gap the lane flagged was real

First `maturin develop`: **build rc=1**, exactly one error —
`error[E0599]: no method named 'request_uri' found for struct 'Response'` (build.log:624).
`Status::is_success()` and `Status::code()` compiled. lychee-lib 0.24's `Response` exposes
`into_body(self) -> ResponseBody` (registry src/types/response.rs:90), no request-uri accessor.
Fix: carry the input url through `to_dict(url, response)`. Second build: **rc=0** (build2.log).

## Finding 2 — the bridge works (§1 question 1)

```
server control arm: missing=000 spike.py=000
== spike.py ==
warning: `VIRTUAL_ENV=/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
https://github.com/lycheeverse/lychee -> ok=True status=200 OK code=200
http://127.0.0.1:8765/missing -> ok=False status=Rejected status code: 404 Not Found code=404
spike rc=0
== teardown x5 ==
run 1 rc=0 stderr_bytes=214
run 2 rc=0 stderr_bytes=214
run 3 rc=0 stderr_bytes=214
run 4 rc=0 stderr_bytes=214
run 5 rc=0 stderr_bytes=214
== dev+faulthandler ==
warning: `VIRTUAL_ENV=/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
dev rc=0
```

Server control arm: the two `curl` probes ran BEFORE the background `http.server` had bound (both
`000`), so they do not discriminate; the discriminating arm is lychee's own result — `Rejected
status code: 404 Not Found code=404` from 127.0.0.1:8765 — which could only come from the server.
Live arm: github → `200 OK`, ok=True. Dead arm → ok=False as DATA, not an exception (§4 invariant held).

## Finding 3 — teardown is clean on this host (§1 question 2)

Five runs of `teardown.py` (await one check, then `sys.exit(0)` inside the coroutine, no runtime
shutdown): **rc=0 ×5**. stderr is 214 bytes on every run and byte-identical (`cmp`): it is uv's
`VIRTUAL_ENV=…/knowledge-base/.venv does not match the project environment path` warning — the
host shell's exported venv, not the extension. No abort, segfault, panic, or "stack" text.
`python -X dev -X faulthandler teardown.py`: **rc=0**, same single uv line, no ResourceWarning.
The rambutan teardown class did not reproduce on macOS; Windows (where rambutan crashed) is UNTESTED.

## Exit line — what `await check()` gives that subprocess + `lychee --format json` cannot

Measured here: **nothing the hk linter needs.** Both arms produce the same facts (url, status,
code, ok). What the binding adds is in-process, per-URL `await` with a typed `Status` and no
process spawn or JSON parse per call; what it costs is a Rust toolchain plus a lychee-lib
dependency tree (aws-lc-sys/ring/reqwest) compiled into a wheel we would own and re-pin. Not
measured: per-call latency vs one CLI spawn over a file list, or Windows teardown.

## Finding 4 — latency, measured after Ray chose option C (2026-08-28)

Bench: `bench.py` (beside this file's source in the spike dir), 50 URLs on a local `python -m http.server`
(25 × 200, 25 × 404), 3 repeats, medians. Every arm is checked against the server's OWN access-log GET count,
because the first two runs lied: run 1 the CLI reported `excludes=2` — it had read the repo's `lychee.toml`
(cwd) — so `--config empty.toml` pins it; run 2 `--no-cache`/`--include-loopback` are not 0.24.2 flags
(cache and loopback-exclusion are opt-IN there). Output of the armed run, verbatim:

```
cli stats: successful=25 errors=25 excludes=0 total=50
  cli stats: successful=25 errors=25 excludes=0 total=50
  cli stats: successful=25 errors=25 excludes=0 total=50
server GETs during cli arm: 90 (expect 150)
  gather statuses: [('200 OK', 25), ('Rejected status code: 404 Not Found', 25)]
  gather statuses: [('200 OK', 25), ('Rejected status code: 404 Not Found', 25)]
  gather statuses: [('200 OK', 25), ('Rejected status code: 404 Not Found', 25)]
server GETs during gather arm: 150 (expect 150)
  seq statuses: [('200 OK', 25), ('Rejected status code: 404 Not Found', 25)]
  seq statuses: [('200 OK', 25), ('Rejected status code: 404 Not Found', 25)]
  seq statuses: [('200 OK', 25), ('Rejected status code: 404 Not Found', 25)]
server GETs during seq arm: 150 (expect 150)
N=50 repeats=3 (median wall-clock s, count checked)
cli one spawn --format json : 1.920s  checked=50
binding gather(N)           : 0.156s  checked=50
binding sequential          : 0.024s  checked=50
binding single call (seq/N) : 0.5 ms/url
control: cli success=25 fail=25 total=50 (expect ~N/2 each)
```

The CLI's 90 GETs against an expected 150 is DEDUPLICATION, not a miss: the 25 "200" URLs are 5 unique
files, so the CLI sends 30 unique requests per run (`unique` in its JSON) where the binding sends 50.
Gather slower than sequential is the single-threaded `http.server` serialising 50 concurrent requests.

Retry policy equalised and the spawn cost isolated, verbatim:

```
cli default retries    : 2.064s ok=25 err=25
cli --max-retries 0    : 1.909s ok=25 err=25
cli --version (spawn)  : 0.009s
cli 25 all-200 urls    : 0.569s
```

So: spawn is 9 ms, retries are not the gap, and the CLI's cost is **per failed URL** (25 all-200 URLs
0.57 s ≈ 23 ms each; adding 25 404s costs another ~1.3 s ≈ 54 ms each) — cause NOT established (the CLI
does more per failure than the library's `check()`; HEAD→GET fallback is the likely candidate, unmeasured).
The binding: **0.5 ms per URL sequential, 3 ms per URL gathered**, same 200/404 facts, no dedup, no retry.

What this does and does not say: on localhost the binding is 10–80× faster per URL. hk's real link check
is network-bound (remote round-trips of 100 ms+), where a 23 ms CLI overhead per URL is a fraction, not a
multiple — the bench did not measure that case. The ONE structural difference stands: the CLI dedups and
retries for you; the binding gives you raw per-URL awaits and leaves both to the caller.

## Decision — Ray, 2026-08-28 (AskUserQuestion, verbatim option label)

> A: stop — keep the CLI in hk

Chosen after Finding 4. The round-3 ruling ("own repo, after a spike here") is superseded by this: the binding is not built.

## Appendix — bench.py, verbatim (the scratchpad dies with the session)

```python
"""Latency bench: N local URLs via ONE lychee CLI spawn vs N await check() calls (gather + sequential).

Local server on 127.0.0.1:8765 removes network noise; the same URL list goes to both arms.
Every number printed is wall-clock seconds, median of REPEATS.
"""
import asyncio, json, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path

import lychee_py
from collections import Counter
LOG = Path(__file__).parent / "server2.log"
def hits() -> int:
    return sum(1 for l in LOG.read_text(errors="replace").splitlines() if "GET " in l)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50
REPEATS = 3
BASE = "http://127.0.0.1:8765"
# half 200s (files that exist), half 404s
existing = ["spike.py", "teardown.py", "Cargo.toml", "pyproject.toml", "bench.py"]
urls = [f"{BASE}/{existing[i % len(existing)]}" if i % 2 == 0 else f"{BASE}/missing-{i}" for i in range(N)]
LYCHEE = shutil.which("lychee")
assert LYCHEE, "lychee CLI not on PATH"


def cli_once() -> tuple[float, int]:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("\n".join(urls))
        path = f.name
    t = time.perf_counter()
    p = subprocess.run([LYCHEE, "--format", "json", "--no-progress", "--config", str(Path(__file__).parent / "empty.toml"), path], capture_output=True, text=True, check=False)
    dt = time.perf_counter() - t
    Path(path).unlink()
    data = json.loads(p.stdout)
    print(f"  cli stats: successful={data['successful']} errors={data['errors']} excludes={data['excludes']} total={data['total']}")
    return dt, data["total"]


async def gather_once() -> tuple[float, int]:
    t = time.perf_counter()
    res = await asyncio.gather(*(lychee_py.check(u) for u in urls))
    dt = time.perf_counter() - t
    print("  gather statuses:", Counter(r["status"] for r in res).most_common(4))
    return dt, len(res)


async def seq_once() -> tuple[float, int]:
    t = time.perf_counter()
    n = 0
    st = Counter()
    for u in urls:
        st[(await lychee_py.check(u))["status"]] += 1
        n += 1
    dt = time.perf_counter() - t
    print("  seq statuses:", st.most_common(4))
    return dt, n


def med(xs): return statistics.median(xs)

h0=hits(); cli = [cli_once() for _ in range(REPEATS)]; h1=hits(); print(f"server GETs during cli arm: {h1-h0} (expect {REPEATS*N})")
gat = [asyncio.run(gather_once()) for _ in range(REPEATS)]; h2=hits(); print(f"server GETs during gather arm: {h2-h1} (expect {REPEATS*N})")
seq = [asyncio.run(seq_once()) for _ in range(REPEATS)]; h3=hits(); print(f"server GETs during seq arm: {h3-h2} (expect {REPEATS*N})")
print(f"N={N} repeats={REPEATS} (median wall-clock s, count checked)")
print(f"cli one spawn --format json : {med([d for d,_ in cli]):.3f}s  checked={cli[0][1]}")
print(f"binding gather(N)           : {med([d for d,_ in gat]):.3f}s  checked={gat[0][1]}")
print(f"binding sequential          : {med([d for d,_ in seq]):.3f}s  checked={seq[0][1]}")
print(f"binding single call (seq/N) : {med([d for d,_ in seq])/N*1000:.1f} ms/url")
# control arm: the CLI actually checked all N and the mix is real
p = subprocess.run([LYCHEE, "--format", "json", "--no-progress", "--config", str(Path(__file__).parent / "empty.toml"), "-"], input="\n".join(urls), capture_output=True, text=True, check=False)
d = json.loads(p.stdout); print(f"control: cli success={d['successful']} fail={d['errors']} total={d['total']} (expect ~N/2 each)")
```

## GitHub repos touched

- [lycheeverse/lychee](https://github.com/lycheeverse/lychee) — lychee-lib 0.24 API (Response::into_body, no request_uri); the live 200 arm
- [PyO3/pyo3](https://github.com/PyO3/pyo3) · [PyO3/pyo3-async-runtimes](https://github.com/PyO3/pyo3-async-runtimes) — the bridge (future_into_py)
- [PyO3/maturin](https://github.com/PyO3/maturin) — the build
