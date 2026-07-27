"""Tests for `kb-setup query` — the kb-query task's `--prose` form.

What is actually under test is WHICH CORPUS ANSWERED. Everything else this
wrapper does is pass-through, and a wrapper that quietly resolved the wrong
graph would still print a plausible answer — which is the failure mode that
makes a scoped corpus worth having in the first place.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import graphify_ops, prose

if TYPE_CHECKING:
    import pytest


class _Recorder:
    """Stands in for `subprocess.run`, capturing the argv it was handed."""

    def __init__(self) -> None:
        self.argv: list[str] | None = None

    def __call__(self, argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.argv = list(argv)
        return subprocess.CompletedProcess(argv, 0)


def _repo(tmp_path: Path, *, full: bool = True, prose_graph: bool = True) -> Path:
    """A repo root holding whichever of the two graphs the case needs."""
    out = tmp_path / "graphify-out"
    out.mkdir()
    if full:
        (out / "graph.json").write_text("{}")
    if prose_graph:
        (out / prose.PROSE_GRAPH_NAME).write_text("{}")
    return tmp_path


def _run(
    monkeypatch: pytest.MonkeyPatch, repo: Path, args: list[str]
) -> tuple[int, list[str] | None]:
    recorder = _Recorder()
    monkeypatch.setattr(graphify_ops.subprocess, "run", recorder)
    return graphify_ops.query(repo, args), recorder.argv


def test_the_default_form_pins_the_full_graph(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Never left to the process cwd — graphify's default is cwd-relative.

    Invoked from the repo root it silently agrees; invoked from anywhere else it
    silently answers from another corpus.
    """
    repo = _repo(tmp_path)
    rc, argv = _run(monkeypatch, repo, ["a question"])
    assert rc == 0
    assert argv is not None
    assert argv[argv.index("--graph") + 1] == str(repo / "graphify-out" / "graph.json")


