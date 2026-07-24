"""kb_setup.currency.upstream — parsing the two upstreams, and their null shapes.

The JSON-null class is the whole point of this file. `payload.get(k, default)`
silently fails whenever an API sends the key PRESENT with a null value, because
the default never fires and `str(None)` produces the 4-character string "None".
For release notes that string is non-empty and marker-free, so it defeated the
empty-notes gate entirely — the most likely way a release has no notes was the
one way the guard could not see.
"""

import json

from kb_setup.currency import upstream


def _fake_gh(monkeypatch, payload: dict) -> None:
    monkeypatch.setattr(upstream, "_gh_api", lambda _path: (json.loads(json.dumps(payload)), ""))


def test_null_body_reads_as_empty_not_the_string_none(monkeypatch) -> None:
    _fake_gh(monkeypatch, {"tag_name": "v0.9.26", "body": None})
    _tag, body, err = upstream.release_for_tag("x/y", "0.9.26")
    assert body == ""
    assert err == ""


def test_missing_body_key_also_reads_as_empty(monkeypatch) -> None:
    _fake_gh(monkeypatch, {"tag_name": "v0.9.26"})
    assert upstream.release_for_tag("x/y", "0.9.26")[1] == ""


def test_real_body_survives(monkeypatch) -> None:
    """Control arm: the fix must not blank out genuine notes."""
    _fake_gh(monkeypatch, {"tag_name": "v0.9.26", "body": "Routine fixes."})
    assert upstream.release_for_tag("x/y", "0.9.26")[1] == "Routine fixes."


def test_null_tag_name_is_an_error_not_an_invented_tag(monkeypatch) -> None:
    """Defaulting to the tag we ASKED for fabricates a release nobody confirmed."""
    _fake_gh(monkeypatch, {"tag_name": None, "body": "notes"})
    tag, _body, err = upstream.release_for_tag("x/y", "0.9.26")
    assert tag == ""
    assert err


def test_unreachable_upstream_reports_error_not_a_verdict(monkeypatch) -> None:
    monkeypatch.setattr(upstream, "_gh_api", lambda _p: ({}, "gh api failed"))
    tag, body, err = upstream.release_for_tag("x/y", "0.9.26")
    assert (tag, body) == ("", "")
    assert err


def test_markers_are_case_insensitive() -> None:
    # Assert the BEHAVIOUR (a marker was found), not which phrase matched — the
    # marker wording is an implementation detail that has already changed once.
    assert upstream.UpstreamStatus(notes="This is a BREAKING CHANGE.").markers
    # Control arm: routine notes yield no markers.
    assert upstream.UpstreamStatus(notes="Routine fixes.").markers == ()


# ------------------------------------------------- multi-release coverage ----

_ALL = ("0.9.24", "0.9.25", "0.9.26", "0.9.27", "0.9.28", "0.10.0")


def test_versions_between_is_exclusive_below_and_inclusive_above() -> None:
    assert upstream.versions_between(_ALL, "0.9.25", "0.9.28") == ("0.9.26", "0.9.27", "0.9.28")
    assert upstream.versions_between(_ALL, "0.9.25", "0.9.26") == ("0.9.26",)


def test_versions_between_is_empty_when_already_current() -> None:
    assert upstream.versions_between(_ALL, "0.9.28", "0.9.28") == ()


def test_versions_between_is_empty_on_an_unparsable_bound() -> None:
    """Fail closed: an unreadable bound must not silently select everything."""
    assert upstream.versions_between(_ALL, "bogus", "0.9.28") == ()


def test_probe_collects_notes_for_every_intermediate_release(monkeypatch) -> None:
    """A patch jump adopts EVERY release in between, so every one must be read.

    `0.9.25 -> 0.9.28` is a patch bump and auto-apply-eligible; reading only
    0.9.28's body would wave through a breaking change announced in 0.9.26.
    """
    monkeypatch.setattr(upstream, "latest_pypi", lambda _p: ("0.9.28", ""))
    monkeypatch.setattr(upstream, "pypi_versions", lambda _p: _ALL)
    seen: list[str] = []

    def _release(_repo: str, version: str) -> tuple[str, str, str]:
        seen.append(version)
        return f"v{version}", f"notes for {version}", ""

    monkeypatch.setattr(upstream, "release_for_tag", _release)
    status = upstream.probe(pypi="graphifyy", github="o/r", current="0.9.25")

    assert seen == ["0.9.26", "0.9.27", "0.9.28"]
    for version in ("0.9.26", "0.9.27", "0.9.28"):
        assert f"notes for {version}" in status.notes
    assert status.unread_versions == ()


def test_probe_records_versions_whose_notes_could_not_be_read(monkeypatch) -> None:
    monkeypatch.setattr(upstream, "latest_pypi", lambda _p: ("0.9.28", ""))
    monkeypatch.setattr(upstream, "pypi_versions", lambda _p: _ALL)

    def _release(_repo: str, version: str) -> tuple[str, str, str]:
        if version == "0.9.28":
            return "v0.9.28", "notes", ""
        return "", "", "404"

    monkeypatch.setattr(upstream, "release_for_tag", _release)
    status = upstream.probe(pypi="graphifyy", github="o/r", current="0.9.25")
    assert status.unread_versions == ("0.9.26", "0.9.27")


# ------------------------------------------------------- marker spellings ----


def test_decorated_breaking_markers_are_all_caught() -> None:
    """Release notes decorate these phrases; a raw substring scan missed most."""
    for body in (
        "BREAKING CHANGE: config format changed",
        "### Breaking changes\n\n- config moved",
        "BREAKING-CHANGE: config format changed",
        "**BREAKING**: the config format changed",
        "feat!: drop the v1 config format",
        "refactor(api)!: rename everything",
    ):
        assert upstream.UpstreamStatus(notes=body).markers, body


def test_routine_notes_yield_no_markers() -> None:
    """Control arm: the matcher must not have become unconditional."""
    assert upstream.UpstreamStatus(notes="Routine: faster BFS and a docs typo fix.").markers == ()
    assert upstream.UpstreamStatus(notes="Fixed a crash when the cache is cold.").markers == ()


def test_a_release_payload_without_a_tag_name_is_not_invented(monkeypatch) -> None:
    """`.get("tag_name", candidate)` fabricated a release that was never confirmed.

    `_gh_api` returns ({}, "") for any exit-0 response whose JSON is not an object,
    so defaulting to the tag we ASKED for made `github_tag` truthy and passed
    gate 2 on a release nobody had seen.
    """
    monkeypatch.setattr(upstream, "_gh_api", lambda _p: ({}, ""))
    tag, body, err = upstream.release_for_tag("o/r", "0.9.26")
    assert tag == ""
    assert body == ""
    assert err


def test_a_real_payload_still_yields_its_tag(monkeypatch) -> None:
    """Control arm: the guard must not blank out genuine releases."""
    monkeypatch.setattr(upstream, "_gh_api", lambda _p: ({"tag_name": "v0.9.26", "body": "x"}, ""))
    assert upstream.release_for_tag("o/r", "0.9.26")[0] == "v0.9.26"
