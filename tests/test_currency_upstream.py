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
# One PyPI document serves both the latest version and the release list — the
# shape `_pypi_json` returns, so `probe` is exercised through the real readers
# rather than through two separately-stubbed helpers that could drift apart.
_PYPI_PAYLOAD: dict[str, object] = {
    "info": {"version": "0.9.28"},
    "releases": {version: [] for version in _ALL},
}


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
    monkeypatch.setattr(upstream, "_pypi_json", lambda _p: (_PYPI_PAYLOAD, ""))
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
    monkeypatch.setattr(upstream, "_pypi_json", lambda _p: (_PYPI_PAYLOAD, ""))

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


# ------------------------------------------------ one payload, one fetch ----


def test_probe_fetches_the_pypi_document_exactly_once(monkeypatch) -> None:
    """`latest` and the release list live in ONE document, so fetch it once.

    Two call sites each doing `GET /pypi/<pkg>/json` meant two identical
    round-trips per run for one payload — and, worse, two chances for the two
    readings to disagree mid-run.
    """
    calls: list[str] = []

    def _json(package: str) -> tuple[dict[str, object], str]:
        calls.append(package)
        return _PYPI_PAYLOAD, ""

    monkeypatch.setattr(upstream, "_pypi_json", _json)
    monkeypatch.setattr(upstream, "release_for_tag", lambda _r, v: (f"v{v}", f"notes for {v}", ""))
    upstream.probe(pypi="graphifyy", github="o/r", current="0.9.25")
    assert calls == ["graphifyy"]


# ---------------------------------------------- three upstream sources ----


def test_a_tool_with_no_upstream_is_untracked_not_unreachable() -> None:
    """Ffmpeg is presence-tracked: neither pypi nor github, so nothing to chase.

    The OLD two-state model returned reachable=False here, which `decide` then
    read as an ambiguity — a permanent, unanswerable "upstream could not be
    checked" on every run of a tool that was never version-tracked.
    """
    status = upstream.probe(pypi="", github="", current="8.1.2")
    assert status.source == "none"
    assert not status.tracked
    # NOT reachable=False: an untracked tool has no upstream to be unreachable.
    assert status.reachable
    assert status.error == ""


def test_github_is_the_version_source_when_there_is_no_pypi(monkeypatch) -> None:
    """mise/hk ship on GitHub, not PyPI — the case that makes the config claim true."""

    def _releases(_path: str) -> tuple[list[object], str]:
        return [
            {"tag_name": "v2026.7.10", "draft": False, "prerelease": False},
            {"tag_name": "v2026.7.12", "draft": False, "prerelease": False},
            {"tag_name": "v2026.8.0-rc1", "draft": False, "prerelease": True},
        ], ""

    monkeypatch.setattr(upstream, "_gh_api_list", _releases)
    monkeypatch.setattr(upstream, "release_for_tag", lambda _r, v: (v, f"notes for {v}", ""))
    status = upstream.probe(pypi="", github="jdx/mise", current="2026.7.10")
    assert status.source == "github"
    assert status.tracked
    # The prerelease is excluded, so the newest STABLE wins — never the rc.
    assert status.latest == "v2026.7.12"


def test_github_latest_is_by_version_not_publish_time(monkeypatch) -> None:
    """A backport patch published last must not become 'latest'.

    `/releases/latest` orders by publish time and would pick the backport; this
    orders by version, so the genuinely newest line wins.
    """

    def _releases(_path: str) -> tuple[list[object], str]:
        # 1.9.1 (a backport) is listed FIRST, as if most-recently published.
        return [
            {"tag_name": "1.9.1", "draft": False, "prerelease": False},
            {"tag_name": "2.0.0", "draft": False, "prerelease": False},
        ], ""

    monkeypatch.setattr(upstream, "_gh_api_list", _releases)
    latest, _all, err = upstream.github_versions("o/r")
    assert err == ""
    assert latest == "2.0.0"


def test_github_source_with_no_stable_releases_fails_closed(monkeypatch) -> None:
    """Only prereleases → no installable version, reported as an error not a pick."""
    monkeypatch.setattr(
        upstream,
        "_gh_api_list",
        lambda _p: ([{"tag_name": "v1.0.0-rc1", "draft": False, "prerelease": True}], ""),
    )
    latest, versions, err = upstream.github_versions("o/r")
    assert latest == ""
    assert versions == ()
    assert err


def test_pypi_wins_when_both_sources_are_declared(monkeypatch) -> None:
    """Mise installs from PyPI, so a GitHub-only version can never be pinned."""
    monkeypatch.setattr(upstream, "_pypi_json", lambda _p: (_PYPI_PAYLOAD, ""))
    called = {"github": False}

    def _never(_p: str) -> tuple[list[object], str]:
        called["github"] = True
        return [], ""

    monkeypatch.setattr(upstream, "_gh_api_list", _never)
    status = upstream.probe(pypi="graphifyy", github="o/r", current="0.9.28")
    assert status.source == "pypi"
    assert not called["github"]  # github must not even be consulted for the version


# ------------------------------------------------ feature highlights ----


def test_feature_lines_are_surfaced_for_review() -> None:
    """A new capability should reach the human even when no breaking marker fired.

    Step 3's other half — the "should we adopt this?" signal.
    """
    notes = (
        "## v0.9.26\n\n"
        "- feat: add a `--backend openai` flag for self-hosted models\n"
        "- fix: cold-cache crash\n"
        "- You can now ingest sitemap.xml directly\n"
    )
    highlights = upstream.UpstreamStatus(notes=notes).feature_highlights
    assert any("backend openai" in h for h in highlights)
    assert any("sitemap.xml" in h for h in highlights)
    # A plain fix is not a feature.
    assert not any("cold-cache" in h for h in highlights)


def test_routine_notes_surface_no_features() -> None:
    """Control arm: the extractor must not flag every line as a feature."""
    notes = "## v0.9.26\n\n- fix: a typo\n- chore: bump deps\n- docs: clarify README\n"
    assert upstream.UpstreamStatus(notes=notes).feature_highlights == ()


def test_feature_highlights_are_capped() -> None:
    """A giant changelog must not flood the interview."""
    notes = "\n".join(f"- feat: feature number {i}" for i in range(50))
    assert len(upstream.UpstreamStatus(notes=notes).feature_highlights) <= 12
