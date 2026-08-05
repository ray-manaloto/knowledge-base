"""Turn a citation into a verdict against this repo's filesystem.

FOUR STATES, NEVER A BOOLEAN. They are kept distinct for the reason
`kb_setup.currency` keeps DRIFT / SKIP / OK distinct: collapsing "could not
tell" into either neighbour is how every defect in that engine's review
happened. A bare filename matching three files is not a broken citation and must
not be reported as one; nor is it a pass. See :class:`State`.

RESOLUTION ORDER, and why each tier exists. Every one was added because the tier
above it produced a measured false positive over this repo's 28 committed
handoffs — the run went from 99 failures to 16, of which 3 were real:

1. **The literal repo-relative path.** No search, nothing to get wrong.
2. **A path SUFFIX in the authored tree.** Authors cite the distinctive tail:
   `currency/run.py` for `python/src/kb_setup/currency/run.py`. Matched on
   segment boundaries, so it never degrades into substring matching.
3. **The derived-output root, one level deep.** `graph.json` is the most-cited
   filename in the corpus and exists nowhere but `graphify-out/`, which is
   pruned from the walk (139,257 files). The bound is deliberate and stated per
   `.claude/rules/probes-need-a-control-arm.md`: every derived artifact cited by
   bare name (`graph.json`, `graph-prose.json`, `GRAPH_REPORT.md`,
   `manifest.json`, `graph.graphml`, `graph.svg`) is at that root's top level,
   and anything deeper is cited with its directory, which needs no search.
4. **The pinned upstream clones under `sources/`.** `watch.py:1499` and
   `redactions.rs:31` name graphify's and mise's own source, which this repo
   pins at a commit and can therefore actually read — so this tier does not just
   remove false positives, it makes the line-number check run against the file
   the author meant. Consulted LAST, so a vendored copy can never shadow an
   authored file of the same name.

WHAT IS NEVER SEARCHED. The virtualenv, git's object store (including each
pinned clone's own), lint/test caches, and every graphify output tree — none
authored, all large, and `README.md` in each would turn ordinary shorthand into
permanent AMBIGUOUS noise. For scale, `find` over the trees involved,
2026-08-03, and note these move: `graphify-out/` 139,257 files, `sources/`
100,434, `.venv/` 3,349, against ~80 in `docs/` and ~50 in `.claude/`. The
ratio is the durable fact — the authored tree is three orders of magnitude
smaller than what surrounds it — and the small counts are stated loosely on
purpose, because a commit that adds one doc invalidates an exact one.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from kb_setup.citations import ELISION

#: Directory NAMES pruned wherever they appear: caches, the virtualenv, git's
#: own object store, and every graphify output tree. None is authored and all
#: are large.
#:
#: `graphify-out` is pruned BY NAME rather than as a root, which the first
#: version got wrong. Measured on this repo, the derived tree also appears at
#: `python/graphify-out/`, `tests/graphify-out/`, `brain/graphify-out/` and
#: `.self-graph/graphify-out/` — so a root-only prune left `graph.json` matching
#: seven files and reported the most-cited filename in the entire corpus as
#: ambiguous when it has one obvious referent.
_DERIVED_ROOT = "graphify-out"
_PRUNED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".rumdl_cache",
        ".self-graph",
        ".venv",
        "__pycache__",
        "node_modules",
        _DERIVED_ROOT,
    }
)

#: Top-level directories pruned entirely. `raw/` is the fetch landing zone — an
#: input, never authored.
_PRUNED_ROOTS: frozenset[str] = frozenset({"raw"})

#: Subdirectories of `sources/` that ARE authored and committed. Everything else
#: under `sources/` is a gitignored clone re-fetched from a pinned manifest, so
#: pruning all of `sources/` would be wrong in the other direction: a vendored
#: transcript is a legitimate citation target.
_SOURCES_KEPT: frozenset[str] = frozenset({"extractions", "media"})


#: How many matching paths an AMBIGUOUS finding names before it says "… total".
_SHOWN_MATCHES = 4

#: Parts in a split `sources/<child>/` prefix. Below this the prefix IS
#: `sources/` itself, whose own contents (the committed `*.manifest` pins) are
#: authored rather than vendored.
_SOURCES_CHILD_PARTS = 3


class State(Enum):
    """The four answers a citation can get.

    RESOLVED and MISSING are the two verdicts. AMBIGUOUS and UNVERIFIABLE are
    kept as their own states rather than folded into either — collapsing "could
    not tell" into a verdict is the mistake `kb_setup.currency` is built to
    avoid, and both of these mean something different from "wrong":

    * AMBIGUOUS — several files match a shorthand. The citation is probably fine
      and a reader may want to disambiguate it.
    * UNVERIFIABLE — the citation is not a claim about this repository at all
      (`graphify/serve.py`, `dotfiles/python/pyproject.toml`). Calling it broken
      would be asserting a fact about a repository we cannot see.
    """

    RESOLVED = "RESOLVED"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class Resolution:
    """One citation's verdict, plus what was found instead when it failed."""

    state: State
    detail: str
    match: Path | None = None


