# Copyright (c) 2026 Raymond Manaloto
"""Resolving a model's output ceiling instead of hardcoding it.

The defect that motivates the module is a literal `max_output_tokens = "8192"`
truncating a paid extraction against a measured 31,887-token need. The defect
that motivates *these tests* is the one a resolver introduces: a
column-positional parse of someone else's markdown table returns a plausible
number for the wrong model the moment the columns move, and nothing downstream
could tell.

So the arms below are weighted toward the FAIL direction. The happy path is one
test; `LayoutChangedError` gets five, one per way the table can shift, because a
parser that only ever succeeded is decoration
(`.claude/rules/probes-need-a-control-arm.md`).

**No test here reaches the network.** `_read_url` is monkeypatched to raise
wherever the CLI is exercised, which both keeps the suite deterministic and
makes the snapshot the source under test rather than whatever the live page
happens to say today.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from kb_setup import model_limits
from kb_setup.result import Rc

# The real shape, trimmed to the three rows the parser reads. Kept verbatim in
# column order so a reordering test can permute it and prove the parse notices.
_TABLE = """
Some prose before the table.

| Feature               | Claude Fable 5 | Claude Opus 5 | Claude Sonnet 5 | Claude Haiku 4.5 |
| :-------------------- | :------------- | :------------ | :-------------- | :--------------- |
| **Description**       | Next-gen       | Agentic       | Balanced        | Fastest          |
| **Claude API alias**  | claude-fable-5 | claude-opus-5 | claude-sonnet-5 | claude-haiku-4-5 |
| **Max output**        | 128k tokens    | 128k tokens   | 128k tokens     | 64k tokens       |
"""


def test_parses_the_real_shape() -> None:
    """The positive arm: the live table's three load-bearing rows."""
    limits = model_limits.parse_docs_table(_TABLE)

    assert limits["claude-opus-5"].max_output_tokens == 128_000
    assert limits["claude-haiku-4-5"].max_output_tokens == 64_000
    assert limits["claude-opus-5"].source == "docs"
    # The docs cell is Tooltip markup a table parse cannot read, so it must be
    # the third state rather than a zero someone could arithmetic on.
    assert limits["claude-opus-5"].max_input_tokens is None


def test_alias_and_value_stay_aligned_when_columns_move() -> None:
    """Reordering columns must move the VALUES with them, not pair the wrong ones.

    This is the failure the parser exists to prevent, so it is armed directly:
    swap Haiku into the first data column and the 64k must follow it.
    """
    swapped = (
        _TABLE.replace(
            "| Claude Fable 5 | Claude Opus 5 | Claude Sonnet 5 | Claude Haiku 4.5 |",
            "| Claude Haiku 4.5 | Claude Opus 5 | Claude Sonnet 5 | Claude Fable 5 |",
        )
        .replace(
            "| claude-fable-5 | claude-opus-5 | claude-sonnet-5 | claude-haiku-4-5 |",
            "| claude-haiku-4-5 | claude-opus-5 | claude-sonnet-5 | claude-fable-5 |",
        )
        .replace(
            "| 128k tokens    | 128k tokens   | 128k tokens     | 64k tokens       |",
            "| 64k tokens     | 128k tokens   | 128k tokens     | 128k tokens      |",
        )
    )

    limits = model_limits.parse_docs_table(swapped)

    assert limits["claude-haiku-4-5"].max_output_tokens == 64_000
    assert limits["claude-fable-5"].max_output_tokens == 128_000


@pytest.mark.parametrize(
    ("mutation", "because"),
    [
        ("Feature", "the header row is what anchors every column position"),
        ("Claude API alias", "without aliases the numbers belong to nobody"),
        ("Max output", "the value row is the whole point"),
    ],
)
def test_a_missing_row_raises_rather_than_guessing(mutation: str, because: str) -> None:
    """Delete each load-bearing row in turn; each must stop the parse."""
    broken = _TABLE.replace(mutation, f"{mutation} RENAMED UPSTREAM")

    with pytest.raises(model_limits.LayoutChangedError):
        model_limits.parse_docs_table(broken)

    assert because  # documents the row's purpose in the failure output


def test_row_width_mismatch_raises() -> None:
    """A column dropped from one row and not the others must not zip silently."""
    broken = _TABLE.replace("| 128k tokens     | 64k tokens       |", "| 128k tokens |")

    with pytest.raises(model_limits.LayoutChangedError):
        model_limits.parse_docs_table(broken)


