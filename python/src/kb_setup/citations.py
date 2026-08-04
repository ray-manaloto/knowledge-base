"""Extract the checkable claims from an authored markdown document.

PURE TEXT-IN / DATA-OUT. This module knows nothing about handoffs, this repo's
layout, or the filesystem — it turns prose into citations, and `kb_setup.resolve`
decides whether each one holds. Kept separate so the next checker (a goal
document, a research report) reuses the parsing rather than growing a second
copy of these regexes (#143, "one primitive with a single caller").

WHY THE EXCLUSIONS OUTWEIGH THE EXTRACTIONS. #145's acceptance criteria say a
checker whose first run emits false positives is one nobody trusts again, and
that is not hypothetical: the naive version of this check, run by hand over a
real handoff, produced **4 false positives out of 9** by treating every
backticked token containing a separator as a repo-relative path. So the module
is deliberately biased toward under-reporting:

* only a backticked span is a citation at all — prose is never scanned for paths;
* only a span that is ONE whole token can be a path, so a command is not a path;
* a separator-bearing token qualifies only if it ends in `/` or carries a known
  file extension, which is what keeps `feat/145-kb-handoff-check` and
  `origin/main` from reading as broken paths;
* a bare filename qualifies only on a known extension, which is what keeps
  `kb_setup.hook_guard`, `0.9.31` and `2026-08-03` out.

Each of those rules costs recall — `sources/media` cited without a trailing
slash is silently skipped — and that is the intended direction. A miss this
checker never reports is a claim a human still reads; a false positive is a
claim a human learns to ignore.

THE `(absent)` MARKER. A path can be cited precisely BECAUSE it does not exist:
this repo's handoffs name `docs/agents/issue-tracker.md`, the path an external
skill hardcodes and will not find. Writing `` `path` (absent) `` marks that, and
the marker is checked in BOTH directions by `kb_setup.handoff` — a citation
marked absent that actually resolves is itself a failure. That is what stops the
marker becoming a silencer: it cannot be applied blanket-fashion without
producing the failures it was reached for to avoid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: File extensions a bare token must carry to be treated as a filename. An
#: ALLOWLIST rather than "anything after the last dot", because the alternative
#: reads `kb_setup.hook_guard`, `0.9.31` and `2026-08-03` as filenames — all
#: three occur in every handoff, so the permissive form is a guaranteed false
#: positive rather than a hypothetical one. The cost is that a citation with an
#: unlisted extension is skipped, which is the safe direction.
_KNOWN_EXT: frozenset[str] = frozenset(
    {
        "c",
        "cfg",
        "cpp",
        "csv",
        "env",
        "gitignore",
        "go",
        "graphml",
        "h",
        "hpp",
        "html",
        "ini",
        "jpg",
        "js",
        "json",
        "jsonl",
        "lock",
        "m4a",
        "manifest",
        "md",
        "mp3",
        "pdf",
        "pkl",
        "png",
        "py",
        "rs",
        "sh",
        "sql",
        "svg",
        "toml",
        "ts",
        "txt",
        "wav",
        "xml",
        "yaml",
        "yml",
    }
)

#: Characters that make a token a pattern, a template, or an abbreviation
#: rather than a path. `<` and `>` cover the `review-<sha>-<lane>.md`
#: placeholder form; `^`/`$` cover a quoted regex fragment; and `…` covers the
#: elision this repo writes constantly when abbreviating a sha
#: (`review-f19b18d6…-cold.md`). That last one was the single largest
#: false-positive class measured over all 28 committed handoffs — an elided path
#: names no file by construction, so reporting it as missing says nothing.
_NON_PATH_CHARS: frozenset[str] = frozenset("*?[]{}<>|\\$!\"'`^…")

#: Bare dotfiles that ARE filenames despite having an empty stem. Needed because
#: the stem rule below exists to reject `.md` / `.py` / `.json` — an extension
#: named in prose ("every `.md` file") is not a citation — and that rule would
#: otherwise take `.gitignore` with it.
_DOTFILES: frozenset[str] = frozenset(
    {".dockerignore", ".editorconfig", ".env", ".gitattributes", ".gitignore"}
)

#: A code span: a run of N backticks closed by a run of N. Matching only SINGLE
#: backticks split a genuine double-backtick escape span containing a literal
#: backtick (`` ``docs/gone.md`x`` ``) and manufactured a path citation out of the
#: fragments. The runs are MAXIMAL — a backtick may not sit either side of a
#: delimiter — or a bare ``` ``` ``` line parses as a span containing a backtick.
#: Excludes newlines so an unclosed backtick cannot swallow the rest of the
#: document into one enormous "citation".
_SPAN_RE = re.compile(r"(?P<ticks>`+)(?!`)(?P<body>[^\n]+?)(?<!`)(?P=ticks)(?!`)")

#: The explicit "cited because it does not exist" marker, immediately after the
#: closing backtick. Anchored to the span rather than to the line so it can only
#: ever exempt the one citation its author pointed at.
_ABSENT_MARKER_RE = re.compile(r"[ \t]?\(absent\)")

#: A fenced code block delimiter, CAPTURING its run length. Fenced content is
#: EXAMPLE text — the paths in it need not exist — so it is blanked before
#: extraction. Three CommonMark rules are load-bearing here, and each was found
#: leaking or swallowing real citations without it: the indent is capped at three
#: spaces (deeper is an indented code line, not a delimiter), a CLOSING fence may
#: carry no info string (so ```` ```python ```` mid-block is content), and the run
#: must be at least as long and of the same character.
#: The length matters: a four-backtick block exists precisely to
#: quote a three-backtick one, and toggling on any fence line let the inner pair
#: close and reopen the outer block, leaking example content out as real
#: citations (and, with the nesting reversed, swallowing real content).
_FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")

#: `path:12` or `path:12-19`.
_LINE_REF_RE = re.compile(r"^(?P<path>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$")

#: `mise run <name>`. The name must start with a letter, which is what stops
#: `mise run <task>` (a placeholder) from being read as a task called `<task>`.
#:
#: A dotted tail is captured DELIBERATELY: without it the match stopped at the
#: dot, so `mise run kb-build.typo` was read as the declared task `kb-build` and
#: reported fine — a typo in a command the next session would run, passing. The
#: tail requires a following name character, so a sentence-final `mise run lint.`
#: still yields `lint` rather than a citation nothing declares.
_TASK_RE = re.compile(r"\bmise run ([A-Za-z][A-Za-z0-9_:-]*(?:\.[A-Za-z0-9_:-]+)*)")


@dataclass(frozen=True)
class Span:
    """One backticked code span, with where it appeared and how it was marked."""

    text: str
    line: int
    marked_absent: bool = False


@dataclass(frozen=True)
class PathCitation:
    """A token claimed to name a path in this repo."""

    text: str
    line: int
    marked_absent: bool = False


@dataclass(frozen=True)
class LineCitation:
    """A `file:line` (or `file:start-end`) reference.

    ``start``/``end`` are equal for a single-line reference, so a consumer never
    has to branch on which form was written.
    """

    path: str
    start: int
    end: int
    line: int
    marked_absent: bool = False


@dataclass(frozen=True)
class TaskCitation:
    """A `mise run <name>` occurrence."""

    name: str
    line: int


def strip_fences(text: str) -> str:
    """Blank out fenced code blocks, PRESERVING the line count.

    Line-for-line replacement rather than deletion: every citation carries the
    line it was found on, and a checker that reports the wrong line is the
    `:1836`-for-`:1830` defect this whole module exists to catch, reintroduced
    inside the catcher.
    """
    out: list[str] = []
    opener = ""
    for line in text.splitlines():
        m = _FENCE_RE.match(line)
        if m is None:
            out.append("" if opener else line)
            continue
        fence = m.group("fence")
        if not opener:
            opener = fence
        elif fence[0] == opener[0] and len(fence) >= len(opener) and not m.group("info").strip():
            # CommonMark: only a run at least as long, of the same character,
            # closes the block. Anything shorter is content.
            opener = ""
        out.append("")
    return "\n".join(out)


def code_spans(text: str) -> list[Span]:
    """Every backticked span outside a fenced block, with its 1-indexed line."""
    stripped = strip_fences(text)
    spans: list[Span] = []
    for m in _SPAN_RE.finditer(stripped):
        marker = _ABSENT_MARKER_RE.match(stripped, m.end())
        spans.append(
            Span(
                text=m.group("body"),
                line=stripped.count("\n", 0, m.start()) + 1,
                marked_absent=marker is not None,
            )
        )
    return spans


def _has_known_ext(token: str) -> bool:
    """True when the token's last segment names a file we would recognise.

    Requires a non-empty stem, which is what rejects a bare extension named in
    prose (`.md`, `.py`, `.json`) without also rejecting real dotfiles — those
    are allowlisted, since a stem rule cannot tell `.gitignore` from `.md`.
    """
    last = token.rsplit("/", 1)[-1]
    if last in _DOTFILES:
        return True
    stem, _, ext = last.rpartition(".")
    return bool(stem) and ext.lower() in _KNOWN_EXT


def _looks_like_a_host(token: str) -> bool:
    """True when the first segment is a hostname, e.g. `code.claude.com/docs/x.md`.

    A schemeless URL is path-shaped and is not a repo-relative path. The dot must
    be past position 0, or every `.claude/…` and `.agent/…` citation — the two
    most common in this repo — would be excluded with it.
    """
    first = token.split("/", 1)[0]
    return "." in first[1:]


def is_path_like(token: str) -> bool:
    """Whether a token is a repo-relative path claim at all.

    Everything this returns False for is excluded BY CONSTRUCTION and never
    reported — criterion 3. The order below is deliberate: the cheap categorical
    rejections (whitespace, flags, URLs, globs) come before the shape test, so a
    token is only ever judged on its extension once it is known to be a bare
    filesystem-looking token.
    """
    if not token or any(c.isspace() for c in token):
        return False
    if token.startswith(("-", "~", "/", ".../")):
        # Flags; and `~`/`/` are outside the repo, so this module cannot
        # adjudicate them either way — silence is the honest answer, not a miss.
        return False
    if "://" in token or token.startswith("git@"):
        return False
    if any(c in _NON_PATH_CHARS for c in token):
        return False
    if "/" in token:
        return not _looks_like_a_host(token) and (token.endswith("/") or _has_known_ext(token))
    return _has_known_ext(token)


def _single_token(span: Span) -> str | None:
    """The span's content when it is one whole token, else None."""
    return span.text if span.text and not any(c.isspace() for c in span.text) else None


