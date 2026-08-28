# Can our Python library call lychee as a library? — a six-source sweep

Date: 2026-08-27 · session `kb-20260827.06` · branch `round/2026-08-27-aggregated-research-eval`
Question (Ray, verbatim): *"use the already existing plugins/skills to search for a way to use
lychee's library functionality to bind to our python library (python to rust bridge)"* —
<https://lychee.cli.rs/guides/library/> — via `/last30days`, `/firecrawl:firecrawl-search`,
`/firecrawl:firecrawl-developer-index`, `/firecrawl:firecrawl-research-index`, `/exa:search`,
`/context7`. Ray's ranking rule, same session: *"prefer tools/libraries/sdks/frameworks that
are actively being worked on (filter by release date/git commit)."*

## Answer

**No maintained Python binding to `lychee-lib` exists, and the lychee maintainers know it.**
Official bindings are an OPEN wishlist item (lycheeverse/lychee#59 lists *"pip (Python
Bindings using pyo3)"* among 66 remaining platforms). The one attempt, `jb--/lychpy`
(PyO3, Rust, `lychpy.check([...])`), was last pushed **2023-09-26**, has 4 stars, and its own
README says *"still in development, and not ready for usage"* — it fails the recency rule
by three years. What the maintainers DID ship is **`lychee-bin` 0.24.2 on PyPI** (PR #1931,
a maturin `bin` release): `uv add lychee-bin` puts the `lychee` binary on the venv PATH.
So the bridge that exists today, is maintained, and needs no Rust toolchain in this repo is
**subprocess + `--format json`** — the shape `bamr87/it-journey`'s `link-checker.py` already
uses. A PyO3 binding of our own would add a Rust build step to a repo whose one Python config
is `pyproject.toml`; it is only worth building if the JSON contract proves insufficient.

Recency filter applied: lycheeverse/lychee pushed 2026-08-25 ✔ · `lychee-lib` crate 0.24.2
updated 2026-05-01 ✔ · `lychee-bin` 0.24.2 on PyPI ✔ · `jb--/lychpy` 2023-09-26 ✘ ·
`rambutan` (an R binding, @drmowinckels.io, 2026-08-01) — alive, but R.

## Ranked sources

**Primary**

| source | what it settled | how reached |
|---|---|---|
| `pypi.org/pypi/<name>/json` | `lychee` = a static blog generator (name collision); `pylychee` = an unrelated "SDK合集"; **`lychee-bin` 0.24.2** = the official binary wheel; `lychee-py` → 404 (the control) | `curl`, step 1 of the sweep |
| `crates.io/api/v1/crates/lychee-lib` | 0.24.2, updated 2026-05-01, 159,031 downloads (control `serde` → 1.0.229) | `curl` |
| docs.rs `lychee_lib` | public API: `check()`, `ClientBuilder`, `Client`, `Collector`, `Input`, `Request`, `Response`, `Status`, `ErrorKind`, `Filter`, `Remap` | `curl` |
| lycheeverse/lychee#59 (OPEN) | *"pip (Python Bindings using pyo3)"* is a remaining wishlist item | Firecrawl developer index (`firecrawl_search`, `categories: ["developer"]`) |
| lycheeverse/lychee#1931 (merged) | maintainer thomas-zahner: *"`lychee-lib` could be used as the canonical library name if we ever decide to release an 'official' one. There already is jb--/lychpy, which we could adopt as well."* → `lychee-bin` chosen; released with rustls default | Exa (`web_search_exa`) |
| `gh api repos/jb--/lychpy` | language Rust, pushed 2023-09-26, 4 stars, README "not ready for usage" | `gh api` (step 2/3) |
| `gh api -X GET search/issues -f q='repo:lycheeverse/lychee python bindings'` | 3 hits: #59 open, #1931 closed, #1874 (deps bump, noise). Channel checked first: `has_issues: true, has_discussions: true`. Control `fragment` → 141 | `gh api` |

**Secondary**