def test_a_unitless_cell_raises() -> None:
    """`128000` where `128k tokens` belonged means the cell changed meaning.

    A lenient parser would happily return 128000 here and be right by luck. The
    unit is the evidence that this is still the cell the parser thinks it is.
    """
    with pytest.raises(model_limits.LayoutChangedError):
        model_limits.parse_tokens("128000")


def test_parse_tokens_scales() -> None:
    assert model_limits.parse_tokens("128k tokens") == 128_000
    assert model_limits.parse_tokens("64K tokens") == 64_000
    assert model_limits.parse_tokens("1M tokens") == 1_000_000


def test_chain_falls_through_to_the_first_source_that_answers(tmp_path: Path) -> None:
    """An empty source is skipped; the first non-empty one wins."""
    answer = {"claude-opus-5": model_limits.ModelLimits("claude-opus-5", 128_000, "snapshot")}

    resolved = model_limits.resolve_all(
        tmp_path,
        {},
        sources=(lambda: None, dict, lambda: answer),
    )

    assert resolved["claude-opus-5"].source == "snapshot"


def test_fails_closed_when_nothing_answers(tmp_path: Path) -> None:
    """The point of the module: no literal fallback, ever."""
    with pytest.raises(model_limits.UnresolvableError):
        model_limits.resolve_all(tmp_path, {}, sources=(lambda: None, dict))


def test_resolve_refuses_an_unknown_model(tmp_path: Path) -> None:
    answer = {"claude-opus-5": model_limits.ModelLimits("claude-opus-5", 128_000, "docs")}

    with pytest.raises(model_limits.UnresolvableError, match="claude-opus-5"):
        model_limits.resolve("claude-nonexistent", tmp_path, {}, sources=(lambda: answer,))


def test_unreachable_docs_return_none_but_a_broken_page_raises() -> None:
    """The two failure classes must stay distinguishable.

    A network blip should fall through to the snapshot; a page whose layout
    moved must stop everything. Collapsing them is how a transient becomes a
    silent wrong answer (`.claude/rules/persistence-gate-retry.md`).
    """

    def unreachable(_url: str, _timeout: int) -> bytes:
        raise OSError("getaddrinfo ENOTFOUND")

    def reachable_but_broken(_url: str, _timeout: int) -> bytes:
        return b"| Nothing | Useful |\n"

    assert model_limits.fetch_docs(opener=unreachable) is None
    with pytest.raises(model_limits.LayoutChangedError):
        model_limits.fetch_docs(opener=reachable_but_broken)


def test_models_api_returns_none_without_a_credential() -> None:
    """An absent credential is the expected state, not a failure."""
    assert model_limits.fetch_models_api({}) is None


def test_models_api_returns_none_when_the_sdk_call_fails() -> None:
    """A rejected credential falls through to the docs rather than failing the run.

    This is the branch my own probe got wrong: a 401 from a typo'd token and a
    401 from an unauthorized credential type are indistinguishable here, so the
    only safe response is to try the next source.
    """

    def boom(_alias: str) -> object:
        raise RuntimeError("401 authentication_error")

    assert model_limits.fetch_models_api({"ANTHROPIC_API_KEY": "x"}, caller=boom) is None


class _FakeModelInfo:
    """The three `ModelInfo` fields this module reads, and nothing else."""

    def __init__(self, model_id: str, max_tokens: int, max_input_tokens: int) -> None:
        self.id = model_id
        self.max_tokens = max_tokens
        self.max_input_tokens = max_input_tokens


def test_models_api_records_the_resolved_id_not_the_alias() -> None:
    """`claude-haiku-4-5` resolves to a dated snapshot; keep both facts.

    The result is KEYED by the alias the caller asked for — otherwise a lookup
    of the alias would miss — while `model` carries what the runtime actually
    named, which is the part the docs table cannot tell us.
    """
    calls: list[str] = []

    def caller(alias: str) -> object:
        calls.append(alias)
        return _FakeModelInfo("claude-haiku-4-5-20251001", 64_000, 200_000)

    limits = model_limits.fetch_models_api(
        {"CLAUDE_CODE_OAUTH_TOKEN": "x", "KB_MODEL_LIMITS_ALIASES": "claude-haiku-4-5"},
        caller=caller,
    )

    assert calls == ["claude-haiku-4-5"]
    assert limits is not None
    entry = limits["claude-haiku-4-5"]
    assert entry.model == "claude-haiku-4-5-20251001"
    assert entry.max_output_tokens == 64_000
    assert entry.max_input_tokens == 200_000
    assert entry.source == "models-api"


