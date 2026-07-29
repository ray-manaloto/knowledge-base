"""A path excluded to protect it from FORMATTERS must stay visible to SCANNERS.

Three paths in this repo are kept byte-for-byte verbatim — `graphify-out/memory/**`
(generated work-memory), `docs/research/**` (promoted agent reports), and
`docs/goals/*-goal.md` (the `/goal` payload, whose bytes ARE the artifact). Each
was excluded from hk's rewriting builtins for that reason, and each was written
into the GLOBAL `exclude`, which also governs `gitleaks`, `detect_private_key`,
and `check_added_large_files`.

That has now been the same defect three times:

* `graphify-out/memory/**` — fixed 2026-07-28 (#66's round) after a `kb-remember`
  note landed carrying three live credentials and every gate went green;
* `docs/research/**` and `docs/goals/*-goal.md` — fixed in #67's round, having
  survived the round that fixed the first one.

A comment saying "do not tidy these onto proseExclude" did not prevent the second
occurrence, so this asserts it instead — against the EVALUATED config (`pkl
eval`), not the file's text. Text would pass on a config that no longer parses
the way it reads, and the whole class of bug here is a list that says one thing
and is spread somewhere else.

It is the hk-side twin of `test_gitleaks_scope.py`, which pins the other half:
`.gitleaks.toml`'s own allowlist. Both halves are needed — fixing either alone
leaves a hole, which is exactly what happened the first time.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).parent.parent.absolute()
_PKL_TIMEOUT = 180

#: Excluded to protect the bytes from a REWRITER, and therefore never allowed
#: into the global `exclude` that the scanners also read.
_VERBATIM_PATHS = (
    "graphify-out/memory/**",
    "docs/research/**",
    "docs/goals/*-goal.md",
)

#: Steps that rewrite or opine on prose. These SHOULD carry the verbatim paths.
_FORMATTERS = ("rumdl", "rumdl_format", "typos", "trailing_whitespace", "newlines")

#: Steps that look for secrets and dangerous content. These must see everything.
#: `gitleaks` is listed despite `gitleaks dir` ignoring its path arguments when
#: given more than one — that bug is what left the first occurrence looking
#: covered, and a gate must not depend on it (see `hk.pkl`).
_SCANNERS = ("gitleaks", "detect_private_key", "check_added_large_files")


def _pkl(expression: str) -> str:
    """Evaluate ``expression`` against `hk.pkl` and return stdout.

    `pkl` is pinned in `mise.toml`, so a missing binary is DRIFT rather than a
    reason to skip — no `pytest.skip` here, deliberately.
    """
    proc = subprocess.run(
        ["pkl", "eval", "-x", expression, "hk.pkl"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=False,
        timeout=_PKL_TIMEOUT,
    )
    assert proc.returncode == 0, f"pkl eval failed for {expression!r}: {proc.stderr[:400]}"
    return proc.stdout.strip()


def _entries(raw: str) -> list[str]:
    """Parse pkl's ``List("a", "b")`` rendering into a python list."""
    inner = raw.removeprefix("List(").removesuffix(")").strip()
    return json.loads(f"[{inner}]") if inner else []


@pytest.fixture(scope="module")
def global_exclude() -> list[str]:
    """The config-level `exclude` — what a step with no `exclude` of its own gets."""
    return _entries(_pkl("exclude"))


@pytest.mark.parametrize("path", _VERBATIM_PATHS)
def test_verbatim_paths_are_not_in_the_global_exclude(path: str, global_exclude: list[str]) -> None:
    """THE REGRESSION GATE. The global list is the one the scanners read."""
    assert path not in global_exclude, (
        f"{path} is excluded from EVERY builtin, scanners included — "
        f"move it to `proseExclude` in hk.pkl"
    )


def test_the_global_exclude_still_excludes_what_it_should(global_exclude: list[str]) -> None:
    """CONTROL ARM — without it the test above passes against an empty list.

    `sources/**` and `raw/**` are ingested external content whose secret-like
    strings are noise by construction; the derived graphify artifacts are
    machine-written. Those belong in the global list and must stay there.
    """
    for path in ("sources/**", "raw/**", "graphify-out/graph.json"):
        assert path in global_exclude


@pytest.mark.parametrize("hook", ["check", "pre-commit"])
@pytest.mark.parametrize("step", _FORMATTERS)
def test_formatters_do_exclude_the_verbatim_paths(hook: str, step: str) -> None:
    """The other direction: the protection must actually be in place somewhere.

    Both hooks, because `hk.pkl` spreads one `lintSteps` mapping into `check`,
    `fix`, and `pre-commit` — and `ci-local-parity.md` rule 5 exists because a
    step present in one and not the others lets a commit pass a hook that
    `mise run lint` fails.
    """
    exclude = _entries(_pkl(f'hooks["{hook}"].steps["{step}"].exclude'))
    for path in _VERBATIM_PATHS:
        assert path in exclude, f"{step} would rewrite {path}"


@pytest.mark.parametrize("hook", ["check", "pre-commit"])
@pytest.mark.parametrize("step", _SCANNERS)
def test_scanners_do_not_exclude_the_verbatim_paths(hook: str, step: str) -> None:
    """A scanner must not carry the formatters' exclude, by any route.

    Checked on the step's OWN exclude as well as the global one, because a
    per-step `exclude` REPLACES the global rather than extending it
    (hk `Config.pkl:99`) — so "tidying" `proseExclude` onto a scanner would
    silence it here without touching the global list this file's headline test
    reads.
    """
    exclude = _entries(_pkl(f'hooks["{hook}"].steps["{step}"].exclude'))
    for path in _VERBATIM_PATHS:
        assert path not in exclude, f"{step} was given the formatters' exclude for {path}"
