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