@dataclass(frozen=True)
class Index:
    """Every path this repo can see, split into what it authored and what it pins.

    Built once and passed down rather than rebuilt per citation: a handoff
    carries tens of citations and the walk is the expensive part. Held as a
    value the caller owns instead of a module-level cache, so nothing can go
    stale behind a caller's back.

    The vendored tier is the pinned upstream clones under `sources/`. Including
    them is not generosity — handoffs cite `watch.py:1499` and `redactions.rs:31`
    meaning graphify's and mise's own source, which this repo pins at a commit
    and can therefore actually READ. Excluding them turned every such citation
    into a false positive AND skipped the line-number check that is the whole
    point of the ticket. Re-derived from `build_index` itself on 2026-08-04:
    the vendored tier is 72,348 files and the whole walk takes 0.54s. (An
    earlier note here said 95,654 in 0.41s, taken from a bare `find sources`
    rather than from this walk, which also prunes each clone's own `.git`.)
    """

    files: tuple[str, ...]
    dirs: tuple[str, ...]
    vendored: tuple[str, ...] = ()

    def authored_only(self) -> Index:
        """This index with the vendored tier dropped.

        A method rather than an `Index(files=…, dirs=…)` at the call site, so the
        narrowing lives on the type that knows its own tiers. (Standards lane.)

        `dataclasses.replace`, NOT `Index(files=…, dirs=…)`. The call-site form
        this replaced dropped the vendored tier by OMISSION — it relied on the
        default — so any field the dataclass gained later would be silently
        dropped with it. The first version of this method moved that form inside
        the method and kept it, which relocated the defect rather than removing
        it while the docstring claimed otherwise. `replace` carries every field
        forward and names the one being changed, which is the difference between
        a fix and a fix-shaped edit. (Cold lane, round 2.)
        """
        return replace(self, vendored=())


def build_index(repo_root: Path) -> Index:
    """Walk the repo once, classifying each path as authored or vendored."""
    files: list[str] = []
    dirs: list[str] = []
    vendored: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        here = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if d not in _PRUNED_DIR_NAMES)
        if here == repo_root:
            dirnames[:] = [d for d in dirnames if d not in _PRUNED_ROOTS]
        prefix = _rel(repo_root, here)
        base = "" if prefix == "." else f"{prefix}/"
        into = vendored if _is_vendored(base) else files
        into.extend(f"{base}{f}" for f in filenames)
        # Classified per CHILD, not per parent: at `sources/` the children split
        # between authored (`media`, `extractions`) and vendored clones.
        dirs.extend(f"{base}{d}" for d in dirnames if not _is_vendored(f"{base}{d}/"))
    return Index(
        files=tuple(sorted(files)),
        dirs=tuple(sorted(dirs)),
        vendored=tuple(sorted(vendored)),
    )