def test_the_prose_form_pins_the_derived_graph(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CONTROL ARM for the above: the flag has to change the corpus.

    A wrapper that accepted `--prose` and queried the same graph would pass the
    default test and every smoke check, while answering from the corpus the flag
    exists to avoid.
    """
    repo = _repo(tmp_path)
    rc, argv = _run(monkeypatch, repo, ["a question", graphify_ops.PROSE_FLAG])
    assert rc == 0
    assert argv is not None
    assert argv[argv.index("--graph") + 1] == str(repo / "graphify-out" / prose.PROSE_GRAPH_NAME)


def test_the_prose_flag_is_not_forwarded_to_graphify(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """It is this wrapper's flag; graphify has never heard of it."""
    _, argv = _run(monkeypatch, _repo(tmp_path), ["q", graphify_ops.PROSE_FLAG])
    assert argv is not None
    assert graphify_ops.PROSE_FLAG not in argv


def test_other_arguments_pass_through_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The wrapper adds a corpus; it is not a re-implementation of the CLI."""
    _, argv = _run(monkeypatch, _repo(tmp_path), ["q", "--budget", "8000", "--dfs"])
    assert argv is not None
    # argv[0] is a RESOLVED path, not the bare name: `graphify_exe` asks mise
    # rather than trusting PATH order (#40), so asserting the literal "graphify"
    # here would pin the very behaviour that was removed. The binary's identity
    # is still checked — by name, not by how it was found.
    assert Path(argv[0]).name == "graphify"
    assert argv[1] == "query"
    assert argv[2:6] == ["q", "--budget", "8000", "--dfs"]


def test_an_explicit_graph_is_left_alone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A caller naming a corpus outranks the default, and is not doubled up."""
    _, argv = _run(monkeypatch, _repo(tmp_path), ["q", "--graph", "/elsewhere/graph.json"])
    assert argv is not None
    assert argv.count("--graph") == 1
    assert argv[argv.index("--graph") + 1] == "/elsewhere/graph.json"


def test_prose_and_an_explicit_graph_together_is_an_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two corpora named, no sensible winner — so neither one silently wins.

    A precedence rule here would mean the answer came from a corpus the caller
    did not choose, which is exactly the confusion the flag exists to remove.
    """
    rc, argv = _run(
        monkeypatch,
        _repo(tmp_path),
        ["q", graphify_ops.PROSE_FLAG, "--graph", "/elsewhere/graph.json"],
    )
    assert rc == 2
    assert argv is None, "graphify must not run when the corpus is ambiguous"


def test_a_missing_prose_graph_names_the_task_that_derives_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing corpus must name its fix — and the RIGHT one of the two tasks."""
    repo = _repo(tmp_path, prose_graph=False)
    rc, argv = _run(monkeypatch, repo, ["q", graphify_ops.PROSE_FLAG])
    assert rc == 2
    assert argv is None, "graphify must not run against a corpus that is not there"
    assert "kb-prose" in capsys.readouterr().err


def test_a_missing_full_graph_names_the_build_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTROL ARM: the two absences are different, and must not collapse.

    Pointing both at one task would send a reader who is missing the derived
    graph into a full rebuild, and a reader who is missing the built graph into
    a derivation that cannot run.
    """
    repo = _repo(tmp_path, full=False)
    rc, argv = _run(monkeypatch, repo, ["q"])
    assert rc == 2
    assert argv is None
    assert "kb-build" in capsys.readouterr().err


def test_the_attached_graph_form_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--graph=<path>` is not a graphify flag, and forwarding it answers wrong.

    Probed 2026-07-25 from a scratch directory: `graphify query q
    --graph=<abs path>` exits 1 with `graph file not found:
    /private/tmp/graphify-out/graph.json`. graphify DROPS the argument and falls
    back to the cwd-relative default — so a caller who writes the attached form
    and happens to be in a directory holding a `graphify-out/` gets a confident
    answer from a corpus they did not name. Rejected rather than forwarded.
    """
    rc, argv = _run(monkeypatch, _repo(tmp_path), ["q", "--graph=/elsewhere/graph.json"])
    assert rc == 2
    assert argv is None
    assert "attached form" in capsys.readouterr().err


def test_the_attached_graph_form_is_rejected_alongside_prose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The combination the standalone-only check used to wave through.

    `--prose --graph=/x` read as prose-only, so the wrapper appended a SECOND
    graph selection and the ambiguity error never fired (caught in review of
    PR #31).
    """
    rc, argv = _run(
        monkeypatch,
        _repo(tmp_path),
        ["q", graphify_ops.PROSE_FLAG, "--graph=/elsewhere/graph.json"],
    )
    assert rc == 2
    assert argv is None


# --- the `--idf` form (knowledge-base#12 P1) ----------------------------------
#
# `--idf` never shells out, so `_Recorder` cannot observe it. What matters
# instead is ARGUMENT HANDLING: this path silently ignoring a flag it cannot
# honour is exactly the "answer read as if the flag applied" failure the whole
# wrapper exists to prevent.


def test_the_idf_flag_is_not_forwarded_to_graphify(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`--idf` is ours, not graphify's — it must never reach the subprocess."""
    recorder = _Recorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    graphify_ops.query(_repo(tmp_path), ["q", "--prose"])
    assert recorder.argv is not None
    assert graphify_ops.IDF_FLAG not in recorder.argv


def test_top_is_validated_by_the_conversion_that_consumes_it() -> None:
    """REGRESSION (CodeRabbit, PR #33): `--top ²` raised instead of erroring.

    `str.isdigit()` is True for any Numeric_Type=Digit character, including
    superscripts, while `int()` accepts only Numeric_Type=Decimal — so
    validating with one predicate and converting with another leaves a gap that
    escapes as an unhandled `ValueError` rather than the parser's message.
    Measured: `"²".isdigit()` is True and `int("²")` raises.

    The fix is to let the conversion BE the validation. Pinned here in both
    directions, because a parser that raises where it should explain is
    indistinguishable from a crash to whoever typed the flag.
    """
    assert "²".isdigit()  # the trap, stated so the fixture cannot rot
    assert isinstance(graphify_ops._parse_idf_args(["q", "--top", "²"]), str)


def test_top_rejects_zero_and_non_numbers_and_accepts_a_positive_integer() -> None:
    parse = graphify_ops._parse_idf_args
    assert isinstance(parse(["q", "--top", "0"]), str)
    assert isinstance(parse(["q", "--top", "abc"]), str)
    assert isinstance(parse(["q", "--top"]), str)
    parsed = parse(["q", "--top", "8"])
    assert not isinstance(parsed, str)
    assert parsed.top == 8


def test_a_graphify_only_flag_is_rejected_rather_than_ignored() -> None:
    """`--budget` steers graphify's traversal, and this path has no traversal.

    Forwarding it is impossible and ignoring it is worse than failing: the
    caller would read a ranked list as though a budget had shaped it.
    """
    error = graphify_ops._parse_idf_args(["q", "--budget", "3000"])
    assert isinstance(error, str)
    assert "--budget" in error


def test_the_question_is_required() -> None:
    assert isinstance(graphify_ops._parse_idf_args([]), str)
    assert isinstance(graphify_ops._parse_idf_args(["--top", "5"]), str)


def test_the_words_of_an_unquoted_question_are_rejoined() -> None:
    """A shell that split the question must not change what was asked."""
    parsed = graphify_ops._parse_idf_args(["how", "does", "X", "work"])
    assert not isinstance(parsed, str)
    assert parsed.question == "how does X work"


def test_an_explicit_graph_is_honoured_by_the_idf_path() -> None:
    parsed = graphify_ops._parse_idf_args(["q", "--graph", "/somewhere/other.json"])
    assert not isinstance(parsed, str)
    assert parsed.graph == Path("/somewhere/other.json")


def test_a_missing_default_corpus_names_the_task_that_derives_it(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    rc = graphify_ops.query(_repo(tmp_path, prose_graph=False), ["q", graphify_ops.IDF_FLAG])
    assert rc == 2
    assert "kb-prose" in capsys.readouterr().err


def test_a_missing_explicit_graph_does_not_name_that_task(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """REGRESSION (CodeRabbit, PR #33): the hint named a task that cannot help.

    `mise run kb-prose` writes the DEFAULT corpus. Telling someone who passed
    their own `--graph` to run it points at a command that would not produce the
    file they asked for — a remediation hint that sends the reader somewhere
    else entirely.
    """
    missing = str(tmp_path / "nope.json")
    rc = graphify_ops.query(_repo(tmp_path), ["q", graphify_ops.IDF_FLAG, "--graph", missing])
    assert rc == 2
    err = capsys.readouterr().err
    assert "kb-prose" not in err
    assert missing in err
