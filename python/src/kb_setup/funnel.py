# Copyright (c) 2026 Raymond Manaloto
"""The research-funnel gate: did this branch's research reach the corpus?

WHY THIS EXISTS. This repo's stated purpose is that research an agent does here
becomes corpus another session can query. That clause had never had a
mechanism, and the drift was measured on the branch that produced this module:
**33 files added under `docs/research/**` and `docs/artifacts/**`, and 0 files
under `sources/**`.** The same round ran `curl` 31 times and wrote into
`sources/` zero times. A doc that is never ingested makes the next session pay
again to learn what this one already learned — the exact failure
`.claude/rules/research-doc-sources.md` and the `kb-curator` skill's MANDATE
exist to prevent, and which scored 0-for-31 when it lived only as prose.

WHAT THE GATE CHECKS. Whether ADDED or MODIFIED files landed under the two
watched research directories (`docs/research/**`, `docs/artifacts/**`) since
this branch diverged from `main`, and — if so — whether the SAME branch also
touched `sources/**`. `sources/REGISTRY.md` counts: registering a source in the
durable backlog (`.claude/rules/research-repo-enumeration.md`) is the mandate's
own minimum bar, and a gate demanding a full manifest for every doc would be
unsatisfiable for research that never touched a repo worth ingesting.

WHAT COUNTS AS AN ESCAPE HATCH, AND WHAT DOES NOT. A commit trailer,
``Funnel-exempt: <reason>``, on any commit in the branch delta — never a flag,
an env var, or a config key. Those would be invisible in the history the
moment the session ends; a trailer is the one form a reviewer can see and
disagree with later. An exemption with an EMPTY reason is not an exemption —
see :func:`_exemption_reason`.

WHAT THIS DOES NOT CHECK. Whether the research was any GOOD, or whether the
funnelled source actually reached `graphify-out/graph.json` — this is a git-only
gate, reading names and trailers, never graph content. It reads and prints; it
never writes to the tree.

**It also only sees COMMITTED history.** `verdict` diffs `base_commit` against
`HEAD` (`_diff_added_or_modified`), so a doc dropped into `docs/research/**` but
never `git add`-ed — or added but not yet committed — reads as `clean`: the
same as a branch that touched nothing at all. This is the intended behaviour,
not an oversight: a ship gate judges what is about to be PUSHED, and
uncommitted content is by definition not that. It means a `FUNNELLED` verdict
is not a promise that every file in the working tree has a home, only that
everything already committed does — worth stating plainly, per
`.claude/rules/probes-need-a-control-arm.md`'s "what this check cannot see".

THE STATE SET, and why five and not fewer:

* ``clean`` — no ADDED/MODIFIED file under either watched directory. The
  question was asked and the answer is no.
* ``funnelled`` — a docs delta AND a `sources/**` delta, both in this branch.
* ``exempt`` — a docs delta, no sources delta, and a non-empty
  ``Funnel-exempt:`` trailer on a commit in the branch.
* ``drift`` — a docs delta, no sources delta, no exemption. The failure this
  gate exists to catch.
* ``no_base`` — the base ref could not be resolved to a merge-base with HEAD
  (detached, no `main`, not a git repo), or the delta itself could not be read.
  **Never renders as clean** — `.claude/rules/probes-need-a-control-arm.md`
  treats "could not check" as a third state, not a free pass, and
  `kb_setup.result.Rc.NOT_RUN`'s own docstring is the same argument for exit
  codes: "we did not look" collapsing into either "found nothing" or "found
  something" is how a gate reports clean without checking anything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import msgspec

from kb_setup import events, review
from kb_setup.result import Rc

#: Mirrors `gates._GIT_TIMEOUT`'s intent: these are cheap metadata reads about
#: one branch's delta, and a wedged one must not become the reason this gate
#: never reports. NOT imported from `gates` — that name is private, and the
#: SLF001 grant in `pyproject.toml` is scoped to `graph_size.py`'s one
#: documented case (reaching into graphify's own resolver), not to every future
#: module that wants a git timeout.
_GIT_TIMEOUT = 30

#: The two directories this gate watches for research that never reached the
#: corpus — the exact pair measured on the branch that motivated this module.
_DOCS_WATCHED = ("docs/research", "docs/artifacts")

#: The corpus's own input contract (`do-not.md` #6): a manifest, a vendored
#: doc under `sources/media/`, a committed extraction chunk under
#: `sources/extractions/`, OR an entry in `sources/REGISTRY.md` — all of them
#: live under this one tree, so watching it is watching the whole contract at
#: once. `REGISTRY.md` counting as funnelled is deliberate: it is the mandate's
#: own minimum bar, and demanding a full manifest for every doc would be
#: unsatisfiable for research that touched no repo worth ingesting.
_SOURCES_WATCHED = "sources"

#: The commit-trailer key. Canonical form: `Funnel-exempt: <one-line reason>`.
#: Deliberately not a flag, env var, or config key — see the module docstring.
_TRAILER_KEY = "Funnel-exempt"


class FunnelVerdict(msgspec.Struct, frozen=True):
    """One measurement of whether this branch's research reached the corpus."""

    state: str
    docs_paths: tuple[str, ...]
    sources_paths: tuple[str, ...]
    exempt_reason: str | None
    note: str


