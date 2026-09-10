# DBOS viability for the upgrade journal — research report

Scope: DBOS as durable-execution engine/journal for issue #729's upgrade
command. READ-ONLY — no deps added, no pyproject.toml touched.

## 0. Prior art already found in this repo (kb-recall-work + docs/research/reports/)

`mise run kb-recall-work -- "DBOS durable workflow journal"` → 88 memory-file
matches, 1 tracked-file match, 7 branch matches, 0 issue matches (topic file:
`.agent/kb/recall/dbos-durable-workflow-journal.md`).

`docs/research/reports/2026-09-09-prior-upgrade-design.md` (1273 lines) already
did substantial DBOS legwork in an earlier round (2026-08-30/31), across pages:

- **`the-upgrade-schema.html` (A.5, 2026-08-30):** round-3 Q10 recommended
  `to-db` — all pipeline state into a DBOS/SQLite-backed 9-table schema. Marked
  explicitly UNDECIDED at the time: "which state machine library... and the
  exact DBOS pin set... neither is guessed here."
- **`what-to-pin.html` (A.8, 2026-08-30):** concrete pin proposal
  `dbos>=2.31.0` (floor, not exact `==`, per house style for Python libs).
  Findings, self-corrected in-page:
  - **SQLite IS the default system store as of the released 2.31.0** — the
    page explicitly retracts an earlier claim that DBOS defaults to Postgres
    ("I told you the opposite earlier... That is false for the released
    2.31.0. SQLite is the default system store." — verified against the
    released tag, not `main`).
  - Resolving `dbos>=2.31.0` + `python-statemachine>=3.2.1` against Python
    3.14 pulls **12 packages: 5 already held, 7 new** — including **two
    PostgreSQL drivers** (`psycopg`, `psycopg-binary`) the design would never
    use (SQLite is the default store) — "a cost worth naming before we pay
    it... for a database this design does not use."
  - Marked explicitly UNVERIFIED: "an end-to-end install of either package on
    3.14.7 (resolution only)... belongs in the adopting ticket as its first
    task."
- **`four-step-upgrade-chain.html` (A.7, 2026-09-01) — Ray's own words, quoted
  in-page, narrows the above:** *"The DBOS plan exists, nothing is built, and
  it already answers 'don't build throwaway'. Plain functions in one module,
  no new dependency — adopting DBOS later is adding decorators. What would be
  waste is a new config file."* This reads as Ray deferring DBOS adoption
  (build plain functions first), dated ONE DAY AFTER the A.5 schema assumed
  DBOS+SQLite as the day-one design. **This is prior to Ray's #729 ruling
  reported by the team lead today (2026-09-09), which explicitly names DBOS
  in the issue title — so the 09-01 deferral has apparently been
  SUPERSEDED by a later, more direct ruling.** Not contradicting my task; just
  noting the timeline so the "extend, don't redo" instruction is honored
  accurately — nothing here still open needs to be relitigated, but the
  history shows the DBOS-vs-plain-functions question was live and reversed at
  least once already.
- **`docs/research/reports/2026-09-09-upgrade-dependency-inventory.md`
  (467 lines)** — not yet read this pass; checking next for anything DBOS
  package/dependency-count specific beyond A.8's 12-package finding.

None of the prior pages independently confirmed: exact current PyPI version
(2.31.0 was the figure in late Aug), transitive dep count on THIS repo's own
lock resolution, license, GitHub issues/PRs/discussions volume+health, or
whether a SQLite backend is genuinely production-grade vs. a "works but not
recommended" mode. Verifying all of those fresh below.

## 1. What is it, concretely — IN PROGRESS

**Package.** PyPI `dbos`, current release **2.31.1** (2026-09; verified fresh
this session via `curl https://pypi.org/pypi/dbos/json`, not the 2.31.0 figure
in the earlier round's page — a real, expected drift since 2026-08-30, not a
correction of it). License **MIT**. `requires_python: >=3.10`; classifiers
explicitly list `Programming Language :: Python :: 3.14` — **this repo's
Python 3.14 pin is a declared-supported version, not a risk.** (Cross-checked:
resolving `dbos>=2.31.1` on Python 3.14.7 via `uv pip compile` succeeds
cleanly — see §4.)