def _inside(repo_root: Path, candidate: Path) -> bool:
    """True when ``candidate`` stays within ``repo_root`` after resolving `..`.

    `Path.exists()` follows `..` straight out of the tree, so
    `python/../../dotfiles/README.md` resolved against a sibling checkout and was
    reported RESOLVED — a false GREEN on a citation this checker has no standing
    to verify, and `line_count` then opened the file.

    BOTH SIDES are resolved, not normalised lexically. A lexical form cannot see
    a symlink, so an in-repo link pointing at a sibling checkout reached the same
    false green by another route; resolving the root as well as the target is
    what keeps a symlinked repo root (every `tmp_path` on macOS is one) from
    reading as an escape in the process.
    """
    root = repo_root.resolve()
    target = candidate.resolve()
    return target == root or root in target.parents


def _is_vendored(base: str) -> bool:
    """True for a path under a pinned upstream clone in `sources/`.

    `sources/media/` and `sources/extractions/` are committed and authored here,
    so they are deliberately NOT vendored — labelling a transcript we wrote as
    somebody else's file would be wrong in the other direction.

    The `sources/` LEVEL ITSELF is authored too, and reading only the second
    segment missed that: for `sources/` the segment is the empty string, never in
    the kept set, so the whole level counted as vendored — which put the
    committed `*.manifest` pins in the vendored tier and kept `sources/media`
    and `sources/extractions` out of the authored directory index entirely.
    """
    if not base.startswith("sources/"):
        return False
    parts = base.split("/")
    if len(parts) < _SOURCES_CHILD_PARTS:
        return False
    return parts[1] not in _SOURCES_KEPT


def resolve_path(repo_root: Path, token: str, index: Index | None = None) -> Resolution:
    """Resolve a path citation against ``repo_root``.

    Tried in order: the literal repo-relative path; then the token as a path
    SUFFIX within the authored tree; then, for a bare filename, the top level of
    the derived-output root. What is left is either a real miss or a claim about
    somewhere else — see :meth:`State`.
    """
    literal = _resolve_literal(repo_root, token)
    if literal is not None:
        return literal

    idx = index if index is not None else build_index(repo_root)
    settled = _from_matches(repo_root, _suffix_matches(token, idx.files, idx.dirs), "")
    if settled is not None:
        return settled

    if _is_single_segment(token):
        derived = _derived_match(repo_root, token)
        if derived is not None:
            return Resolution(
                State.RESOLVED, f"derived output: {_rel(repo_root, derived)}", derived
            )

    # Only now the pinned upstream clones, so a vendored copy can never shadow
    # an authored file of the same name.
    settled = _from_matches(repo_root, _suffix_matches(token, idx.vendored, ()), "vendored: ")
    if settled is not None:
        return settled

    if "/" not in token:
        return Resolution(State.MISSING, f"no file named {token} in this repo or its sources")
    return _unresolved_relative(repo_root, token, idx)


def resolve_elided(repo_root: Path, token: str, index: Index | None = None) -> Resolution:
    """Resolve a citation whose middle is ABBREVIATED — `review-8a46d08…-cold.md` (#148).

    A DIFFERENT QUESTION from :func:`resolve_path`, which is why it is a different
    function rather than a flag. That one asks whether one named file exists; this
    asks whether anything here matches a pattern the author wrote. `Path.exists()`
    cannot be asked at all, so the literal tier has no analogue and the index is
    the only evidence.

    THE ELISION STAYS INSIDE ONE SEGMENT. It stands for the tail of a sha, not for
    a subtree, and letting it cross `/` would turn every abbreviated citation into
    a `**` that resolves against almost anything — a check that cannot say no.
    Paired arms pin it: `docs/a…beta.md` misses while `docs/alpha/b…a.md` resolves
    in the same repo.

    SEVERAL MATCHES IS RESOLVED, NOT AMBIGUOUS. `resolve_path` reports AMBIGUOUS
    because a shorthand naming four files is probably fine but worth
    disambiguating; here the author asked for a set on purpose, so there is
    nothing to disambiguate. The count goes in the detail instead, because a
    pattern loose enough to match sixty reports has verified very little and the
    reader is the one who can tell whether that was intended. Deciding *how*
    specific is specific enough would be a threshold nobody could defend, and the
    honest alternative is to show the number.

    The vendored tier is consulted after the authored one, exactly as
    :func:`resolve_path` orders them, so a pinned clone can never shadow a file
    this repo wrote.
    """
    idx = index if index is not None else build_index(repo_root)
    pattern = _elided_pattern(token)
    wants_dir = token.endswith("/")
    pool = idx.dirs if wants_dir else idx.files
    matches = [p for p in pool if pattern.match(p)]
    if matches:
        return _elided_resolution(repo_root, matches, "")
    # No `wants_dir` guard: `build_index` puts only FILES in the vendored tier
    # (verified — 0 of 72,296 entries is a directory), so a guard here would be
    # a second guard for a property the index already holds. This commit argues
    # exactly that in `elided_citations`; applying the doctrine in one file and
    # not the other is the inconsistency. (Standards lane, J4.)
    vendored = [p for p in idx.vendored if pattern.match(p)]
    if vendored:
        return _elided_resolution(repo_root, vendored, "vendored: ")
    return _elided_miss(repo_root, token)