def _git(repo_root: Path, *args: str) -> tuple[bool, str]:
    """Run `git *args` from `repo_root`; return ``(ok, raw stdout)``.

    Shaped like `review._git_result` — the ok/raw split matters because `git
    diff` legitimately answers "" (identical trees), so collapsing failure into
    "" the way `review._git` does for `rev-parse`/`merge-base` would let a git
    failure read as "the delta is empty", the exact could-not-check-rendered-as-
    green this repo refuses everywhere else.

    A SEPARATE copy of that shape, not an import of it: `review._git_result` is
    private, and the SLF001 grant in `pyproject.toml` is scoped to
    `graph_size.py`'s one documented reach into graphify's own resolver, not to
    every future module that wants a git runner. A second small one is the
    accepted cost of that boundary.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT,
        )
    except OSError, subprocess.SubprocessError, UnicodeDecodeError:
        # UnicodeDecodeError: `text=True` decodes inside `subprocess.run`, and a
        # path or commit body git holds as non-UTF-8 bytes would otherwise raise
        # a traceback out of the middle of a gate whose whole contract is a
        # worded refusal — `review._git_result`'s own documented reason for
        # catching it here rather than letting it propagate.
        return False, ""
    if proc.returncode != 0:
        return False, ""
    return True, proc.stdout


def _diff_added_or_modified(
    repo_root: Path, base_commit: str, *pathspecs: str
) -> tuple[str, ...] | None:
    """ADDED/MODIFIED paths under ``pathspecs`` between ``base_commit`` and HEAD.

    Two-dot from an already-resolved MERGE BASE, not a literal three-dot
    against the original ref — and the two are the same set. `git diff
    A...B` is defined as `git diff $(git merge-base A B) B`, verified
    empirically this session on a throwaway repo (a rename-and-add landed
    identically either way). Since :func:`verdict` already resolves the merge
    base via `review.base_sha` — itself a three-dot resolver, per its own
    docstring — diffing from that resolved commit reuses the one merge-base
    computation instead of asking git to redo it, which is also
    `review._delta_paths`' own established idiom here (`base_sha` once, then a
    two-dot diff from the result).

    ``--no-renames``: a doc MOVED into a watched directory is, for this gate's
    purpose, indistinguishable from one newly written there — either way there
    is new content in the tree needing a source. Turning rename detection off
    keeps every `--name-status` row a plain `(status, path)` pair with no
    2-path rename records to special-case, unlike `graph.py`'s `_classify_change`
    (which wants renames ON, for a different question). ``-z`` sidesteps
    `core.quotePath` escaping, so a path with a quote or non-ASCII byte compares
    as the bytes git actually has — `review._delta_paths`' own reasoning.

    Returns ``None`` when git could not be read, never an empty tuple — an
    empty tuple means "checked, and there is nothing here", and those are
    different facts. See :data:`_GIT_TIMEOUT`.
    """
    ok, out = _git(
        repo_root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        base_commit,
        "HEAD",
        "--",
        *pathspecs,
    )
    if not ok:
        return None
    tokens = [t for t in out.split("\0") if t]
    # `--no-renames` guarantees every record is a (status, path) pair — no
    # 2-path rename rows can appear, so a plain positional zip is exact rather
    # than an approximation. `strict=False`, explicitly (not the bare default,
    # and not `strict=True`): a malformed or odd-length stream is git behaving
    # unexpectedly, and the honest response for a read-only gate is to use what
    # pairs cleanly rather than crash the gate over it.
    pairs = zip(tokens[0::2], tokens[1::2], strict=False)
    paths = [path for status, path in pairs if status[:1] in {"A", "M"}]
    return tuple(sorted(paths))


def _commit_body(repo_root: Path, sha: str) -> str | None:
    """The full commit message (subject + body) of ``sha``, or ``None``."""
    ok, out = _git(repo_root, "log", "-1", "--format=%B", sha)
    return out if ok else None


def _trailer_reason(body: str) -> str:
    """The value of the first non-empty ``Funnel-exempt:`` trailer in ``body``.

    ``git interpret-trailers --parse --only-trailers`` rather than a hand-rolled
    regex — `.claude/rules/use-tool-builtins.md`. This is the first trailer
    parser in this codebase (a sweep for `trailer`/`interpret-trailers` across
    `python/` and `tests/` found none, against a control that DID hit), so its
    behaviour was checked empirically rather than assumed:

    * an ordinary commit message with no trailer block — subject only, or a
      prose body with no `Key: value` lines — parses to NOTHING, so this never
      false-positives on ordinary prose;
    * an EMPTY-valued trailer (``Funnel-exempt:`` with nothing after the colon)
      is preserved as a trailer with an empty value, not dropped — which is
      what makes the empty-reason case distinguishable from no trailer at all,
      rather than the two collapsing into the same "found nothing" result.

    Returns "" for both "no trailer" and "trailer with an empty reason" — the
    caller (:func:`_exemption_reason`) does not need to tell those apart; both
    fall through to `drift`.
    """
    try:
        proc = subprocess.run(
            ["git", "interpret-trailers", "--parse", "--only-trailers"],
            input=body,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT,
        )
    except OSError, subprocess.SubprocessError, UnicodeDecodeError:
        return ""
    if proc.returncode != 0:
        return ""
    for line in proc.stdout.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == _TRAILER_KEY:
            reason = value.strip()
            if reason:
                return reason
    return ""


def _exemption_reason(repo_root: Path, base_commit: str) -> str:
    """The first non-empty ``Funnel-exempt:`` reason on this branch, or "".

    Walks every commit in ``base_commit..HEAD`` (this branch's own commits,
    the same range `review._reviewed_ancestors` walks for a receipt) rather
    than only HEAD: the trailer can sit on any commit in the delta, not
    necessarily the tip.

    A git failure here (an unreadable `rev-list`, an unreadable commit body)
    returns "" rather than propagating a distinct failure state — the caller
    then reports `drift`, which is the FAIL-CLOSED direction: a gate that
    cannot confirm an exemption must not grant one silently.
    """
    ok, out = _git(repo_root, "rev-list", f"{base_commit}..HEAD", "--")
    if not ok:
        return ""
    for sha in out.split():
        body = _commit_body(repo_root, sha)
        if body is None:
            continue
        reason = _trailer_reason(body)
        if reason:
            return reason
    return ""


def _no_base(base: str, *, docs: tuple[str, ...] = ()) -> FunnelVerdict:
    """A `no_base` verdict: the gate could not ask its question.

    ONE shared note covers all three failure causes the spec's state table
    names — an unresolvable base ref, an unreadable docs delta, an unreadable
    sources delta — because the table asks only that `no_base` be
    distinguishable from `clean` IN WORDS, not that each git-read failure earns
    its own sentence. `docs` is threaded through so a failure discovered only
    after the docs delta was already read (the sources delta call) does not
    throw that evidence away.
    """
    return FunnelVerdict(
        state="no_base",
        docs_paths=docs,
        sources_paths=(),
        exempt_reason=None,
        note=(
            f"could not resolve '{base}' to a merge-base with HEAD, or could not "
            "read the branch delta from git — detached HEAD, no such ref, not a "
            "git repo, or a transient git failure. The gate could not ask its "
            "question."
        ),
    )


def _drift(docs: tuple[str, ...]) -> FunnelVerdict:
    """The `drift` verdict: the failure this gate exists to catch."""
    return FunnelVerdict(
        state="drift",
        docs_paths=docs,
        sources_paths=(),
        exempt_reason=None,
        note=(
            f"{len(docs)} file(s) landed under docs/research/** or "
            "docs/artifacts/**, and nothing under sources/** — research produced "
            "on this branch has not reached the corpus. Register the source "
            "(sources/REGISTRY.md counts) or add a `Funnel-exempt: <reason>` "
            "commit trailer if this really has nothing to funnel."
        ),
    )


def verdict(repo_root: Path, *, base: str = review.DEFAULT_BASE_REF) -> FunnelVerdict:
    """Measure whether this branch's research reached the corpus.

    Resolves ``base`` to a merge-base via `review.base_sha` — three-dot
    semantics, matching `git diff <base>...HEAD`, per that function's own
    docstring — then diffs from the resolved commit. See
    :func:`_diff_added_or_modified` for why that is the same comparison as a
    literal three-dot diff against ``base`` itself.

    See :func:`_no_base` for why its three underlying failure causes collapse
    into one state and one return point here rather than three.

    ``base`` defaults to `review.DEFAULT_BASE_REF` ("origin/main"), NOT a bare
    local `"main"` — this was the ONE `base_sha(` call site in the package
    that passed a bare local ref (`review.py:974`, `review.py:1066` and
    `cli.py:724` all use this same constant already). A bare `"main"` breaks
    two ways: on a clone or worktree with no local `main` branch the gate
    returns `no_base` for a reason unrelated to the branch's own delta, and
    where local `main` has drifted from `origin/main` the delta measured is
    not the delta being shipped. Imported rather than repeated as a literal,
    so this default and `review`'s own definition can never name different
    refs.
    """
    base_commit = review.base_sha(repo_root, base)
    docs_changed = (
        None if not base_commit else _diff_added_or_modified(repo_root, base_commit, *_DOCS_WATCHED)
    )
    if not base_commit or docs_changed is None:
        return _no_base(base)
    if not docs_changed:
        return FunnelVerdict(
            state="clean", docs_paths=(), sources_paths=(), exempt_reason=None, note=""
        )

    sources_changed = _diff_added_or_modified(repo_root, base_commit, _SOURCES_WATCHED)
    if sources_changed is None:
        return _no_base(base, docs=docs_changed)
    if sources_changed:
        return FunnelVerdict(
            state="funnelled",
            docs_paths=docs_changed,
            sources_paths=sources_changed,
            exempt_reason=None,
            note="",
        )

    reason = _exemption_reason(repo_root, base_commit)
    if reason:
        return FunnelVerdict(
            state="exempt", docs_paths=docs_changed, sources_paths=(), exempt_reason=reason, note=""
        )

    return _drift(docs_changed)


def render(v: FunnelVerdict) -> str:
    """One block: the verdict, what changed, and why — never just the state word.

    `no_base` prints its own sentence via `note` rather than the bare word
    `NO_BASE`, because `.claude/rules/probes-need-a-control-arm.md` treats a
    could-not-check verdict as the one that most needs to be said in words, not
    only carried in the exit code.
    """
    lines = [f"funnel: {v.state.upper()}"]
    if v.docs_paths:
        lines.append(f"  docs delta ({len(v.docs_paths)}): {', '.join(v.docs_paths)}")
    if v.sources_paths:
        lines.append(f"  sources delta ({len(v.sources_paths)}): {', '.join(v.sources_paths)}")
    if v.exempt_reason:
        lines.append(f"  exempt: {v.exempt_reason}")
    if v.note:
        lines.append(f"  {v.note}")
    return "\n".join(lines)


def main(repo_root: Path, args: list[str] | None = None) -> int:
    """CLI boundary: 0 for clean/funnelled/exempt, 1 on drift, `Rc.NOT_RUN` on no_base.

    ``args``, though this gate takes no flags today, is refused rather than
    silently ignored when non-empty — `Rc.BAD_REQUEST`, the same "an unknown
    flag is a mistake, not a no-op" stance `gates.check_gates` takes for its own
    `_FLAGS`. That also keeps every `kb-setup <cmd>` boundary the same shape:
    `cli.py` passes `rest` uniformly, and a signature that silently dropped it
    would be the one exception.
    """
    if args:
        print(f"kb-setup funnel: takes no arguments (got {args!r})", file=sys.stderr)
        return int(Rc.BAD_REQUEST)
    v = verdict(repo_root)
    events.say("funnel.verdict", render(v), state=v.state)
    if v.state == "drift":
        return int(Rc.FINDINGS)
    if v.state == "no_base":
        return int(Rc.NOT_RUN)
    return int(Rc.OK)