**No external server or Postgres instance is mandatory.** It is an in-process
Python library (decorators around your functions); the durable "system
database" the library writes to can be a **local SQLite file** — confirmed
from the released package's own dependency metadata AND from the live docs
(`docs.dbos.dev/python/reference/configuration.md`, fetched fresh this
session): *"If no connection string is provided, DBOS uses a SQLite
database"* (`sqlite:///[application_name].sqlite`) — **SQLite is the
zero-config default**, not an opt-in mode you have to configure. DBOS Conductor
(a hosted dashboard/orchestration add-on) is optional — `conductor_key: ...
If provided, application connects to Conductor` — confirmed not required.

## 2. SQLite or Postgres — THE DECIDING FACT

**SQLite is real, merged, long-lived, and the documented default — but DBOS's
own docs and marketing treat Postgres as the "production" target, and the base
package installs a Postgres driver unconditionally even when SQLite is all you
use.**

Evidence, cited:

- Merged PR **#441 "SQLite Support"** (merged 2025-08-27, NOT #680 as the
  2026-08-30 design round cited — that PR is "Retry Serialization Errors in
  Datasources," unrelated; the 2026-08-30 round's own citation was wrong, the
  underlying claim was right). PR #441's own description, quoted verbatim:
  *"This is intended to be used for lightweight development and testing,
  allowing users to get started with DBOS or test their DBOS apps without
  needing a Postgres database. It may also be useful for embedded
  applications... The SQLite system database is 100% feature complete."*
- **companion merged PR #442 "System Database URL"** (2025-08-27) plumbed the
  connection-string config that makes SQLite selectable.
- SQLite-specific bugfixes have shipped continuously since — **#553** "Fix
  SQLite threading bugs" (2026-01-07), **#564** "SQLite Isolation Level"
  (2026-01-21), **#790** "Fix Flaky SQLite Tests" (2026-07-21) — i.e. it is
  exercised in CI over a year later, not an abandoned stub.
- **Live docs, current as of this session** (`docs.dbos.dev/python/reference/
  configuration.md`): *"This may be either Postgres or SQLite, **though
  Postgres is recommended for production**."* And: `use_listen_notify` "Defaults
  to True in Postgres and **must be False in SQLite**" (SQLite uses polling
  for notifications, not instant wakeup — a real behavioral difference, not
  just a config knob).
- **The live GitHub README (fetched fresh, `main` branch)** frames the entire
  project around Postgres — "DBOS provides lightweight durable workflows built
  on top of Postgres," "connect it to a Postgres database" in the quickstart —
  SQLite is not mentioned once in the README's marketing copy despite being
  the code default. The library's own public-facing story assumes Postgres;
  SQLite is a documented but secondary path.
- **Cost, confirmed by a fresh isolated resolution** (`uv pip compile` against
  `dbos>=2.31.1` alone, Python 3.14, read-only — no pyproject.toml touched):
  11 total packages, of which **`psycopg==3.3.5` and `psycopg-binary==3.3.5`
  (a Postgres driver, incl. a compiled binary wheel) are UNCONDITIONAL base
  dependencies of the `dbos` package itself** — installed even for a pure
  SQLite user who will never open a Postgres connection. Also new to this
  repo: `sqlalchemy==2.0.52` (dbos uses it internally for cross-dialect system
  tables — the same design that makes SQLite "100% feature complete"),
  `greenlet` (sqlalchemy transitive), `websockets` (dbos direct dep, used for
  its Conductor/streaming feature we would not use). 5 of the 11 are already
  in this repo's `uv.lock` today (click, python-dateutil, pyyaml, six,
  typing-extensions) — **6 genuinely new**: dbos, greenlet, psycopg,
  psycopg-binary, sqlalchemy, websockets.

**Verdict on this question: SQLite is production-**usable** for a
single-process local CLI (this repo's actual use case is exactly the
"lightweight/embedded" case the merging PR names as the intended one), but it
is explicitly NOT what DBOS calls "production" in its own docs — that word
means a deployed, possibly multi-instance service, which is not what an
upgrade-journal CLI is. Not a blocker; a caveat Ray should see stated plainly,
because it means the project's own maintainers would not vouch for this
exact configuration if asked "is DBOS+SQLite production ready" without
qualification.**

## 3. What it actually buys here

The need per the team lead's brief: a write-ahead journal — record intent
before a mutation, record completion after, so a crash leaves a durable
RECOVERY_REQUIRED state a resume can reconcile.

DBOS's durable-execution model is built for exactly this shape and gives real
things a hand-rolled sqlite3 journal would have to build itself:
- **Automatic checkpointing of workflow + step state** on every step boundary,
  with configurable idempotency (`workflow_id`) so a *replayed* run after a
  crash resumes rather than re-executing from scratch — the hand-rolled
  version would need to hand-write "have I already done this step" logic per
  mutation type.
