---
type: "query"
date: "2026-08-07T08:12:17.482994+00:00"
question: "Does bumping the python pin in mise.toml change the interpreter the gates actually run on?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does bumping the python pin in mise.toml change the interpreter the gates actually run on?

## Answer

NO, not on its own. Measured 2026-08-07: .venv resolved a uv-DOWNLOADED CPython 3.14.0 while mise.toml pinned 3.14.6 then 3.14.7, so mise run test, mise run lint, ruff, ty and every uv run kb-setup executed on 3.14.0 for two weeks. The bump was found to be inert only because it was VERIFIED rather than assumed. Two things agreed with the wrong answer and are why no gate caught it: pyproject requires-python is a FLOOR of 3.14, and the old pyvenv.cfg recorded version_info = 3.14 with NO patch component. Only resolving the venv symlink -- into a directory literally named cpython-3.14.0-macos-aarch64-none -- exposes the patch, so any check built on pyvenv.cfg would pass forever. FIX: uv venv --python with the mise interpreter path, which also makes pyvenv.cfg record the full 3.14.7. Gates were captured on 3.14.0 BEFORE the swap and re-run after, identical 4 of 4, so the green is a comparison and not an assumption. Filed as issue 227.

## Outcome

- Signal: useful