def test_models_api_reads_max_tokens_when_a_credential_exists() -> None:
    calls: list[str] = []

    def caller(alias: str) -> object:
        calls.append(alias)
        return _FakeModelInfo(alias, 128_000, 1_000_000)

    limits = model_limits.fetch_models_api(
        {"CLAUDE_CODE_OAUTH_TOKEN": "x", "KB_MODEL_LIMITS_ALIASES": "claude-opus-5"},
        caller=caller,
    )

    assert calls == ["claude-opus-5"]
    assert limits is not None
    assert limits["claude-opus-5"].max_output_tokens == 128_000
    assert limits["claude-opus-5"].max_input_tokens == 1_000_000
    assert limits["claude-opus-5"].source == "models-api"


def test_snapshot_round_trip_and_delta(tmp_path: Path) -> None:
    first = {"claude-opus-5": model_limits.ModelLimits("claude-opus-5", 8_192, "docs")}
    second = {
        "claude-opus-5": model_limits.ModelLimits("claude-opus-5", 128_000, "docs"),
        "claude-haiku-4-5": model_limits.ModelLimits("claude-haiku-4-5", 64_000, "docs"),
    }

    # The first write has no predecessor, so every model reads as an addition.
    first_delta = model_limits.write_snapshot(tmp_path, first, "2026-08-17")
    assert "+ claude-opus-5: max_output 8192" in first_delta
    assert "no change" in model_limits.write_snapshot(tmp_path, first, "2026-08-17")
    delta = model_limits.write_snapshot(tmp_path, second, "2026-08-18")

    assert "~ claude-opus-5: max_output 8192 -> 128000" in delta
    assert "+ claude-haiku-4-5: max_output 64000" in delta
    read_back = model_limits.read_snapshot(tmp_path)
    assert read_back is not None
    assert read_back["claude-opus-5"].max_output_tokens == 128_000
    assert read_back["claude-opus-5"].source == "snapshot"


def test_delta_reports_every_field_not_just_the_output_ceiling(tmp_path: Path) -> None:
    """The switch from docs to Models API filled in max_input on all four models.

    The first version of `_render_delta` compared only `max_output_tokens` and
    printed *(no change)* for that write — a record whose diff cannot see a
    change, which is the exact failure this module argues against one level up.
    """
    docs_shaped = {"claude-haiku-4-5": model_limits.ModelLimits("claude-haiku-4-5", 64_000, "docs")}
    api_shaped = {
        "claude-haiku-4-5": model_limits.ModelLimits(
            "claude-haiku-4-5-20251001", 64_000, "models-api", max_input_tokens=200_000
        )
    }

    model_limits.write_snapshot(tmp_path, docs_shaped, "2026-08-17")
    delta = model_limits.write_snapshot(tmp_path, api_shaped, "2026-08-18")

    assert "max_input None -> 200000" in delta
    assert "resolved_id claude-haiku-4-5 -> claude-haiku-4-5-20251001" in delta


def test_resolved_id_round_trips_so_the_delta_does_not_cry_wolf(tmp_path: Path) -> None:
    """Re-writing identical data must report no change, dated snapshot included."""
    limits = {
        "claude-haiku-4-5": model_limits.ModelLimits(
            "claude-haiku-4-5-20251001", 64_000, "models-api", max_input_tokens=200_000
        )
    }

    model_limits.write_snapshot(tmp_path, limits, "2026-08-17")

    assert "no change" in model_limits.write_snapshot(tmp_path, limits, "2026-08-18")


def test_absent_snapshot_is_none_not_an_error(tmp_path: Path) -> None:
    assert model_limits.read_snapshot(tmp_path) is None


def test_an_empty_snapshot_raises_rather_than_reading_as_clean(tmp_path: Path) -> None:
    path = tmp_path / model_limits.SNAPSHOT_PATH
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"models": {}}), encoding="utf-8")

    with pytest.raises(model_limits.LayoutChangedError):
        model_limits.read_snapshot(tmp_path)