def line_citations(text: str) -> list[LineCitation]:
    """Every `file:line` / `file:start-end` reference in the document."""
    found: list[LineCitation] = []
    for span in code_spans(text):
        token = _single_token(span)
        if token is None:
            continue
        m = _LINE_REF_RE.match(token)
        if m is None or not is_path_like(m.group("path")):
            continue
        start = int(m.group("start"))
        end = int(m.group("end")) if m.group("end") else start
        found.append(
            LineCitation(
                path=m.group("path"),
                start=start,
                end=end,
                line=span.line,
                marked_absent=span.marked_absent,
            )
        )
    return found


def path_citations(text: str) -> list[PathCitation]:
    """Every path claim that is NOT a `file:line` reference.

    The exclusion is not tidiness: a `file:line` whose path is wrong would
    otherwise produce two findings for one mistake, and a reader fixing the
    second would find the first already gone.
    """
    found: list[PathCitation] = []
    for span in code_spans(text):
        token = _single_token(span)
        if token is None or not is_path_like(token):
            continue
        if _LINE_REF_RE.match(token):
            continue
        found.append(
            PathCitation(
                text=token,
                line=span.line,
                marked_absent=span.marked_absent,
            )
        )
    return found


def task_citations(text: str) -> list[TaskCitation]:
    """Every `mise run <name>` in the document, backticked or in plain prose.

    Scanned over the whole (fence-stripped) text rather than over code spans
    only: `mise run x` is unambiguous wherever it appears, and handoffs write it
    both ways. Fenced blocks stay excluded — they are examples.
    """
    stripped = strip_fences(text)
    return [
        TaskCitation(name=m.group(1), line=stripped.count("\n", 0, m.start()) + 1)
        for m in _TASK_RE.finditer(stripped)
    ]
