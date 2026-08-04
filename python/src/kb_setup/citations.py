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

#: `<task> rc=<n>` — a gate claim in the five spellings this repo's handoffs
#: actually use: `` `mise run lint` **rc=0** ``, `` `mise run lint` → **rc=0** ``,
#: `` `brain-audit` rc=0 ``, a bare `lint rc=0`, and the table-cell
#: `` | `mise run lint` | **rc=0** at `78f7190` | ``. The optional decoration
#: between the task and its `rc=` is what makes one pattern cover all five; a
#: pattern per spelling would have gone stale the first time someone wrote a
#: sixth — and the fifth was found in the corpus by a review lane after the
#: comment here had already claimed "the four spellings this repo's handoffs
#: actually use". The count in a comment is a measurement, so it can be wrong.
#:
#: At most ONE cell boundary is crossed, so the task is still the token NEAREST
#: the `rc=`. A pattern that skipped arbitrary `|` would attach an exit code to
#: whichever task appeared earliest in the row.
#:
#: `rc=` must be followed by DIGITS — `rc=$?` records HOW an exit code was read
#: and claims nothing about its value.
_GATE_CLAIM_RE = re.compile(
    r"`?(?:mise run )?(?P<task>[A-Za-z][A-Za-z0-9_-]*)`?"
    r"[ \t]*\|?[ \t]*(?:→[ \t]*)?\*{0,2}rc=(?P<rc>\d+)"
)

#: The DISTRIBUTIVE form: `Gates on `f3e233a`, all rc=0: <list of tasks>`. One
#: phrase vouching for four gates, so skipping it would leave the highest-stakes
#: claim in the corpus unchecked.
#:
#: The tasks it distributes over are `mise run <name>` occurrences ONLY, which is
#: a deliberate BOUND and not an oversight: a bare comma-separated list after the
#: colon cannot be told from prose, and `all rc=0: lint, test, currency check`
#: would claim a gate called `currency`. The bound is stated because a
#: bare-name list would be silently skipped rather than reported — measured over
#: all 30 committed handoffs on 2026-08-04, that form occurs **0 times** against
#: 4 occurrences of the `mise run` form, so the recall given up is zero *today*.
#: That count is the condition on the claim, and it moves the moment someone
#: writes one. (Standards lane.)
#:
#: The trailing colon is load-bearing, not punctuation-matching. Without it the
#: parenthetical in `` `mise run kb-gates` **rc=0** (lint/test/brain-audit/eval
#: all rc=0), `mise run lint-docs` `` — one real handoff line — swept up every
#: later `mise run` on the line, manufacturing claims nobody wrote. A colon
#: introduces a list; a closing paren trails one.
_ALL_RC_RE = re.compile(r"\ball\b[^\n:]{0,40}?rc=(?P<rc>\d+)\*{0,2}[ \t]*:")

#: Words that introduce :data:`_ALL_RC_RE` and name no task. Without this, the
#: phrase `all rc=0` reads as a claim about a gate called `all` — a citation the
#: composer would then report as undeclared, which is a true statement about a
#: task that was never claimed.
_DISTRIBUTIVE_WORDS: frozenset[str] = frozenset({"all"})

#: A commit token: a code span that is hex and nothing else. Seven is git's own
#: abbreviation floor and the length this repo's handoffs write.
#:
#: Deliberately unable to match `main`, `origin/main`, or a branch name — and
#: `Gates on `main`, all rc=0` is a real handoff line. A claim bound to a branch
#: is bound to nothing checkable, because the branch has moved since; reading it
#: as a commit would be inventing the binding the whole check exists to demand.
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")

#: A line that ENDS the block above it and starts a new one: a list item, a
#: heading, a table row, or a block quote. Blank lines break a block too.
_BLOCK_BREAK_RE = re.compile(r"^\s*(?:[-*+][ \t]|\d+[.)][ \t]|#{1,6}[ \t]|\||>)")


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