def _elided_pattern(token: str) -> re.Pattern[str]:
    """``token`` as a regex over indexed paths, matching on segment boundaries.

    The same suffix discipline as :func:`_suffix_matches`, for the same reason: a
    multi-segment citation names any path ENDING in it (`currency/run.py` finds
    `python/src/kb_setup/currency/run.py`), while a bare filename names a
    basename. Anchoring at a `/` rather than anywhere is what stops
    `laude/rules/x.md` resolving against `.claude/rules/x.md` — a checker that
    accepts any tail has stopped being able to say no.
    """
    needle = token.rstrip("/")
    body = "[^/]*".join(re.escape(part) for part in needle.split(ELISION))
    # ONE form covers both shapes. `(?:.*/)?` is the segment-boundary anchor: it
    # consumes whole leading directories or nothing, so a multi-segment token
    # matches any path ending in it and a bare filename matches a basename —
    # without a separate branch that could drift from `_suffix_matches`.
    return re.compile(f"^(?:.*/)?{body}$")


def _elided_resolution(repo_root: Path, matches: list[str], label: str) -> Resolution:
    """RESOLVED for any number of matches, naming the one or counting the many."""
    if len(matches) == 1:
        return Resolution(State.RESOLVED, f"{label}{matches[0]}", repo_root / matches[0])
    # No `sorted()` here: every tier of `Index` is already `tuple(sorted(...))`
    # and a comprehension preserves order, so re-sorting was a no-op dressed as a
    # guarantee. The overflow suffix matches `_from_matches` verbatim — one
    # reader sees both, and two spellings of "there are more" is the drift a
    # third caller would harden into a fork. (Standards lane, J2.)
    shown = ", ".join(matches[:_SHOWN_MATCHES])
    more = "" if len(matches) <= _SHOWN_MATCHES else f", … ({len(matches)} total)"
    return Resolution(State.RESOLVED, f"{label}{len(matches)} files match: {shown}{more}")


def _elided_miss(repo_root: Path, token: str) -> Resolution:
    """Decide whether an unmatched elided citation is WRONG or about another repo.

    The first-segment test :func:`_unresolved_relative` makes, minus its near-hit
    tier — a near hit suffix-matches a literal tail, and an elided tail has no
    literal form to match with. Dropping it costs the "did you mean" suggestion
    and nothing else; inventing a fuzzy version of it here would be guessing in
    the one module whose contract is to under-report.
    """
    segments = token.strip("/").split("/")
    first = segments[0]
    if len(segments) == 1 or (repo_root / first).exists():
        return Resolution(State.MISSING, f"nothing matches (repo-relative): {token}")
    return Resolution(
        State.UNVERIFIABLE,
        f"matches nothing here, and `{first}/` is not a top-level entry — may name another repo",
    )


