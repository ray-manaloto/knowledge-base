# Copyright (c) 2026 Raymond Manaloto
"""`kb_setup.ccdocs_mirror` — refresh and staleness of the vendored docs (#829).

Every test runs against a fake fetcher over `tmp_path`; none reaches the network.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from kb_setup import ccdocs_mirror as cm
from kb_setup import docs_mirror as dm

if TYPE_CHECKING:
    from pathlib import Path

_MD = "text/markdown; charset=utf-8"
_NOW = datetime(2026, 10, 2, tzinfo=UTC)
_LLMS, _SITEMAP = cm.INVENTORIES
_MAPPED_URLS: list[str] = []


@pytest.fixture(autouse=True)
def _offline_webclaw(monkeypatch: pytest.MonkeyPatch) -> None:
    # Map contributes the test's own inventory URLs; fallback cannot turn the
    # existing HTML/307 negative arms into successful fetches.
    _MAPPED_URLS.clear()
    monkeypatch.setattr(dm, "webclaw_map", lambda _site: list(_MAPPED_URLS))
    monkeypatch.setattr(dm, "webclaw_fetch", lambda _url: None)


def _url(name: str) -> str:
    return cm.PREFIX + name


def _ok(body: str, ctype: str = _MD) -> cm.Response:
    return cm.Response(200, ctype, body.encode())


def _fetcher(pages: dict[str, cm.Response], *, llms: str, sitemap: str) -> cm.Fetcher:
    _MAPPED_URLS[:] = sorted(cm.inventory_urls(llms) | cm.inventory_urls(sitemap))
    table = {_LLMS: _ok(llms, "text/plain"), _SITEMAP: _ok(sitemap, "application/xml")}
    table |= {url + ".md": resp for url, resp in pages.items()}

    def fetch(url: str) -> cm.Response:
        return table.get(url, cm.Response(404, "text/html", b""))

    return fetch


def _seed(root: Path, pages: dict[str, str]) -> Path:
    mirror = root / cm.MIRROR
    mirror.mkdir(parents=True)
    rows = []
    for name, body in pages.items():
        (mirror / cm.page_name(_url(name))).write_text(body)
        rows.append(cm.Row(_url(name), f"200|{_MD}", "md", len(body.encode())).line())
    (mirror / cm.FETCH_TSV).write_text("\n".join(rows) + "\n")
    return mirror


def test_refresh_adds_updates_and_stamps(tmp_path: Path) -> None:
    mirror = _seed(tmp_path, {"hooks": "old", "costs": "same"})
    fetch = _fetcher(
        {_url("hooks"): _ok("new"), _url("costs"): _ok("same"), _url("a/b"): _ok("fresh")},
        llms=f"- [B]({_url('a/b')}.md): x.",
        sitemap=f"<loc>{_url('hooks')}</loc>",
    )
    out = cm.refresh(tmp_path, fetcher=fetch, now=_NOW)
    assert out.added == [_url("a/b")]
    assert out.changed == [_url("hooks")]
    assert out.unchanged == 1
    assert (out.kept, out.missing) == ([], [])
    assert (mirror / "a__b.md").read_text() == "fresh"
    assert (mirror / "hooks.md").read_text() == "new"
    rows = cm.read_rows(mirror)
    assert set(rows) == {_url("hooks"), _url("costs"), _url("a/b")}
    assert rows[_url("hooks")].size == 3
    stamp = json.loads((mirror / cm.STAMP).read_text())
    assert stamp == {"fetched_at": _NOW.isoformat(), "pages": 3}


def test_a_failed_page_keeps_its_previous_copy_and_row(tmp_path: Path) -> None:
    mirror = _seed(tmp_path, {"claude-tag": "captured", "hooks": "h"})
    before = cm.read_rows(mirror)[_url("claude-tag")]
    fetch = _fetcher(
        # A redirect off-site: not markdown, so not the page we asked for.
        {_url("claude-tag"): cm.Response(307, "", b""), _url("hooks"): _ok("h")},
        llms=_url("hooks"),
        sitemap=_url("claude-tag"),
    )
    out = cm.refresh(tmp_path, fetcher=fetch, now=_NOW)
    assert [k.split(" ")[0] for k in out.kept] == [_url("claude-tag")]
    assert out.missing == []
    assert (mirror / "claude-tag.md").read_text() == "captured"
    assert cm.read_rows(mirror)[_url("claude-tag")] == before


def test_an_html_answer_is_not_accepted_as_a_page(tmp_path: Path) -> None:
    mirror = _seed(tmp_path, {"hooks": "md body"})
    fetch = _fetcher(
        {_url("hooks"): _ok("<html>", "text/html")}, llms=_url("hooks"), sitemap=_url("hooks")
    )
    out = cm.refresh(tmp_path, fetcher=fetch, now=_NOW)
    assert len(out.kept) == 1
    assert (mirror / "hooks.md").read_text() == "md body"


def test_a_listed_page_that_cannot_be_fetched_or_kept_is_missing(tmp_path: Path) -> None:
    _seed(tmp_path, {"hooks": "h"})
    fetch = _fetcher({_url("hooks"): _ok("h")}, llms=_url("new-page"), sitemap=_url("hooks"))
    out = cm.refresh(tmp_path, fetcher=fetch, now=_NOW)
    assert [m.split(" ")[0] for m in out.missing] == [_url("new-page")]
    assert _url("new-page") not in cm.read_rows(tmp_path / cm.MIRROR)


def test_main_exits_findings_when_a_page_is_missing(tmp_path: Path) -> None:
    _seed(tmp_path, {"hooks": "h"})
    fetch = _fetcher({_url("hooks"): _ok("h")}, llms=_url("new-page"), sitemap=_url("hooks"))
    assert cm.main(tmp_path, ["refresh"], fetcher=fetch) == cm.Rc.FINDINGS


def test_main_exits_ok_on_a_clean_refresh(tmp_path: Path) -> None:
    _seed(tmp_path, {"hooks": "h"})
    fetch = _fetcher({_url("hooks"): _ok("h")}, llms=_url("hooks"), sitemap=_url("hooks"))
    assert cm.main(tmp_path, ["refresh"], fetcher=fetch) == cm.Rc.OK


def test_main_exits_not_run_when_an_inventory_is_unreadable(tmp_path: Path) -> None:
    _seed(tmp_path, {"hooks": "h"})
    assert cm.main(tmp_path, ["refresh"], fetcher=lambda _u: cm.Response(503, "", b"")) == 127


@pytest.mark.parametrize("broken", [_LLMS, _SITEMAP])
def test_an_unreadable_inventory_writes_nothing(tmp_path: Path, broken: str) -> None:
    mirror = _seed(tmp_path, {"hooks": "old"})
    tsv_before = (mirror / cm.FETCH_TSV).read_text()
    inner = _fetcher({_url("hooks"): _ok("new")}, llms=_url("hooks"), sitemap=_url("hooks"))

    def fetch(url: str) -> cm.Response:
        return cm.Response(0, "", b"", "fetch failed: timed out") if url == broken else inner(url)

    with pytest.raises(cm.InventoryUnavailableError):
        cm.refresh(tmp_path, fetcher=fetch, now=_NOW)
    assert (mirror / "hooks.md").read_text() == "old"
    assert (mirror / cm.FETCH_TSV).read_text() == tsv_before
    assert not (mirror / cm.STAMP).exists()


def test_an_inventory_listing_no_pages_is_unreadable(tmp_path: Path) -> None:
    _seed(tmp_path, {"hooks": "h"})
    fetch = _fetcher({}, llms="nothing here", sitemap=_url("hooks"))
    with pytest.raises(cm.InventoryUnavailableError, match="listed no docs pages"):
        cm.refresh(tmp_path, fetcher=fetch, now=_NOW)


def test_inventory_urls_normalise_md_suffix_and_sentence_dots() -> None:
    text = f"see {_url('a/b')}.md. and <loc>{_url('c')}</loc> and {_url('d')}."
    assert cm.inventory_urls(text) == {_url("a/b"), _url("c"), _url("d")}


def _stamp(root: Path, when: datetime) -> None:
    mirror = root / cm.MIRROR
    mirror.mkdir(parents=True, exist_ok=True)
    (mirror / cm.FETCH_TSV).touch()
    (mirror / cm.STAMP).write_text(json.dumps({"fetched_at": when.isoformat(), "pages": 1}))


def test_staleness_is_silent_when_fresh(tmp_path: Path) -> None:
    _stamp(tmp_path, _NOW - timedelta(days=cm.STALE_AFTER_DAYS - 1))
    assert cm.staleness(tmp_path, now=_NOW) == ""


def test_staleness_reports_an_old_mirror(tmp_path: Path) -> None:
    _stamp(tmp_path, _NOW - timedelta(days=cm.STALE_AFTER_DAYS))
    assert f"fetched {cm.STALE_AFTER_DAYS} days ago" in cm.staleness(tmp_path, now=_NOW)


def test_staleness_never_reads_a_missing_stamp_as_fresh(tmp_path: Path) -> None:
    (tmp_path / cm.MIRROR).mkdir(parents=True)
    (tmp_path / cm.MIRROR / cm.FETCH_TSV).touch()
    assert "freshness UNKNOWN" in cm.staleness(tmp_path, now=_NOW)


def test_staleness_is_silent_where_no_mirror_is_vendored(tmp_path: Path) -> None:
    assert cm.staleness(tmp_path, now=_NOW) == ""


def test_currency_check_prints_the_stale_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _stamp(tmp_path, datetime(2000, 1, 1, tzinfo=UTC))
    cm.report_staleness(tmp_path)
    assert "[ccdocs]" in capsys.readouterr().out


def test_the_committed_mirror_has_a_readable_stamp() -> None:
    from pathlib import Path as _Path

    # Real clock, not `_NOW`: the committed stamp carries a time of day, and a
    # fixed midnight `now` reads it as future-dated. Age may say "stale"; it must
    # never say UNKNOWN.
    repo = _Path(__file__).parent.parent
    assert "UNKNOWN" not in cm.staleness(repo)


@pytest.mark.parametrize("args", [[], ["nope"], ["refresh", "extra"], ["check", "x"]])
def test_main_refuses_a_malformed_request(tmp_path: Path, args: list[str]) -> None:
    assert cm.main(tmp_path, args) == cm.Rc.BAD_REQUEST


def test_the_sessionstart_currency_check_runs_the_staleness_probe(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The wiring, not the probe: `currency check` is what SessionStart runs, so a
    # deleted call site would leave a stale mirror silent while every unit test of
    # `staleness` stayed green.
    from pathlib import Path as _Path

    from kb_setup.currency import run as currency_run

    monkeypatch.setattr(dm, "staleness", lambda _root, _site: "SENTINEL-stale-mirror")
    assert currency_run.check(_Path(__file__).parent.parent) == 0
    assert "SENTINEL-stale-mirror" in capsys.readouterr().out


# --- round-2 cold review of 4979b5e4 -------------------------------------------


def test_a_refresh_that_fetched_nothing_does_not_advance_the_stamp(tmp_path: Path) -> None:
    mirror = _seed(tmp_path, {"hooks": "h", "costs": "c"})
    fetch = _fetcher(
        {_url("hooks"): _ok("<html>", "text/html"), _url("costs"): _ok("<html>", "text/html")},
        llms=_url("hooks"),
        sitemap=_url("costs"),
    )
    assert cm.main(tmp_path, ["refresh"], fetcher=fetch) == cm.Rc.FINDINGS
    assert not (mirror / cm.STAMP).exists()


def test_one_stale_md_page_holds_the_stamp_back(tmp_path: Path) -> None:
    mirror = _seed(tmp_path, {"hooks": "h", "costs": "c"})
    fetch = _fetcher(
        {_url("hooks"): _ok("h2"), _url("costs"): cm.Response(0, "", b"", "fetch failed: x")},
        llms=_url("hooks"),
        sitemap=_url("costs"),
    )
    out = cm.refresh(tmp_path, fetcher=fetch, now=_NOW)
    assert (out.changed, out.stamped) == ([_url("hooks")], False)
    assert (mirror / "hooks.md").read_text() == "h2"


def test_a_kept_webclaw_page_does_not_hold_the_stamp_back(tmp_path: Path) -> None:
    mirror = _seed(tmp_path, {"hooks": "h"})
    (mirror / "claude-tag.md").write_text("captured")
    with (mirror / cm.FETCH_TSV).open("a") as f:
        f.write(cm.Row(_url("claude-tag"), "200|text/html", "webclaw", 8).line() + "\n")
    fetch = _fetcher(
        {_url("hooks"): _ok("h"), _url("claude-tag"): cm.Response(307, "", b"")},
        llms=_url("hooks"),
        sitemap=_url("claude-tag"),
    )
    assert cm.main(tmp_path, ["refresh"], fetcher=fetch) == cm.Rc.OK
    assert (mirror / cm.STAMP).exists()


def test_a_404_served_as_markdown_is_not_a_page(tmp_path: Path) -> None:
    # The live site answers a missing page with `404 text/markdown` (measured).
    mirror = _seed(tmp_path, {"hooks": "real"})
    fetch = _fetcher(
        {_url("hooks"): cm.Response(404, _MD, b"# Not found")},
        llms=_url("hooks"),
        sitemap=_url("hooks"),
    )
    out = cm.refresh(tmp_path, fetcher=fetch, now=_NOW)
    assert len(out.kept) == 1
    assert (mirror / "hooks.md").read_text() == "real"


def test_a_crash_mid_loop_leaves_the_mirror_untouched(tmp_path: Path) -> None:
    mirror = _seed(tmp_path, {"a": "A", "b": "B"})
    inner = _fetcher({_url("a"): _ok("A2")}, llms=_url("a"), sitemap=_url("b"))

    def fetch(url: str) -> cm.Response:
        if url == _url("b") + ".md":
            raise RuntimeError
        return inner(url)

    with pytest.raises(RuntimeError):
        cm.refresh(tmp_path, fetcher=fetch, now=_NOW)
    assert (mirror / "a.md").read_text() == "A"


def test_fetch_turns_an_http_protocol_error_into_a_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import http.client

    class Broken:
        def __init__(self, *_a: object, **_k: object) -> None: ...
        def request(self, *_a: object) -> None: ...
        def getresponse(self) -> object:
            raise http.client.IncompleteRead(b"partial")

        def close(self) -> None: ...

    monkeypatch.setattr(http.client, "HTTPSConnection", Broken)
    resp = cm.fetch(_url("hooks") + ".md")
    assert resp.error.startswith("fetch failed: IncompleteRead")


def test_a_malformed_fetch_tsv_is_not_run_and_writes_nothing(tmp_path: Path) -> None:
    mirror = _seed(tmp_path, {"hooks": "h"})
    (mirror / cm.FETCH_TSV).write_text("only\ttwo\n")
    fetch = _fetcher({_url("hooks"): _ok("new")}, llms=_url("hooks"), sitemap=_url("hooks"))
    assert cm.main(tmp_path, ["refresh"], fetcher=fetch) == cm.Rc.NOT_RUN
    assert (mirror / "hooks.md").read_text() == "h"


def test_a_trailing_slash_url_is_the_same_page() -> None:
    assert cm.inventory_urls(f"<loc>{_url('overview')}/</loc>") == {_url("overview")}


@pytest.mark.parametrize(
    ("stamp", "reason"),
    [
        ("{not json", "JSONDecodeError"),
        ('{"pages": 1}', "KeyError"),
        ('{"fetched_at": 5}', "TypeError"),
        ('{"fetched_at": "2026-10-02T16:31:13"}', "TypeError"),
        ('{"fetched_at": "2027-10-02T00:00:00+00:00"}', "stamp is in the future"),
    ],
)
def test_an_unusable_stamp_is_unknown_never_fresh(tmp_path: Path, stamp: str, reason: str) -> None:
    (tmp_path / cm.MIRROR).mkdir(parents=True)
    (tmp_path / cm.MIRROR / cm.FETCH_TSV).touch()
    (tmp_path / cm.MIRROR / cm.STAMP).write_text(stamp)
    line = cm.staleness(tmp_path, now=_NOW)
    assert "freshness UNKNOWN" in line
    assert reason in line