@dataclass(frozen=True)
class GateClaim:
    """A claim that a named gate exited with a particular code.

    ``shas`` is every commit token named in the claim's own BLOCK — the list
    item, paragraph or table row it sits in — and it is a tuple rather than a
    single value because 0, 1 and 2+ are three different answers. Zero is a
    claim bound to no commit; two is a block whose binding is ambiguous. Both
    are things the composer must be able to say, and a `str | None` can only
    say one of them.

    ``task`` is whatever token preceded the `rc=`, NOT a known gate. This module
    cannot know which tasks this repo declares, and asking it to would move a
    filesystem question into a text parser (#143). The composer filters.
    """

    task: str
    rc: int
    shas: tuple[str, ...]
    line: int

    @property
    def sha(self) -> str:
        """The one commit this claim is bound to. Empty unless there is exactly one.

        A named accessor rather than `shas[0]` at each call site: zero and two
        are real answers a caller must handle first, and `[0]` reads as though
        they were not — it raises on the first and silently picks on the second.
        Returning `""` for both makes the unhandled case fall out as "names no
        commit" rather than as a wrong binding.
        """
        return self.shas[0] if len(self.shas) == 1 else ""


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


def _blocks(stripped: str) -> list[tuple[int, int]]:
    """Character bounds of each block in ``stripped`` — the claim-binding unit.

    A block is one list item, paragraph, table row or block quote. It is the
    unit because a handoff names commits everywhere — in gotchas, in review
    tables, in its own header — so binding a gate claim to the nearest PRECEDING
    sha in the document would let the paragraph above a gate list vouch for it.
    A claim inherits only what its own block says.
    """
    lines = stripped.split("\n")
    offsets: list[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1

    bounds: list[tuple[int, int]] = []
    start: int | None = None
    for i, line in enumerate(lines):
        if (not line.strip() or _BLOCK_BREAK_RE.match(line)) and start is not None:
            bounds.append((offsets[start], offsets[i]))
            start = None
        if line.strip() and start is None:
            start = i
    if start is not None:
        bounds.append((offsets[start], len(stripped)))
    return bounds


def gate_claims(text: str) -> list[GateClaim]:
    """Every claim that a gate exited with a particular code.

    Two forms, both real and both from this repo's committed handoffs: a DIRECT
    `` `mise run lint` **rc=0** ``, and a DISTRIBUTIVE `all rc=0: <list>` whose
    single phrase vouches for every task after it in the block.

    A direct claim WINS over a distributive one for the same task in the same
    block. That is not tidiness: `` `mise run kb-gates` **rc=0** (lint/test all
    rc=0), `mise run lint-docs` **rc=0** `` would otherwise yield two claims on
    `lint-docs` that happen to agree, and agreeing by luck is not verification.
    """
    stripped = strip_fences(text)
    claims: list[GateClaim] = []
    for start, end in _blocks(stripped):
        body = stripped[start:end]
        first_line = stripped.count("\n", 0, start) + 1

        def line_of(offset: int, body: str = body, first_line: int = first_line) -> int:
            return first_line + body.count("\n", 0, offset)

        shas = tuple(
            m.group("body") for m in _SPAN_RE.finditer(body) if _COMMIT_RE.match(m.group("body"))
        )
        claimed: set[str] = set()
        for m in _GATE_CLAIM_RE.finditer(body):
            task = m.group("task")
            if task in _DISTRIBUTIVE_WORDS:
                continue
            claimed.add(task)
            claims.append(GateClaim(task, int(m.group("rc")), shas, line_of(m.start())))
        # Each phrase owns the text up to the NEXT phrase, not to the end of the
        # block. Scanning to the end let `all rc=0: <list>; all rc=1: <list>`
        # bind the SECOND list to rc=0 and then suppress the second phrase via
        # `claimed` — so the parser reported the opposite of what was written,
        # and the checker would go on to confirm it. A manufactured claim is
        # worse than a missed one: a miss leaves the handoff unchecked, while
        # this one puts a verdict behind words nobody wrote. (Cold lane.)
        phrases = list(_ALL_RC_RE.finditer(body))
        # Deduped on (task, rc), NOT on task alone. `claimed` holds only the
        # DIRECT claims, because a direct rc genuinely overrides a distributive
        # one — but two distributive phrases naming the same task with DIFFERENT
        # codes are two claims that contradict each other, and suppressing the
        # second one hid the contradiction from the checker entirely. Emitting
        # both means one of them FAILS against the record, which is how a reader
        # gets told. (Cold lane, round 2; pre-existing, in the path this round
        # already touched.)
        distributed: set[tuple[str, int]] = set()
        for i, phrase in enumerate(phrases):
            rc = int(phrase.group("rc"))
            stop = phrases[i + 1].start() if i + 1 < len(phrases) else len(body)
            for cite in _TASK_RE.finditer(body, phrase.end(), stop):
                name = cite.group(1)
                if name in claimed or (name, rc) in distributed:
                    continue
                distributed.add((name, rc))
                claims.append(GateClaim(name, rc, shas, line_of(cite.start())))
    return claims


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
