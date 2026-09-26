# Spec — isolate mise state in tests and the redaction control arm (knowledge-base half of dotfiles#1169/#1248)

Ratified by Ray 2026-09-26 (AskUserQuestion, dotfiles session `dotfiles-20260926.000`): implement the
`MISE_STATE_DIR` isolation in both repos, knowledge-base first. Design source: the codex SDLC team review
`ray-manaloto/dotfiles` `docs/research/kb/reports/agents/sdlc-team-mise-warn-2026-09-26.md` §Q3/§Q5 (live-armed).

## 1. Objective

A test (or eval control arm) that runs the real `mise` against a throwaway `mise.toml` must not register that file in
the HOST's `~/.local/state/mise/tracked-configs`. Today `tests/test_evals.py:570-585` writes
`[settings] not_a_real_setting = true` and every later host `mise` command can print
`mise WARN unknown field in …/pytest-NNN/…/mise.toml: settings.not_a_real_setting` until pytest deletes the dir; the
host registry held 1,466 links (1,259 dangling) on 2026-09-26. Fix the cause (registration), not the symptom.

## 2. Files

- `tests/conftest.py` — add an autouse, function-scoped fixture `isolated_mise_state(tmp_path, monkeypatch) -> Path`
  that creates `tmp_path / "mise-state"` and sets `MISE_STATE_DIR` to it with `monkeypatch.setenv` (assignment, not
  setdefault — an inherited host value must be overridden).
- `python/src/kb_setup/eval_cases.py` — `_redaction_collision_control` (`:715`) runs `mise env --redacted` against a
  throwaway config in PRODUCTION eval runs too, not only under pytest; its child must get
  `MISE_STATE_DIR=<its own temp dir>/mise-state`. If `evals.run_command_split` (`evals.py:202`) has no env parameter,
  add an optional keyword-only `env: Mapping[str, str] | None = None` passed to the subprocess (None = inherit, today's
  behaviour).
- `tests/test_mise_state_isolation.py` — the regression module (§5).

Nothing else. Do not redirect `HOME`, `MISE_CONFIG_DIR`, `MISE_DATA_DIR` or `MISE_CACHE_DIR` (installs and the host's
trust setting must stay shared).

## 3. Interfaces

- `isolated_mise_state` fixture: autouse, returns the `Path` of the per-test state dir.
- `run_command_split(argv, *, cwd=None, timeout=DEFAULT_TIMEOUT, env=None) -> tuple[int, str, str]` (only if the env
  parameter is missing today).

## 4. Constraints and invariants

- Isolation must not suppress the warning the probe test relies on: `test_the_probe_survives_a_stderr_warning_from_the_real_command`
  still sees mise's stderr WARN and still passes.
- State isolation also isolates trust records. If a test relied on ambient trust, give it explicit, narrowly scoped
  trust (`MISE_TRUSTED_CONFIG_PATHS=<its tmp dir>`) — never a broad trust and never a warning suppression.
- No inline suppressions; ruff + ty clean; exact behaviour, not log-string sniffing.
- The regression's oracle is an EXACT name→target mapping in a fake "host" state dir, never the real host count.

## 5. Verification

Regression test (in `tests/test_mise_state_isolation.py`), per the codex design:

1. Seed a disposable outer "host" state dir; snapshot its entry-name → target mapping.
2. Run a CHILD pytest (current interpreter, `-p no:cacheprovider`) against a scratch test file that loads this repo's
   `tests/conftest.py` and runs the real `mise ls --json` in its `tmp_path` containing a `mise.toml`. The child gets
   the outer dir as `MISE_STATE_DIR` plus a disposable `XDG_STATE_HOME`.
3. Assert: child rc 0; the outer mapping is UNCHANGED; the child's own `tmp_path/mise-state/tracked-configs` gained the
   config link.
4. FAIL arm, stated in a comment and actually executed by the architect: remove the fixture's `setenv` → the outer
   mapping gains the link and the test goes red.
The scratch test must not request the fixture by name (a missing fixture would error before mise ran, proving
nothing). Skip only when `mise` is not on PATH.

Plus, for the eval control: a test that `_redaction_collision_control` passes a `MISE_STATE_DIR` inside its temp dir
to the child (fake runner seam or the new `env` parameter).

Commands (report each real exit code):

```
mise run kb-check -- tests/conftest.py tests/test_mise_state_isolation.py python/src/kb_setup/eval_cases.py python/src/kb_setup/evals.py
mise run test
```

## 6. Commit

`caller` — leave changes uncommitted on branch `fix/mise-state-isolation`.

## 7. PREMISES

| # | Kind | Claim | Source |
|---|---|---|---|
| 1 | L | The leaking test writes `not_a_real_setting` into `tmp_path/mise.toml` and runs real mise | `tests/test_evals.py:570-585` |
| 2 | L | The probe runs `mise env --redacted --json` via `run_command_split(argv, cwd=, timeout=)` | `python/src/kb_setup/evals.py:293-295`, `:202-207` |
| 3 | L | `_redaction_collision_control` writes a throwaway `mise.toml` and runs real mise in production evals | `python/src/kb_setup/eval_cases.py:715-725` |
| 4 | L | `tests/conftest.py` has no autouse or mise-state fixture | `grep` of `tests/conftest.py` this session |
| 5 | E | `MISE_STATE_DIR` redirects registration: link lands in the explicit dir, host count 1466→1466 | dotfiles `docs/research/kb/reports/agents/sdlc-team-mise-warn-2026-09-26.md` Q3 live arm |
| 6 | P | mise's own e2e harness isolates `MISE_STATE_DIR` per test | same report §Q2/§Q3; jdx/mise `e2e/run_test` |
| 7 | A | No other KB test writes a mise config AND runs real mise (the codex inventory found two KB sites) | same report §Q3 table — re-grep to confirm |
