# Copyright (c) 2026 Raymond Manaloto
"""Multi-site mirror policies, using fake inputs and isolated temporary trees."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import structlog
from kb_setup import docs_mirror as dm

_NOW = datetime(2026, 10, 2, tzinfo=UTC)
_AV = dm.SITES["agentsview"]
_CC = dm.SITES["claude-code"]
_MD = "text/markdown"
_REPO = Path(__file__).resolve().parent.parent


def _url(name: str, site: dm.Site = _AV) -> str:
    return site.prefix + name


def _ok(body: str = "fresh") -> dm.Response:
    return dm.Response(200, _MD, body.encode())


def _native(site: dm.Site, pages: dict[str, dm.Response], listed: list[str]) -> dm.Fetcher:
    table = dict.fromkeys(
        site.inventories, dm.Response(200, "text/plain", "\n".join(listed).encode())
    )
    table.update({url + ".md": response for url, response in pages.items()})
    return lambda url: table.get(url, dm.Response(404, "text/html", b""))


def _mapper(listed: list[str]) -> dm.Mapper:
    return lambda _site: listed


def _seed(root: Path, site: dm.Site, pages: dict[str, str], *, method: str = "md") -> Path:
    mirror = root / site.mirror
    mirror.mkdir(parents=True)
    rows: list[str] = []
    for name, body in pages.items():
        url = _url(name, site)
        (mirror / dm.page_name(site, url)).write_text(body, encoding="utf-8")
        rows.append(dm.Row(url, "200|text/markdown", method, len(body.encode())).line())
    (mirror / dm.FETCH_TSV).write_text("\n".join(rows) + "\n", encoding="utf-8")
    (mirror / dm.STAMP).write_text(
        json.dumps({"fetched_at": (_NOW - timedelta(days=14)).isoformat(), "pages": len(rows)}),
        encoding="utf-8",
    )
    return mirror


def _miss(mirror: Path, url: str, count: int, first_seen: datetime) -> None:
    (mirror / dm.MISSES).write_text(
        json.dumps({url: {"count": count, "first_seen": first_seen.isoformat()}}) + "\n",
        encoding="utf-8",
    )


def _snapshot(mirror: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in mirror.iterdir()}


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("https://agentsview.io/docs/configuration.md", _url("docs/configuration")),
        ("https://www.agentsview.io/docs/", _url("docs/index")),
        ("https://www.agentsview.io/", _url("index")),
        ("https://www.agentsview.io/docs/x/", _url("docs/x")),
        ("https://www.agentsview.io/docs/x?tab=python", None),
        ("https://www.agentsview.io/docs/x#details", None),
        ("https://www.agentsview.io/logo.png", None),
        ("https://outside.example/docs/x", None),
    ],
)
def test_agentsview_normalisation(raw: str, canonical: str | None) -> None:
    assert dm.normalise(_AV, raw) == canonical
    assert dm.inventory_urls(_AV, f"<loc>{raw}</loc>") == ({canonical} if canonical else set())
    if canonical:
        expected = canonical.removeprefix(_AV.prefix).replace("/", "__") + ".md"
        assert dm.page_name(_AV, raw) == expected


def test_an_empty_non_index_path_is_rejected() -> None:
    assert dm.normalise(replace(_AV, index_sections=()), _AV.prefix) is None
    assert dm.normalise(_CC, _CC.prefix) is None


def test_a_map_only_page_is_discovered_and_fetched(tmp_path: Path) -> None:
    listed = [_url("alive")]
    mapped = [*listed, _url("map-only")]
    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, dict.fromkeys(mapped, _ok()), listed),
        mapper=_mapper(mapped),
        now=_NOW,
    )
    assert set(out.added) == set(mapped)
    assert set(dm.read_rows(tmp_path / _AV.mirror)) == set(mapped)
    assert out.stamped


@pytest.mark.parametrize(
    ("prior_count", "age", "retired"), [(1, 8, False), (2, 6, False), (2, 7, True)]
)
def test_retirement_requires_count_and_elapsed_age(
    tmp_path: Path, prior_count: int, age: int, *, retired: bool
) -> None:
    mirror = _seed(tmp_path, _AV, {"alive": "old", "removed": "previous"})
    removed = _url("removed")
    first_seen = _NOW - timedelta(days=age)
    _miss(mirror, removed, prior_count, first_seen)
    before_stamp = (mirror / dm.STAMP).read_bytes()
    listed = [_url("alive")]
    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, {_url("alive"): _ok()}, listed),
        mapper=_mapper(listed),
        now=_NOW,
    )
    assert out.retired == ([removed] if retired else [])
    assert out.stamped == retired
    assert (mirror / "removed.md").exists() != retired
    assert (removed in dm.read_rows(mirror)) != retired
    if retired:
        assert not (mirror / dm.MISSES).exists()
        assert json.loads((mirror / dm.STAMP).read_text())["fetched_at"] == _NOW.isoformat()
    else:
        assert len(out.kept) == 1
        assert (mirror / dm.STAMP).read_bytes() == before_stamp
        assert json.loads((mirror / dm.MISSES).read_text())[removed] == {
            "count": prior_count + 1,
            "first_seen": first_seen.isoformat(),
        }


def test_a_candidate_holds_stamp_and_logs_retire_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mirror = _seed(tmp_path, _AV, {"alive": "old", "removed": "previous"})
    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(dm.events, "warn", lambda event, message: logged.append((event, message)))
    listed = [_url("alive")]
    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, {_url("alive"): _ok()}, listed),
        mapper=_mapper(listed),
        now=_NOW,
    )
    assert not out.stamped
    assert logged == [
        (
            "avdocs.retire_candidate",
            (
                f"[avdocs]   retirement candidate (1 consecutive 404s "
                f"since {_NOW.isoformat()}): {_url('removed')}"
            ),
        )
    ]
    assert (mirror / dm.MISSES).read_text().endswith("\n")


def test_an_orphan_miss_is_pruned(tmp_path: Path) -> None:
    # Neither a row nor listed: nothing will ever fetch it again, so its miss
    # record would otherwise be rewritten forever.
    mirror = _seed(tmp_path, _AV, {"alive": "old"})
    _miss(mirror, _url("gone-long-ago"), 2, _NOW - timedelta(days=3))
    listed = [_url("alive")]
    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, {_url("alive"): _ok()}, listed),
        mapper=_mapper(listed),
        now=_NOW,
    )
    assert out.stamped
    assert not (mirror / dm.MISSES).exists()


@pytest.mark.parametrize(
    "bad", ["https://www.agentsview.io/docs/x?tab=1", "https://elsewhere.example/docs/x"]
)
def test_a_row_that_is_not_a_page_refuses_before_writing(tmp_path: Path, bad: str) -> None:
    mirror = _seed(tmp_path, _AV, {"alive": "old"})
    with (mirror / dm.FETCH_TSV).open("a", encoding="utf-8") as f:
        f.write(dm.Row(bad, "200|text/markdown", "md", 1).line() + "\n")
    before = _snapshot(mirror)
    listed = [_url("alive")]
    native = _native(_AV, {_url("alive"): _ok()}, listed)
    with pytest.raises(dm.MirrorUnreadableError):
        dm.refresh(tmp_path, _AV, fetcher=native, mapper=_mapper(listed), now=_NOW)
    assert _snapshot(mirror) == before
    rc = dm.main(tmp_path, ["refresh", "agentsview"], fetcher=native, mapper=_mapper(listed))
    assert rc == dm.Rc.NOT_RUN


@pytest.mark.parametrize("inventory", ["llms", "sitemap", "map"])
def test_a_page_listed_in_any_inventory_is_never_counted(tmp_path: Path, inventory: str) -> None:
    mirror = _seed(tmp_path, _AV, {"alive": "old", "listed": "previous"})
    listed_url = _url("listed")
    _miss(mirror, listed_url, 2, _NOW - timedelta(days=8))
    inventories = dict.fromkeys(_AV.inventories, _ok(_url("alive")))
    if inventory != "map":
        inventories[_AV.inventories[0 if inventory == "llms" else 1]] = _ok(listed_url)
    inventories[_url("alive") + ".md"] = _ok()
    mapped = [listed_url] if inventory == "map" else [_url("alive")]
    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=lambda url: inventories.get(url, dm.Response(404, "text/html", b"")),
        mapper=_mapper(mapped),
        now=_NOW,
    )
    assert not out.retired
    assert len(out.kept) == 1
    assert not (mirror / dm.MISSES).exists()


@pytest.mark.parametrize(
    "response", [dm.Response(503, "", b""), dm.Response(0, "", b"", "timeout")]
)
def test_a_server_or_network_error_resets_misses(tmp_path: Path, response: dm.Response) -> None:
    mirror = _seed(tmp_path, _AV, {"alive": "old", "removed": "previous"})
    removed = _url("removed")
    _miss(mirror, removed, 2, _NOW - timedelta(days=8))
    listed = [_url("alive")]
    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, {_url("alive"): _ok(), removed: response}, listed),
        mapper=_mapper(listed),
        now=_NOW,
    )
    assert not out.retired
    assert not out.stamped
    assert not (mirror / dm.MISSES).exists()


@pytest.mark.parametrize("status", [404, 410])
def test_both_permanent_not_found_statuses_count(tmp_path: Path, status: int) -> None:
    mirror = _seed(tmp_path, _AV, {"alive": "old", "removed": "previous"})
    listed = [_url("alive")]
    dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(
            _AV, {_url("alive"): _ok(), _url("removed"): dm.Response(status, "", b"")}, listed
        ),
        mapper=_mapper(listed),
        now=_NOW,
    )
    assert json.loads((mirror / dm.MISSES).read_text())[_url("removed")]["count"] == 1


def test_webclaw_recovers_listed_html(tmp_path: Path) -> None:
    url = _url("docs/configuration")
    calls: list[str] = []

    def fallback(requested: str) -> dm.WebclawPage:
        calls.append(requested)
        return dm.WebclawPage("https://agentsview.io/docs/configuration/", b"# fallback")

    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, {url: dm.Response(200, "text/html", b"html")}, [url]),
        mapper=_mapper([url]),
        page_fetcher=fallback,
        now=_NOW,
    )
    mirror = tmp_path / _AV.mirror
    assert calls == [url]
    assert out.stamped
    assert (mirror / "docs__configuration.md").read_bytes() == b"# fallback"
    assert dm.read_rows(mirror)[url] == dm.Row(
        url, "200|text/markdown; source=webclaw", "webclaw", 10
    )


@pytest.mark.parametrize("method", ["md", "webclaw"])
def test_only_a_known_webclaw_row_can_use_unlisted_html_fallback(
    tmp_path: Path, method: str
) -> None:
    mirror = _seed(tmp_path, _AV, {"alive": "old", "unlisted": "previous"}, method=method)
    url = _url("unlisted")
    listed = [_url("alive")]
    calls: list[str] = []

    def fallback(requested: str) -> dm.WebclawPage:
        calls.append(requested)
        return dm.WebclawPage(requested, b"fresh")

    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(
            _AV, {listed[0]: _ok(), url: dm.Response(200, "text/html", b"html")}, listed
        ),
        mapper=_mapper(listed),
        page_fetcher=fallback,
        now=_NOW,
    )
    assert calls == ([url] if method == "webclaw" else [])
    assert out.stamped == (method == "webclaw")
    assert (mirror / "unlisted.md").read_text() == ("fresh" if method == "webclaw" else "previous")


@pytest.mark.parametrize("response", ["mapped", "json", "empty", "malformed", "failed"])
def test_default_webclaw_commands_and_json_shape_use_only_fake_subprocesses(
    monkeypatch: pytest.MonkeyPatch, response: str
) -> None:
    url = _url("docs/x")
    output = {
        "mapped": url + "\n",
        "json": json.dumps({"metadata": {"url": url}, "content": {"markdown": "# page"}}),
        "empty": json.dumps({"metadata": {"url": url}, "content": {"markdown": ""}}),
        "malformed": "not json",
        "failed": "",
    }

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs == {"capture_output": True, "text": True, "timeout": 120, "check": False}
        expected = (
            ["webclaw", "--map", "--no-map-crawl", _AV.origin]
            if response == "mapped"
            else ["webclaw", "-f", "json", url]
        )
        assert args == expected
        return subprocess.CompletedProcess(args, 1 if response == "failed" else 0, output[response])

    monkeypatch.setattr(dm.subprocess, "run", run)
    if response == "mapped":
        assert dm.webclaw_map(_AV) == [url]
    else:
        expected_page = dm.WebclawPage(url, b"# page") if response == "json" else None
        assert dm.webclaw_fetch(url) == expected_page


@pytest.mark.parametrize("failure", ["missing", "timeout", "rc"])
def test_default_mapper_returns_none_on_unavailable_subprocess(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    def run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if failure == "missing":
            raise FileNotFoundError("webclaw")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 120)
        return subprocess.CompletedProcess(args, 1, "")

    monkeypatch.setattr(dm.subprocess, "run", run)
    assert dm.webclaw_map(_AV) is None


@pytest.mark.parametrize("status", [404, 410, 500, 503, 0])
def test_webclaw_never_runs_on_not_found_server_or_network_failure(
    tmp_path: Path, status: int
) -> None:
    url = _url("docs/configuration")
    calls: list[str] = []

    def fallback(requested: str) -> None:
        calls.append(requested)

    response = dm.Response(status, "text/html", b"", "error" if status == 0 else "")
    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, {url: response}, [url]),
        mapper=_mapper([url]),
        page_fetcher=fallback,
        now=_NOW,
    )
    assert calls == []
    assert len(out.missing) == 1
    assert not out.stamped


@pytest.mark.parametrize("location", [_url("different"), "https://offsite.example/docs/x"])
def test_a_moved_page_never_calls_webclaw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    mirror = _seed(tmp_path, _AV, {"docs/x": "previous"})
    url = _url("docs/x")
    _miss(mirror, url, 2, _NOW - timedelta(days=8))
    calls: list[str] = []
    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(dm.events, "warn", lambda event, message: logged.append((event, message)))

    def fallback(requested: str) -> None:
        calls.append(requested)

    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, {url: dm.Response(307, "", b"", location=location)}, [url]),
        mapper=_mapper([url]),
        page_fetcher=fallback,
        now=_NOW,
    )
    assert calls == []
    assert logged == [("avdocs.moved", f"[avdocs]   MOVED {url} -> {location}")]
    assert len(out.kept) == 1
    assert not (mirror / dm.MISSES).exists()
    assert (mirror / "docs__x.md").read_text() == "previous"


def test_a_same_page_redirect_can_use_webclaw(tmp_path: Path) -> None:
    url = _url("docs/x")
    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, {url: dm.Response(308, "", b"", location="/docs/x/")}, [url]),
        mapper=_mapper([url]),
        page_fetcher=lambda _url: dm.WebclawPage(url, b"fresh"),
        now=_NOW,
    )
    assert out.stamped
    assert dm.read_rows(tmp_path / _AV.mirror)[url].method == "webclaw"


def test_webclaw_rejects_a_different_final_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = _url("docs/x")
    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(dm.events, "warn", lambda event, message: logged.append((event, message)))
    out = dm.refresh(
        tmp_path,
        _AV,
        fetcher=_native(_AV, {url: dm.Response(200, "text/html", b"html")}, [url]),
        mapper=_mapper([url]),
        page_fetcher=lambda _requested: dm.WebclawPage(_url("different"), b"wrong"),
        now=_NOW,
    )
    assert len(out.missing) == 1
    assert dm.read_rows(tmp_path / _AV.mirror) == {}
    assert not (tmp_path / _AV.mirror / "docs__x.md").exists()
    assert logged == [
        (
            "avdocs.webclaw_rejected",
            f"[avdocs]   webclaw rejected {url}: final_url {_url('different')}",
        )
    ]


@pytest.mark.parametrize("name", ["claude-tag", "other"])
def test_only_grandfathered_failed_webclaw_rows_allow_the_stamp(tmp_path: Path, name: str) -> None:
    mirror = _seed(tmp_path, _CC, {"alive": "old", name: "previous"}, method="webclaw")
    listed = [_url("alive", _CC)]
    out = dm.refresh(
        tmp_path,
        _CC,
        fetcher=_native(
            _CC, {listed[0]: _ok(), _url(name, _CC): dm.Response(503, "", b"")}, listed
        ),
        mapper=_mapper(listed),
        page_fetcher=lambda _url: None,
        now=_NOW,
    )
    assert out.stamped == (name == "claude-tag")
    assert len(out.kept) == 1
    assert (mirror / f"{name}.md").read_text() == "previous"


@pytest.mark.parametrize("mapped", [None, [], ["https://elsewhere.example/docs/x"]])
def test_an_unavailable_mapper_is_not_run_and_writes_nothing(
    tmp_path: Path, mapped: list[str] | None
) -> None:
    mirror = _seed(tmp_path, _AV, {"alive": "old", "removed": "previous"})
    _miss(mirror, _url("removed"), 2, _NOW - timedelta(days=8))
    before = _snapshot(mirror)
    listed = [_url("alive")]
    rc = dm.main(
        tmp_path,
        ["refresh", "agentsview"],
        fetcher=_native(_AV, {listed[0]: _ok()}, listed),
        mapper=lambda _site: mapped,
    )
    assert rc == dm.Rc.NOT_RUN
    assert _snapshot(mirror) == before


def test_a_crash_defers_retirement_misses_and_page_writes(tmp_path: Path) -> None:
    mirror = _seed(tmp_path, _AV, {"a-removed": "previous", "b-alive": "old", "z-crash": "old"})
    _miss(mirror, _url("a-removed"), 2, _NOW - timedelta(days=8))
    before = _snapshot(mirror)
    listed = [_url("b-alive"), _url("z-crash")]
    native = _native(_AV, {_url("b-alive"): _ok()}, listed)

    def fetch(url: str) -> dm.Response:
        if url == _url("z-crash") + ".md":
            raise RuntimeError("simulated crash")
        return native(url)

    with pytest.raises(RuntimeError, match="simulated crash"):
        dm.refresh(tmp_path, _AV, fetcher=fetch, mapper=_mapper(listed), now=_NOW)
    assert _snapshot(mirror) == before


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (dm.Rc.OK, dm.Rc.OK, dm.Rc.OK),
        (dm.Rc.OK, dm.Rc.FINDINGS, dm.Rc.FINDINGS),
        (dm.Rc.FINDINGS, dm.Rc.NOT_RUN, dm.Rc.NOT_RUN),
        (dm.Rc.NOT_RUN, dm.Rc.FINDINGS, dm.Rc.NOT_RUN),
    ],
)
def test_refresh_all_returns_the_worst_rc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first: dm.Rc, second: dm.Rc, expected: dm.Rc
) -> None:
    attempted: list[str] = []
    results = {"claude-code": first, "agentsview": second}

    def refresh(_root: Path, site: dm.Site, **_kwargs: object) -> dm.Outcome:
        attempted.append(site.key)
        if results[site.key] == dm.Rc.NOT_RUN:
            raise dm.InventoryUnavailableError("fake unavailable inventory")
        return dm.Outcome([], [], 1, [], [], stamped=results[site.key] == dm.Rc.OK)

    monkeypatch.setattr(dm, "refresh", refresh)
    assert dm.main(tmp_path, ["refresh", "all"]) == expected
    assert attempted == ["claude-code", "agentsview"]


def _manifest(root: Path, *, clone: bool = False) -> Path:
    path = root / "sources/codex-docs.manifest"
    path.parent.mkdir(parents=True)
    path.write_text(
        "url = https://example.com/codex-docs\nref = main\ncommit = abc123\n", encoding="utf-8"
    )
    if clone:
        path.with_suffix("").mkdir()
    return path


def test_codex_staleness_is_silent_without_a_manifest(tmp_path: Path) -> None:
    assert dm.codex_docs_staleness(tmp_path, _NOW) == ""


def test_codex_staleness_reports_a_bad_manifest(tmp_path: Path) -> None:
    path = _manifest(tmp_path)
    path.write_text("missing fields\n", encoding="utf-8")
    assert "UNKNOWN (ValueError" in dm.codex_docs_staleness(tmp_path, _NOW)


@pytest.mark.parametrize("failure", ["git", "timeout", "binary"])
def test_codex_staleness_reports_git_failures(tmp_path: Path, failure: str) -> None:
    _manifest(tmp_path)

    def git(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["timeout"] == 10
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 10)
        if failure == "binary":
            raise FileNotFoundError("git")
        raise subprocess.CalledProcessError(1, args)

    assert "UNKNOWN" in dm.codex_docs_staleness(tmp_path, _NOW, git=git)


@pytest.mark.parametrize("date", ["nonsense", "", "2026-10-01T00:00:00"])
def test_codex_staleness_reports_unparsable_or_naive_dates(tmp_path: Path, date: str) -> None:
    _manifest(tmp_path)
    assert "UNKNOWN" in dm.codex_docs_staleness(
        tmp_path,
        _NOW,
        git=lambda args, **_kwargs: subprocess.CompletedProcess(args, 0, date),
    )


@pytest.mark.parametrize("clone", [False, True])
@pytest.mark.parametrize("age", [6, 7])
def test_codex_staleness_reads_the_last_pin_advance_on_every_host(
    tmp_path: Path, *, clone: bool, age: int
) -> None:
    # Whether the gitignored clone exists must not change the question asked:
    # the same committed state answers the same on every host.
    _manifest(tmp_path, clone=clone)

    def git(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs == {"capture_output": True, "text": True, "check": True, "timeout": 10}
        assert args == [
            "git",
            "-C",
            str(tmp_path),
            "log",
            "-1",
            "--format=%cI",
            "--",
            "sources/codex-docs.manifest",
        ]
        return subprocess.CompletedProcess(args, 0, (_NOW - timedelta(days=age)).isoformat())

    line = dm.codex_docs_staleness(tmp_path, _NOW, git=git)
    if age < dm.STALE_AFTER_DAYS:
        assert line == ""
    else:
        assert "age of the last pin advance" in line
        assert "7 days" in line
        assert "mise run kb-update -- codex-docs" in line


def test_sessionstart_staleness_never_asks_the_codex_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # SessionStart is documented stat-only; the codex pin age spawns `git`.
    def boom(*_a: object, **_k: object) -> str:
        raise AssertionError("SessionStart asked the codex pin")

    monkeypatch.setattr(dm, "codex_docs_staleness", boom)
    dm.report_staleness(tmp_path)
    assert capsys.readouterr().out == ""


def test_a_mirror_with_pages_but_no_stamp_is_unknown(tmp_path: Path) -> None:
    site = dm.SITES["agentsview"]
    mirror = tmp_path / site.mirror
    mirror.mkdir(parents=True)
    (mirror / "docs__quickstart.md").write_text("x", encoding="utf-8")
    assert "freshness UNKNOWN" in dm.staleness(tmp_path, site, now=_NOW)


@pytest.mark.parametrize(
    "raw", ["a/../b", "a/./b", "a//b", "../b", "a/.."], ids=["up", "dot", "empty", "lead", "tail"]
)
def test_dot_and_empty_segments_are_not_pages(raw: str) -> None:
    site = dm.SITES["claude-code"]
    assert dm.normalise(site, site.prefix + raw) is None
    assert dm.normalise(site, site.prefix + "a/b") == site.prefix + "a/b"  # control


@pytest.fixture
def isolated_structlog(tmp_path: Path) -> Path:
    # -S excludes site-packages; copying only structlog proves the import closure
    # instead of allowing the project's installed graphify to mask a dependency.
    deps = tmp_path / "deps"
    shutil.copytree(Path(structlog.__file__).parent, deps / "structlog")
    return deps


def _isolated(deps: Path, code: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH="python/src")
    return subprocess.run(
        [sys.executable, "-S", "-c", f"import sys; sys.path.insert(0, {str(deps)!r}); {code}"],
        cwd=_REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_the_module_imports_without_graphify(isolated_structlog: Path) -> None:
    result = _isolated(
        isolated_structlog, "import kb_setup.docs_mirror; assert 'graphify' not in sys.modules"
    )
    assert result.returncode == 0, result.stderr


def test_a_gitkeep_only_mirror_makes_module_check_silent(
    tmp_path: Path, isolated_structlog: Path
) -> None:
    for site in dm.SITES.values():
        mirror = tmp_path / site.mirror
        mirror.mkdir(parents=True)
        (mirror / ".gitkeep").touch()
    result = _isolated(
        isolated_structlog,
        f"import os, runpy; os.chdir({str(tmp_path)!r}); "
        "sys.argv = ['kb_setup.docs_mirror', 'check']; "
        "runpy.run_module('kb_setup.docs_mirror', run_name='__main__')",
    )
    assert result.returncode == 0, result.stderr
    assert (result.stdout, result.stderr) == ("", "")
