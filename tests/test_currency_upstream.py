# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.currency.upstream — parsing the two upstreams, and their null shapes.

The JSON-null class is the whole point of this file. `payload.get(k, default)`
silently fails whenever an API sends the key PRESENT with a null value, because
the default never fires and `str(None)` produces the 4-character string "None".
For release notes that string is non-empty and marker-free, so it defeated the
empty-notes gate entirely — the most likely way a release has no notes was the
one way the guard could not see.
"""

import json

import pytest
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


def test_github_source_accepts_a_declared_project_tag_prefix(monkeypatch) -> None:
    """Codex's ``rust-v`` releases are versions, not an unreadable upstream."""
    monkeypatch.setattr(
        upstream,
        "_gh_api_list",
        lambda _p: ([{"tag_name": "rust-v0.147.0", "draft": False, "prerelease": False}], ""),
    )
    latest, versions, err = upstream.github_versions("openai/codex", tag_prefix="rust-v")
    assert (latest, versions, err) == ("0.147.0", ("0.147.0",), "")


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


# ------------------------------- section-based notes (the real corpora) ----
#
# Every test above this line writes its fixture in the ONE format the detector
# already understood — conventional-commits `feat:` lines and adoption prose. All
# three passed while the detector scored **zero** on every real release this repo
# tracks (control-armed 2026-07-29: mise v2026.7.16 = 0 matches across 10.8KB
# with nine `## Added` bullets, graphify 0.9.27-0.9.30 = 0 across 9.2KB,
# claude-code 2.1.220 = 0). A fixture shaped like the code under test cannot fail,
# so the arms below are written in the formats upstream actually publishes.


def _github_generated_notes() -> str:
    """The shape `gh api /releases` returns and mise publishes: named sections."""
    return (
        "## v2026.7.16\n\n"
        "A release summary paragraph that announces nothing by itself.\n\n"
        "## Highlights\n"
        "- The task output cache gains per-run controls (`--task-cache`)\n\n"
        "## Added\n"
        "- **task:** experimental `task.cache_dir` setting and `MISE_TASK_CACHE_DIR`\n"
        "- **mcp:** new `list_commands` tool exposing each command's effect\n\n"
        "## Fixed\n"
        "- **npm:** reproducing a lockfile no longer requires `allow_low_downloads`\n\n"
        "## New Contributors\n"
        "* @someone made their first contribution\n"
    )


def test_bullets_under_a_feature_section_are_features_without_any_phrase() -> None:
    """The regression that mattered: `## Added` bullets carry no `feat:` and no phrase.

    This is why the detector reported nothing for mise across a 10.8KB changelog.
    """
    status = upstream.UpstreamStatus(notes=_github_generated_notes())
    highlights = status.feature_highlights
    assert any("task.cache_dir" in h for h in highlights)
    assert any("list_commands" in h for h in highlights)
    assert any("per-run controls" in h for h in highlights)
    assert not status.feature_scan_unrecognised


def test_a_fix_is_not_promoted_even_when_it_matches_a_feature_phrase() -> None:
    """`no longer requires` under `## Fixed` is a fix. Section beats phrase."""
    highlights = upstream.UpstreamStatus(notes=_github_generated_notes()).feature_highlights
    assert not any("allow_low_downloads" in h for h in highlights)


def test_contributor_lines_are_not_features() -> None:
    """`New Contributors` must not prefix-match the `new` feature section."""
    highlights = upstream.UpstreamStatus(notes=_github_generated_notes()).feature_highlights
    assert not any("first contribution" in h for h in highlights)


# ------------------------------------- the third state: unparsable notes ----


def test_prose_notes_with_no_recognisable_format_report_could_not_tell() -> None:
    """Graphify's real shape: bold subheads, mixed bullets, no `## Added`.

    The scan must NOT answer this with an empty tuple that reads as "no features".
    """
    notes = (
        "## v0.9.27\n\n"
        "A large maintenance release.\n\n"
        "**Install and data safety**\n\n"
        "- `claude install` no longer overwrites a settings file it cannot parse\n"
    )
    status = upstream.UpstreamStatus(notes=notes)
    assert status.feature_highlights == ()
    assert status.feature_scan_unrecognised