| source | what it added | how reached |
|---|---|---|
| lycheeverse/lychee#420 | *"For Node we can look into Neon and for Python pyo3"* — the idea, 2021-era | developer index |
| `bamr87/it-journey/scripts/validation/link-checker.py` | prior art for the subprocess+JSON bridge: `["lychee", "--output", json]`, `fail_map`/`error_map` parsing, curl fallback | Exa |
| peterbabic.com (2026-04-16), tech-tales.blog (2026-05-08) | pre-push lychee on changed `.md` only, warning-only for external links; `lychee.toml` with `cache`, `max_cache_age`, `exclude` | Exa |
| arXiv 2507.00264 | PyO3 vs ctypes vs cffi — PyO3 is the toolchain if a binding is ever built | Firecrawl research index (`firecrawl_research_search_papers`) |
| context7 `/lycheeverse/lychee`, `/websites/lychee_cli_rs` | README-level "use as a library"; the `lychee.toml` key list; `.lycheeignore`; `--cache` → `.lycheecache` | context7 `resolve-library-id` → `query-docs` |
| `/last30days` (below) | one live binding in the window — **R**, not Python | last30days engine |

## What `/last30days` returned

🌐 last30days v3.21.1 · synced 2026-08-27

What I learned:

**The only binding anyone shipped this month is for R, and it bit its author** - [@drmowinckels.io](https://bsky.app/profile/drmowinckels.io/post/3mrzgs3e6u72w) on Bluesky, 2026-08-01: "101 tests passed — then R crashed on exit with a Windows stack-buffer-overrun 🫠 I wrapped Rust's link checker lychee into an R package (rambutan)." A teardown crash in a wrapper around an async Rust runtime is exactly the class of defect a PyO3 binding would inherit.

**Nobody in r/rust, r/Python or r/learnrust discussed lychee bindings** - the one PyO3 thread in the window is unrelated ([r/rust](https://www.reddit.com/r/rust/comments/1w06pbs/why_waste_200ms_on_an_llm_judge_i_built_a_02ms/), an "edgeguard" guardrail with Python bindings); the lychee mentions on Bluesky are "use this tool" posts, not integration posts. Reddit was partial (HTTP 429 after 16 items), so this is thin coverage, not silence.

**The X column is noise** - every X hit is a drink or a cannabis strain named Lychee. Off-topic, dropped.

KEY PATTERNS from the research:
1. Bindings for lychee are a wishlist, not a project - per [lycheeverse/lychee#59](https://github.com/lycheeverse/lychee/issues/59)
2. The maintained Python-side artifact is the binary wheel - per [lychee-bin on PyPI](https://pypi.org/project/lychee-bin/)
3. Wrapping the async runtime is where wrappers break - per [@drmowinckels.io](https://bsky.app/profile/drmowinckels.io/post/3mrzgs3e6u72w)

---
✅ All agents reported back!
├─ 🟠 Reddit: 16 threads │ 1,591 upvotes │ 349 comments │ ⚠ partial after 16 items: HTTP 429: Too Many Requests (run doctor for fixes)
├─ 🔵 X: 19 posts │ 97 likes │ 14 reposts
├─ 🔴 YouTube: 5 videos │ 36,405 views │ 2/5 with transcripts
├─ 🟡 HN: 4 storys │ 361 points │ 76 comments
├─ 🦋 Bluesky: 3 posts │ 6 likes
├─ 🐙 GitHub: 1 item │ 3,866 stars │ 78 comments
├─ ⛏️ Digg: 23 clusters │ 179 posts │ 97 authors
├─ 🗣️ Top voices: @Kenetik, @mynzagric254, @lolitaknotdress │ r/rust, r/learnrust, r/Python
├─ 🕒 Recent evidence is thin: only 29 of 71 dated items are from the last 7 days.
└─ 📎 Raw results saved to ~/Documents/Last30Days/lychee-link-checker-rust-library-from-python-raw-v3.md
---

Engine invocation: `--plan` (3 subqueries: primary / bindings / python-rust-bridge),
`--github-repo=lycheeverse/lychee`, `--subreddits=rust,Python,learnrust,devops`,
`LAST30DAYS_NATIVE_SEARCH=1`. Partial coverage: Web HTTP 422, Instagram/TikTok HTTP 402,
Reddit 429 after 16 items — those sources were not established quiet.

## Every null, with its arm

| the null | the arm (same shape, known-good input) |
|---|---|
| PyPI `lychee-py` → 404 | `lychee-bin` → 200, 0.24.2 |
| Firecrawl GitHub code search `lychee_lib pyo3` → no binding repo (only PyO3's own CI using lychee) | the same index returned `pyo3/maturin` and `daheige/pyo3-in-action` READMEs |
| Firecrawl research index → no lychee paper | it returned five PyO3-binding papers, so the index discriminates; it is the wrong index for this question, as its own skill says |
| tracker "python bindings" → 3, none an implementation | `has_issues: true`; control `fragment` → 141 |
| context7 → nothing beyond the README | it did return the `lychee.toml` key list from `/websites/lychee_cli_rs` |
| last30days Reddit → no bindings thread | Reddit returned 16 items before the 429; the arm is the partial-coverage flag, not a clean zero |

## Not measured

- Whether `uv add lychee-bin` resolves and runs in THIS repo's venv on macOS arm64 (the
  #1931 thread reports macOS 26 arm64 works; NixOS did not). Not run here — the mise pin
  `lychee = "0.24.2"` (aqua) was chosen instead, so the binary is host-scoped, not venv-scoped.
- `lychee-lib`'s API stability across 0.2x — docs.rs shows the surface, not its churn.
- Whether `rambutan`'s teardown crash reproduces under PyO3/tokio — a lead, not a finding.
- agy (`antigravity:research`) was NOT spent on this question; grep.app and deps.dev were
  not used (deps.dev would give the same PyPI/crates facts keyless).

## lychee on this repo — the prototype, measured

- `lychee --dump` over all 922 tracked `.md`/`.html`: **996 unique http(s) URLs**;
  github.com 467, **docs.doppler.com 377**, fonts.googleapis.com 38.
- Unconfigured full run: **killed at 5 min** (Bash timeout), stderr a loop of
  `Host docs.doppler.com sent an unexpectedly big rate limit backoff duration of 30m. Capping the duration to 1m`.
- `docs/**/*.md` (432 files) with doppler excluded, `--timeout 10 --max-retries 0
  --max-concurrency 64 --accept 200..=299,429`: **1,058 links · 1,026 ok · 32 errors ·
  10 redirects · 34 s.** 29 of the 32 are `Cannot resolve root-relative link` on
  `/Users/rmanaloto/…/file.md:15`-style citations in two research reports (a doc defect —
  absolute machine paths — not a link fault); 3 are real: one 403, one 404, one 405.
- The JSON shape (0.24.2): top keys `total successful errors timeouts redirects excludes
  unknown unsupported` + `error_map` / `success_map` / `redirect_map` / `timeout_map`
  keyed by input file, each value a list of `{url, status: {code|text, details}, span}`.
  **There is no `fail_map` key** — it-journey's parser reads one, so it reads nothing here.
- hk 1.56.1 ships `Builtins.lychee` (`lychee --no-progress {{files}}`, `types = List("text")`,
  `effect = "read"`), so the linter is one assignment in `hk.pkl`.

## GitHub repos touched

- [lycheeverse/lychee](https://github.com/lycheeverse/lychee) — the library, #59, #420, #1931
- [jb--/lychpy](https://github.com/jb--/lychpy) — the abandoned PyO3 binding
- [pyo3/pyo3](https://github.com/pyo3/pyo3) — uses lychee in its own CI (developer-index hits)
- [pyo3/maturin](https://github.com/pyo3/maturin) — the build tool `lychee-bin` was published with
- [bamr87/it-journey](https://github.com/bamr87/it-journey) — prior art for the subprocess+JSON bridge
- [firecrawl/firecrawl-claude-plugin](https://github.com/firecrawl/firecrawl-claude-plugin) — the `firecrawl-developer-index` and `firecrawl-search` skills read for thread 38d175ff
- [firecrawl/cli](https://github.com/firecrawl/cli) — `firecrawl developer <query>` exists in our pinned 1.23.1
- [yuting0624/antigravity-for-claude-code](https://github.com/yuting0624/antigravity-for-claude-code) — `commands/research.md` and the skill's deep-research recipe, read from the 0.23.0 plugin cache
- [jdx/hk](https://github.com/jdx/hk) — `pkl/builtins/lychee.pkl`, `docs/cli/check.md` (`-S --step`), `docs/environment_variables.md` (`HK_PROFILE`)
