"""The gitleaks allowlist must not cover `graphify-out/memory/`.

This is a regression gate for a real incident (2026-07-28, #66's own review).
`.gitleaks.toml` allowlisted all of `^graphify-out/` on the stated premise that
none of it is ever committed. `graphify-out/memory/` is the ONE committed
subdirectory of that tree, so the scanner was configured to look away from the
one place in it where a secret of OURS could land — and `kb-remember` then wrote
a work-memory note ABOUT a credential leak with three live tokens pasted in.
hk's gitleaks step went green over them. Three review lanes caught it; no tool
did.

It matters more since `kb_setup.review.EXEMPT_PATHS`: a commit whose whole delta
is `graphify-out/memory/**` can ship on an ancestor's receipt, so no review lane
reads it either. Scanner coverage of that path is a PRECONDITION for the
exemption, which is why this pins the config rather than trusting a comment.

Config-level, not a gitleaks invocation: the regexes are the thing that was
wrong, they are cheap to assert, and a test that shells out to a pinned binary
answers a slower question less directly. The `gitleaks` run itself is
control-armed in `.gitleaks.toml`'s own comment block, with both arms recorded.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from kb_setup import review

_REPO = Path(__file__).parent.parent.absolute()

#: Paths that MUST be scanned — every exempt path, plus the second-brain vault's
#: mirror of the same convention.
_MUST_SCAN = (
    "graphify-out/memory/query_20260728_072907_a_note.md",
    "brain/graphify-out/memory/query_20260101_000000_a_note.md",
    "docs/goals/README.md",
    "python/src/kb_setup/review.py",
)

#: Paths that must STAY allowlisted — derived artifacts whose content-hashes and
#: ingested corpus text read as secret-like noise. Without this arm the test
#: would pass just as well against an empty allowlist, which is not the config
#: anyone wants.
_MUST_SKIP = (
    "graphify-out/graph.json",
    "graphify-out/GRAPH_REPORT.md",
    "graphify-out/wiki/index.md",
    "graphify-out/cache/x.json",
    "graphify-out/2026-07-22/graph.json",
    "brain/graphify-out/graph.json",
    "sources/some-repo/README.md",
    "raw/fetched.md",
)


def _allowlist_paths() -> list[str]:
    data = tomllib.loads((_REPO / ".gitleaks.toml").read_text(encoding="utf-8"))
    return list(data["allowlist"]["paths"])


def _allowlisted(path: str) -> bool:
    return any(re.search(pattern, path) for pattern in _allowlist_paths())


@pytest.mark.parametrize("path", _MUST_SCAN)
def test_scanned_paths_are_not_allowlisted(path: str) -> None:
    """A path a secret of ours could reach must be visible to the scanner."""
    assert not _allowlisted(path)


@pytest.mark.parametrize("path", _MUST_SKIP)
def test_derived_and_ingested_paths_stay_allowlisted(path: str) -> None:
    """CONTROL ARM — the allowlist must still suppress the noise it exists for."""
    assert _allowlisted(path)


def test_the_memory_directory_itself_is_not_allowlisted() -> None:
    """Gitleaks tests DIRECTORIES against this list while walking, not just files.

    The first fix enumerated `^graphify-out/[^/]+$` for top-level derived files
    — which also matches the extensionless directory `graphify-out/memory`, so
    gitleaks skipped the whole tree and the fix changed nothing. Measured, not
    reasoned: the run logged `skipping directory: global allowlist
    path=graphify-out/memory`. Requiring a dot is what separates a derived FILE
    from that directory.
    """
    assert not _allowlisted("graphify-out/memory")
    assert not _allowlisted("brain/graphify-out/memory")


def test_every_exempt_review_path_is_scanned() -> None:
    """Derived from `EXEMPT_PATHS`, so adding one there cannot silently skip this.

    A hand-listed set in `_MUST_SCAN` would go stale the moment someone widened
    the exemption — the failure this whole pairing exists to prevent.
    """
    for entry in review.EXEMPT_PATHS:
        probe = f"{entry}some-file.md" if entry.endswith("/") else entry
        assert not _allowlisted(probe), f"{entry} is exempt from review AND from gitleaks"