def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cut the network so the CLI tests exercise the snapshot, not the live page.

    Without this the docs source answers first and the assertions would pass or
    fail on whatever platform.claude.com says today — a test that measures the
    internet rather than the code.
    """

    def unreachable(_url: str, _timeout: int) -> bytes:
        raise OSError("getaddrinfo ENOTFOUND")

    monkeypatch.setattr(model_limits, "_read_url", unreachable)


def _snapshot_only(tmp_path: Path) -> None:
    model_limits.write_snapshot(
        tmp_path,
        {"claude-opus-5": model_limits.ModelLimits("claude-opus-5", 128_000, "docs")},
        "2026-08-17",
    )


def test_cli_reports_and_exits_ok(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _offline(monkeypatch)
    _snapshot_only(tmp_path)

    rc = model_limits.main(tmp_path, ["claude-opus-5"], {})

    assert rc == int(Rc.OK)
    out = capsys.readouterr().out
    assert "max_output= 128000" in out
    assert "source=snapshot" in out


@pytest.mark.parametrize(
    "argv",
    [
        ["--nope"],
        ["claude-nonexistent"],
        ["--write"],
        ["--observed-at"],
    ],
)
def test_cli_rejects_a_malformed_request(
    tmp_path: Path,
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bad ask exits 2, never 0 — `kb-skill-score`'s precedent.

    `--write` with no `--observed-at` is in this list deliberately: writing a
    record with no observation date makes it undatable, which is the same class
    of defect as an unreadable one.
    """
    _offline(monkeypatch)
    _snapshot_only(tmp_path)

    assert model_limits.main(tmp_path, argv, {}) == int(Rc.BAD_REQUEST)