def test_a_recognised_fixes_only_release_is_a_confident_zero() -> None:
    """Control arm for the state above — the two must not collapse into one.

    A named `## Fixed` section means the format WAS understood, so "no features"
    is an answer rather than a shrug.
    """
    status = upstream.UpstreamStatus(notes="## v1.0.1\n\n## Fixed\n\n- a typo\n")
    assert status.feature_highlights == ()
    assert not status.feature_scan_unrecognised


def test_empty_notes_are_not_reported_as_unreadable() -> None:
    """No notes is not a parse failure — ffmpeg has no release channel at all."""
    assert not upstream.UpstreamStatus(notes="").feature_scan_unrecognised
    assert not upstream.UpstreamStatus(notes="   \n").feature_scan_unrecognised


def test_the_display_cap_reports_what_it_dropped() -> None:
    """A silent truncation reads as 'that was all of them'."""
    notes = "## Added\n" + "\n".join(f"- feature number {i}" for i in range(20))
    status = upstream.UpstreamStatus(notes=notes)
    assert len(status.feature_highlights) == 12
    assert status.features_dropped == 8


def test_no_cap_no_dropped_count() -> None:
    """Control arm: the counter must stay 0 when nothing was cut."""
    status = upstream.UpstreamStatus(notes="## Added\n- one thing\n")
    assert status.features_dropped == 0


# --------- the format check is PER RELEASE, not per body (cold-lane finding) ----
#
# `probe()` concatenates the notes of every release in a multi-patch jump, so a
# single flag over the whole string let one release's `## Added` certify the span.


def test_one_unreadable_release_in_a_span_is_reported_even_when_another_is_read() -> None:
    """The masking case: v1.0.1 is sectioned, v1.0.2 is bold-subhead prose.

    The features from the readable release are still surfaced, AND the span is
    flagged unreadable — because the list is now known to be incomplete. Two
    conditions had to change for this: the per-release flag, and dropping
    `not highlights` from `feature_scan_unrecognised`.
    """
    notes = (
        "## v1.0.1\n\n## Added\n- a real feature\n\n"
        "## v1.0.2\n\nA prose release.\n\n**Bold subhead**\n\n- really a feature\n"
    )
    status = upstream.UpstreamStatus(notes=notes)
    assert any("a real feature" in h for h in status.feature_highlights)
    assert status.feature_scan_unrecognised


def test_a_span_where_every_release_is_readable_is_not_flagged() -> None:
    """Control arm: the per-release check must still be able to say 'all read'."""
    notes = "## v1.0.1\n\n## Added\n- a\n\n## v1.0.2\n\n## Fixed\n- b\n"
    assert not upstream.UpstreamStatus(notes=notes).feature_scan_unrecognised


def test_the_preamble_before_the_first_version_heading_is_not_an_unread_release() -> None:
    """A GitHub body opens with `## vX` then prose; that empty span is not evidence.

    Counting it would make EVERY sectioned changelog report unreadable — which is
    how the first version of this fix broke mise.
    """
    notes = "## v2026.7.16\n\nA summary paragraph.\n\n## Added\n- a thing\n"
    status = upstream.UpstreamStatus(notes=notes)
    assert any("a thing" in h for h in status.feature_highlights)
    assert not status.feature_scan_unrecognised


def test_a_version_heading_does_not_leak_the_previous_releases_section() -> None:
    """A release boundary resets section state.

    Otherwise a bullet directly under `## v1.0.2` would still be read as sitting
    in the `## Added` that ended the previous release, and be reported as a
    feature of the wrong release.
    """
    notes = "## v1.0.1\n\n## Added\n- real feature\n\n## v1.0.2\n\n- an unsectioned bullet\n"
    highlights = upstream.UpstreamStatus(notes=notes).feature_highlights
    assert any("real feature" in h for h in highlights)
    assert not any("unsectioned bullet" in h for h in highlights)


def test_prose_dates_and_counts_are_not_mistaken_for_version_headings() -> None:
    """`_VERSION_HEADING_RE` needs two numeric components, so prose cannot reset."""
    notes = "## 2 breaking changes\n\n## Added\n- a thing\n"
    status = upstream.UpstreamStatus(notes=notes)
    assert any("a thing" in h for h in status.feature_highlights)
    assert not status.feature_scan_unrecognised


