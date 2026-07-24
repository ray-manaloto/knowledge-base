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


def test_null_tag_name_falls_back_to_the_candidate(monkeypatch) -> None:
    _fake_gh(monkeypatch, {"tag_name": None, "body": "notes"})
    assert upstream.release_for_tag("x/y", "0.9.26")[0] == "0.9.26"


def test_unreachable_upstream_reports_error_not_a_verdict(monkeypatch) -> None:
    monkeypatch.setattr(upstream, "_gh_api", lambda _p: ({}, "gh api failed"))
    tag, body, err = upstream.release_for_tag("x/y", "0.9.26")
    assert (tag, body) == ("", "")
    assert err


def test_markers_are_case_insensitive() -> None:
    status = upstream.UpstreamStatus(notes="This is a BREAKING CHANGE.")
    assert "breaking change" in status.markers
    # Control arm: routine notes yield no markers.
    assert upstream.UpstreamStatus(notes="Routine fixes.").markers == ()
