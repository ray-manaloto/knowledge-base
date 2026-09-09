# Copyright (c) 2026 Raymond Manaloto
"""`kb-recall-work` — what already exists on a topic, BEFORE anything is designed (#727).

WHY THIS MODULE EXISTS. Ray, 2026-09-09, verbatim: *"we have been working
towards this already — the dynamic workflows should search this project, git
local branches or git worktrees, github issues, plans (include from ~/.claude)
and ensure we never forget this."* He was right. When the dependency-upgrade
workflow was designed that day, 13 published design pages, ~10 plan files, 7
handoffs, ~12 unmerged branches and 199 matching issues already existed for the
topic — every one found by hand, by five fact-finding agents, at the cost of a
session. This is that search as ONE deterministic command, so phase 0 of the
saved upgrade workflow can run it and nobody has to remember to.

WHAT IT REUSES (`use-tool-builtins.md`). `git grep --all-match` is the
tracked-file search; `git for-each-ref`, `rev-list --left-right --count` and
`worktree list --porcelain` are the branch census, with ONE `gh pr list
--state merged` per repo to tell a squash-merged head from live work — matched
by the PR's head COMMIT against the measured tip, never by name alone; `gh api
search/issues` is the issue search (never `gh search`, which returns `[]` on a
rate limit and reads as "none"); `kb_setup.recall` is the work-memory ranking,
called in-process.
Nothing here re-implements a search a tool already ships — the module is the
seam that runs all seven probes with one denominator each.

THE CONTRACT, shared with `session_select` and `write_attribution`: **every
probe reports what it EXAMINED beside what it MATCHED**, and a probe whose tool
failed says `could_not_ask` rather than `0`. Two refusals follow:

- nothing was examined at all -> `Rc.NOT_RUN`, naming why, and no report;
- something was examined and the topic matched nothing -> the report is still
  written (the branch census is worth having regardless), and the CLI exits
  `Rc.NOT_RUN` naming every count — so a workflow step can never mistake "no
  prior work" for "the step was skipped" (#727's FAIL arm).

TWO MATCHING RULES, deliberately asymmetric. A FILE (tracked source, a plan, a
design page) must contain EVERY stem — a file is long, and requiring all of them
is what makes the hit precise. A NAME (a branch, a worktree) matches on ANY stem
— a name is a few words, and requiring all of them would miss `feat/upgrade-x`
for the topic "dependency upgrade". Stems are crude prefix stems (`dependency`
-> `dependenc`, `upgrade` -> `upgrad`) so plurals and verb forms fall inside a
substring search; they are printed in every report because a token spelling is
a bound (`probes-need-a-control-arm.md` rule 3).

WHAT IT DOES NOT CLAIM. It finds what the WORDS reach. A branch named for its
ticket number, a plan that discusses the topic in synonyms, an issue titled in
other vocabulary — none are found, and the report says so by printing the
stems. Widen the topic, or read the `branches` section, which lists EVERY branch
with unique commits whether or not it matched: pending work is pending
regardless of what it is called.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec

from kb_setup import events, recall
from kb_setup.generated.recall_work import (
    Branch,
    Hit,
    Probe,
    ProbeName,
    ProbeStatus,
    RecallWork,
    Repo,
    Verdict,
    Where,
)
from kb_setup.lexical import tokenize
from kb_setup.result import Err, Ok, Rc, Result, exit_code

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

#: A command runner: argv, cwd, timeout -> (rc, stdout, stderr). Injectable so the
#: tests drive `gh` with canned answers while `git` runs for real.
type Runner = Callable[[Sequence[str], Path | None, float], tuple[int, str, str]]

_GIT_TIMEOUT = 60.0
_GH_TIMEOUT = 90.0

#: Sibling checkouts examined by default when they exist beside this repo.
#: `graphify` is the fork checkout Ray named as the ONE place fork work happens
#: (`docs/direction/2026-09-09-ray-directives.md` §2); `dotfiles` is the sibling
#: whose lock-refresh machinery the upgrade workflow reuses.
DEFAULT_SIBLINGS = ("graphify", "dotfiles")

#: Tracked paths the file probe never searches. `graphify-out/memory/` is the
#: memory probe's territory; `sources/` and `raw/` are vendored upstream material
#: (the graph's territory) — a hit there is not OUR prior work.
EXCLUDED_PATHSPECS = ("graphify-out", "sources", "raw")

#: Plan locations, relative to the repo root. `~/.claude/plans` is added at run
#: time because Ray asked for it by name ("include from ~/.claude").
PLAN_GLOBS = (
    ".planning/*/task_plan.md",
    ".planning/*/findings.md",
    ".planning/*/progress.md",
    ".agent/plans/session-*.md",
)

#: Words that carry no topic. Short and deliberately incomplete: a stopword list
#: that grows is a second, unmeasured ranking signal, which is why `lexical.py`
#: has none. This one exists only so `--all-match` is never asked to require
#: "the" of every file.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "does",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "our",
        "that",
        "the",
        "this",
        "to",
        "we",
        "what",
        "when",
        "which",
        "with",
    }
)
_MIN_TOKEN = 3
#: A stem shorter than this keeps the whole token: cutting `mise` to three letters
#: would reach "promise" and "missing", which is noise, not recall.
_MIN_STEM = 4
#: Longest suffix first, so `dependencies` loses `ies` rather than `s`.
_SUFFIXES = ("ies", "ing", "es", "ed", "s", "y", "e")

DEFAULT_TOP = 10
DEFAULT_LIMIT = 40
_MAX_SEARCH_PAGE = 100
#: The output contract's `topic` bound (`schemas/recall-work.schema.json`,
#: `maxLength`). Enforced BEFORE searching: a 639-character topic once ran to
#: completion and emitted JSON its own decoder refused (Astra round 1, P2).
_MAX_TOPIC = 512
#: Full object names travel internally so a merged PR's head can be matched to
#: the measured tip; this many characters are shown.
_SHORT_SHA = 12
#: Merged PRs listed per repo, newest first. dotfiles is past 990 PRs, so 1000
#: would already be a page that comes back full; the probe says when one does.
_MERGED_PR_LIMIT = 3000
#: Pending branches shown on stdout; the report carries the rest.
_SUMMARY_ROWS = 25
_MAX_SLUG = 60
_TITLE_BYTES = 8192
#: `for-each-ref` is asked for five tab-separated columns, one of which is the
#: `%(ahead-behind:<base>)` pair (git >= 2.41) — the whole census in ONE call per
#: repo. The first live run made one `rev-list` per branch, 516 of them.
_REF_COLUMNS = 5
_COUNT_COLUMNS = 2

_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_SLUG_RE = re.compile(r"github\.com[:/](?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?/?$")
_VERDICT_ORDER = {Verdict.live: 0, Verdict.unverified: 1, Verdict.current: 2, Verdict.merged: 3}


# --- stems -------------------------------------------------------------------


def _stem(token: str) -> str:
    """Strip one common suffix so a substring search reaches the inflected forms.

    A crude PREFIX stem, not a linguistic one: `dependency` -> `dependenc` reaches
    "dependencies"; `upgrade` -> `upgrad` reaches "upgrading" and "upgraded". A
    token that would fall under `_MIN_STEM` keeps its whole spelling.
    """
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_STEM:
            return token[: -len(suffix)]
    return token


def stems(topic: str) -> list[str]:
    """The prefix stems a topic searches for — first-seen order, deduplicated."""
    seen: list[str] = []
    for token in tokenize(topic):
        if token in _STOPWORDS or len(token) < _MIN_TOKEN:
            continue
        stem = _stem(token)
        if stem not in seen:
            seen.append(stem)
    return seen


def search_words(topic: str) -> list[str]:
    """The topic's words with stopwords removed, unstemmed — what GitHub search gets."""
    return [t for t in tokenize(topic) if t not in _STOPWORDS and len(t) >= _MIN_TOKEN]