def resolve_extension_typo(
    repo_root: Path, token: str, repairs: tuple[str, ...], index: Index | None = None
) -> Resolution | None:
    """MISSING naming the one repair that resolves, or None to STAY SILENT.

    The resolution half of #154. `kb_setup.citations` proposes the spellings a
    token's extension is one edit from; this decides whether any of them names
    something real. None is not a fourth state — it means the token never becomes
    a finding at all, which is the allowlist's existing behaviour preserved for
    everything this cannot positively identify as a typo.

    THREE THINGS MAKE IT SILENT, and each one removed a measured false positive:

    * **The token already resolves.** `notes.org` naming a real `notes.org` is an
      unknown-but-VALID extension, which is precisely what the allowlist exists
      to say nothing about. Repairing it would report a correct citation.
    * **No repair resolves, or several do.** The resolve step is a SECOND gate
      behind the edit distance, and it is the one doing most of the work:
      measured over this repo's authored markdown, **34 distinct tokens reach it
      and are silenced by it** — `Formula/r/ripgrep.rb` repairs to `.rs`,
      `.tar.gz` to `.tar.go`, `conf.d` to `conf.c`/`conf.h`/`conf.md`, and none
      of those files exists. `exactly one` is the same discipline
      :func:`_near_hit` keeps, for the same reason: two plausible referents is a
      guess, not a finding.

      (This bullet illustrated itself with `codegraph.db` "really is one edit
      from `.md`" until a cold round measured it: `_one_edit_apart('db', 'md')`
      is **False** — two substitutions — so that token is silenced by the
      DISTANCE and was the one example that could not demonstrate the point it
      was making. The examples above are re-derived from the corpus.)
    * **The repair only matched something VENDORED.** `runner.os` — a GitHub
      Actions context expression — repaired to `.rs` and suffix-matched
      `sources/hk/src/step/runner.rs` inside the pinned hk clone. That was the
      single false positive in the corpus measurement.

    WHAT IS EXCLUDED IS THE VENDORED TIER — *not* "the authored tree only", which
    is how #154's amended criterion and this round's commit message both first
    put it. The difference is load-bearing rather than pedantic: `resolve_path`'s
    literal-stat tier and its derived-output tier consult no index at all and
    stay live, which is exactly why `graph.jsom` resolves to
    `graphify-out/graph.json` and gets caught. An authored-only rule taken
    literally would leave `graph.jsom` passing — one of the two cases the ticket
    was filed about. Dropping the tier from the INDEX rather than from the answer
    also keeps a literal full-length vendored path a reader actually wrote
    checkable. (Spec lane, F1 — the #157 defect class inside the #157 fix.)
    """
    idx = index if index is not None else build_index(repo_root)
    # The token's OWN existence test asks the FULL index and demands MISSING.
    # Two separate defects lived in the narrower `is RESOLVED` form against
    # `authored`, and both made this function say `no file named X` about an X
    # the index can see (Silent-failure lane, F2 and F3):
    #
    # * **AMBIGUOUS fell through.** Several real files matching the written
    #   spelling is the opposite of absent, and `State` has four members exactly
    #   so "could not tell" is never rendered as a verdict. So does UNVERIFIABLE
    #   — `graphify/serve.pyx` names another repo, and this has no standing to
    #   call it missing. Demanding MISSING is the only test that licenses the
    #   sentence this function goes on to write.
    # * **The vendored tier was excluded from the wrong question.** `watch.pyi`
    #   naming a real file inside a pinned clone was reported absent while
    #   `resolve_path` could open it. Reading graphify's and mise's own source is
    #   why that tier exists at all.
    #
    # `authored_only()` still applies to the REPAIRS below, which is where it was
    # measured and where `runner.os` needs it. One narrowing, one question.
    if resolve_path(repo_root, token, idx).state is not State.MISSING:
        return None
    authored = idx.authored_only()
    # Uniqueness is counted on RESOLVED ALONE, and the name is taken afterwards.
    # Folding `match is not None` into the filter made a match-less RESOLVED —
    # which no tier produces today — able to turn a two-hit case (silent) into a
    # one-hit FINDING, by dropping a row from the count rather than from the
    # message. Counting and naming are different questions; asking them in one
    # comprehension is what let the second one answer the first. (Cold lane,
    # round 2, F-A.)
    hits = [
        got
        for got in (resolve_path(repo_root, repair, authored) for repair in repairs)
        if got.state is State.RESOLVED
    ]
    if len(hits) != 1:
        return None
    # The PATH, not the resolution's detail. `detail` is tier-dependent — tier 3
    # renders `derived output: graphify-out/graph.json` — so interpolating it
    # produced "did you mean derived output: …?". `_near_hit`, the machinery this
    # generalises from, names a bare path, and the suggestion has to read like
    # something you can paste back. (Spec lane, F2.)
    match = hits[0].match
    named = _rel(repo_root, match) if match is not None else hits[0].detail
    return Resolution(
        State.MISSING,
        f"no file named {token} — its extension looks mistyped; did you mean {named}?",
    )


