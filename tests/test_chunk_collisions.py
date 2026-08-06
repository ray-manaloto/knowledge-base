"""Cross-chunk `source_file` ownership (#189).

Every arm here is about a defect NO per-chunk check can see: both chunks are
well-formed, both validate, and the loss happens at merge time when
`build_merge` hands the shared file to whichever chunk replays last and deletes
the other's nodes for it. Measured 2026-08-06 (PR #197): 72 nodes of
`mattpocock-skills-docs.json` destroyed by an unrelated chunk, with
`kb-validate-chunks` ✓, the cold review passing it as data, and `kb-build` rc=0.

The suite therefore proves BOTH directions on every rule — a colliding pair is
refused AND the same pair with a declaration is clean — because a detector
verified only on the failing input cannot be distinguished from one that
always fires.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import chunks


def _node(nid: str, source_file: str, captured_at: str = "2026-08-01") -> dict:
    return {
        "id": nid,
        "label": nid,
        "_origin": "semantic",
        "file_type": "concept",
        "source_file": source_file,
        "source_url": "https://example.invalid/x",
        "captured_at": captured_at,
    }


def _chunk(
    tmp_path: Path,
    name: str,
    files: dict[str, str],
    *,
    supersedes: list[str] | None = None,
) -> Path:
    """Write a chunk claiming `{source_file: captured_at}`, one node each."""
    body: dict = {
        "nodes": [_node(f"{name}_{i}", sf, at) for i, (sf, at) in enumerate(files.items())],
        "edges": [],
        "hyperedges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }
    if supersedes is not None:
        body["supersedes"] = supersedes
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(body), encoding="utf-8")
    return p


def test_two_chunks_claiming_one_file_undeclared_is_refused(tmp_path: Path) -> None:
    """The measured defect: a bare `CHANGELOG.md` owned by two unrelated sources."""
    a = _chunk(tmp_path, "a-docs", {"CHANGELOG.md": "2026-08-01"})
    b = _chunk(tmp_path, "b-docs", {"CHANGELOG.md": "2026-08-02"})

    issues = chunks.collision_issues([a, b])

    assert len(issues) == 1
    assert "undeclared supersession" in issues[0]
    assert "CHANGELOG.md" in issues[0]
    # Both chunks are NAMED — a message that says only "a collision exists"
    # leaves the reader to find the pair, which is the archaeology this replaces.
    assert "a-docs.json" in issues[0]
    assert "b-docs.json" in issues[0]


def test_declaring_the_supersession_clears_it(tmp_path: Path) -> None:
    """CONTROL ARM for the arm above: same pair, one line added, clean.

    Without this the refusal could be coming from any property of the fixture.
    It is the replay WINNER that must declare — b sorts last by capture date.
    """
    a = _chunk(tmp_path, "a-docs", {"CHANGELOG.md": "2026-08-01"})
    b = _chunk(tmp_path, "b-docs", {"CHANGELOG.md": "2026-08-02"}, supersedes=["CHANGELOG.md"])

    assert chunks.collision_issues([a, b]) == []


def test_the_loser_declaring_does_not_clear_it(tmp_path: Path) -> None:
    """A declaration by the chunk that does NOT own the file is not a declaration.

    Replay makes the last chunk the owner, so `supersedes` is only meaningful on
    the winner. Accepting the loser's copy would let a chunk silence a warning
    about damage being done TO it.
    """
    a = _chunk(tmp_path, "a-docs", {"CHANGELOG.md": "2026-08-01"}, supersedes=["CHANGELOG.md"])
    b = _chunk(tmp_path, "b-docs", {"CHANGELOG.md": "2026-08-02"})

    issues = chunks.collision_issues([a, b])

    assert len(issues) == 1
    assert "undeclared supersession" in issues[0]


def test_date_inversion_is_reported_even_when_declared(tmp_path: Path) -> None:
    """The staler extraction winning is legal by replay order and almost never meant.

    `replay_order` keys on the chunk's MAX `captured_at`, so a chunk carrying a
    fresh page and a stale one replays last as a whole and its stale copy wins
    per-file. Only a per-file comparison can see it — this is the P1 the #186
    round-2 cold lane raised and the reason `_chunk_claims` is per-file.
    """
    old = _chunk(tmp_path, "old-docs", {"page.md": "2026-08-09"})
    mixed = _chunk(
        tmp_path,
        "new-docs",
        {"page.md": "2026-08-01", "other.md": "2026-08-10"},
        supersedes=["page.md"],
    )

    issues = chunks.collision_issues([old, mixed])

    assert len(issues) == 1, issues
    assert "date inversion" in issues[0]
    assert "2026-08-09" in issues[0]


def test_no_inversion_when_the_winner_is_also_the_newer_capture(tmp_path: Path) -> None:
    """CONTROL ARM: the ordinary refresh shape must be silent."""
    old = _chunk(tmp_path, "old-docs", {"page.md": "2026-08-01"})
    new = _chunk(tmp_path, "new-docs", {"page.md": "2026-08-09"}, supersedes=["page.md"])

    assert chunks.collision_issues([old, new]) == []


def test_disjoint_chunks_never_collide(tmp_path: Path) -> None:
    """The healthy corpus shape — every file claimed once."""
    a = _chunk(tmp_path, "a-docs", {"a/one.md": "2026-08-01", "a/two.md": "2026-08-01"})
    b = _chunk(tmp_path, "b-docs", {"b/one.md": "2026-08-02"})

    assert chunks.collision_issues([a, b]) == []


def test_one_chunk_cannot_collide_with_itself(tmp_path: Path) -> None:
    """A single chunk, and the same chunk passed twice.

    The second half is not academic: `kb-merge` re-merging an already-committed
    chunk passes it alongside the corpus glob that contains it, so without the
    resolve-and-dedup a routine re-merge would refuse itself.
    """
    a = _chunk(tmp_path, "a-docs", {"CHANGELOG.md": "2026-08-01"})

    assert chunks.collision_issues([a]) == []
    assert chunks.collision_issues([a, a]) == []
    assert chunks.collision_issues([a, tmp_path / "a-docs.json"]) == []


def test_one_file_under_two_spellings_is_still_one_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The REAL re-merge shape: a relative path and an absolute one, same file.

    `mise run kb-merge -- sources/extractions/x.json` hands `merge_chunk` a
    RELATIVE path, while `_committed_chunks` globs from `repo_root` and yields an
    absolute one. Both name the same file; only `.resolve()` makes them one key.

    This arm exists because the test above could not exhibit its own harm.
    Deleting the resolve-and-dedup left it green — `claims` is a dict keyed by
    Path, so two IDENTICAL Path objects collapse anyway — while the mutant
    reports 1 issue here and 0 there. Measured both ways before this was written,
    which is what distinguishes a coverage gap from a no-op mutation.
    """
    a = _chunk(tmp_path, "a-docs", {"CHANGELOG.md": "2026-08-01"})
    monkeypatch.chdir(tmp_path)

    assert chunks.collision_issues([Path("a-docs.json"), a]) == []


