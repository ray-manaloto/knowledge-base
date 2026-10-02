# Copyright (c) 2026 Raymond Manaloto
"""The vendored Claude Code docs mirror must be TRACKED and COMPLETE (#829).

Regression gate for the defect #829's first ruling would have shipped: it named
`sources/claude-code-docs/` as the destination, and that path is a gitignored
build-time clone (`.gitignore` `sources/*/`; `graph.py:_ensure_clone` rmtree's a
clone dir without `.git` and re-clones it). Pages written there reach no commit
and are erased by the next `kb-build`. The mirror therefore lives under
`sources/media/claude-code-docs/`, which IS tracked — and these tests keep it
there, and keep it whole.

`fetch.tsv` is the provenance record: one row per page, `url<TAB>status|type<TAB>
method<TAB>bytes`. Every row must have its page and every page its row, so a
partial copy or a hand-dropped page fails here rather than in a citation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).parent.parent.absolute()
_MIRROR = Path("sources/media/claude-code-docs")
_PREFIX = "https://code.claude.com/docs/en/"
_METHODS = frozenset({"md", "webclaw"})


def _rows() -> list[list[str]]:
    text = (_REPO / _MIRROR / "fetch.tsv").read_text(encoding="utf-8")
    return [line.split("\t") for line in text.splitlines() if line.strip()]


def _page_name(url: str) -> str:
    """Map a docs URL to its flat filename: `a/b` -> `a__b.md` (the `$CC` scheme)."""
    assert url.startswith(_PREFIX), url
    return url.removeprefix(_PREFIX).replace("/", "__") + ".md"


def _ignored(rel: str) -> bool:
    """True when git would ignore `rel` (`git check-ignore` rc 0 = ignored, 1 = not)."""
    result = subprocess.run(
        ["git", "-C", str(_REPO), "check-ignore", "-q", "--no-index", rel],
        check=False,
        capture_output=True,
    )
    assert result.returncode in {0, 1}, result.stderr
    return result.returncode == 0


def test_mirror_path_is_not_gitignored() -> None:
    assert not _ignored(f"{_MIRROR}/costs.md")


def test_ignore_probe_discriminates() -> None:
    # Control arm: the path #829 first named IS ignored, so the probe above can fail.
    assert _ignored("sources/claude-code-docs/costs.md")


def test_every_row_has_its_page_and_every_page_its_row() -> None:
    expected = {_page_name(row[0]) for row in _rows()}
    present = {p.name for p in (_REPO / _MIRROR).glob("*.md")}
    assert expected - present == set(), "rows with no page"
    assert present - expected == set(), "pages with no row"


def test_rows_are_unique_successful_fetches() -> None:
    rows = _rows()
    urls = [row[0] for row in rows]
    assert len(urls) == len(set(urls))
    for url, status, method, size in rows:
        assert status.startswith("200|"), url
        assert method in _METHODS, url
        assert int(size) == (_REPO / _MIRROR / _page_name(url)).stat().st_size, url


@pytest.mark.parametrize(
    "page",
    # The six plugin pages the site still serves but no inventory lists — the
    # ones `$CC` citations name. Dropping them breaks live citations silently.
    [
        "discover-plugins.md",
        "plugin-dependencies.md",
        "plugin-hints.md",
        "plugin-marketplaces.md",
        "plugin-relevance.md",
        "plugins-reference.md",
    ],
)
def test_orphan_plugin_pages_are_kept(page: str) -> None:
    assert (_REPO / _MIRROR / page).is_file()