def test_cli_reports_not_run_when_nothing_resolves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No snapshot and no network: 127, never a false OK.

    `NOT_RUN` rather than `OK` is the whole contract — "we did not look" must
    not read as "we looked and it is fine".
    """
    _offline(monkeypatch)

    assert model_limits.main(tmp_path, [], {}) == int(Rc.NOT_RUN)


def test_a_credential_reaches_the_header_its_kind_requires() -> None:
    """An API key is `X-Api-Key`; an auth token is `Authorization: Bearer`.

    The defect this arms: every credential was passed as `auth_token=`, and the
    installed SDK maps the two constructor parameters to DIFFERENT headers
    (`anthropic/_client.py:348,357`). Since `ANTHROPIC_API_KEY` is preferred
    FIRST, a real API key went out as a Bearer token, failed auth, and
    `fetch_models_api` swallowed the failure and fell through to the docs — a
    credential silently unused while the resolver reported `source=docs`.

    It was invisible to every existing test because they inject `caller=` and so
    never reach the constructor. This asserts on the client the constructor
    builds, which needs no network and no live credential.

    Both arms are required: with only the API-key half, passing everything as
    `api_key=` would pass — the mirror of the original defect.
    """

    def headers_of(credential: model_limits.Credential) -> dict[str, str]:
        """The headers the client THIS MODULE builds would actually send.

        `sdk_client` is called, not `anthropic.Anthropic`. The first version of
        this test constructed its own client and asserted on that — so it
        verified the SDK's behaviour, which was never in doubt, and said nothing
        about the code under test. `kb-arms` caught it: restoring the defect
        (`auth_token=` for every credential) left the test GREEN. A test that
        cannot fail is worse than no test, because it reports coverage.
        """
        return dict(model_limits.sdk_client(credential).auth_headers)

    api_key_headers = headers_of(model_limits.Credential(value="sk-test", is_api_key=True))
    assert api_key_headers.get("X-Api-Key") == "sk-test"
    assert "Authorization" not in api_key_headers

    # Bound to a credential-free NAME, and that shape is deliberate: ruff's S106
    # flags a literal passed to an argument called `auth_token`, and S105 then
    # flags a variable whose own name reads as a credential. The sanctioned
    # alternative — widening the tests' per-file ignores with a credential-hygiene
    # rule — would blind every test file to a genuinely hardcoded secret in order
    # to satisfy one line, so the line moved instead.
    sentinel = "oat-test"
    token_headers = headers_of(model_limits.Credential(value=sentinel, is_api_key=False))
    assert token_headers.get("Authorization") == f"Bearer {sentinel}"
    assert "X-Api-Key" not in token_headers


def test_the_credential_kind_is_read_from_the_environment() -> None:
    """Which variable answered decides which header is used.

    The control is the third arm: no credential at all must be `None`, or a
    function that always returned an API-key credential would satisfy the first
    two.
    """
    api = model_limits.credential_from({"ANTHROPIC_API_KEY": "sk-1"})
    assert api is not None
    assert api.is_api_key is True

    oauth = model_limits.credential_from({"CLAUDE_CODE_OAUTH_TOKEN": "oat-1"})
    assert oauth is not None
    assert oauth.is_api_key is False

    assert model_limits.credential_from({}) is None


def test_writing_one_model_does_not_unrecord_the_others(tmp_path: Path) -> None:
    """`--write <model>` refreshes an entry; it must not delete the rest.

    The snapshot is the OFFLINE fallback, so a truncating write is not cosmetic —
    the next resolution with no network simply would not know the dropped models.

    The control is the second assertion: the refreshed model must actually carry
    its NEW value, or a fix that merged the other way (previous wins) would
    satisfy the first.
    """
    both = {
        "claude-opus-5": model_limits.ModelLimits("claude-opus-5", 128_000, "models-api"),
        "claude-haiku-4-5": model_limits.ModelLimits("claude-haiku-4-5", 64_000, "models-api"),
    }
    model_limits.write_snapshot(tmp_path, both, "2026-08-17")

    only_opus = {
        "claude-opus-5": model_limits.ModelLimits("claude-opus-5", 200_000, "models-api"),
    }
    model_limits.write_snapshot(tmp_path, only_opus, "2026-08-18")

    after = model_limits.read_snapshot(tmp_path)
    assert after is not None
    assert set(after) == {"claude-opus-5", "claude-haiku-4-5"}
    assert after["claude-opus-5"].max_output_tokens == 200_000


def test_the_snapshot_is_written_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A torn write would hand the offline fallback half a JSON document.

    Asserted by observing that the repo's atomic helper is the writer, because a
    real torn write cannot be produced deterministically in a test. The arm is
    honest about being a wiring check rather than a durability proof — but wiring
    is exactly what regressed here, since the original used `path.write_text`.
    """
    calls: list[Path] = []
    real = model_limits.atomic.write_text

    def spy(path: Path, text: str) -> None:
        calls.append(path)
        real(path, text)

    monkeypatch.setattr(model_limits.atomic, "write_text", spy)
    model_limits.write_snapshot(
        tmp_path,
        {"claude-opus-5": model_limits.ModelLimits("claude-opus-5", 128_000, "models-api")},
        "2026-08-17",
    )

    assert calls == [tmp_path / model_limits.SNAPSHOT_PATH]


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("{ this is not json", id="torn-write"),
        pytest.param('{"models": {}}', id="empty-models"),
        pytest.param('{"models": {"claude-opus-5": {}}}', id="entry-missing-the-ceiling"),
        pytest.param(
            '{"models": {"claude-opus-5": {"max_output_tokens": "lots"}}}', id="not-a-number"
        ),
    ],
)
def test_a_corrupt_snapshot_is_a_named_failure_not_a_traceback(
    tmp_path: Path, content: str
) -> None:
    """This is the LAST link in the fallback chain — it is reached at the worst moment.

    `read_snapshot` is consulted only when the Models API and the docs are both
    unavailable, so an unhandled `JSONDecodeError` or `KeyError` from inside a
    comprehension surfaced as a raw traceback exactly when the operator had the
    least context. Every shape now reports what is wrong with the FILE.

    The control is the last assertion: a well-formed snapshot must still read
    cleanly, or a `read_snapshot` that raised unconditionally would pass all four.
    """
    path = tmp_path / model_limits.SNAPSHOT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    with pytest.raises(model_limits.LayoutChangedError):
        model_limits.read_snapshot(tmp_path)

    model_limits.write_snapshot(
        tmp_path,
        {"claude-opus-5": model_limits.ModelLimits("claude-opus-5", 128_000, "models-api")},
        "2026-08-17",
    )
    assert model_limits.read_snapshot(tmp_path) is not None


def test_observed_at_refuses_a_flag_as_its_value() -> None:
    """`--observed-at --nope` persisted `--nope` into the committed snapshot as a date.

    The unknown-flag check runs on what REMAINS after the value is consumed, so a
    greedy read swallowed the flag first and nothing downstream objected.

    The control is the second arm: a real date must still parse, or a check that
    rejected every value would satisfy the first.
    """
    assert "--observed-at" in model_limits._parse_argv(["--write", "--observed-at", "--nope"]).error
    assert model_limits._parse_argv(["--write", "--observed-at", "2026-08-17"]).error == ""