def _resolve_literal(repo_root: Path, token: str) -> Resolution | None:
    """The token read as a literal repo-relative path, or None to keep looking.

    Two things `Path.exists()` alone does not check, both of which produced a
    false GREEN — the one direction a checker must never fail in:

    * **containment** — `exists()` follows `..` straight out of the tree, so
      `python/../../dotfiles/README.md` resolved against a sibling checkout;
    * **kind** — a trailing slash is normalised away, so `docs/a.md/` resolved
      against the FILE `docs/a.md` while claiming to name a directory.
    """
    candidate = repo_root / token
    if not (candidate.exists() and _inside(repo_root, candidate)):
        return None
    if not token.endswith("/") or candidate.is_dir():
        return Resolution(State.RESOLVED, token.rstrip("/"), candidate)
    return Resolution(
        State.MISSING,
        f"{token} names a directory, but {token.rstrip('/')} is a file",
    )


def _from_matches(repo_root: Path, matches: list[str], label: str) -> Resolution | None:
    """A resolution for 1 or many matches, or None when there were none."""
    if len(matches) == 1:
        return Resolution(State.RESOLVED, f"{label}{matches[0]}", repo_root / matches[0])
    if len(matches) > 1:
        shown = ", ".join(matches[:_SHOWN_MATCHES])
        more = "" if len(matches) <= _SHOWN_MATCHES else f", … ({len(matches)} total)"
        return Resolution(State.AMBIGUOUS, f"{len(matches)} files match: {shown}{more}")
    return None


def _unresolved_relative(repo_root: Path, token: str, index: Index) -> Resolution:
    """Decide whether an unresolved multi-segment citation is wrong or elsewhere.

    Two pieces of evidence, in order of strength.

    First, a NEAR HIT: does a multi-segment tail of the token match exactly one
    real path? `pyhton/src/kb_setup/handoff.py` shares `src/kb_setup/handoff.py`
    with a real file, so it is this repo's path misspelled — a real miss, and the
    suggestion goes in the finding. This test exists because the weaker one below
    cannot see a typo IN the first segment: the segment is absent *because* it is
    misspelled, so asking "does segment 1 exist" lets the typo answer its own
    question and waves the citation through as somebody else's file. That is the
    failure class #145 was written for, escaping at exit 0.

    The two-segment floor is what keeps the near-hit rule honest. Without it,
    `dotfiles/python/pyproject.toml` would match our root `pyproject.toml` on
    basename alone, and every cross-repo citation would become a confident false
    accusation — the direction the ticket calls fatal to the checker's trust.

    Second, the first segment: `docs/agents/issue-tracker.md` claims this repo
    has a `docs/agents/` and it does not, while `graphify/serve.py` claims
    nothing about this repo at all. That test needs at least one segment BEYOND
    the first or it is circular — a single-segment citation like `.github/` asks
    exactly the question the test asks, so answering no twice would report a
    claim about this repo as a claim about another one.
    """
    segments = token.strip("/").split("/")
    first = segments[0]
    if len(segments) == 1 or (repo_root / first).exists():
        return Resolution(State.MISSING, f"no such path (repo-relative): {token}")
    near = _near_hit(token, segments, index)
    if near is not None:
        return Resolution(
            State.MISSING, f"no such path (repo-relative): {token} — did you mean {near}?"
        )
    return Resolution(
        State.UNVERIFIABLE,
        f"names no path here, and `{first}/` is not a top-level entry — may name another repo",
    )