def test_a_prose_heading_that_starts_with_a_version_is_not_a_release_boundary() -> None:
    """`## 2.0 migration guide` split one release in two.

    The predecessor regex was anchored only on the LEFT — it asked the heading to
    START with a version and never asked what followed — so a prose section opened
    a new span. The per-release `all(...)` then scored that span on its own, found
    no recognised feature format in plain prose, and marked a fully-readable
    release partially unrecognised. The sibling test above only covered
    `## 2 breaking changes`, which fails on the two-numeric-components rule and so
    never reached this gap.

    THE PROSE MUST FOLLOW A RECOGNISED SECTION, and that is the whole test. A
    first draft put the prose heading FIRST and was green under the bug: the
    `## Added` simply landed in the second span and scored fine either way, so the
    probe could not fail. Measured both ways on this shape: 2 spans / recognised
    with the fix, 3 spans / UNRECOGNISED without it.
    """
    for prose in ("## 2.0 migration guide", "## 3.14 compatibility notes"):
        notes = (
            f"## v1.0.0\n\n## Added\n- a real feature\n\n"
            f"{prose}\n\nPlain prose describing the upgrade path.\n"
        )
        status = upstream.UpstreamStatus(notes=notes)
        assert any("a real feature" in h for h in status.feature_highlights), prose
        assert not status.feature_scan_unrecognised, prose


def test_real_release_headings_are_still_boundaries() -> None:
    """CONTROL ARM for the tightening: the shapes this repo actually meets.

    GitHub generates the tag alone; Keep-a-Changelog generates the dated form
    (whose hyphens `_normalize` turns into spaces, hence the digit-led branch).
    A rule that rejected these would silently restore the round-1 masking bug —
    one release's `## Added` certifying the next.
    """
    for heading in ("## v1.0.2", "## 2026.7.16", "## v1.0.2 — a title", "## 1.0.2 - 2026-01-01"):
        notes = f"## v1.0.1\n\n## Added\n- real feature\n\n{heading}\n\n- unsectioned bullet\n"
        highlights = upstream.UpstreamStatus(notes=notes).feature_highlights
        assert any("real feature" in h for h in highlights), heading
        assert not any("unsectioned" in h for h in highlights), heading


# ------------------------------------------- same_release (cold lane, round 2) ----


def test_same_release_ignores_decoration_and_zero_padding() -> None:
    """`v2.1.220` and `2.1.220` are ONE release; a raw `==` said otherwise.

    Three call sites compared raw strings — `probe`'s early return, `decide`'s,
    and `_has_upgrade` — so they were free to disagree about the same pair. They
    now share this one function.
    """
    assert upstream.same_release("2.1.220", "v2.1.220")
    assert upstream.same_release("v2.1.220", "2.1.220")
    assert upstream.same_release("1.2", "1.2.0")


def test_same_release_still_separates_genuinely_different_releases() -> None:
    """CONTROL ARM: an always-True `same_release` must not pass.

    It would satisfy the test above while disabling every upgrade this engine
    exists to find.
    """
    assert not upstream.same_release("0.9.26", "0.9.30")
    assert not upstream.same_release("v1.0.0", "v2.0.0")
    # Unparsable on either side falls back to string equality, both ways.
    assert not upstream.same_release("nightly", "0.9.30")
    assert upstream.same_release("nightly", "nightly")


def test_probe_does_not_fetch_notes_for_a_decoration_only_mismatch(monkeypatch) -> None:
    """The behaviour the string `==` actually cost.

    Notes were fetched for a release already installed, which `decide` then ran
    its gates against.
    """
    monkeypatch.setattr(upstream, "github_versions", lambda _r: ("v2.1.220", ("v2.1.220",), ""))
    monkeypatch.setattr(
        upstream,
        "release_for_tag",
        lambda _r, _v: pytest.fail("fetched notes for a release already installed"),
    )
    status = upstream.probe(pypi="", github="anthropics/claude-code", current="2.1.220")
    assert status.latest == "v2.1.220"
    assert not status.notes
