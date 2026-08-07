# Copyright (c) 2026 Raymond Manaloto
"""The session's working state as DATA — `mise run kb-session-state` (#144).

WHAT THIS REPLACES. `/clear-prep` step 1 asks an agent to run four commands —
branch, status, log, PR — and reformat their output into a handoff by hand,
every session. That is four chances to transcribe something, and this repo has
already paid for exactly that class of error twice: a `file:line` read off a
`sed` window by eye (`:1836` for `:1830`, propagated into three files), and a PR
number read out of a `mise run` log where redaction had masked digits mid-number
(`pull/[redacted]59`). A snapshot nobody retypes cannot drift from its source.

WHY IT RETURNS DATA RATHER THAN A BLOCK OF MARKDOWN. :func:`gather` and
:func:`render` are separate (criterion 2) because #149's ship-time branch check
needs the STATE and has no use for the prose. A gatherer that returned a
formatted string would force that caller to parse back out what this module
already had, which is how a second, worse answer to "what branch are we on" gets
written.

A FAILED `gh` LOOKUP IS ITS OWN STATE. Decided on #144 before any code, and it
is the one thing here that was not the implementer's call. "No open PR" and
"could not ask `gh`" are different sentences, and rendering the second as the
first would put a claim in a handoff that nothing checked — the precise defect
`kb-handoff-check` (#145/#147) exists to catch, emitted by the tool that feeds
it. :class:`PrState` therefore has three members, not a bool, matching
`resolve.State`, `handoff.Verdict` and `currency`'s DRIFT/SKIP/OK next door.

READ THE BLOCK FROM AN UNREDACTED RUN — AND IT IS NOT ONLY THE BRANCH. mise's
output redaction masks digit runs matching the user's secrets, so
`mise run kb-session-state` mangles **the branch, every commit SHA, and every
issue/PR number**: `feat/144-…` prints as `feat/[redacted]44-…` and
`90e2591cda13` as `90e259[redacted]cda[redacted]3`. SHAs and PR numbers are the
worse half — they are what `kb-gates` records and `kb-review` receipts are keyed
by, so a reader who checks the branch (which the first draft of this paragraph
told them to do, naming only the branch) would still paste a corrupted SHA.

That is the SAME defect this module exists to remove — a PR number was once read
out of a log as `pull/[redacted]59` — arriving through the transport rather than
the transcriber. The repo already tracks it as the advisory-by-design eval case
`tier1.mise-redaction-legible`, whose own message says every figure `mise run`
prints is untrustworthy while it holds. The cause is the USER's mise config
(`_.fnox-env`), which `do-not.md` #11 forbids this repo from editing, so the
mitigation is `uv run kb-setup session-state` — same code, no redaction layer.
`/clear-prep` step 1 therefore fences THAT command, not the task.

THE PROBE IS `gh pr list --state open`, NOT `gh pr view <branch>`. `pr.py`
records what the latter does: it resolves a branch to its PR REGARDLESS of
state, returning a MERGED PR with rc=0 — which once made `ship` print success
having opened nothing. A snapshot built on that call would report a long-merged
PR as the session's open one, with no way for a reader to tell.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from kb_setup import gates

#: Bound on the git reads. Short: these are cheap metadata queries, and a wedged
#: one must not become the reason the session has no snapshot at all.
_GIT_TIMEOUT = 30

#: Bound on the `gh` calls, matching `pr._GH_TIMEOUT`. Longer because it is a
#: network round trip; expiry lands in :attr:`PrState.UNVERIFIABLE`, which is a
#: real answer here rather than a failure.
_GH_TIMEOUT = 120

#: How many commits a snapshot carries. EIGHT, matching the `git log --oneline -8`
#: that `/clear-prep` step 1 ran before this task replaced it. Five read better in
#: a bullet, but shipping five would have silently narrowed the workflow this
#: replaces — a reduction nobody asked for and no reviewer would see.
DEFAULT_COMMITS = 8

#: What `git rev-parse --abbrev-ref HEAD` returns when HEAD is detached — the
#: literal string, not an error. A paused bisect or a `git checkout <sha>`
#: therefore arrives looking like a branch by this name, which `pr._ship_preflight`
#: also has to guard. Here it matters for a second reason: `gh pr list --head HEAD`
#: is a well-formed query that finds nothing, so treating it as a branch would
#: turn "we are not on a branch" into a confident "no open PR".
DETACHED = "HEAD"

#: `git status --porcelain` status code meaning "nothing in this half". Index
#: and worktree are read INDEPENDENTLY (X and Y), because `MM` is genuinely both
#: staged and unstaged and collapsing it loses the distinction a handoff reader
#: needs: "staged: foo" alone invites them to believe the staged content is the
#: whole change.
#: A `frozenset`, matching :data:`_PAIRED_CODES` next door, because the test is
#: set MEMBERSHIP. As a bare string it was substring containment wearing the same
#: syntax — harmless here (the `_STATUS_PREFIX` guard makes every tested value
#: length 1, and the standards lane tried to construct a reaching case and could
#: not) but two spellings of one idea in adjacent constants.
_UNMODIFIED = frozenset({" "})

#: Codes whose `-z` record is followed by a SECOND NUL-terminated field holding
#: the original path. Failing to consume it does not merely render renames oddly
#: — it shifts every subsequent entry by one, so unrelated files land in the
#: wrong bucket or as garbage. `--no-renames` would dodge this, at the cost of a
#: flag whose absence on an older git would silently change the parse.
_PAIRED_CODES = frozenset({"R", "C"})

#: Length of the `XY ` prefix on a porcelain record, before the path starts.
_STATUS_PREFIX = 3

#: `git-status(1)` spells an UNMERGED path seven ways: `DD AU UD UA DU AA UU`.
#: Five contain a `U`; `DD` and `AA` do not, which is why the membership test
#: needs both halves. None of these letters is a "nothing here" code, so without
#: an explicit branch every one of them reads as staged-and-unstaged.
_UNMERGED_CODE = "U"
_UNMERGED_PAIRS = frozenset({"DD", "AA"})


class PrState(Enum):
    """The three answers a PR lookup can get.

    NONE and OPEN are the two verdicts. UNVERIFIABLE is kept as its own state
    rather than folded into NONE, for the reason recorded on #144: `gh` being
    unreachable, rate-limited or unauthenticated is not evidence that no PR
    exists, and a handoff that says "0 open PRs" on the strength of a question
    nobody managed to ask is the false green this whole programme removes.
    """

    NONE = "NONE"
    OPEN = "OPEN"
    UNVERIFIABLE = "UNVER"


@dataclass(frozen=True)
class PullRequest:
    """The PR half of a snapshot.

    ``detail`` is never empty when ``state`` is UNVERIFIABLE — :func:`render`
    prints it verbatim, so a silent unknown would become an unexplained one. It
    means ONE thing: why there is no answer. ``note`` carries the separate job
    of annotating an answer we DO have (currently: more than one open PR on the
    head). They were one field until the standards lane pointed out that a
    caller filtering on ``detail`` could not tell an explanation from an
    annotation — and that this docstring already claimed ``detail`` was only the
    former while the code used it for both.

    ``number``/``title``/``checks``/``checks_green`` are populated only for OPEN.

    ``checks_green`` mirrors `pr.checks_state`'s verdict and is None unless
    ``state`` is OPEN. It is False BOTH for a binding check that failed and for
    a checks lookup that could not be read: `pr.checks_state` owns that collapse
    and it gates `ship`/`land`, so it is not rewritten from here — ``checks``
    carries the sentence that distinguishes them. Recorded rather than silently
    discarded, because without it a caller asking "are the checks green?" had to
    substring-match prose that can also read "could not read checks (rc=1)".
    (Spec lane, criterion 3.)
    """

    state: PrState
    number: int | None = None
    title: str = ""
    checks: str = ""
    checks_green: bool | None = None
    detail: str = ""
    note: str = ""


@dataclass(frozen=True)
class Commit:
    """One recent commit: the full SHA and its subject line."""

    sha: str
    subject: str


@dataclass(frozen=True)
class Changes:
    """The staged / unstaged / untracked split.

    ``read`` is the third state, and it is why :attr:`clean` is a property
    rather than an ``if not changes.staged`` at each call site. Three empty
    tuples mean "nothing changed" only when git actually answered; outside a
    repository, or when git fails, they mean nothing was learned. A caller
    reading the tuples alone cannot tell those apart, and the one that reads
    them as clean writes the unchecked claim into a handoff.
    """

    staged: tuple[str, ...] = ()
    unstaged: tuple[str, ...] = ()
    untracked: tuple[str, ...] = ()
    unmerged: tuple[str, ...] = ()
    read: bool = True

    @property
    def clean(self) -> bool:
        """Whether git was asked AND reported nothing. An unread tree is not clean."""
        return self.read and not (self.staged or self.unstaged or self.untracked or self.unmerged)

    @property
    def conflicted(self) -> bool:
        """Whether any path is UNMERGED — i.e. nothing can be committed yet.

        Its own question, not a shade of "dirty": a conflicted tree blocks a
        commit outright, which is the single most important thing a handoff can
        say about where a session stopped.
        """
        return bool(self.unmerged)


@dataclass(frozen=True)
class Snapshot:
    """One session's working state. ``branch`` is None when git could not be read."""

    branch: str | None
    changes: Changes
    commits: tuple[Commit, ...]
    pr: PullRequest

    @property
    def detached(self) -> bool:
        """Whether HEAD is detached rather than on a branch."""
        return self.branch == DETACHED