#: Segments a tail must keep for a near hit to mean anything. At one segment the
#: rule is just "some file has this basename", which is not evidence about a path.
_MIN_NEAR_HIT_SEGMENTS = 2


def _near_hit(token: str, segments: list[str], index: Index) -> str | None:
    """The one real path a multi-segment tail of ``token`` names, or None."""
    trailing = "/" if token.endswith("/") else ""
    for start in range(1, len(segments) - _MIN_NEAR_HIT_SEGMENTS + 1):
        tail = "/".join(segments[start:]) + trailing
        matches = _suffix_matches(tail, index.files, index.dirs)
        if len(matches) == 1:
            return matches[0]
    return None


def _suffix_matches(token: str, files: tuple[str, ...], dirs: tuple[str, ...]) -> list[str]:
    """Paths in ``files``/``dirs`` that ``token`` names, matched on segment boundaries.

    A bare filename matches on its basename; a multi-segment token matches any
    path ending in it — which is how `currency/run.py` finds
    `python/src/kb_setup/currency/run.py`, the form authors actually write.

    The boundary is load-bearing. Matching a raw string suffix would let
    `laude/rules/x.md` resolve against `.claude/rules/x.md`, and a checker that
    accepts any tail has stopped being able to say no.
    """
    needle = token.rstrip("/")
    pool = dirs if token.endswith("/") else files
    if "/" in needle:
        return [p for p in pool if p == needle or p.endswith(f"/{needle}")]
    return [p for p in pool if p.rsplit("/", 1)[-1] == needle]


def _is_single_segment(token: str) -> bool:
    """True for a bare filename or a bare directory name — `graph.json`, `wiki/`."""
    return "/" not in token.strip("/")


def _derived_match(repo_root: Path, token: str) -> Path | None:
    """A top-level entry of the derived-output root, or None. Deliberately shallow.

    Files AND directories: handoffs write `memory/` and `wiki/` as shorthand for
    the derived tree's own subdirectories exactly as often as they write
    `graph.json` for the file beside them, and a tier that answered one form and
    not the other reported the shorthand as broken.
    """
    candidate = repo_root / _DERIVED_ROOT / token.strip("/")
    return candidate if candidate.exists() else None


def _rel(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def declared_tasks(repo_root: Path) -> frozenset[str]:
    """Task names THIS REPO declares, from its own `mise.toml`.

    Deliberately parses the file rather than asking the tool for its task list.
    `mise tasks ls` merges the user's GLOBAL config: measured 2026-08-04 it
    reports 4 more tasks than `mise.toml` declares (46 vs 42), and a handoff
    naming one of those extras would pass here and fail on every other machine
    (#143). The DELTA is the durable fact — both totals move whenever this repo
    adds a task, including the commit that first wrote this sentence.

    A missing or malformed file yields an empty set rather than raising: the
    caller reports "not declared", which is the honest reading when there are no
    declarations to check against.
    """
    config = repo_root / "mise.toml"
    if not config.is_file():
        return frozenset()
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError, OSError, UnicodeDecodeError:
        return frozenset()
    tasks = data.get("tasks")
    if not isinstance(tasks, dict):
        return frozenset()
    names: set[str] = set()
    for name, body in tasks.items():
        names.add(name)
        names.update(_aliases(body))
    return frozenset(names)


def _aliases(body: object) -> list[str]:
    """A task's `alias`, whether written as a string or a list."""
    if not isinstance(body, dict):
        return []
    alias = body.get("alias")
    if isinstance(alias, str):
        return [alias]
    if isinstance(alias, list):
        return [a for a in alias if isinstance(a, str)]
    return []


def line_count(path: Path) -> int | None:
    """Lines in ``path``, or None when it cannot be read.

    None rather than 0 on failure. Zero would put every line reference into the
    file out of range at once — turning one unreadable file into a pile of
    confident failures, which is the "could not check rendered as a verdict"
    mistake this module exists to avoid.
    """
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not body:
        return 0
    return len(body.splitlines())