- **Exactly-once step execution semantics** (documented OAOO — "once and only
  once" — pattern), which is precisely "crash leaves RECOVERY_REQUIRED, resume
  reconciles" already built as a first-class primitive rather than a
  bespoke state column.
- **Built-in queues/notifications/scheduling** if the upgrade protocol ever
  needs to batch or schedule dependency bumps (Ray's `commit-per-dependency`,
  `batch = one PR` decision, per the prior round's #638 record) — those map
  onto DBOS queues directly rather than requiring hand-rolled batching logic.
- Prior round's own framing (`four-step-upgrade-chain.html`, Ray quoted): *"The
  DBOS plan exists... Plain functions in one module, no new dependency —
  adopting DBOS later is adding decorators."* This is accurate and matters for
  scope: a hand-rolled sqlite3 journal and a DBOS-backed one are NOT
  architecturally divergent designs — DBOS's own model is "write plain
  functions, decorate them," so the migration cost between the two is low
  either direction.

Fair caveat: for THIS repo's narrow need (record intent, record completion,
resume-reconcile identities), a hand-rolled sqlite3 table with two rows
(`stage_event`-shaped) and one WAL-mode connection would cover the literal
requirement with zero new dependencies. DBOS buys battle-tested crash-recovery
semantics, idempotency keys, and optional queueing/scheduling beyond that
literal ask — worth it if the upgrade protocol grows into the fuller design
already sketched in `the-upgrade-schema.html` (9 tables, multi-stage pipeline),
overkill if the scope stays "just don't lose track of an interrupted bump."

## 4. The cost

- **New dependency, floor-pinned** (`dbos>=2.31.1`) per this repo's house style
  for Python libraries (exact `==` pins are for tools/manifests, not `[project]`
  floors — `pyproject.toml`'s existing `anthropic`/`httpx2`/`structlog` floors
  are the precedent). Confirmed this does NOT trip `check_first`/`hook_guard` —
  it would go through `uv add`, the sanctioned path, never `uv add` was RUN
  here (constraint: read-only, no deps added).
- **Transitive cost, freshly measured (not inherited):** 11 packages resolve
  for `dbos` alone on Python 3.14; **6 are new** to this repo's `uv.lock`:
  `dbos`, `greenlet`, `psycopg`, `psycopg-binary`, `sqlalchemy`, `websockets`.
  Two of those six (`psycopg`, `psycopg-binary`) are a Postgres driver this
  design would never call. `psycopg-binary` ships a compiled wheel (**4.6 MiB
  download** observed this session) — a real per-platform install cost, not
  pure-Python.
- **No web framework, no ORM in the "front door" sense** — SQLAlchemy is
  present but used internally by DBOS for its own system tables, not exposed
  as a general ORM for this repo's own schema. **No bundled server process.**
- If `python-statemachine` (the state-machine library the prior round paired
  with DBOS) is added too, that is a separate, smaller cost not re-measured
  this session — the prior round's page (`what-to-pin.html`) already covers it
  and nothing here contradicts that.

## 5. Upstream health

`dbos-inc/dbos-transact-py` (GitHub API, fetched fresh this session):
- **1,565 stars, 93 forks, 10 subscribers.**
- `has_issues: true`, **`has_discussions: false`** — a Discussions search here
  is *structurally* zero and would be a false negative if reported as "no
  discussion activity"; there simply is no Discussions tab to search. Control
  arm run per the instruction: searched issues for a known-present term
  (`durable`) → **40 hits**, confirming the search API itself works before
  trusting the `sqlite`-scoped searches below.
- `open_issues_count: 4` (this count includes open PRs too, per GitHub API
  semantics) — low, and `pushed_at: 2026-09-10T00:34:54Z` — **pushed within
  the last 24 hours of this research**, i.e. actively developed, not
  dormant. Most recent merged PR in the sqlite-scoped search: **#844**, merged
  2026-09-09.
- Issue/PR search for `sqlite` (47 total hits, control-armed above): a healthy
  mix of merged features (#441, #442, #511, #553, #564, #790) and recently
  closed bugs, several SQLite-specific (`#761` "SQLite datasource OAOO
  pre-check read is not covered by the lock retry loop," `#768` "Queued
  workflows get whole-second-quantized timeout deadlines on SQLite") — real
  edge-case bugs were found and fixed, which reads as an actively-used code
  path rather than an untested one, but also means SQLite has had (and had
  fixed) real correctness bugs as recently as this year.
- **Not independently checked**: full closed-issue count, release cadence in
  numeric form (496 total PyPI releases observed, including many prereleases —
  not decomposed into a cadence figure), and whether any CURRENTLY open issue
  is SQLite-blocking (none of the 4 open issues in the `has_issues` count were
  read individually beyond the sqlite-scoped search above — **UNVERIFIED**).

## 6. Prior art in this repo — does the earlier evaluation still hold?

**Mostly yes, with two corrections and one important nuance already flagged
by the repo's own prior self-review — not new findings, just re-confirmed:**

- The earlier round's **own follow-up session** (`findings.md` in the same
  plan) had ALREADY flagged that issue **#638 cited a "merged DBOS PR" that
  does not exist** and traced it to a mis-cited closed issue (#101). This
  session independently found the SAME defect by checking #101 directly (it
  is CLOSED, unmerged, dated 2024-09-13, unrelated to the actual shipped
  work) and by finding what #638 probably meant to cite is far more likely
  **#441/#442** (matching PR titles, matching merge dates, matching described
  behavior) — **not #680** as this session's own sibling report
  (`2026-09-09-upgrade-dependency-inventory.md:333`) states. That sibling
  report's "#680" citation is itself now REFUTED by this session's read of
  PR #680 (title: "Retry Serialization Errors in Datasources," unrelated to
  SQLite) — flagging this so whoever reads that report next does not
  propagate a citation this report has now disproven.
