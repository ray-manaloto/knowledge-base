# Copyright (c) 2026 Raymond Manaloto
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
    # The REST of `.agent/` stays scanned — the telemetry exclusion is narrowed
    # to one subdirectory, and this is the arm that keeps it narrow. Agent
    # reports and review receipts routinely quote probe output.
    ".agent/kb/reports/agents/a-report.md",
    ".agent/notepad.md",
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
    # The Firecrawl scrape cache: untrusted third-party page text, gitignored
    # since #502, so it can never be committed. One page produced 24
    # `aws-access-token` findings and turned `mise run lint` red on 2026-08-25.
    ".firecrawl/search-observability-services-scraped.json",
    ".self-graph/graphify-out/cache/stat-index.json",
    ".self-graph/graphify-out/graph.json",
    # The raw-API-body telemetry sink: a verbatim copy of the conversation, so a
    # finding there is about what was said rather than about this repository, and
    # `gitleaks dir` walks directories so it landed in scope the moment it
    # existed (86 findings, ~500 MB scanned). Gitignored and pinned as such.
    ".agent/telemetry/ff431a36-b0bf-4af8-9f00-12cac7a6abe2.request.json",
    # `kb-graphify-native-extract`'s own output tree: same content-hash noise
    # shape as `.self-graph/`, confirmed on the real 2026-08-23 run.
    ".agent/kb/native-extract/graphify-out/cache/stat-index.json",
    ".agent/kb/native-extract/graphify-out/graph.json",
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


#: Constructs Python's `re` accepts and Go's RE2 — which gitleaks uses — does not.
#: Lookaround and backreferences are the whole list; RE2 rejects them by design
#: because they are what makes backtracking possible.
#:
#: The backreference entry is a PATTERN, not `\1`-`\3` spelled out. The literal
#: list was itself a bound that hid its own existence: `\4` and up passed a test
#: whose name promises RE2-safety. An enumeration of "the first few" is the same
#: defect class as a `-maxdepth` (`probes-need-a-control-arm.md` rule 3).
#: (Cold lane, round 3.)
_NOT_IN_RE2 = ("(?=", "(?!", "(?<=", "(?<!")
_BACKREFERENCE = re.compile(r"\\[1-9]")


@pytest.mark.parametrize("pattern", _allowlist_paths())
def test_patterns_are_re2_safe(pattern: str) -> None:
    """The config is read by Go RE2; this file checks it with Python `re`.

    That mismatch is a probe defect, not a nitpick: Python compiles `(?!` fine,
    so the exact repair this file exists to prevent — "simplify the enumeration
    back to one negated pattern" — would pass the whole suite and break gitleaks
    at runtime. Measured on gitleaks 8.30.1: `^graphify-out/(?!memory/)` aborts
    with `invalid perl operator: (?!`, and an unparsable pattern is an allowlist
    entry that does not apply, i.e. noise rather than blindness — but a config
    that crashes the scanner is not a working gate either.

    A denylist of the constructs RE2 lacks, not a reimplementation of RE2: the
    engines agree on everything this config actually uses. (Standards lane,
    round 2.)
    """
    assert re.compile(pattern)
    for construct in _NOT_IN_RE2:
        assert construct not in pattern, f"{construct} does not compile in Go RE2"
    assert not _BACKREFERENCE.search(pattern), "Go RE2 rejects every numbered backreference"


def test_the_re2_check_rejects_a_lookahead() -> None:
    """CONTROL ARM — the probe above must be able to fail.

    Without this, `_NOT_IN_RE2` could be an empty tuple and every pattern would
    still "pass".
    """
    bad = "^graphify-out/(?!memory/)"
    assert re.compile(bad), "Python accepts it, which is exactly the problem"
    assert any(construct in bad for construct in _NOT_IN_RE2)
    # And the backreference arm, past where a hand-listed `\\1`-`\\3` stopped.
    assert _BACKREFERENCE.search(r"^(a)graphify-out/\4")


def test_every_exempt_review_path_is_scanned() -> None:
    """Derived from `EXEMPT_PATHS`, so adding one there cannot silently skip this.

    A hand-listed set in `_MUST_SCAN` would go stale the moment someone widened
    the exemption — the failure this whole pairing exists to prevent.
    """
    for entry in review.EXEMPT_PATHS:
        probe = f"{entry}some-file.md" if entry.endswith("/") else entry
        assert not _allowlisted(probe), f"{entry} is exempt from review AND from gitleaks"
