# Copyright (c) 2026 Raymond Manaloto
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


def test_the_merging_chunk_wins_regardless_of_its_capture_date(tmp_path: Path) -> None:
    """`kb-merge` ownership is NOT replay ownership, and conflating them was a P1.

    `build_merge` prunes on the INCOMING chunk's claims unconditionally
    (`build.py:1531-1537`), so a lone merge is won by whatever is being merged,
    whatever its capture date. Ranking by replay order there reported the exact
    destructive case as clean: re-merging an OLDER committed chunk over a newer
    sibling that legitimately declared the shared file.

    Both halves are asserted, because only the pair shows the parameter is doing
    work rather than being accepted and ignored.
    """
    old = _chunk(tmp_path, "old-docs", {"page.md": "2026-08-01"})
    new = _chunk(tmp_path, "new-docs", {"page.md": "2026-08-09"}, supersedes=["page.md"])

    # Replaying both: the newer chunk wins and has declared. Clean.
    assert chunks.collision_issues([old, new]) == []

    # Merging the OLDER one alone: it wins, it declared nothing, and it is about
    # to delete the newer chunk's nodes for that file.
    issues = chunks.collision_issues([old, new], merging=old)
    # TWO problems, and both are true of this merge: it is undeclared, and the
    # winner is also the staler capture. The inversion arm reaching the merge
    # door was not designed in — it falls out of `how` being one word, which is
    # the right kind of falling out.
    assert len(issues) == 2, issues
    assert "undeclared supersession" in issues[0]
    assert "this merge makes old-docs.json own it" in issues[0]
    assert "date inversion" in issues[1]
    assert "by this merge" in issues[1]

    # Merging the newer one is still fine — it declared.
    assert chunks.collision_issues([old, new], merging=new) == []


def test_merging_a_chunk_that_does_not_claim_the_file_falls_back_to_replay(
    tmp_path: Path,
) -> None:
    """`merging` only decides files the incoming chunk actually claims.

    A third chunk being merged says nothing about who owns a file it never
    names, so those keep replay-order semantics. Without this the parameter
    would silently re-attribute every collision in the corpus to whatever
    happened to be merging.
    """
    a = _chunk(tmp_path, "a-docs", {"shared.md": "2026-08-01"})
    b = _chunk(tmp_path, "b-docs", {"shared.md": "2026-08-02"})
    c = _chunk(tmp_path, "c-docs", {"unrelated.md": "2026-08-03"})

    issues = chunks.collision_issues([a, b, c], merging=c)

    assert len(issues) == 1, issues
    assert "replay makes b-docs.json own it" in issues[0]


def test_assemble_carries_every_input_declaration_into_the_output(tmp_path: Path) -> None:
    """A declaration dropped at assembly disarms the gate it was written for.

    `assemble` validated `supersedes` on every input and then wrote a dict with
    no such key, so a chunk built by `kb-assemble` arrived at the collision gate
    having silently lost the one thing that lets it pass. Union across inputs,
    sorted, and absent entirely when nothing declared — an empty list would be a
    claim rather than a default.
    """
    a = _chunk(tmp_path, "a", {"x.md": "2026-08-01"}, supersedes=["x.md"])
    b = _chunk(tmp_path, "b", {"y.md": "2026-08-01"}, supersedes=["y.md", "x.md"])
    plain = _chunk(tmp_path, "p", {"z.md": "2026-08-01"})

    out = chunks.assemble(tmp_path, "combined", [a, b])
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["supersedes"] == ["x.md", "y.md"]

    bare = json.loads(chunks.assemble(tmp_path, "bare", [plain]).read_text(encoding="utf-8"))
    assert "supersedes" not in bare


@pytest.mark.parametrize(
    ("raw", "expect"),
    [
        ("docs/x.md", "docs/x.md"),
        ("docs\\x.md", "docs/x.md"),
        ("./docs/x.md", "docs/x.md"),
        ("././docs/x.md", "docs/x.md"),
        ("", None),
        (None, None),
        (12, None),
    ],
)
def test_source_file_is_normalised_the_way_the_merge_compares_it(
    raw: object, expect: str | None
) -> None:
    r"""`build_merge` matches `_norm_source_file`'s output, not the raw string.

    Comparing raw strings asked a different question from the one the merge
    answers: `docs\\x.md` and `docs/x.md` read as two identities to the gate and
    as ONE to graphify, so a real supersession was judged disjoint and then
    silently pruned. (Cold lane, round 2, P1.)
    """
    assert chunks.normalise_source_file(raw) == expect


def test_two_spellings_of_one_identity_now_collide(tmp_path: Path) -> None:
    """The defect, end to end — and the control that the pair is not just equal.

    Without normalisation this pair passed the gate while graphify treated them
    as one file. `unrelated/x.md` is the control: it must NOT collide, so the
    refusal is coming from the identity rather than from the fixture shape.
    """
    a = _chunk(tmp_path, "a-docs", {"docs\\x.md": "2026-08-01"})
    b = _chunk(tmp_path, "b-docs", {"./docs/x.md": "2026-08-02"})
    c = _chunk(tmp_path, "c-docs", {"unrelated/x.md": "2026-08-03"})

    assert len(chunks.collision_issues([a, b])) == 1
    assert chunks.collision_issues([a, c]) == []


def test_an_absolute_source_file_is_refused_per_chunk() -> None:
    """What normalisation CANNOT reconcile is refused instead of approximated.

    Relativising an absolute path needs the root graphify will be given, which
    `chunk_claims` does not have and must not guess. So the contract is narrowed
    at the door: emit the clone-relative form. Measured across all 3,733 committed
    identities — zero are absolute, so this rejects nothing that exists.
    """

    def _mk(sf: str) -> dict:
        return {"nodes": [_node("n", sf)], "edges": []}

    assert [i for i in chunks.validate(_mk("/abs/docs/x.md")) if "ABSOLUTE" in i]
    assert [i for i in chunks.validate(_mk("C:/docs/x.md")) if "ABSOLUTE" in i]
    # CONTROL: the ordinary relative form is untouched.
    assert not [i for i in chunks.validate(_mk("docs/x.md")) if "ABSOLUTE" in i]