def _git(args: list[str], repo_root: Path) -> tuple[int, str]:
    """Run a git command in ``repo_root``; return ``(rc, stdout)``.

    ``errors="replace"`` rather than the default strict decode. `text=True`
    decodes inside `subprocess.run`, so a single path git emits verbatim that is
    not UTF-8 would raise straight out of a reporting function and cost the
    caller the ENTIRE snapshot. A mojibake filename is strictly more useful than
    no working state at all, and this module gates nothing — so it degrades the
    one path rather than failing the whole read. That choice is also why
    `UnicodeDecodeError` is absent from the handler below: it can no longer be
    raised here, and an exception clause that cannot fire is dead code that
    reads as live protection.
    """
    try:
        proc = subprocess.run(
            # `cwd=`, the spelling `pr._run` and `gates.tree_dirty` both use.
            # `git -C <root>` is equivalent and was two idioms for one job in
            # adjacent modules. (Standards lane.)
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=_GIT_TIMEOUT,
        )
    except OSError, subprocess.SubprocessError:
        return 1, ""
    return proc.returncode, proc.stdout or ""


def _gh(args: list[str], repo_root: Path) -> tuple[int, str]:
    """Run a `gh` command; return ``(rc, stdout+stderr)``.

    A named seam so the tests can pin it. Stubbing `subprocess.run` instead
    would also stub the git calls, and criterion 5 says git is exercised for
    real — the fixture repo IS the test double.

    stdout and stderr are merged, matching `pr._run`. That makes the JSON parse
    fail whenever gh prints anything alongside its output, and the parse failing
    is read as UNVERIFIABLE — fail-closed, deliberately. An unreadable answer is
    not "no PR".
    """
    try:
        proc = subprocess.run(
            ["gh", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=_GH_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"gh: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _checks_state(number: int, repo_root: Path) -> tuple[bool, str]:
    """A PR's check state, via `pr.checks_state`.

    A named seam for the same reason `gates.head_sha` is one: the tests pin this,
    and pinning `pr.checks_state` itself would silently pin it for `ship` and
    `land` too.

    ``repo_root`` is threaded through as ``cwd``. It was omitted, making this the
    only read in the module that ignored the root it was given and resolved `gh`
    against the process's directory instead. (Cold lane, P3.)
    """
    from kb_setup import pr

    return pr.checks_state(number, cwd=repo_root)


def current_branch(repo_root: Path) -> str | None:
    """The checked-out branch, ``"HEAD"`` when detached, or None if unreadable.

    None and ``"HEAD"`` are different and both matter: the first means git could
    not be asked, the second means it answered and there is no branch. Only the
    first is a failure; both make a PR lookup meaningless.

    `symbolic-ref` FIRST, and `rev-parse` only as the detached fallback. The
    order is the fix for a false negative the cold lane found by running it:
    `git rev-parse --abbrev-ref HEAD` exits **128** on an UNBORN branch — a repo
    with no commits yet, which is `git init` plus `git checkout -b work`, an
    entirely ordinary state — while still printing `HEAD` to stdout. Trusting
    only its rc turned a branch that is perfectly knowable into this module's
    "could not be asked" state, and the render then said `COULD NOT READ` beside
    a correctly-read staged file list. That is this module's own collapse
    running backwards: not an unchecked claim, but a checked answer thrown away.

    `git symbolic-ref --short HEAD` answers rc=0 on an unborn branch and fails
    when HEAD is detached, so the two commands are complementary rather than
    redundant — the fallback is what still detects :data:`DETACHED`.
    """
    rc, out = _git(["symbolic-ref", "--short", "HEAD"], repo_root)
    name = out.strip()
    if rc == 0 and name:
        return name
    # Detached HEAD (symbolic-ref refuses), or not a repository at all.
    # `rev-parse --abbrev-ref` prints the literal "HEAD" for the former.
    rc, out = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    name = out.strip()
    if rc != 0 or not name:
        return None
    return name


def _parse_status(out: str) -> Changes:
    """Parse `git status --porcelain -z` into the four buckets.

    Index (X) and worktree (Y) are read as separate answers, so a path can
    appear in two buckets — which is the truth for `MM`, not a bug.

    UNMERGED IS CHECKED BEFORE EITHER, because it is not describable as either.
    """
    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    unmerged: list[str] = []

    fields = out.split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        # `-z` output ends with a trailing NUL, so the final split field is
        # always empty; a short record is malformed and skipped rather than
        # indexed into.
        if len(entry) < _STATUS_PREFIX:
            continue
        x, y, path = entry[0], entry[1], entry[_STATUS_PREFIX:]
        if x in _PAIRED_CODES or y in _PAIRED_CODES:
            # Consume the origin path. Not doing so shifts everything after it.
            i += 1
        if x == "?" and y == "?":
            untracked.append(path)
            continue
        # `!!` only appears under `--ignored`, which is not passed. Skipped
        # anyway so that adding the flag later cannot silently file ignored
        # files as staged changes.
        if x == "!" and y == "!":
            continue
        # BEFORE the two generic branches. An unmerged pair has no " " half, so
        # it would otherwise fall through and be reported as both staged AND
        # unstaged — rendered identically to an ordinary `MM`. A reader sees
        # "staged: f.txt / unstaged: f.txt" and concludes it needs re-staging,
        # when in truth nothing can be committed until the conflict is resolved.
        # (Cold lane, P2, probed against a real `git merge`.)
        if _UNMERGED_CODE in (x, y) or x + y in _UNMERGED_PAIRS:
            unmerged.append(path)
            continue
        if x not in _UNMODIFIED:
            staged.append(path)
        if y not in _UNMODIFIED:
            unstaged.append(path)

    return Changes(
        tuple(staged), tuple(unstaged), tuple(untracked), unmerged=tuple(unmerged), read=True
    )


def working_changes(repo_root: Path) -> Changes:
    """The working tree's split, or an unread :class:`Changes` if git failed.

    `git status --porcelain` prints nothing for a clean tree AND nothing when
    the invocation fails, so the rc is what discriminates — the output alone
    cannot. Same reasoning as `gates.tree_dirty`.
    """
    rc, out = _git(["status", "--porcelain", "-z"], repo_root)
    if rc != 0:
        return Changes(read=False)
    return _parse_status(out)


def recent_commits(repo_root: Path, limit: int = DEFAULT_COMMITS) -> tuple[Commit, ...]:
    """The newest ``limit`` commits, newest first. Empty when git cannot be read.

    A NUL separates the SHA from the subject rather than a space: `%s` is the
    subject line, which routinely contains spaces, colons and parentheses, and
    splitting on any of those would truncate real subjects.
    """
    if limit < 1:
        return ()
    rc, out = _git(["log", f"-{limit}", "--format=%H%x00%s"], repo_root)
    if rc != 0:
        return ()
    commits: list[Commit] = []
    for line in out.splitlines():
        sha, _, subject = line.partition("\0")
        if sha:
            commits.append(Commit(sha=sha, subject=subject))
    return tuple(commits)


def _pr_rows(out: str) -> list[dict[str, object]] | None:
    """`gh pr list --json` rows, or None when the payload is not that.

    Strict, and fails closed. `json.loads` succeeding says the bytes are JSON,
    not that they answer the question — `{"message": "Not Found"}` parses fine
    and is an error, and a scalar row would let `.get` raise out of a function
    whose whole contract is to return a state.
    """
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        return None
    return data


def pull_request(repo_root: Path, branch: str | None) -> PullRequest:
    """The open PR for ``branch``, or why there is no answer.

    Every non-answer returns UNVERIFIABLE with a reason. Only a well-formed
    empty list returns NONE — the one case where `gh` was asked and said no.
    """
    if branch is None:
        return PullRequest(
            PrState.UNVERIFIABLE,
            detail="could not read the branch, so there was nothing to look a PR up by",
        )
    if branch == DETACHED:
        # `gh pr list --head HEAD` is a valid query that matches nothing, so
        # without this the detached case would report a checked "no open PR".
        return PullRequest(
            PrState.UNVERIFIABLE,
            detail="detached HEAD — no branch to look a PR up by",
        )

    rc, out = _gh(
        ["pr", "list", "--head", branch, "--state", "open", "--json", "number,title"],
        repo_root,
    )
    if rc != 0:
        return PullRequest(PrState.UNVERIFIABLE, detail=f"gh exited {rc}: {out.strip()[:200]}")

    rows = _pr_rows(out)
    if rows is None:
        return PullRequest(
            PrState.UNVERIFIABLE,
            detail=f"could not read gh's output: {out.strip()[:200]}",
        )
    return _pr_from_rows(rows, repo_root)


def _pr_from_rows(rows: list[dict[str, object]], repo_root: Path) -> PullRequest:
    """Turn `gh`'s ANSWERED rows into a state.

    Split from :func:`pull_request` so the branch guards and the payload reading
    stay separately readable, and separately testable.
    """
    if not rows:
        return PullRequest(PrState.NONE)

    number = rows[0].get("number")
    # `bool` is a subclass of `int`, so a bare isinstance check accepts `true`
    # and then renders it as PR #1. Same trap `gates._is_exit_code` documents.
    if not isinstance(number, int) or isinstance(number, bool):
        return PullRequest(
            PrState.UNVERIFIABLE,
            detail="gh returned a PR row with no usable number",
        )
    title = rows[0].get("title")
    green, checks = _checks_state(number, repo_root)
    # More than one open PR on a single head is possible and worth saying, since
    # everything below reports only the first. It goes in `note`, not `detail`:
    # `detail` means "why there is no answer", and this is an answer.
    extra = f" ({len(rows)} open PRs on this branch; showing the first)" if len(rows) > 1 else ""
    return PullRequest(
        PrState.OPEN,
        number=number,
        title=title if isinstance(title, str) else "",
        checks=checks,
        checks_green=green,
        note=extra,
    )


def gather(repo_root: Path, *, limit: int = DEFAULT_COMMITS, with_pr: bool = True) -> Snapshot:
    """Read the session's working state. Renders nothing (criterion 2).

    ``with_pr=False`` skips the network call entirely and reports the PR state
    as UNVERIFIABLE-because-not-asked. That is not a placeholder: a caller that
    declined to look has exactly as much evidence about the PR as one whose
    lookup failed, and giving it a cheerier value would be inventing one.

    Named ``with_pr`` rather than ``pr``, which was four things in one module —
    the sibling module imported in :func:`_checks_state`, the :class:`Snapshot`
    field, :func:`_render_pr`'s :class:`PullRequest` parameter, and this flag.
    (Standards lane.)
    """
    branch = current_branch(repo_root)
    return Snapshot(
        branch=branch,
        changes=working_changes(repo_root),
        commits=recent_commits(repo_root, limit),
        pr=(
            pull_request(repo_root, branch)
            if with_pr
            else PullRequest(PrState.UNVERIFIABLE, detail="the PR lookup was not requested")
        ),
    )


def _render_changes(changes: Changes) -> list[str]:
    """The tree lines. An unread tree says so; it never renders as clean."""
    if not changes.read:
        return ["- **tree**: COULD NOT READ — git did not answer"]
    if changes.clean:
        return ["- **tree**: clean"]
    lines = ["- **tree**:"]
    # UNMERGED first and shouted. It is not one more category of change — it is
    # the reason nothing in this tree can be committed, and a handoff that
    # buries it under two other buckets has told the reader the wrong thing
    # about where the session actually is.
    if changes.unmerged:
        lines.append(
            f"  - **UNMERGED — conflict, nothing can be committed until resolved** "
            f"({len(changes.unmerged)}): {', '.join(changes.unmerged)}"
        )
    for label, paths in (
        ("staged", changes.staged),
        ("unstaged", changes.unstaged),
        ("untracked", changes.untracked),
    ):
        if paths:
            lines.append(f"  - {label} ({len(paths)}): {', '.join(paths)}")
    return lines


def _render_pr(pr: PullRequest) -> str:
    """The PR line — one per state, and the three never read the same.

    Structured data that distinguishes three answers, rendered by something that
    prints two of them alike, puts the collapse straight back into the artifact
    a human reads. That is the half of #144's design decision that lives here.
    """
    if pr.state is PrState.NONE:
        return "- **open PR**: none"
    if pr.state is PrState.OPEN:
        title = f" — {pr.title}" if pr.title else ""
        checks = f" (checks: {pr.checks})" if pr.checks else ""
        return f"- **open PR**: #{pr.number}{title}{checks}{pr.note}"
    return f"- **open PR**: COULD NOT ASK — {pr.detail}"


def render(snapshot: Snapshot) -> str:
    """The paste-ready block (criterion 1). Reads nothing — pure in its argument."""
    if snapshot.branch is None:
        branch = "- **branch**: COULD NOT READ — git did not answer"
    elif snapshot.detached:
        branch = f"- **branch**: {DETACHED} (detached — not on a branch)"
    else:
        branch = f"- **branch**: `{snapshot.branch}`"

    lines = [branch, *_render_changes(snapshot.changes)]

    if snapshot.commits:
        lines.append("- **recent commits**:")
        lines.extend(f"  - `{c.sha[: gates.SHA_ABBREV]}` {c.subject}" for c in snapshot.commits)
    else:
        lines.append("- **recent commits**: none read")

    lines.append(_render_pr(snapshot.pr))
    return "\n".join(lines)


#: Every flag `kb-session-state` accepts. An unrecognised one is REFUSED rather
#: than ignored, the split `kb-gates` draws: silently dropping `--no-pr` would
#: make the command take the opposite position from the one the command line
#: states, spend a network call nobody asked for, and still exit 0.
_FLAGS = frozenset({"--no-pr"})


def main(args: list[str], repo_root: Path) -> int:
    """`kb-session-state [--no-pr]` — 0 always, 2 on a request that cannot be honoured.

    It never exits non-zero for what it FINDS. A snapshot reports; an rc that
    tracked cleanliness would make the task useless exactly when it is wanted,
    since you take a snapshot precisely when there is something to say.
    """
    unknown = [a for a in args if a.startswith("-") and a not in _FLAGS]
    if unknown:
        print(
            f"kb-session-state: unknown flag(s) {', '.join(unknown)} "
            f"(accepted: {', '.join(sorted(_FLAGS))})",
            file=sys.stderr,
        )
        return 2
    # POSITIONALS ARE REFUSED TOO. This command takes none, so anything here is
    # a mistake — a mistyped flag that lost its dashes, or a path the caller
    # thought was accepted. Ignoring them exited 0 on `session-state bogus`
    # while the comment above claimed unrecognised input is refused rather than
    # ignored, so the guard enforced half its own stated rule. `kb-gates` may
    # ignore positionals because it TAKES them (gate names). (Standards lane.)
    positional = [a for a in args if not a.startswith("-")]
    if positional:
        print(
            f"kb-session-state: takes no positional argument(s), got "
            f"{', '.join(positional)} (accepted: {', '.join(sorted(_FLAGS))})",
            file=sys.stderr,
        )
        return 2
    print(render(gather(repo_root, with_pr="--no-pr" not in args)))
    return 0
