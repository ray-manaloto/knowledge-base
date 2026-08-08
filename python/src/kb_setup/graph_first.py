# Copyright (c) 2026 Raymond Manaloto
"""PreToolUse guard: DENY a BROAD source search until the graph has been queried.

Ray, 2026-08-08 (#253). The measurement that bought this module: one session ran
**0 graphify/kb-query calls against 19 direct source reads** while the graphify
hook printed ``MANDATORY … you MUST run graphify query`` on nearly every one of
them. A 100% violation rate on a directive that announced itself every time.

The A/B is already in hand, on the same agent and in this same repo:

===================  =============================  ==============
directive            enforcement                    measured rate
===================  =============================  ==============
no bare interpreter  :mod:`kb_setup.hook_guard`     62 -> **0**
                     **DENIES**
graph-first          the graphify hook only         **0 of 19**
                     **WARNS**
===================  =============================  ==============

A hook that denies changes behaviour; a hook that warns does not. That is now
measured twice here rather than argued (`mise-tasks-only.md` § Enforcement
layers: *markdown alone is "relying on the LLM", so it is never the only layer*).

Scope, verbatim from Ray's clear-prep interview and NOT to be relitigated:

    DENY a Grep/rg with no file path (directory- or repo-wide) until a graph
    query has run this session; ALLOW Read of a named file and Grep scoped to
    one file.

    No escape — run the query.

The target is **orientation**, which is the job the graph replaces. Reading a
named file to change a specific line is not orientation and stays unblocked. An
override token was offered and REJECTED: *an escape hatch I can invoke is one I
will invoke.*

Precision, not evasion, is the risk this module manages. Every measured defect in
this repo's guard family has been a false positive
(`a-guards-false-positives-are-text-about-the-guard`), so every ambiguous input
resolves to ALLOW: an unparsable command, an unknown session, an unwritable
state directory, a path that does not exist. A guard that blocks legitimate work
gets switched off by the humans it annoys, which costs more than the orientation
it saves.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

#: A graph query — the thing that unblocks the session.
#:
#: Deliberately NOT `graphify query`, which :func:`kb_setup.hook_guard.decide`
#: denies: a command that never runs cannot orient anyone, and crediting it would
#: hand out the unblock for free. Only the forms this repo actually permits count
#: — the `kb-query` task, and the read-only introspection verbs that have no task
#: equivalent (`mise-tasks-only.md`).
_GRAPH_QUERY = re.compile(r"\bmise\s+run\s+kb-query\b|\bgraphify\s+(?:explain|path|god-nodes)\b")

#: Searchers that walk a TREE by default. `grep` is absent on purpose — plain
#: `grep pattern file` is not a tree walk, so it is handled by `_GREP_RECURSIVE`.
_TREE_SEARCHERS = frozenset({"rg", "ag", "ack", "ripgrep"})

#: `grep` only recurses when told to. `-r`/`-R` may arrive bundled (`-rn`).
_GREP_RECURSIVE = re.compile(r"^-[A-Za-z]*[rR]")

#: File extensions that make a target SOURCE. Kept identical to
#: `kb_setup.session_reflect._SOURCE_READ`, because that detector is what
#: MEASURES the ratio this guard exists to move — two different answers to "is
#: this source?" would make the guard and its own scoreboard disagree.
_SOURCE_EXT = frozenset({".py", ".pkl", ".toml", ".js", ".ts"})

#: In-repo directories that hold prose, logs, corpus input or derived output —
#: never the source a graph query would have oriented you in. Searching them is
#: not orientation, so acceptance criterion 3 requires they never deny.
#:
#: `/tmp` and friends are deliberately ABSENT: an absolute path outside the
#: project root is handled by :func:`_is_prose_target` as a rule rather than a
#: list. That covers every scratch location at once instead of the three anyone
#: happens to remember — and it removed the only reason this module would have
#: needed an S108 suppression, which `zero-skip-policy.md` would have required
#: Ray to approve. A lint that pushes you to a better rule is not an obstacle.
_PROSE_ROOTS = ("docs", "raw", "reflections", "sources", ".agent", "graphify-out")

#: `--glob`/`--type`/`--include` restrict a tree walk to a file class. When every
#: restriction names a non-source class, the walk cannot reach source and must
#: not deny.
_RESTRICT_FLAGS = ("-g", "--glob", "-t", "--type", "--include")

_REASON = (
    "Query the graph before searching the tree. This is orientation, which is the "
    "job the graph replaces — and the reason it is a DENY rather than a warning is "
    "measured: the warning was ignored 19 times out of 19 in one session (#253).\n\n"
    "Run this first:\n\n"
    '    mise run kb-query -- "{question}"\n\n'
    "Then this search is unblocked for the rest of the session. Not denied: `Read` "
    "of a named file, a search scoped to ONE file, and any search of prose, logs "
    "or /tmp. There is no override token, by Ray's explicit decision — an escape "
    "hatch I can invoke is one I will invoke. (kb_setup.graph_first)"
)


def _state_path(root: Path, session_id: str) -> Path:
    """Where this session's "the graph has been queried" marker lives.

    Keyed by `session_id`, which the PreToolUse payload carries (verified against
    a real captured payload, not assumed). That key IS the invalidation rule and
    is why no TTL exists: a new session gets a new id and starts blocked again,
    which is exactly the scope of the directive. `.agent/state/` is the
    conventional home (`agent-artifact-conventions.md`) and is gitignored, so the
    marker never travels between machines.
    """
    return root / ".agent" / "state" / "graph-first" / f"{session_id}.queried"


def has_queried(root: Path, session_id: str) -> bool:
    """Has a graph query run in this session? Unreadable state means YES (allow)."""
    if not session_id:
        return True
    try:
        return _state_path(root, session_id).exists()
    except OSError:
        return True


def note_query(root: Path, session_id: str, command: str) -> None:
    """Record the marker when `command` is a graph query. Never raises.

    Called from the PreToolUse hook, so it fires when the query is ISSUED rather
    than when it succeeds. That is the optimistic direction on purpose: the
    pessimistic one would need a second PostToolUse hook, and a failed query that
    unblocks a search is a far cheaper error than a successful query that does
    not.
    """
    if not session_id or not _GRAPH_QUERY.search(command):
        return
    try:
        path = _state_path(root, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    except OSError:
        return


#: A heredoc body is DATA, never a command — everything from ``<<TAG`` onward is
#: payload the shell hands to a program. :mod:`kb_setup.hook_guard` imports THIS
#: pattern rather than keeping its own: both guards need the identical answer to
#: "where do the shell's commands stop?", and hook_guard measured what happens
#: when a guard reads a heredoc body as code — it denied the very commit message
#: documenting itself. One definition, enforced in both places, is the same shape
#: as `hook_guard.decide` being shared with `skill_lint`.
HEREDOC = re.compile(r"<<-?\s*'?\"?\w+")


def _segments(command: str) -> list[tuple[str, bool]]:
    """`command` split into (segment, reads_stdin) pairs.

    `reads_stdin` marks a segment whose input is a PIPE rather than the tree.
    `mise run kb-query -- "x" | rg foo` searches bytes already in hand — bounding
    output, not orienting — and denying it would punish the exact habit this
    guard exists to encourage. That is the same shape as the `_last_arg`
    redirect defect in `session_reflect`, which reported two properly-armed
    probes as UNARMED because each sent its output to its own log.

    The split is QUOTE-AWARE, walked character by character rather than done with
    `re.split`. A regex cannot see quoting, so `git commit -m "docs && rg decide"`
    — an ordinary commit — split into a segment reading `rg decide` and was
    DENIED (cold lane, P2). That is the same class as every other measured defect
    in this repo's guards: text ABOUT a search read as a search.
    """
    body = HEREDOC.split(command, maxsplit=1)[0]
    out: list[tuple[str, bool]] = []
    piped, quote, start, i = False, "", 0, 0
    while i < len(body):
        ch = body[i]
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif (sep := _separator_at(body, i)) is not None:
            out.append((body[start:i], piped))
            piped = sep == "|"
            i += len(sep)
            start = i
            continue
        i += 1
    out.append((body[start:], piped))
    return out


def _separator_at(body: str, i: int) -> str | None:
    """The shell separator starting at `body[i]`, longest first, else None.

    Longest-first matters: `&&` and `||` must be recognised before the single
    `&`/`|`, or a `&&` would be read as a pipe and the following segment wrongly
    treated as reading stdin — which is an ALLOW, the dangerous direction.
    """
    for sep in ("||", "&&", ";", "&", "|", "\n"):
        if body.startswith(sep, i):
            return sep
    return None


def _words(segment: str) -> list[str]:
    """Shell words of one segment; whitespace-split when the quoting is unbalanced.

    Splitting on separators before `shlex` can cut a quoted `;` in half, leaving a
    fragment `shlex` refuses. Falling back rather than dropping the segment keeps
    the guard's answer approximate instead of absent — and the approximation errs
    toward ALLOW, since a mangled fragment rarely still looks like a tree search.
    """
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def _restricted_to_prose(words: list[str]) -> bool:
    """Do `--glob`/`--type`/`--include` restrictions exclude every source class?

    True only when at least one restriction exists and NONE of them can match a
    source extension — `rg TODO -g '*.md'` cannot reach a `.py` file, so it is not
    orientation. An unrecognised restriction returns False (deny stays possible),
    because a filter this cannot read is not a filter this can trust.

    A NEGATED glob is the case that made that last sentence load-bearing.
    `rg -g '!*.md' decide .` names markdown and reaches every source file in the
    repo — the exact inverse of the positive form, and graded identically to it
    until the cold lane ran one (P1). The extension test asks "does this value
    mention source?", which a negation answers backwards, so a leading `!`
    disqualifies the whole restriction set rather than being parsed: an
    exclusion tells you what a walk SKIPS, never what it cannot reach.
    """
    values = [
        words[i + 1]
        for i, w in enumerate(words[:-1])
        if w in _RESTRICT_FLAGS or any(w.startswith(f + "=") for f in _RESTRICT_FLAGS)
    ]
    values += [
        w.split("=", 1)[1] for w in words if "=" in w and w.split("=", 1)[0] in _RESTRICT_FLAGS
    ]
    if not values or any(v.startswith(("!", "^")) for v in values):
        return False
    return not any(ext.lstrip(".") in v or ext in v for v in values for ext in _SOURCE_EXT)


def _is_prose_target(target: str, cwd: Path) -> bool:
    """Is this path prose, a log, or derived output rather than the repo's source?

    "Absolute and outside the project root" is a RULE rather than a list of
    scratch directories, and it is the better rule twice over: it covers every
    `/tmp`, `/var/folders`, `$TMPDIR` and home-directory log at once instead of
    the three anyone happens to remember, and searching outside the repo cannot
    be orientation IN the repo by construction.
    """
    # `removeprefix`, never `lstrip("./")` — lstrip strips a character SET, so it
    # ate the leading dot of `.agent/plans/` and reported a prose directory as
    # source. Caught by this module's own ALLOW arm, which is the arm that matters.
    clean = target.removeprefix("./").rstrip("/")
    path = Path(target).expanduser()
    if path.is_absolute() and not path.is_relative_to(cwd):
        return True
    if any(clean == r or clean.startswith(r + "/") for r in _PROSE_ROOTS):
        return True
    return bool(path.suffix) and path.suffix not in _SOURCE_EXT


def _looks_like_a_path(word: str, cwd: Path) -> bool:
    """Is this argument a PATH rather than the search pattern or a flag's value?

    By SHAPE, not by position — and that is the whole fix for two cold-lane
    findings that were one defect seen from opposite sides (P1 and P2).

    The previous version identified paths positionally: skip flags, then drop the
    first bare word as the pattern. That cannot be made correct by enumeration,
    because it needs a complete list of every flag that takes a value. `rg --sort
    path decide` — a pathless, repo-wide search — read `path` as the pattern and
    `decide` as a single-file target, and was ALLOWED; and `rg -e decide <file>`
    had its pattern eaten by `-e`, so the real file was dropped as "the pattern"
    and a legitimate single-file search was DENIED. One list, two opposite
    failures, both of which return the moment someone uses a flag nobody listed.

    A separator or an existing entry answers the question without a list: search
    patterns rarely contain `/`, and a target that exists is a target.
    """
    return "/" in word or word in {".", ".."} or (cwd / word).exists()


def _paths_of(words: list[str], cwd: Path) -> list[str]:
    """The PATH arguments of a search command; empty means it walks the whole tree.

    Flag VALUES are still skipped where the flag is known to take one, so
    `-g 'src/*.py'` cannot be mistaken for a target. That list is now a
    refinement rather than the mechanism — an unlisted flag costs precision here,
    where it used to cost the guard entirely.
    """
    value_flags = {*_RESTRICT_FLAGS, "-m", "--max-count", "-A", "-B", "-C", "-e", "--regexp"}
    paths: list[str] = []
    skip = False
    for word in words[1:]:
        if skip:
            skip = False
            continue
        if word.startswith("-"):
            skip = word in value_flags
            continue
        if _looks_like_a_path(word, cwd):
            paths.append(word)
    return paths


def _is_single_file(target: str, cwd: Path) -> bool:
    """Is `target` one file rather than a tree?

    A path that does not exist counts as a file — the ambiguous case resolves to
    ALLOW like every other one here. A trailing `/` or `.` is a tree by spelling
    alone and needs no filesystem at all.
    """
    if target in {".", ".."} or target.endswith("/"):
        return False
    try:
        return not (cwd / target).expanduser().is_dir()
    except OSError:
        return True


def _searches_the_tree(segment: str, cwd: Path, *, piped: bool) -> str | None:
    """The search PATTERN if this segment walks the tree for source, else None."""
    if piped:
        return None
    words = _words(segment)
    if not words:
        return None
    head = Path(words[0]).name
    rest = words[1:]
    if head == "git" and rest and rest[0] == "grep":
        # `git grep` walks the whole worktree with no `-r`, so it is a TREE
        # searcher rather than a `grep`. Routing it through the grep branch asked
        # for a `-r` it never carries and allowed every repo-wide `git grep`.
        words, head, rest = [words[0], *rest[1:]], "rg", rest[1:]
    recursive = (
        any(_GREP_RECURSIVE.match(w) for w in rest) if head == "grep" else head in _TREE_SEARCHERS
    )
    if not recursive or _restricted_to_prose(words):
        return None
    paths = _paths_of(words, cwd)
    if paths and all(_is_single_file(p, cwd) or _is_prose_target(p, cwd) for p in paths):
        return None
    pattern = next((w for w in rest if not w.startswith("-")), "")
    return pattern or "<what you were looking for>"


def _decide_grep(tool_input: dict[str, object], cwd: Path) -> str | None:
    """The Grep TOOL has no shell string to parse — its scope is structured fields.

    No Bash probe can reach this branch, which is why `.claude/settings.json` had
    to grow `|Grep` on this hook's matcher and why the coverage is fixtures rather
    than a live arm.
    """
    pattern = tool_input.get("pattern")
    path = tool_input.get("path")
    glob = tool_input.get("glob") or tool_input.get("type")
    if isinstance(glob, str) and glob and not any(e.lstrip(".") in glob for e in _SOURCE_EXT):
        return None
    if (
        isinstance(path, str)
        and path
        and (_is_single_file(path, cwd) or _is_prose_target(path, cwd))
    ):
        return None
    question = pattern if isinstance(pattern, str) and pattern else "<what you were looking for>"
    return _REASON.format(question=question)


def decide(
    tool_name: str, tool_input: dict[str, object], cwd: Path, *, queried: bool
) -> str | None:
    """Deny-reason for a broad source search before any graph query, else None.

    The guard's decision surface, mirroring :func:`kb_setup.hook_guard.decide` so
    the tier-2 fixture table can grade this the same way — a gate reaching
    through a private name is a gate that can be refactored out from under.
    """
    if queried:
        return None
    if tool_name == "Grep":
        return _decide_grep(tool_input, cwd)
    if tool_name != "Bash":
        return None
    command = tool_input.get("command")
    if not isinstance(command, str):
        return None
    for segment, piped in _segments(command):
        pattern = _searches_the_tree(segment, cwd, piped=piped)
        if pattern:
            return _REASON.format(question=pattern)
    return None