def _all(text: str, terms: Sequence[str]) -> bool:
    lowered = text.lower()
    return all(term in lowered for term in terms)


def _any(text: str, terms: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def slug(topic: str) -> str:
    """A filesystem-safe report name: lowercase, runs of anything else become `-`."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return cleaned[:_MAX_SLUG].strip("-") or "topic"


# --- runner + repo context ----------------------------------------------------


def subprocess_runner(
    argv: Sequence[str], cwd: Path | None, timeout: float
) -> tuple[int, str, str]:
    """Run one command, bounded. A missing binary or a timeout is an rc, never a raise."""
    try:
        proc = subprocess.run(
            list(argv), cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError as exc:
        return 127, "", f"{argv[0]}: not found ({exc})"
    except subprocess.TimeoutExpired:
        return 124, "", f"{argv[0]}: timed out after {timeout:g}s"
    return proc.returncode, proc.stdout, proc.stderr


@dataclass(frozen=True)
class Worktree:
    """One entry of `git worktree list --porcelain`."""

    path: Path
    head: str
    branch: str | None


@dataclass(frozen=True)
class RepoCtx:
    """One checkout, resolved: where it is, what its base is, what is checked out."""

    path: Path
    name: str
    base: str
    base_branch: str
    slug: str | None
    #: None when `git worktree list` itself failed. That is not "no worktrees":
    #: with what is checked out unknown, no branch in this repo may read `merged`.
    worktrees: tuple[Worktree, ...] | None

    @property
    def checked_out(self) -> frozenset[str]:
        """Branch names some worktree has checked out — never deletable from here."""
        if self.worktrees is None:
            return frozenset()
        return frozenset(w.branch for w in self.worktrees if w.branch is not None)

    def is_primary(self, worktree: Worktree) -> bool:
        """True for the repo itself; macOS's `/var` -> `/private/var` link is resolved."""
        return worktree.path.resolve() == self.path.resolve()


def _git(ctx_path: Path, runner: Runner, *args: str) -> tuple[int, str, str]:
    return runner(["git", *args], ctx_path, _GIT_TIMEOUT)


def _slug_of(url: str) -> str | None:
    match = _SLUG_RE.search(url.strip())
    return match.group("slug") if match else None


def _base_ref(path: Path, runner: Runner) -> tuple[str, str] | None:
    """(ref to measure against, its branch name): origin/HEAD, else origin/main, else main."""
    rc, out, _ = _git(path, runner, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if rc == 0 and out.strip():
        ref = out.strip()
        return ref, ref.split("/", 1)[1] if "/" in ref else ref
    for ref, branch in (("origin/main", "main"), ("main", "main")):
        rc, _, _ = _git(path, runner, "rev-parse", "--verify", "-q", ref)
        if rc == 0:
            return ref, branch
    return None


def _worktrees(top: Path, runner: Runner) -> list[Worktree] | None:
    """The porcelain worktree list, or None when git could not produce one.

    None, not `[]`: an empty list reads as "nothing checked out anywhere" and
    would let a checked-out branch be judged deletable (Astra round 1, P2).
    """
    rc, out, _ = _git(top, runner, "worktree", "list", "--porcelain")
    if rc != 0:
        return None
    found: list[Worktree] = []
    path: Path | None = None
    head = ""
    branch: str | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            if path is not None:
                found.append(Worktree(path, head, branch))
            path, head, branch = Path(line.removeprefix("worktree ")), "", None
        elif line.startswith("HEAD "):
            head = line.removeprefix("HEAD ")
        elif line.startswith("branch "):
            branch = line.removeprefix("branch ").removeprefix("refs/heads/")
    if path is not None:
        found.append(Worktree(path, head, branch))
    return found


def repo_context(path: Path, runner: Runner) -> RepoCtx | None:
    """Resolve a checkout, or None when it is not a git repo with a measurable base."""
    rc, out, _ = _git(path, runner, "rev-parse", "--show-toplevel")
    if rc != 0 or not out.strip():
        return None
    top = Path(out.strip())
    base = _base_ref(top, runner)
    if base is None:
        return None
    rc, url, _ = _git(top, runner, "remote", "get-url", "origin")
    listed = _worktrees(top, runner)
    return RepoCtx(
        path=top,
        name=top.name,
        base=base[0],
        base_branch=base[1],
        slug=_slug_of(url) if rc == 0 else None,
        worktrees=None if listed is None else tuple(listed),
    )


# --- the request ----------------------------------------------------------------


@dataclass(frozen=True)
class Options:
    """A parsed `kb-recall-work` invocation."""

    topic: str
    repos: tuple[Path, ...] = ()
    siblings: bool = True
    offline: bool = False
    top: int = DEFAULT_TOP
    limit: int = DEFAULT_LIMIT
    as_json: bool = False
    out: Path | None = None
    memory_dir: Path | None = None
    plans_home: Path | None = None


@dataclass(frozen=True)
class Search:
    """What every probe needs: the terms, the runner, and the bounds."""

    topic: str
    stems: list[str]
    runner: Runner
    offline: bool
    limit: int
    top: int


# --- probes ---------------------------------------------------------------------


def _summary_of(path: Path) -> str:
    """A page's `<title>`, else a markdown file's first H1, else empty. Reads 8 KB."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            head = handle.read(_TITLE_BYTES)
    except OSError:
        return ""
    title = _TITLE_RE.search(head)
    if title:
        return " ".join(title.group(1).split())
    heading = _HEADING_RE.search(head)
    return heading.group(1) if heading else ""


def _is_artifact_page(rel: str) -> bool:
    return rel.startswith("docs/artifacts/") and rel.endswith(".html")


def _tracked_paths(ctx: RepoCtx, runner: Runner) -> list[str] | None:
    """The tracked files the grep can reach — the SAME pathspec, so the denominator is honest.

    Counting every tracked file while grepping only the eligible ones reported
    1,749 examined for 1,183 searchable on this checkout (Astra round 1, P2).
    """
    excludes = [f":(exclude){p}" for p in EXCLUDED_PATHSPECS]
    rc, out, _ = _git(ctx.path, runner, "ls-files", "-z", "--", ".", *excludes)
    if rc != 0:
        return None
    return [p for p in out.split("\0") if p]


def _grep_tracked(ctx: RepoCtx, search: Search) -> list[str] | None:
    """Tracked files containing EVERY stem, or None when git grep itself failed."""
    argv = ["grep", "-I", "-i", "-l", "-F", "--all-match"]
    for stem in search.stems:
        argv += ["-e", stem]
    argv += ["--", ".", *[f":(exclude){p}" for p in EXCLUDED_PATHSPECS]]
    rc, out, err = _git(ctx.path, search.runner, *argv)
    if rc == 0:
        return sorted(out.splitlines())
    if rc == 1 and not err.strip():
        return []  # git grep's "no match" is rc 1 with nothing on stderr
    return None


def probe_files(repos: Sequence[RepoCtx], search: Search) -> tuple[Probe, Probe]:
    """`tracked_files` and `artifact_pages`, from one `git grep` per repo."""
    files_examined = pages_examined = 0
    file_hits: list[Hit] = []
    page_hits: list[Hit] = []
    broken: list[str] = []
    for ctx in repos:
        tracked = _tracked_paths(ctx, search.runner)
        matched = _grep_tracked(ctx, search) if tracked is not None else None
        if tracked is None or matched is None:
            broken.append(ctx.name)
            continue
        files_examined += len(tracked)
        pages_examined += sum(1 for p in tracked if _is_artifact_page(p))
        for rel in matched:
            hit = Hit(ref=rel, summary=_summary_of(ctx.path / rel), repo=ctx.name)
            (page_hits if _is_artifact_page(rel) else file_hits).append(hit)
    all_broken = bool(broken) and len(broken) == len(repos)
    status = ProbeStatus.could_not_ask if all_broken else ProbeStatus.ran
    note = f"; git failed in {', '.join(broken)}" if broken else ""
    excluded = ", ".join(f"{p}/" for p in EXCLUDED_PATHSPECS)
    files = Probe(
        name=ProbeName.tracked_files,
        status=status,
        examined=files_examined,
        matched=len(file_hits),
        detail=f"git grep --all-match over tracked files, excluding {excluded}{note}",
        hits=file_hits,
    )
    pages = Probe(
        name=ProbeName.artifact_pages,
        status=status,
        examined=pages_examined,
        matched=len(page_hits),
        detail=f"the docs/artifacts/*.html subset of the same grep{note}",
        hits=page_hits,
    )
    return files, pages


@dataclass(frozen=True)
class _Ref:
    name: str
    where: Where
    tip: str
    date: str
    subject: str
    ahead: int
    behind: int


#: (full tip oid, date, subject, ahead, behind)
type _RefMeta = tuple[str, str, str, int, int]


def _parse_ref_line(line: str) -> tuple[str, _RefMeta] | None:
    """One `for-each-ref` line -> (refname, (tip, date, subject, ahead, behind)), or None."""
    parts = line.split("\t", _REF_COLUMNS - 1)
    if len(parts) < _REF_COLUMNS:
        return None
    refname, tip, date, counts, subject = parts
    pair = counts.split()
    if len(pair) != _COUNT_COLUMNS or not all(c.isdigit() for c in pair):
        return None
    return refname, (tip, date, subject, int(pair[0]), int(pair[1]))


def _refs(ctx: RepoCtx, runner: Runner) -> tuple[list[_Ref], int] | None:
    """Every local and origin branch except the base, measured, in ONE git call.

    Returns (rows, unmeasured). Local and remote refs of one name are ONE row
    (`both`) only when their tips are identical; divergent tips are two rows,
    each measured and judged on its own — collapsing them showed the local
    counts as `both` and made a remote-only tip a deletion candidate (Astra
    round 1, P1). `%(ahead-behind:<base>)` is what makes this one call rather
    than one per branch.
    """
    fmt = (
        "%(refname)%09%(objectname)%09%(committerdate:short)%09"
        f"%(ahead-behind:{ctx.base})%09%(subject)"
    )
    rc, out, _ = _git(
        ctx.path, runner, "for-each-ref", f"--format={fmt}", "refs/heads", "refs/remotes/origin"
    )
    if rc != 0:
        return None
    local: dict[str, _RefMeta] = {}
    remote: dict[str, _RefMeta] = {}
    unmeasured = 0
    for line in out.splitlines():
        parsed = _parse_ref_line(line)
        if parsed is None:
            unmeasured += 1
            continue
        refname, meta = parsed
        if refname.startswith("refs/heads/"):
            local[refname.removeprefix("refs/heads/")] = meta
        elif refname.startswith("refs/remotes/origin/"):
            name = refname.removeprefix("refs/remotes/origin/")
            if name != "HEAD":
                remote[name] = meta
    return _merge_sides(local, remote, ctx.base_branch), unmeasured


def _merge_sides(
    local: dict[str, _RefMeta], remote: dict[str, _RefMeta], base_branch: str
) -> list[_Ref]:
    """One `both` row per identical pair; a divergent pair is two rows, one per tip."""
    rows: list[_Ref] = []
    for name in sorted(set(local) | set(remote)):
        if name == base_branch:
            continue
        here, there = local.get(name), remote.get(name)
        if here is not None and there is not None and here[0] == there[0]:
            rows.append(_Ref(name, Where.both, *here))
            continue
        if here is not None:
            rows.append(_Ref(name, Where.local, *here))
        if there is not None:
            rows.append(_Ref(name, Where.remote, *there))
    return rows


@dataclass(frozen=True)
class _MergedHead:
    """One merged PR: its number and the head commit it was merged FROM."""

    number: int
    oid: str


@dataclass(frozen=True)
class _MergedHeads:
    """A repo's PRs merged INTO its base, keyed by head branch name."""

    by_name: dict[str, list[_MergedHead]]
    #: Rows GitHub returned BEFORE any filtering or de-duplication — the only
    #: honest saturation signal. Counting distinct names missed a full page whose
    #: names repeated (Astra round 1, P2).
    rows: int

    @property
    def saturated(self) -> bool:
        """True when the page came back full, so an older merge may be missing."""
        return self.rows >= _MERGED_PR_LIMIT

    def match(self, name: str, tip: str) -> _MergedHead | None:
        """The merged PR whose head commit IS this tip. A name alone is not evidence.

        A branch reused after its PR merged carries the same name and a newer
        tip; matching by name called that unfinished work `merged` (Astra round
        1, P1). A squash merge leaves the branch tip where the PR's head was, so
        an untouched merged branch still matches.
        """
        for head in self.by_name.get(name, []):
            if head.oid == tip:
                return head
        return None


def _merged_heads(ctx: RepoCtx, runner: Runner) -> _MergedHeads | None:
    """The repo's merged PRs from ONE `gh pr list`, keyed by head branch.

    One call per repo rather than one per branch: the first live run asked GitHub
    once for each of 98 branches in this repo alone and took five minutes. This
    asks once and matches locally. `None` means GitHub could not be asked (no
    GitHub origin, a failed call, non-JSON) — a state the caller keeps apart from
    "asked, and no PR was merged from that head".

    Only PRs merged INTO the base branch count; one merged into some other
    branch is not merged into the base. The bound: only the newest
    `_MERGED_PR_LIMIT` merged PRs are listed, so a branch merged further back
    reads `live`; the probe's detail says so when the page came back full.
    """
    if ctx.slug is None:
        return None
    argv = ["gh", "pr", "list", "--repo", ctx.slug, "--state", "merged"]
    argv += ["--json", "number,headRefName,headRefOid,baseRefName"]
    argv += ["--limit", str(_MERGED_PR_LIMIT)]
    rc, out, _ = runner(argv, None, _GH_TIMEOUT)
    if rc != 0:
        return None
    try:
        rows = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(rows, list):
        return None
    by_name: dict[str, list[_MergedHead]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("baseRefName") != ctx.base_branch:
            continue
        number, head, oid = row.get("number"), row.get("headRefName"), row.get("headRefOid")
        if isinstance(number, int) and isinstance(head, str) and isinstance(oid, str):
            by_name.setdefault(head, []).append(_MergedHead(number, oid))
    return _MergedHeads(by_name, len(rows))


def _verdict(ctx: RepoCtx, row: _Ref, merged: _MergedHead | None, *, asked: bool) -> Verdict:
    if ctx.worktrees is None:
        # What is checked out is unknown, so nothing here may read `merged`.
        return Verdict.unverified
    if row.where is not Where.remote and row.name in ctx.checked_out:
        return Verdict.current
    if row.ahead == 0 or merged is not None:
        return Verdict.merged
    return Verdict.live if asked else Verdict.unverified


def _branch_row(ctx: RepoCtx, row: _Ref, search: Search, merged: _MergedHeads | None) -> Branch:
    matched = merged.match(row.name, row.tip) if merged is not None else None
    branch = Branch(
        repo=ctx.name,
        name=row.name,
        where=row.where,
        tip=row.tip[:_SHORT_SHA],
        date=row.date,
        subject=row.subject,
        ahead=row.ahead,
        behind=row.behind,
        verdict=_verdict(ctx, row, matched, asked=merged is not None),
        topic_match=_any(f"{row.name} {row.subject}", search.stems),
    )
    if matched is not None:
        branch.merged_pr = matched.number
    return branch


@dataclass
class _Census:
    """What the branch probe accumulates across repos, and the bounds it hit."""

    rows: list[Branch] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    broken: list[str] = field(default_factory=list)
    full_pages: list[str] = field(default_factory=list)
    unmeasured: int = 0


def _census_detail(search: Search, census: _Census) -> str:
    unverified = sum(1 for b in census.rows if b.verdict is Verdict.unverified)
    detail = (
        "name or tip subject contains ANY stem; every branch is measured against its repo's base"
    )
    if search.offline:
        detail += "; --offline, so merged-by-squash was not asked and ahead>0 reads unverified"
    elif unverified:
        detail += f"; GitHub could not be asked for {unverified} branch(es), left unverified"
    if census.full_pages:
        detail += (
            f"; only the newest {_MERGED_PR_LIMIT} merged PRs were listed in "
            f"{', '.join(census.full_pages)}, so an older merge can read live"
        )
    if census.unmeasured:
        detail += f"; {census.unmeasured} ref(s) could not be measured"
    if census.broken:
        detail += f"; could not list refs in {', '.join(census.broken)}"
    return detail


def _census_repo(ctx: RepoCtx, search: Search, census: _Census) -> None:
    listed = _refs(ctx, search.runner)
    if listed is None:
        census.broken.append(ctx.name)
        return
    rows, unmeasured = listed
    census.unmeasured += unmeasured
    merged = None if search.offline else _merged_heads(ctx, search.runner)
    if merged is not None and merged.saturated:
        census.full_pages.append(ctx.name)
    for row in rows:
        branch = _branch_row(ctx, row, search, merged)
        census.rows.append(branch)
        if branch.topic_match:
            hit = Hit(ref=row.name, summary=row.subject, repo=ctx.name, date=row.date)
            hit.state = branch.verdict.value
            census.hits.append(hit)


def probe_branches(repos: Sequence[RepoCtx], search: Search) -> tuple[Probe, list[Branch]]:
    """`branches`: topic-matching names as hits, and EVERY measured branch as the census."""
    census = _Census()
    for ctx in repos:
        _census_repo(ctx, search, census)
    # Newest first within a verdict, live verdicts first overall (stable sorts).
    census.rows.sort(key=lambda b: b.date, reverse=True)
    census.rows.sort(key=lambda b: _VERDICT_ORDER[b.verdict])
    all_broken = bool(census.broken) and len(census.broken) == len(repos)
    probe = Probe(
        name=ProbeName.branches,
        status=ProbeStatus.could_not_ask if all_broken else ProbeStatus.ran,
        examined=len(census.rows),
        matched=len(census.hits),
        detail=_census_detail(search, census),
        hits=census.hits,
    )
    return probe, census.rows


def probe_worktrees(repos: Sequence[RepoCtx], search: Search) -> Probe:
    """`worktrees`: every LINKED worktree is listed; matched = its branch names a stem."""
    hits: list[Hit] = []
    matched = 0
    broken: list[str] = []
    for ctx in repos:
        if ctx.worktrees is None:
            broken.append(ctx.name)
            continue
        for wt in ctx.worktrees:
            if ctx.is_primary(wt):
                continue
            match = wt.branch is not None and _any(wt.branch, search.stems)
            matched += int(match)
            label = wt.branch if wt.branch is not None else f"detached at {wt.head[:_SHORT_SHA]}"
            hit = Hit(ref=str(wt.path), summary=label, repo=ctx.name)
            hit.state = "topic" if match else "other"
            hits.append(hit)
    detail = (
        "linked worktrees only (the primary is the repo itself); all listed, "
        "matched = branch name contains a stem"
    )
    if broken:
        detail += (
            f"; COULD NOT LIST worktrees in {', '.join(broken)}, so no branch there reads merged"
        )
    all_broken = bool(broken) and len(broken) == len(repos)
    return Probe(
        name=ProbeName.worktrees,
        status=ProbeStatus.could_not_ask if all_broken else ProbeStatus.ran,
        examined=len(hits),
        matched=matched,
        detail=detail,
        hits=hits,
    )


def _gh_json(runner: Runner, argv: Sequence[str]) -> tuple[object | None, str]:
    """`gh api` output as JSON, or (None, why). Never a zero for a failed call."""
    rc, out, err = runner(["gh", *argv], None, _GH_TIMEOUT)
    if rc != 0:
        reason = err.strip().splitlines()[0] if err.strip() else f"gh exited {rc}"
        return None, reason
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        return None, f"gh returned non-JSON ({exc})"
    return data, ""


def _issues_enabled(ctx: RepoCtx, runner: Runner) -> tuple[bool | None, str]:
    data, why = _gh_json(runner, ["api", f"repos/{ctx.slug}"])
    if not isinstance(data, dict):
        return None, why or "unexpected repo payload"
    return bool(data.get("has_issues")), ""


#: GitHub search answers a timed-out query with rc 0, JSON, and this flag set —
#: `sources/gh/pkg/search/searcher.go:201-205`. A count from such a payload is
#: not a count (Astra round 1, P2).
_INCOMPLETE = "GitHub search returned incomplete_results (its search timed out)"


def _search_count(data: object) -> tuple[int | None, str]:
    """A search payload's total, or why it cannot be trusted."""
    if not isinstance(data, dict) or not isinstance(data.get("total_count"), int):
        return None, "no total_count in the search payload"
    if data.get("incomplete_results"):
        return None, _INCOMPLETE
    return int(data["total_count"]), ""


def _issue_total(ctx: RepoCtx, runner: Runner) -> tuple[int | None, str]:
    query = f"q=repo:{ctx.slug} is:issue"
    argv = ["api", "-X", "GET", "search/issues", "-f", query, "-f", "per_page=1"]
    data, why = _gh_json(runner, argv)
    if data is None:
        return None, why
    return _search_count(data)


@dataclass(frozen=True)
class _Found:
    """One topic search: how many issues matched in all, the page shown, or why not."""

    total: int | None
    hits: list[Hit] = field(default_factory=list)
    why: str = ""


def _issue_search(ctx: RepoCtx, search: Search) -> _Found:
    phrase = " ".join(search_words(search.topic))
    query = f"q=repo:{ctx.slug} is:issue {phrase}"
    argv = ["api", "-X", "GET", "search/issues", "-f", query]
    argv += ["-f", f"per_page={min(search.limit, _MAX_SEARCH_PAGE)}", "-f", "sort=updated"]
    data, why = _gh_json(search.runner, argv)
    if data is None:
        return _Found(None, why=why)
    total, why = _search_count(data)
    if total is None or not isinstance(data, dict):
        return _Found(None, why=why)
    hits: list[Hit] = []
    items = data.get("items")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("number"), int):
            continue
        hit = Hit(ref=f"#{item['number']}", summary=str(item.get("title") or ""), repo=ctx.name)
        hit.state = str(item.get("state") or "")
        hit.date = str(item.get("updated_at") or "")[:10]
        hits.append(hit)
    return _Found(total, hits)


@dataclass(frozen=True)
class _RepoIssues:
    """One repo's share of the issues probe: ran with counts, failed, or a note."""

    outcome: str
    text: str
    examined: int = 0
    matched: int = 0
    hits: list[Hit] = field(default_factory=list)


def _issues_for(ctx: RepoCtx, search: Search) -> _RepoIssues:
    if ctx.slug is None:
        return _RepoIssues("note", f"{ctx.name}: no GitHub origin")
    enabled, why = _issues_enabled(ctx, search.runner)
    if enabled is None:
        return _RepoIssues("failed", f"{ctx.name}: {why}")
    if not enabled:
        return _RepoIssues("note", f"{ctx.name}: issues disabled")
    total, why = _issue_total(ctx, search.runner)
    if total is None:
        return _RepoIssues("failed", f"{ctx.name}: {why}")
    found = _issue_search(ctx, search)
    if found.total is None:
        return _RepoIssues("failed", f"{ctx.name}: {found.why}")
    return _RepoIssues("ran", "", total, found.total, found.hits)


def probe_issues(repos: Sequence[RepoCtx], search: Search) -> Probe:
    """`issues`: GitHub search, open AND closed, per repo with an origin on GitHub.

    `examined` is every issue the repo has (a second search with no topic), so a
    zero beside it is a zero of something — and a search that could not be asked
    is `could_not_ask`, never counted as none.
    """
    detail = (
        "GitHub search (is:issue, open and closed) for the topic words; "
        "examined = every issue in the repo"
    )
    if search.offline:
        return Probe(
            name=ProbeName.issues,
            status=ProbeStatus.skipped,
            examined=0,
            matched=0,
            detail="--offline",
            hits=[],
        )
    results = [_issues_for(ctx, search) for ctx in repos]
    ran = [r for r in results if r.outcome == "ran"]
    failed = [r.text for r in results if r.outcome == "failed"]
    notes = [r.text for r in results if r.outcome == "note"]
    if ran:
        status = ProbeStatus.ran
    elif failed:
        status = ProbeStatus.could_not_ask
    else:
        status = ProbeStatus.skipped
    if failed:
        detail += "; COULD NOT ASK " + "; ".join(failed)
    if notes:
        detail += "; " + "; ".join(notes)
    return Probe(
        name=ProbeName.issues,
        status=status,
        examined=sum(r.examined for r in ran),
        matched=sum(r.matched for r in ran),
        detail=detail,
        hits=[hit for r in ran for hit in r.hits],
    )


def _display(path: Path, repo_root: Path) -> str:
    for base, prefix in ((repo_root, ""), (Path.home(), "~/")):
        try:
            return prefix + str(path.relative_to(base))
        except ValueError:
            continue
    return str(path)


def _mtime_date(path: Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        return ""
    return datetime.fromtimestamp(stat.st_mtime, tz=UTC).date().isoformat()


def probe_plans(repos: Sequence[RepoCtx], search: Search, plans_home: Path | None) -> Probe:
    """`plans`: every checkout's plan files and handoffs, plus `~/.claude/plans/*.md` once.

    Every checkout, not only the root: a sibling's `.agent/plans/session-*.md` is
    untracked, so no other probe can reach it, and the first version searched
    the root alone while listing the siblings as examined (Astra round 1, P2).
    """
    home = plans_home if plans_home is not None else Path.home() / ".claude" / "plans"
    files: list[tuple[Path, RepoCtx | None]] = []
    for ctx in repos:
        for pattern in PLAN_GLOBS:
            files.extend((p, ctx) for p in sorted(ctx.path.glob(pattern)))
    if home.is_dir():
        files.extend((p, None) for p in sorted(home.glob("*.md")))
    hits: list[Hit] = []
    unreadable = 0
    for path, ctx in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            unreadable += 1
            continue
        if _all(text, search.stems):
            heading = _HEADING_RE.search(text)
            root = ctx.path if ctx is not None else Path.home()
            hit = Hit(ref=_display(path, root), summary=heading.group(1) if heading else "")
            hit.date = _mtime_date(path)
            if ctx is not None:
                hit.repo = ctx.name
            hits.append(hit)
    examined = len(files) - unreadable
    detail = (
        f"{', '.join(PLAN_GLOBS)} in every checkout, and {home}; a plan must contain EVERY stem"
    )
    if unreadable:
        detail += f"; {unreadable} file(s) could not be read"
    return Probe(
        name=ProbeName.plans,
        status=ProbeStatus.ran if examined else ProbeStatus.skipped,
        examined=examined,
        matched=len(hits),
        detail=detail if examined else f"no plan files found ({detail})",
        hits=hits,
    )


def probe_memory(memory_dir: Path, search: Search) -> Probe:
    """`memory`: `kb-recall`'s BM25 ranking of the work-memory store, in-process."""
    request = recall.RecallRequest(
        question=search.topic,
        top=search.top,
        outcome="all",
        since=None,
        as_json=False,
        memory_dir=None,
    )
    result = recall.run_recall(request, memory_dir)
    if isinstance(result, Err):
        return Probe(
            name=ProbeName.memory,
            status=ProbeStatus.skipped,
            examined=0,
            matched=0,
            detail=result.message,
            hits=[],
        )
    if not isinstance(result, Ok):
        return Probe(
            name=ProbeName.memory,
            status=ProbeStatus.could_not_ask,
            examined=0,
            matched=0,
            detail="kb-recall returned an unexpected result",
            hits=[],
        )
    report = result.value
    hits: list[Hit] = []
    for h in report.hits:
        hit = Hit(ref=h.path, summary=h.question)
        hit.state, hit.date, hit.score = h.outcome, h.date[:10], h.score
        hits.append(hit)
    detail = f"kb-recall BM25 over {memory_dir} (outcome=all); top {search.top} shown"
    if report.unparsable:
        # `kb-recall` counts the files it could not index; dropping that here
        # reported a complete search over an incomplete store (Astra round 1, P2).
        detail += f"; {report.unparsable} file(s) in the store were NOT indexed"
    return Probe(
        name=ProbeName.memory,
        status=ProbeStatus.ran,
        examined=report.searched,
        matched=report.matched,
        detail=detail,
        hits=hits,
    )


# --- the run --------------------------------------------------------------------


def _sibling_paths(repo_root: Path, options: Options) -> list[Path]:
    found: list[Path] = []
    if options.siblings:
        found.extend(p for name in DEFAULT_SIBLINGS if (p := repo_root.parent / name).is_dir())
    found.extend(p for p in options.repos if p not in found)
    return found


def _iso(now: datetime | None) -> str:
    stamp = now if now is not None else datetime.now(UTC)
    return stamp.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def run(
    repo_root: Path,
    options: Options,
    runner: Runner = subprocess_runner,
    *,
    now: datetime | None = None,
) -> Result[RecallWork]:
    """Run every probe. Returns, never raises; writes nothing (that is `main`'s job)."""
    if len(options.topic) > _MAX_TOPIC:
        return Err(
            f"the topic is {len(options.topic)} characters; the output contract "
            f"allows {_MAX_TOPIC}",
            rc=Rc.BAD_REQUEST,
        )
    topic_stems = stems(options.topic)
    if not topic_stems:
        return Err(
            f"the topic {options.topic!r} has no searchable word (stopwords and words "
            f"under {_MIN_TOKEN} characters are dropped)",
            rc=Rc.BAD_REQUEST,
        )
    root = repo_context(repo_root, runner)
    if root is None:
        return Err(
            f"{repo_root} is not a git checkout with a base branch — nothing was examined",
            rc=Rc.NOT_RUN,
        )
    repos = [root]
    for path in _sibling_paths(repo_root, options):
        ctx = repo_context(path, runner)
        if ctx is not None and ctx.path not in {r.path for r in repos}:
            repos.append(ctx)
    search = Search(
        topic=options.topic,
        stems=topic_stems,
        runner=runner,
        offline=options.offline,
        limit=options.limit,
        top=options.top,
    )
    files, pages = probe_files(repos, search)
    branch_probe, census = probe_branches(repos, search)
    memory_dir = options.memory_dir or repo_root / "graphify-out" / "memory"
    probes = [
        files,
        pages,
        branch_probe,
        probe_worktrees(repos, search),
        probe_issues(repos, search),
        probe_plans(repos, search, options.plans_home),
        probe_memory(memory_dir, search),
    ]
    ran = [p for p in probes if p.status is ProbeStatus.ran]
    if sum(p.examined for p in ran) == 0:
        return Err(
            "nothing was examined — "
            + "; ".join(f"{p.name.value}: {p.status.value} ({p.detail})" for p in probes),
            rc=Rc.NOT_RUN,
        )
    default_report = repo_root / ".agent" / "kb" / "recall" / f"{slug(options.topic)}.md"
    return Ok(
        RecallWork(
            schema_version=1,
            topic=options.topic,
            stems=topic_stems,
            generated_at=_iso(now),
            repos=[Repo(name=r.name, path=str(r.path), base=r.base, slug=r.slug) for r in repos],
            probes=probes,
            branches=census,
            matched_total=sum(p.matched for p in ran),
            report_path=str(options.out or default_report),
        )
    )


# --- rendering ------------------------------------------------------------------


def _hit_line(hit: Hit) -> str:
    parts = [f"`{hit.ref}`"]
    if isinstance(hit.repo, str):
        parts.append(f"[{hit.repo}]")
    if isinstance(hit.state, str) and hit.state:
        parts.append(f"({hit.state})")
    if isinstance(hit.date, str) and hit.date:
        parts.append(hit.date)
    if isinstance(hit.score, float):
        parts.append(f"score={hit.score:.2f}")
    line = " ".join(parts)
    return f"{line} — {hit.summary}" if hit.summary else line


def _counts(work: RecallWork) -> str:
    return ", ".join(
        f"{p.name.value} {p.matched}/{p.examined}"
        if p.status is ProbeStatus.ran
        else f"{p.name.value} {p.status.value.upper()}"
        for p in work.probes
    )


def render_report(work: RecallWork, *, limit: int = DEFAULT_LIMIT) -> str:
    """The markdown report: a probe table, the hits per probe, and the whole branch census."""
    lines = [
        f"# recall-work: {work.topic}",
        "",
        f"- generated: {work.generated_at}",
        f"- stems: {', '.join(work.stems)} (prefix stems — a token spelling is a bound)",
        "- repos: " + ", ".join(f"{r.name} (base `{r.base}`)" for r in work.repos),
        f"- topic matches: {work.matched_total}",
        "",
        "## Probes",
        "",
        "| probe | status | examined | matched | bound |",
        "|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {p.name.value} | {p.status.value} | {p.examined} | {p.matched} | {p.detail} |"
        for p in work.probes
    )
    for probe in work.probes:
        if not probe.hits:
            continue
        heading = f"## {probe.name.value} — {probe.matched} matched of {probe.examined} examined"
        lines += ["", heading, ""]
        lines.extend(f"- {_hit_line(h)}" for h in probe.hits[:limit])
        if len(probe.hits) > limit:
            lines.append(f"- … {len(probe.hits) - limit} more not shown (--limit {limit})")
    lines += [
        "",
        "## Branches — every branch measured, topic-matching or not",
        "",
        "| repo | branch | where | ahead | behind | verdict | merged PR | date | topic | subject |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for b in work.branches:
        merged = str(b.merged_pr) if isinstance(b.merged_pr, int) else ""
        topic = "yes" if b.topic_match else ""
        subject = b.subject.replace("|", "\\|")
        lines.append(
            f"| {b.repo} | `{b.name}` | {b.where.value} | {b.ahead} | {b.behind} | "
            f"{b.verdict.value} | {merged} | {b.date} | {topic} | {subject} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_summary(work: RecallWork) -> str:
    """The stdout summary: one line per probe, then the branches with unique commits."""
    lines = [
        f"[recall-work] {work.topic!r} — stems: {', '.join(work.stems)}",
        "  repos: " + ", ".join(f"{r.name} ({r.base})" for r in work.repos),
    ]
    lines.extend(
        f"  {p.name.value:<15} {p.status.value:<14} "
        f"examined {p.examined:>6}  matched {p.matched:>5}"
        for p in work.probes
    )
    lines.append(f"  topic matches: {work.matched_total} -> {work.report_path}")
    pending = [b for b in work.branches if b.verdict in (Verdict.live, Verdict.unverified)]
    if pending:
        lines.append(f"  branches with unique commits and no merged PR: {len(pending)}")
        lines.extend(
            f"    {b.repo:<14} {b.name:<44} +{b.ahead}/-{b.behind} {b.verdict.value:<10} "
            f"{b.date} {b.subject[:60]}"
            for b in pending[:_SUMMARY_ROWS]
        )
        if len(pending) > _SUMMARY_ROWS:
            lines.append(f"    … {len(pending) - _SUMMARY_ROWS} more in the report")
    return "\n".join(lines)


def render_json(work: RecallWork) -> str:
    """The generated contract, as indented JSON."""
    return msgspec.json.format(msgspec.json.encode(work).decode(), indent=2)


# --- the CLI --------------------------------------------------------------------

_VALUE_FLAGS = ("--repo", "--top", "--limit", "--out", "--memory-dir", "--plans-home")
_BOOL_FLAGS = ("--no-siblings", "--offline", "--json")
_USAGE = (
    'kb-recall-work "<topic>" [--repo PATH]... [--no-siblings] [--offline] '
    "[--top N] [--limit N] [--json] [--out PATH]"
)


def _apply_value(flag: str, raw: str, values: dict[str, object]) -> Err | None:
    if flag == "--repo":
        repos = values.setdefault("repos", [])
        if isinstance(repos, list):
            repos.append(Path(raw))
        return None
    if flag in ("--top", "--limit"):
        if not raw.isdigit() or int(raw) < 1:
            return Err(f"{flag} needs a positive integer, got {raw!r}", rc=Rc.BAD_REQUEST)
        values[flag] = int(raw)
        return None
    values[flag] = Path(raw)
    return None


def _path_or_none(value: object) -> Path | None:
    return value if isinstance(value, Path) else None


def parse(args: Sequence[str]) -> Result[Options]:
    """The CLI grammar. Bare words are the topic; a malformed flag is a BAD_REQUEST."""
    words: list[str] = []
    values: dict[str, object] = {"repos": []}
    flags: set[str] = set()
    pending = list(args)
    while pending:
        item = pending.pop(0)
        if item in _BOOL_FLAGS:
            flags.add(item)
        elif item in _VALUE_FLAGS:
            if not pending:
                return Err(f"{item} needs a value", rc=Rc.BAD_REQUEST)
            refusal = _apply_value(item, pending.pop(0), values)
            if refusal is not None:
                return refusal
        elif item.startswith("-"):
            return Err(f"unknown argument: {item} (usage: {_USAGE})", rc=Rc.BAD_REQUEST)
        else:
            words.append(item)
    topic = " ".join(words).strip()
    if not topic:
        return Err(f"a topic is required (usage: {_USAGE})", rc=Rc.BAD_REQUEST)
    repos = values["repos"]
    top = values.get("--top", DEFAULT_TOP)
    limit = values.get("--limit", DEFAULT_LIMIT)
    return Ok(
        Options(
            topic=topic,
            repos=tuple(repos) if isinstance(repos, list) else (),
            siblings="--no-siblings" not in flags,
            offline="--offline" in flags,
            top=top if isinstance(top, int) else DEFAULT_TOP,
            limit=limit if isinstance(limit, int) else DEFAULT_LIMIT,
            as_json="--json" in flags,
            out=_path_or_none(values.get("--out")),
            memory_dir=_path_or_none(values.get("--memory-dir")),
            plans_home=_path_or_none(values.get("--plans-home")),
        )
    )


def main(repo_root: Path, argv: Sequence[str] = ()) -> int:
    """`kb-recall-work <topic>`: run, write the report, print, and exit by the contract."""
    parsed = parse(argv)
    if not isinstance(parsed, Ok):
        events.warn("recall_work.refused", f"[recall-work] refusing — {parsed.message}")
        return exit_code(parsed)
    options = parsed.value
    result = run(repo_root, options)
    if not isinstance(result, Ok):
        events.warn("recall_work.not_run", f"[recall-work] {result.message}", topic=options.topic)
        return exit_code(result)
    work = result.value
    report = Path(work.report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(work, limit=options.limit), encoding="utf-8")
    if options.as_json:
        events.say("recall_work.json", render_json(work), topic=options.topic)
    else:
        events.say(
            "recall_work.summary",
            render_summary(work),
            topic=options.topic,
            matched=work.matched_total,
        )
    if work.matched_total == 0:
        events.warn(
            "recall_work.no_match",
            f"[recall-work] no prior work matched {options.topic!r} — examined: {_counts(work)}; "
            f"stems: {', '.join(work.stems)}; the branch census is still at {report}",
            topic=options.topic,
        )
        return int(Rc.NOT_RUN)
    return int(Rc.OK)