- The earlier round's "SQLite is the default system store as of 2.31.0" claim
  **holds** and is re-confirmed against the current release (2.31.1) and
  against live docs, independently of that report.
- The earlier round's 12-package/7-new resolution figure (paired with
  `python-statemachine`) is **consistent in kind** with this session's
  11-package/6-new figure for `dbos` alone — the psycopg-pair finding is the
  same fact, independently re-derived.
- **Not previously stated anywhere found**: the "Postgres recommended for
  production" line from DBOS's own current docs, and the README's Postgres-
  only marketing framing. This is new evidence this session adds to the
  record — the prior round evaluated the dependency-and-code facts
  thoroughly but did not fetch DBOS's own docs/README to check how the
  project frames its own recommended usage.
- Ray's ruling reported today (issue #729 titled to explicitly adopt DBOS) is
  **consistent with, not overturning,** the design-round history: DBOS-SQLite
  was Ray's own decision in the `/grilling` round (#638) and endorsed by
  `fable-advisor`'s architecture verdict in the same issue (confined to one
  module, ship as plain functions DBOS decorates). The 2026-09-01 page
  (`four-step-upgrade-chain.html`) reads as a scope-sequencing note ("build
  plain functions first, DBOS later"), not a reversal — and #729 today appears
  to be that "later" arriving.

## Verdict

**VIABLE WITH CONSTRAINTS.**

**The single fact that decides it:** DBOS's SQLite backend is real, merged
(PR #441/#442, 2025-08-27), the documented **zero-config default**, and
actively maintained — so it satisfies the "must work offline on one laptop,
no external process" requirement outright. The constraint is that DBOS's own
docs say *"Postgres is recommended for production"* and its base package
installs a Postgres driver (`psycopg`/`psycopg-binary`) unconditionally even
when SQLite is all that's used — so this is a supported-but-secondary path
through someone else's project, not the path its maintainers optimize for or
would unconditionally vouch for at "production" framing. Python 3.14 is
explicitly declared supported (not a risk), and a fresh isolated resolution on
this repo's actual Python confirms it installs cleanly (11 packages, 6 new).

**What I could not determine:** (1) whether any of the 4 currently-open
GitHub issues on the repo is SQLite-specific and unresolved (not individually
read); (2) a numeric release-cadence figure beyond "pushed within 24h,
PyPI shows 496 historical releases including prereleases"; (3) whether
`python-statemachine` (the pairing library from the prior round) still
resolves cleanly alongside dbos on 3.14 — not re-verified this session, only
`dbos` alone was resolved; (4) DBOS's crash-recovery guarantees under SQLite
specifically under concurrent access from multiple processes (this repo's
upgrade command is presumably single-process, so likely moot, but not
confirmed against DBOS's own docs on SQLite locking behavior beyond the
`use_listen_notify=False`/polling note above).

## GitHub repos touched

- [dbos-inc/dbos-transact-py](https://github.com/dbos-inc/dbos-transact-py) — the DBOS Python library itself: SQLite support PRs (#441, #442), refuted PR citation (#680), sqlite bugfix history, repo health metrics (stars/forks/issues/discussions), README.
