# premise-verifier — kb837 spec (HEAD 683463b5), received 2026-10-02 (condensed-verbatim of the key rows)

Verdict: CORRECT THE SPEC FIRST.

Rows: 10 CONFIRMED, 1 REFUTED, 3 UNVERIFIABLE (8, 9, 13 — network), 2 ASSUMED (14, 15).
- Row 7 REFUTED: claude-tag's status is `200|text/html; charset=utf-8` (`fetch.tsv:64`).
- Row 14 resolves to `manifest.load(path) -> Manifest` (`manifest.py:166`), with fields `.commit` and `.clone_dir` (`:86-88`). It raises `ValueError` at `:169-211`.
- Row 10 closure: stdlib + structlog only. `events` lazily imports `sinks`, which is also stdlib + structlog. `result.py` needs py ≥ 3.12.

MISSING, load-bearing:

1. `tests/test_ccdocs_mirror.py:201-213` patches `cm.staleness` and expects `currency_run.check` to print it. Re-exporting breaks this wiring test. The lambda takes one positional argument.
2. `tests/test_vendored_claude_code_docs.py:88` requires every status to start with `200|`. A `<native>|webclaw` status breaks both that test and the format.
3. `test_vendored_claude_code_docs.py:77-80` allowlists only `fetch.tsv` and `fetch.stamp.json`, so `fetch.misses.json` fails it.
4. The autouse fake page-fetcher must return `None`, or the tests at `:74-87` (307) and `:90-97` (200 html) change meaning.
5. Injection must be patchable at call time, so no definition-time default binding. Patch the engine module, and keep the `fetcher=` keyword on `cm.main`.
6. `docs/research/arms/2026-10-02-ccdocs-mirror.toml` anchors 15 arms on `ccdocs_mirror.py` text, plus W1 on `run.py:135`. Both go stale.
7. webclaw finds 219 pages against the mirror's 231. The unlisted plugin pages return 200, so they won't retire.