def test_an_unreadable_chunk_yields_no_claims_rather_than_raising(tmp_path: Path) -> None:
    """`validate_files` is the door that reports a broken chunk with a real message.

    Raising here would report the same defect worse — as a traceback out of a
    detector, blaming the file that happens to be readable.
    """
    good = _chunk(tmp_path, "good-docs", {"x.md": "2026-08-01"})
    broken = tmp_path / "broken-docs.json"
    broken.write_text("{not json", encoding="utf-8")
    absent = tmp_path / "absent-docs.json"

    assert chunks.collision_issues([good, broken, absent]) == []


def test_a_top_level_array_chunk_yields_no_claims(tmp_path: Path) -> None:
    """Valid JSON that is not an object. `_chunk_claims` must not `.get()` a list."""
    good = _chunk(tmp_path, "good-docs", {"x.md": "2026-08-01"})
    arr = tmp_path / "arr-docs.json"
    arr.write_text("[]", encoding="utf-8")

    assert chunks.collision_issues([good, arr]) == []


@pytest.mark.parametrize(
    ("declared", "expect"),
    [
        (None, 0),
        ([], 0),
        (["a.md"], 0),
        ("a.md", 1),
        ({"a.md": True}, 1),
        ([""], 1),
        ([1], 1),
        (["ok.md", None], 1),
    ],
)
def test_supersedes_shape_is_validated_per_chunk(declared: object, expect: int) -> None:
    """A malformed declaration must be caught by whoever can still fix it.

    `collision_issues` reads `supersedes` with an `isinstance` filter, so a
    string value (`"a.md"`, which iterates as characters) or a dict would degrade
    silently into "declares nothing" and reappear as a confusing collision
    refusal one step later.
    """
    chunk: dict = {"nodes": [], "edges": []}
    if declared is not None:
        chunk["supersedes"] = declared

    issues = [i for i in chunks.validate(chunk) if "supersedes" in i]

    assert len(issues) == expect, issues
