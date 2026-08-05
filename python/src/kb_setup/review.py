"""Receipts for the local cross-family review (`.claude/skills/kb-review`).

The review itself cannot live here. It spawns Claude agents, and only the model
can do that — a mise task is a shell command (`mise-tasks-only.md`,
`zero-bash-logic.md`). So the work splits: the *skill* runs the four lenses, and
this module records and enforces that it happened.

`kb-ship` calls :func:`receipt_state` and refuses to push a commit that has no
receipt. That inversion is the point — a gate the model can talk itself past is
not a gate, and CodeRabbit (advisory, rate-limited on 4 of 5 PRs here) is not
one either. The receipt is what makes the local review the real gate.

Receipts are gitignored: one proves that *this machine* reviewed *this commit*.
Committing them would make them stale on the first rebase, and a stale receipt
is worse than none — a green light nobody earned.

The one place that strict commit-keying bends is :data:`EXEMPT_PATHS`: the
round's own closing tasks write files that cannot exist until after the review,
so an ancestor's receipt covers HEAD when everything committed since is inside
that set. See :func:`_covering_candidates` — it changes which receipt is asked, not
what is asked of it.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Where receipts land, relative to the repo root. Under `.agent/` because a
#: receipt is machine-local by design (`agent-artifact-conventions.md`).
RECEIPT_DIR = Path(".agent/kb/review")

#: Where each lane's report must be written, as `review-<sha>-<lane>.md`.
#:
#: This is what stops the receipt being pure honor-system. Without it,
#: `--lanes standards,spec,cold:codex,silent-failure --blocking 0` minted a
#: full-coverage receipt in one command with **zero evidence any lane ran** —
#: the widest version of a hole whose narrower forms this module had already
#: closed twice. Found by the spec lane, and `agent-report-persistence.md`
#: independently requires these reports on disk anyway.
#:
#: It raises the bar; it is not proof. A determined caller can write a stub
#: file. What it buys is that the honest path is the easy one and faking
#: coverage takes deliberate work — the same "strictly less than a signed
#: receipt" honesty the skill states about the whole mechanism.
REPORT_DIR = RECEIPT_DIR / "reports"

#: A skipped lane must say WHY, as `lane:reason`. A bare lane name is rejected:
#: "did not run" and "does not apply here" are different states, and collapsing
#: them is how a gap gets reported as coverage.
_SKIP_SEPARATOR = ":"

#: The ONLY reasons that excuse a lane. A skip must be a JUSTIFICATION — the
#: lane had nothing to say about this diff — not a report that it never ran.
#:
#: Accepting any non-empty reason was the second version of the same defect: the
#: reference docs already said "a lane that could not be spawned is
#: `not-yet-run`, never `not-applicable`", and then `cold:not-yet-run` sailed
#: through the gate. A doc and the code disagreeing is worse than either alone,
#: and here the code was the permissive one. Found by the cold lane on its
#: SECOND pass, over the commit that fixed its first finding.
#:
#: Reasons that excuse ANY lane: the lane genuinely had nothing to say here.
_SKIP_ANY_LANE = ("not-applicable-",)

#: The reason a lane did not run because the SKILL CHOSE not to run it. Distinct
#: from `not-applicable-` on purpose: that one asserts a judgement — the lane read
#: this diff and had nothing to say — whereas this asserts a policy, that the
#: review deliberately runs one lane. Reusing `not-applicable-` for "we chose not
#: to" would make every future receipt claim a judgement nobody made, which is the
#: gap-wearing-a-reason's-clothes shape this file has now closed three times.
_BY_POLICY = "by-policy-one-lane"

#: Reasons that excuse ONE named lane, and no other. `no-spec-available` is the
#: spec lane's alone — a cold or silent-failure lane does not review against a
#: spec, so "there is no spec" cannot explain why it did not run.
#:
#: The THIRD instance of one hole. The reason was matched without ever looking
#: at the lane it was attached to, so `cold:no-spec-available` bought a pass for
#: a lane that never ran — after `--lanes placeholder` and `cold:not-yet-run`
#: had already been closed. The comment on the line right above it said "spec
#: lane, and only when there genuinely is no spec"; nothing enforced it. Found
#: by the cold lane, again, which is now three for three on this gate.
#:
#: `_BY_POLICY` is scoped here rather than in `_SKIP_ANY_LANE` for exactly that
#: lesson: **`cold` is deliberately absent.** The one-lane policy IS "run cold",
#: so `cold:by-policy-one-lane` is self-contradictory and must never buy a pass.
#: A lane-blind prefix would have accepted it, and the `not ran_raw` backstop
#: only catches the case where ALL four are skipped.
_SKIP_BY_LANE = {
    "spec": ("no-spec-available", _BY_POLICY),
    "standards": (_BY_POLICY,),
    "silent-failure": (_BY_POLICY,),
}

#: The four lenses. Every one must be ACCOUNTED FOR in a receipt — either it ran
#: or it was skipped with a reason. Without this list the gate accepted any
#: non-empty string, so `--lanes placeholder` satisfied it: a gate the model
#: could talk itself past, which is the exact thing this module exists to stop.
#: Found by the cold cross-family lane reviewing this module's own first draft.
#:
#: A lane entry may name a variant after a colon (`cold:codex`,
#: `cold:claude-fallback-SAME-FAMILY`) — the prefix is what must be known.
LANES = ("standards", "spec", "cold", "silent-failure")

#: Paths whose content cannot exist until AFTER the review has happened, because
#: the round's own closing tasks write them (#66).
#:
#: `kb-remember` writes `graphify-out/memory/*.md` and `kb-goal-outcome` edits
#: `docs/goals/README.md` — both mandated by every rider's P7 ("close the
#: loop"). Because the receipt is keyed to a commit, their output could never be
#: committed to the branch it belongs to: before the receipt it is unreviewed,
#: after it HEAD has moved past the receipt and `ship`/`land` refuse. Three
#: rounds running left them uncommitted, one `git clean -xdf` from gone.
#:
#: **That timing is the whole justification, and it is the only one.** The first
#: draft of this comment also claimed these were "paths a review lane cannot
#: meaningfully review" — which the review of this very commit falsified: three
#: lanes found three live credentials pasted into one of these files by
#: `kb-remember`. A lane reads them fine. What it cannot do is read them before
#: they exist.
#:
#: So exempting them removes the only lane read they would ever get, which makes
#: **scanner** coverage of these paths load-bearing rather than incidental.
#: `.gitleaks.toml` used to allowlist all of `graphify-out/`; it no longer does,
#: and `tests/test_gitleaks_scope.py` pins that. Do not add a path here that the
#: scanner cannot see.
#:
#: An entry ending in `/` is a directory prefix; anything else is one exact
#: path. Deliberately NOT a glob: a pattern language here would be a second
#: thing to get wrong on the gate's permissive side.
#:
#: `graphify-out/reflections/` is the third P7 writer and is **absent on
#: purpose** — it is gitignored (`.gitignore`, "reflect derived doc"), so it can
#: never appear in a `git diff` and an entry for it could never fire. #66
#: suggested including it; a rule that can only be dead is not a rule
#: (`probes-need-a-control-arm.md`). `kb-reflect`'s other output is the
#: `.graphify_*` learning overlay, gitignored for the same reason.
EXEMPT_PATHS = ("graphify-out/memory/", "docs/goals/README.md")

#: The ref the branch's base is resolved against — the REMOTE-TRACKING one.
#:
#: It was local `main`, while the PR is opened against GitHub's
#: (`gh pr create --base main`). Those disagree in two directions and only one
#: is safe: local `main` merely BEHIND makes the merge-base older, so the review
#: covered MORE than the branch; local `main` AHEAD **along the branch's own
#: ancestry** moves the merge-base forward, so the review covered LESS and the
#: receipt claims a coverage it does not have. Using `origin/main` removes
#: exactly the unsafe direction. (#54)
#:
#: **It costs no network, and the issue's own framing said otherwise.**
#: `origin/main` is a local remote-tracking ref: `git merge-base -- origin/main
#: HEAD` reads `.git/refs/remotes/origin/main` and never opens a socket.
#: Measured both arms — that call 0.64s against `git ls-remote origin main`
#: (a real network round-trip) at 2.5s. So this is not a correctness-for-network
#: trade; the only thing given up is freshness, and a stale `origin/main` errs
#: in the SAFE direction above.
#:
#: One new failure mode, accepted deliberately (Ray, 2026-07-30): a clone with
#: no `origin/main` ref resolves to "" and `_base_coverage_gap` REFUSES rather
#: than falling back to local `main`. Falling back would silently reinstate the
#: defect on exactly the machines least likely to notice, and "could not check"
#: is never rendered as clean anywhere else in this module.
#:
#: Shared by the gate (`ship`/`land` pass it as ``require_base``) and by the
#: receipt writer's default `--fixed-point`, so the two cannot name different
#: refs — the drift this module has now closed in four other places.
DEFAULT_BASE_REF = "origin/main"

#: How many leading SHA characters a lane report may use to name its commit.
#:
#: Twelve, matching the `sha[:12]` this module prints in every message — so the
#: form a lane naturally quotes back is the form that is accepted. Deliberately
#: NOT git's default abbreviation, which can be as short as 7: a 7-hex run
#: appears in ordinary prose often enough to match by accident, and a check that
#: can pass by coincidence asserts something it never verified. (#56)
_SHA_ABBREV = 12

#: How many disqualifying paths the refusal message names before summarising.
#: A DISPLAY bound, so it states the remainder ("+3 more") rather than truncating
#: silently — a bound that hides its own existence is how "absent" and
#: "unreachable" get confused (`probes-need-a-control-arm.md` rule 3).
_MAX_NAMED_PATHS = 5

#: Sort key ranking an UNREADABLE delta below every countable refusal, so a
#: candidate that names a real file is reported ahead of one that could not be
#: checked at all. Larger than any plausible path count and not
#: `sys.maxsize`-magic; it only ever has to lose a comparison.
_UNREADABLE_RANK = 1_000_000

_GIT_TIMEOUT = 30


def _lane_prefix(entry: str) -> str:
    """Return the lane an entry names, ignoring any `:variant` suffix."""
    return entry.partition(_SKIP_SEPARATOR)[0]


def _justifies(lane: str, reason: str) -> bool:
    """Return whether ``reason`` excuses ``lane`` — nothing else does.

    `not-applicable-` is a PREFIX and requires a non-empty why after it: a bare
    `not-applicable-` is the same empty claim as no reason at all, and
    `str.startswith` accepted it. Every other justification is matched EXACTLY,
    because `startswith` also accepted `no-spec-availablex` — a typo bought a
    pass for a lane that never ran. Both found by the cold lane.
    """
    for prefix in _SKIP_ANY_LANE:
        if reason.startswith(prefix) and len(reason) > len(prefix):
            return True
    return reason in _SKIP_BY_LANE.get(lane, ())


def _skip_reason_help() -> str:
    """Return a human summary of every accepted skip reason, with its scope."""
    scoped = ", ".join(
        f"{reason} ({lane} lane only)"
        for lane, reasons in _SKIP_BY_LANE.items()
        for reason in reasons
    )
    return ", ".join((*_SKIP_ANY_LANE, scoped))


@dataclass(frozen=True)
class Receipt:
    """One review of one commit, by the lanes named in it.

    A record rather than six loose parameters: the fields only ever travel
    together, and `lanes_ran` is meaningless without `lanes_skipped` beside it.
    """

    sha: str
    fixed_point: str
    #: The base RESOLVED to a commit. `fixed_point` alone is a movable name —
    #: `main` today is not `main` tomorrow — so it cannot say which base was
    #: actually reviewed.
    #:
    #: **GATED, twice** — this line read "Recorded, not gated" until #57, which
    #: was true when written and was falsified by the two checks that landed
    #: after it: :func:`_check_range` refuses an EMPTY range (`fixed_point_sha ==
    #: sha`) for every consumer, and :func:`_base_coverage_gap` refuses a receipt
    #: whose base is not the branch's merge-base whenever ``require_base`` is
    #: given. The comment nearest the field was the one that rotted, which is the
    #: whole of #57: a false comment costs the next reader more than a missing
    #: one, and here it said the field was inert on the exact commit that made it
    #: load-bearing.
    #:
    #: The original worry it recorded is still real and is what bounds the second
    #: check rather than removing it: a base that legitimately moves must not
    #: invalidate an honest receipt, so `_base_coverage_gap` runs only for the
    #: callers that ship the WHOLE branch, never for the writer's own read-back.
    fixed_point_sha: str
    lanes_ran: tuple[str, ...]
    lanes_skipped: tuple[str, ...]
    findings: int
    blocking: int
    #: Stamped ONCE, at construction. `as_payload()` used to call
    #: `datetime.now()` on every invocation, so `rejection()` validated a payload
    #: that differed from the one `write_receipt()` then wrote. Nothing gates on
    #: the timestamp, so it changed no verdict — but "the bytes we checked are
    #: the bytes we wrote" is the property this module sells, and it did not hold.
    written_at: str = field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(timespec="seconds")
    )

    def as_payload(self) -> dict[str, Any]:
        """Return the JSON form written to disk."""
        return {
            "sha": self.sha,
            "written_at": self.written_at,
            "fixed_point": self.fixed_point,
            "fixed_point_sha": self.fixed_point_sha,
            "lanes_ran": list(self.lanes_ran),
            "lanes_skipped": list(self.lanes_skipped),
            "findings": self.findings,
            "blocking": self.blocking,
        }


def rejection(repo_root: Path, receipt: Receipt) -> str | None:
    """Return why ``receipt`` would be rejected, or None if it would pass.

    The :func:`_all_reasons` checks :func:`receipt_state` applies, reachable
    BEFORE the write so a bad receipt is refused rather than written and then
    reported as failing. One implementation of THOSE, so the writer and the
    reader cannot drift apart on them.

    **It does not cover ``require_base``, and the claim here used to imply it
    did.** `_base_coverage_gap` lives in :func:`receipt_state`, outside
    `_all_reasons`, and the CLI calls neither with a base — so
    `kb-review-receipt --fixed-point HEAD^` prints `OK` for a receipt that
    `ship` and `land` both then refuse. That is fail-CLOSED, so the behaviour is
    safe and only the wording was wrong; but "cannot drift apart" is exactly the
    sentence a reader trusts instead of re-checking, and the one place it did not
    hold is the field most likely to be wrong on a second review round. (#57)
    """
    return _all_reasons(repo_root, receipt.as_payload(), receipt.sha)


def _all_reasons(repo_root: Path, data: dict[str, Any], sha: str) -> str | None:
    """The complete verdict. ONE composition, called by both writer and reader.

    Composing `_reject_reason or _evidence_gap` independently in two places is
    how the writer and the reader drift back apart, which is the gap this
    module exists to close.
    """
    return _reject_reason(data, sha) or _evidence_gap(repo_root, data, sha)


def _evidence_gap(repo_root: Path, data: dict[str, Any], sha: str) -> str | None:
    """Return why the claimed lanes' reports are absent or unbound, or None."""
    missing, unbound = _report_gaps(repo_root, data, sha)
    if missing:
        return (
            f"claims lane(s) {', '.join(missing)} ran, but no non-empty report is at "
            f"{REPORT_DIR}/review-{safe_sha(sha)}-<lane>.md — a lane that left no "
            f"report is a claim, not a review"
        )
    if unbound:
        return (
            f"lane(s) {', '.join(unbound)} left a report that never names {sha[:_SHA_ABBREV]} — "
            f"a filename is not a binding, so state the reviewed commit IN the report "
            f"(the fix-round template in kb-review/SKILL.md already does)"
        )
    return None


def _binds_sha(body: str, sha: str) -> bool:
    """Return whether ``body`` DECLARES that it is about ``sha``.

    The filename already encodes the commit, and a filename is chosen by the
    orchestrator rather than by the lane — so on its own it records where a file
    was put, not what was read. This asks the report to say so itself.

    Accepts the full SHA or its :data:`_SHA_ABBREV`-character prefix, because
    that is the form this module prints everywhere else (`sha[:12]`) and the form
    a lane naturally quotes back. Shorter prefixes are refused: git's default
    abbreviation can be as short as 7, and a 7-hex string is common enough in
    ordinary prose to match by accident, which would make the check assert
    something it had not checked.
    """
    return sha in body or (len(sha) >= _SHA_ABBREV and sha[:_SHA_ABBREV] in body)


def safe_sha(sha: str) -> str:
    """Return ``sha`` reduced to commit characters.

    Defence in depth behind the CLI's refusal to take a `--sha`: a value with a
    path separator in it would otherwise steer a write out of the receipt dir.

    Public because `kb_setup.gates` keys its own per-commit artifact the same
    way, one directory over. A second copy of a path-containment helper is the
    kind of duplication that stays identical right up until one of them is
    hardened and the other is not.
    """
    return "".join(c for c in sha if c.isalnum())


def _safe_lane(lane: str) -> str:
    """Return ``lane`` reduced to filename-safe characters, KEEPING hyphens.

    Hyphens are load-bearing: the lane is `silent-failure`, and stripping the
    hyphen made the gate hunt for `…-silentfailure.md` while every doc said
    `…-silent-failure.md`. Following the skill verbatim then failed the gate.

    The tests did not catch it because they built their fixture paths with
    :func:`report_path` and so inherited the same normalisation — a tautological
    probe (`probes-need-a-control-arm.md`). The test that guards this now spells
    the documented filename out literally.
    """
    return "".join(c for c in lane if c.isalnum() or c in "-_")


def receipt_path(repo_root: Path, sha: str) -> Path:
    """Return the receipt path for ``sha`` (not necessarily existing)."""
    return repo_root / RECEIPT_DIR / f"receipt-{safe_sha(sha)}.json"


def _git(repo_root: Path, *args: str) -> str:
    """Return stripped stdout of `git *args`, or "" if it cannot be read.

    Callers of this form fail closed on "" because every answer they ask for is
    non-empty when it succeeds. :func:`_git_result` is for the questions where
    an empty answer is a legitimate result — see its docstring.
    """
    return _git_result(repo_root, *args)[1].strip()


def _git_result(repo_root: Path, *args: str) -> tuple[bool, str]:
    """Return ``(ran_ok, RAW stdout)`` for `git *args`.

    :func:`_git` collapses failure into ``""``, which is right for `rev-parse`
    and `merge-base` — they never legitimately answer nothing. It is WRONG for
    `git diff`, where "" is the perfectly ordinary answer "these two trees are
    identical". Collapsing the two there would let a git failure read as "the
    delta is empty, so nothing unreviewed was added" — a could-not-check
    rendered as green, which is the one thing this module refuses everywhere
    else. So the ok flag is carried separately rather than inferred.

    Raw, and NOT stripped: :func:`_git` strips for its own callers. Stripping
    here ate a leading space from the first path of a `-z` NUL stream, which
    could turn `" python/x.py"` into `"python/x.py"` — and, in the shape that
    matters, an indented path into an exempt-looking one. Stripping the
    delimiter-joined blob contradicted `_delta_paths`' own claim to compare the
    bytes git has. (Cold and silent-failure lanes, independently.)
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
    except subprocess.TimeoutExpired:
        # Distinguished from a clean miss on purpose: a timeout means the
        # question was never answered, and a silent "" would read as an answer.
        print(f"  git {' '.join(args)}: timed out after {_GIT_TIMEOUT}s")
        return False, ""
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
        # `UnicodeDecodeError` is raised by `text=True`'s decode and is NOT an
        # `OSError` or a `SubprocessError`, so a pathname git holds as non-UTF-8
        # bytes escaped as a TRACEBACK out of the middle of `ship`/`land` —
        # a crash where this module's entire contract is a worded refusal. It is
        # reachable: `git diff -z` emits raw pathname bytes precisely so they are
        # not re-encoded. (Cold lane.)
        print(f"  git {' '.join(args)}: {exc}")
        return False, ""
    if proc.returncode != 0:
        # The rc path is the one that ACTUALLY fires — a bad ref exits 128 rather
        # than raising — and it was the one branch here that returned a silent ""
        # while both exception paths above printed why. Two lines under a comment
        # saying a silent "" would read as an answer. Callers fail closed on "",
        # so this costs diagnosis rather than safety, which is exactly why it was
        # invisible. (Silent-failure lane, third pass.)
        detail = (proc.stderr or proc.stdout or "").strip()
        print(f"  git {' '.join(args)}: rc={proc.returncode} {detail[:160]}")
        return False, ""
    return True, proc.stdout


def head_sha(repo_root: Path) -> str:
    """Return the full SHA at HEAD, or "" if git cannot be read."""
    return _git(repo_root, "rev-parse", "HEAD")


def base_sha(repo_root: Path, fixed_point: str, *, head: str = "HEAD") -> str:
    """Resolve ``fixed_point`` to the merge-base commit, or "" if unresolvable.

    Three-dot semantics, matching the `git diff <base>...HEAD` the review runs
    against: the question is what the branch added, not how the base has moved.

    ``head`` lets a caller that has already captured a SHA pin the comparison to
    THAT commit. The receipt writer reads HEAD once for `sha` and then resolved
    the base against live `HEAD` a moment later, so a checkout in between labelled
    the receipt with a base from a different branch. (Cold lane.)
    """
    # `--` terminates option parsing: without it a fixed point spelled like a flag
    # (`--fork-point`) is read by git as an OPTION rather than a ref, so the
    # command silently answers a different question. Probed both arms: with `--`,
    # `--fork-point` → "Not a valid object name"; without it → a wrong answer,
    # silently. (Cold lane.)
    return _git(repo_root, "merge-base", "--", fixed_point, head)


def write_receipt(repo_root: Path, receipt: Receipt) -> Path:
    """Write ``receipt`` under :data:`RECEIPT_DIR` and return its path."""
    path = receipt_path(repo_root, receipt.sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt.as_payload(), indent=2) + "\n", encoding="utf-8")
    return path


def _unexplained_skips(skipped: list[str]) -> list[str]:
    """Return skipped-lane entries whose reason does not excuse THAT lane.

    Three ways to fail: no reason at all, a reason that merely REPORTS the lane
    did not run, or a reason that is only valid for a DIFFERENT lane.
    `cold:not-yet-run` is a gap wearing a reason's clothes; `cold:no-spec-available`
    is a gap wearing the spec lane's clothes.

    Takes the already-normalised list rather than re-reading ``data``. Reading
    one key through two idioms — `data.get(k, [])` here, `data.get(k) or []` in
    the caller — meant `"lanes_skipped": null` raised TypeError out of this
    function while the caller treated the same value as empty. A crash is not a
    verdict, and one key deserves one read.
    """
    bad: list[str] = []
    for entry in skipped:
        lane, _, reason = entry.partition(_SKIP_SEPARATOR)
        if not reason or not _justifies(lane, reason):
            bad.append(entry)
    return bad


def report_path(repo_root: Path, sha: str, lane: str) -> Path:
    """Return where ``lane``'s report for ``sha`` must be written.

    The `:variant` is STRIPPED: a lane recorded as `cold:codex` leaves
    `…-cold.md`. `_report_gaps` already read it that way (via
    `_lane_prefix`), so a caller passing the variant to this helper got
    `…-coldcodex.md` while the gate hunted `…-cold.md` — the same
    writer/reader divergence as the `_safe_lane` hyphen bug, one layer up, and
    latent for the same reason: nothing passed a variant here.
    """
    lane_file = _safe_lane(_lane_prefix(lane))
    return repo_root / REPORT_DIR / f"review-{safe_sha(sha)}-{lane_file}.md"


def strip_lane_variant(token: str) -> str:
    """Return a cited lane-report filename with any `:variant` removed (#148).

    `review-<sha>-cold:codex.md` → `review-<sha>-cold.md`. The WRITER already
    does this — :func:`report_path` runs the lane through :func:`_lane_prefix`
    before building the name — so a file carrying a variant can never exist. A
    handoff that cites the lane AS RECORDED is therefore naming a spelling that
    is unmatchable by construction, and a checker taking it literally would
    report a lane whose report is on disk as one that never ran. That is the
    false-accusation direction #145 calls fatal to a checker's credibility, and
    it is what criterion 3 of #148 is about.

    It repairs the SPELLING and vouches for nothing: the repaired name still has
    to match a real report.

    THE DIRECTORY IS CHECKED, and this docstring used to say so while the code
    did not. It tested `stem.startswith("review-")` on the BASENAME alone, so
    `docs/review-2026:q3.md` became `docs/review-2026.md` — a token outside this
    module's directory, silently rewritten into a name that may well exist. That
    is the FALSE-GREEN direction inside the one package whose contract is to
    under-report, and it was defended by a sentence claiming the opposite. The
    standards lane found it by running the function rather than reading it.

    A citation with NO directory is still accepted, because that is a real form —
    handoffs write `` `review-abc…-cold.md` `` bare beside the full path, and
    `resolve` matches a bare filename on its basename. What is excluded is a
    token that names a DIFFERENT directory, which is the case that could not be
    about a lane report.

    ONLY `_lane_prefix` IS REPRODUCED, NOT `_safe_lane`, and that asymmetry is
    deliberate rather than the half-copy it looks like. `report_path` composes
    `_safe_lane(_lane_prefix(lane))`, and a review lane proposed matching it here.
    Running it: `_safe_lane("review-abc1234…-cold")` returns
    `"review-abc1234-cold"` — it keeps only alphanumerics, `-` and `_`, so it
    DESTROYS the elision and silently turns a pattern into a literal that matches
    nothing. The two sides are not symmetric because the inputs are not: the
    writer sanitises a lane name on its way to becoming a filename, while this
    reads a citation an author wrote, whose whole point is the character
    `_safe_lane` removes.

    Lives here rather than in `kb_setup.resolve` because the `:variant`
    convention is this module's — it owns `_lane_prefix`, `report_path` and the
    directory they write into.
    """
    head, _, name = token.rpartition("/")
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem.startswith("review-") or _SKIP_SEPARATOR not in stem:
        return token
    if head and head.strip("/") != str(REPORT_DIR):
        return token
    return f"{head}/{_lane_prefix(stem)}.{ext}" if head else f"{_lane_prefix(stem)}.{ext}"


def _report_gaps(repo_root: Path, data: dict[str, Any], sha: str) -> tuple[list[str], list[str]]:
    """Return ``(lanes with no usable report, lanes whose report names another commit)``.

    Two distinct failures, reported separately because the remedies differ: the
    first means run the lane, the second means say what it read.

    **The second half is #56.** The receipt is minted against fresh HEAD and
    there is deliberately no `--sha`, so nothing bound "the commit the lanes
    reviewed" to "the commit the receipt is for". The filename did *look* like
    that binding — a report is resolved as `review-<receipt sha>-<lane>.md`, so a
    moved HEAD leaves the old report invisible and the receipt refused — and for
    the accidental case that is genuinely enough. But a filename is chosen by the
    ORCHESTRATOR, not by the lane, so it records where a file was put rather than
    what was read. The cold lane rated that P1 while reviewing PR #79 and Ray
    reversed the earlier risk acceptance (2026-07-30).

    **The issue as written is still not what got built, and deliberately.**
    Capturing HEAD at lane dispatch and refusing if it moved would make
    `kb-review/SKILL.md` step 4's fix-round path impossible — committing the fix
    is what moves HEAD. Asking the report to NAME its commit closes the same gap
    while leaving that path open: the fix-round template already states the fixed
    SHA, so an honest fix-round report passes, and it now passes *visibly* rather
    than by convention.

    It is still not proof — a determined caller can paste the SHA into a stub,
    exactly as one could already write a stub at all (`lanes.md` says so). What
    it removes is the case where a report is evidence for a commit **nobody ever
    claimed it was about**, and it makes the honest path the easy one. Measured
    on the two reports on disk when this landed: one named its SHA, one did not,
    so the lane prompt now requires it.
    """
    # `data.get(k, [])`, matching `_check_lanes` — the THIRD idiom for one key
    # was here (`or []`), contradicting the "one key deserves one read" rule two
    # functions up. It is unreachable with a malformed value only because
    # `_all_reasons` runs `_reject_reason` first; that ordering is now stated
    # rather than relied on silently, and `or []` below is the belt to its braces.
    missing: list[str] = []
    unbound: list[str] = []
    for entry in _as_entries(data.get("lanes_ran", [])) or []:
        lane = _lane_prefix(str(entry))
        path = report_path(repo_root, sha, lane)
        try:
            # STRICT decoding, matching `_load_receipt`. This read with
            # `errors="replace"`, so a corrupted or partly-binary file decoded
            # into U+FFFD noise, survived `.strip()`, and counted as evidence
            # that a lane ran — while `_load_receipt` three functions down
            # refuses undecodable RECEIPT bytes outright. One module, two
            # answers to "what is readable", and the permissive one was guarding
            # the evidence while the strict one guarded the claim. The receipt
            # side is the one that is right: unreadable evidence is not
            # evidence. The bar stays soft either way — a stub file still passes,
            # as `lanes.md` says — this only stops the two reads disagreeing. (#58)
            body = path.read_text(encoding="utf-8") if path.is_file() else ""
        except OSError, UnicodeDecodeError:
            # Unreadable is "could not check", which must refuse rather than
            # traceback out of the middle of `ship`. `UnicodeDecodeError` needs
            # naming explicitly — it is NOT an `OSError`, the same trap
            # `_load_receipt` records — or strict decoding would convert this
            # refusal into a crash.
            body = ""
        if not body.strip():
            missing.append(lane)
        elif not _binds_sha(body, sha):
            # Checked only when a report EXISTS: "no report" and "a report that
            # does not say what it read" are different states, and reporting the
            # second for a lane that simply never ran would send the reader
            # looking for a file that is not there.
            unbound.append(lane)
    return missing, unbound


def _check_identity(data: dict[str, Any], sha: str) -> str | None:
    """Reject a receipt that is not about this commit, or not about any range."""
    if data.get("sha") != sha:
        # A receipt filed under this SHA that records another is a copied file.
        return f"records a different SHA ({data.get('sha')})"
    # `isinstance(..., str)` as well as non-blank: these were coerced with `str()`
    # before the check, so a JSON `true` became the string "True" and passed as a
    # perfectly good fixed point. Stringifying before validating turns "the wrong
    # type" into "some text", which is never what a type check wants. (Cold lane.)
    fixed_point = data.get("fixed_point")
    if not isinstance(fixed_point, str) or not fixed_point.strip():
        # Without a base, the receipt says a review happened but not of WHAT.
        return "names no fixed point, so it does not say what was reviewed"
    fixed_point_sha = data.get("fixed_point_sha")
    if not isinstance(fixed_point_sha, str) or not fixed_point_sha.strip():
        # An unresolvable fixed point (a typo, a deleted branch) recorded an
        # empty sha and sailed through, so the receipt claimed a base it never
        # resolved. Unresolvable is "could not check", never "clean".
        return "has an unresolved fixed point, so its comparison base is unknown"
    return None


def _as_entries(value: object) -> list[str] | None:
    """Return ``value`` as a list of strings, or None if it is not a list.

    A numeric `lanes_ran` is valid JSON and used to raise TypeError out of the
    validator, crashing `kb-ship` instead of refusing it. A crash is not a
    verdict — malformed input has to fail CLOSED with a reason.
    """
    if not isinstance(value, list):
        return None
    return [str(v) for v in value]


def _accounting_reason(ran: list[str], skipped: list[str]) -> str | None:
    """Return why the lane set is not fully and consistently accounted for.

    The three ways one receipt can misdescribe its own coverage: a lane claimed
    twice over, a lane that does not exist, and a lane nobody mentioned. Split
    out of :func:`_check_lanes` so each stays a named guard clause rather than
    being merged to satisfy a return-count limit — the limit is a signal to
    decompose, not to compress.

    ``accounted`` is DERIVED here rather than passed in. It took it as a third
    parameter that was exactly `{prefix(e) for e in ran + skipped}`, so a caller
    could hand over a set inconsistent with the other two arguments — an instance
    of the very defect this function exists to detect. (Standards lane.)
    """
    accounted = {_lane_prefix(e) for e in (*ran, *skipped)}
    # A lane did one or the other. Listing it in both collapsed to a single set
    # entry, so `--lanes cold:codex --skipped cold:not-applicable-x` satisfied
    # "accounted for" twice over while saying two contradictory things about one
    # lane — and the skill's own worked example used to do exactly that.
    contradictory = sorted({_lane_prefix(e) for e in ran} & {_lane_prefix(e) for e in skipped})
    if contradictory:
        return (
            f"lists lane(s) as BOTH run and skipped: {', '.join(contradictory)} — a "
            f"lane did one or the other, and claiming both is not coverage"
        )

    unknown = sorted(accounted - set(LANES))
    if unknown:
        return f"names unknown lane(s): {', '.join(unknown)} (known: {', '.join(LANES)})"

    missing = [lane for lane in LANES if lane not in accounted]
    if missing:
        return (
            f"lane(s) unaccounted for: {', '.join(missing)} — each must either run "
            f"or be skipped with a reason"
        )
    return None


def _check_lanes(data: dict[str, Any], _sha: str) -> str | None:
    """Reject a receipt whose lanes are unexplained, invented, or missing.

    All three are one defect wearing three hats: a receipt that claims more
    coverage than the review actually had.
    """
    # `data.get(k, [])`, NOT `data.get(k) or []`: absent and present-but-null are
    # different states. Absent defaults to empty (a receipt with all four lanes
    # run legitimately has no skips); an explicit `null`, `0`, or `""` is a
    # MALFORMED array and must be refused, not quietly read as empty. `or []`
    # collapsed the two, which is the same "could not check rendered as clean"
    # this module refuses everywhere else.
    ran_raw = _as_entries(data.get("lanes_ran", []))
    skipped_raw = _as_entries(data.get("lanes_skipped", []))
    if ran_raw is None or skipped_raw is None:
        return "has a malformed lane list (lanes_ran/lanes_skipped must be arrays)"

    unexplained = _unexplained_skips(skipped_raw)
    if unexplained:
        return (
            f"skipped lane(s) not excused: {', '.join(unexplained)} — a skip must "
            f"justify itself with one of {_skip_reason_help()}; a lane that merely "
            f"did not run is a gap, not a skip"
        )

    accounting = _accounting_reason(ran_raw, skipped_raw)
    if accounting is not None:
        return accounting

    if not ran_raw:
        return "records no lane that actually ran"
    return None


def _check_blocking(data: dict[str, Any], _sha: str) -> str | None:
    """Reject a receipt with unresolved blocking findings, or an unreadable count."""
    blocking = data.get("blocking")
    if not isinstance(blocking, int) or isinstance(blocking, bool):
        return "has no readable blocking count"
    # A negative count is malformed, not "fewer than zero blockers". Only
    # `> 0` was rejected, so a hand-authored `"blocking": -1` read as clean —
    # the same "unreadable rendered as green" this module refuses everywhere
    # else. The CLI cannot produce one; a hand-edited receipt can, which is
    # exactly the reader this check exists for.
    if blocking < 0:
        return f"has a negative blocking count ({blocking}) — that is malformed, not zero"
    if blocking > 0:
        return f"{blocking} blocking review finding(s) — resolve them or re-review"
    return None


def _check_range(data: dict[str, Any], sha: str) -> str | None:
    """Reject a receipt whose comparison range is EMPTY.

    `--fixed-point HEAD` resolves through `git merge-base HEAD HEAD` to HEAD
    itself, and `fixed_point_sha` was only ever checked for non-blankness — so a
    receipt recording a zero-line diff satisfied the entire gate in one flag.

    The adversarial reading is not the dangerous one. The LIKELY one is: on a
    second or third review round the natural instinct is "review what changed
    since last time" (`--fixed-point HEAD^`), which mints an honest-looking
    receipt covering one commit of twelve. `ship` additionally requires the base
    to be the branch's own merge-base — see :func:`receipt_state`'s
    ``require_base`` — but an empty range is malformed for any consumer, so it is
    refused here for all of them. (Cold lane, third pass.)
    """
    if str(data.get("fixed_point_sha") or "").strip() == sha:
        return (
            "records an EMPTY comparison range (fixed_point_sha == sha) — nothing "
            "was reviewed; `--fixed-point HEAD` resolves to HEAD itself"
        )
    return None


#: Run in order; the first reason wins. Split into named checks rather than one
#: long branch so each is separately testable and the list reads as the contract.
_CHECKS = (_check_identity, _check_range, _check_lanes, _check_blocking)


def _reject_reason(data: dict[str, Any], sha: str) -> str | None:
    """Return why ``data`` fails as a receipt for ``sha``, or None if it passes.

    Every check fails CLOSED: anything unreadable means the question was never
    answered, which is not the same as "nothing is wrong"
    (`probes-need-a-control-arm.md`).
    """
    for check in _CHECKS:
        reason = check(data, sha)
        if reason is not None:
            return reason
    return None


def _base_coverage_gap(
    repo_root: Path, data: dict[str, Any], require_base: str, sha: str
) -> str | None:
    """Return why the receipt's base does not cover the whole branch, or None.

    A receipt is honest about the range it reviewed, and the gate never checked
    that the range was the range being SHIPPED. `--fixed-point HEAD^` on a
    twelve-commit branch produces a truthful receipt covering one commit, and
    `kb-ship` accepted it for all twelve. This is the check that makes "reviewed"
    mean "reviewed the thing you are pushing".

    The base is resolved against ``sha`` — the commit being validated — and NOT
    against live `HEAD`. That distinction is what lets `land` use this at all:
    `land` validates the PR head oid, which is usually not the local HEAD, so a
    HEAD-relative merge-base would refuse every merge. `base_sha` grew its
    ``head`` parameter for exactly this and only the receipt WRITER used it;
    reading it here is the other half.

    Fails CLOSED on an unresolvable base: if the comparison cannot be made, the
    question was never asked.
    """
    want = base_sha(repo_root, require_base, head=sha)
    if not want:
        return f"could not resolve '{require_base}' to compare the review's base against"
    got = str(data.get("fixed_point_sha") or "").strip()
    if got != want:
        return (
            f"was reviewed against {got[:12] or '(nothing)'}, but this branch's base is "
            f"{want[:12]} — a partial range does not gate the whole branch; re-review "
            f"against {require_base}"
        )
    return None


def _is_exempt(path: str) -> bool:
    """Return whether ``path`` could not have existed at review time (:data:`EXEMPT_PATHS`).

    Wording matters here and this line got it wrong once: it said "one a review
    lane cannot cover", which is the rationale the constant above retracts in
    bold. A lane reads these files perfectly well — the review of the very commit
    that introduced this helper found three live credentials in one of them. The
    retraction landed at the constant and not at the helper implementing it, and
    it is the retracted version that invites widening the set.

    A DELETION inside an exempt path passes too, which is wider than the
    motivating case (P7 only ever adds a memory file and edits one table cell).
    Deliberate: the property being checked is that the shipped tree matches a
    reviewed tree outside these paths, and a delete satisfies that as squarely as
    an add. Narrowing to additions would be a rule about how the files got there
    rather than about what is shipping.
    """
    return any(
        path.startswith(entry) if entry.endswith("/") else path == entry for entry in EXEMPT_PATHS
    )


def _delta_paths(repo_root: Path, older: str, newer: str) -> list[str] | None:
    """Return every path differing between two commits, or None if unreadable.

    ``--no-renames`` on purpose: with rename detection on, moving a reviewed
    source file INTO an exempt directory shows only the exempt destination, so
    the delta would read as exempt while a reviewed file was silently deleted.
    Off, the same move is a delete plus an add and the deleted path fails the
    check. ``-z`` sidesteps `core.quotePath` escaping entirely, so a path with a
    quote or a non-ASCII byte in it is compared as the bytes git actually has
    rather than as a re-encoded display form.

    **This is an ENDPOINT diff, and that bound is worth stating.** A file added
    in one intervening commit and deleted in a later one appears in neither tree,
    so it is invisible here. What that does NOT mean is that unreviewed content
    can reach `main`: `land` merges with ``--squash``, so what lands is this
    endpoint tree, and the guarantee — the shipped tree equals a reviewed tree
    outside :data:`EXEMPT_PATHS` — holds exactly.

    Where it is real is the PUSHED BRANCH: `ship` pushes every commit, so an
    intermediate blob reaches the remote even though the squash discards it.
    That is not a property of this fallback — the lanes themselves review
    ``<base>...HEAD``, an endpoint diff, so the same blob is invisible to an
    ordinary review — which is why it is recorded here and filed rather than
    patched under a fallback that did not cause it. (Cold lane, round 3.)
    """
    ok, out = _git_result(
        repo_root, "diff", "--name-only", "--no-renames", "-z", older, newer, "--"
    )
    if not ok:
        return None
    return [p for p in out.split("\0") if p]


def _reviewed_ancestors(repo_root: Path, sha: str, base_ref: str) -> tuple[list[str], str]:
    """Return EVERY commit on this branch below ``sha`` that has a receipt.

    All of them, not one. The first draft took only the first and justified it
    with "a farther ancestor is strictly harder to accept, because every path in
    the nearer delta is also in the farther one". That is **false**, and two
    lanes said so independently: add `foo.py` in one commit and delete it in the
    next, and the farther delta does not contain `foo.py` while the nearer one
    does. It also claimed `git rev-list` yields the NEAREST first, which it does
    not — rev-list orders by commit date, so a merge can put a farther commit
    ahead of a nearer one.

    Neither error was unsafe, and that is exactly why they survived: the check is
    TREE-based, so any ancestor whose delta to ``sha`` is exempt-only proves the
    same thing — the shipped tree equals a reviewed tree except in exempt paths.
    The cost of trying one candidate was a refusal where an acceptance was
    warranted. Trying all of them removes the ordering claim entirely rather than
    asserting a property the code does not enforce.

    The walk is bounded to ``base_ref..sha`` — this branch's own commits. That
    is not a convenience: a receipt for some commit already on `main` is a
    receipt for a review of a DIFFERENT branch, and letting the search reach one
    would let ancient reviews vouch for new work.
    """
    base = base_sha(repo_root, base_ref, head=sha)
    if not base:
        return [], f"could not resolve '{base_ref}' to look for a reviewed ancestor"
    ok, out = _git_result(repo_root, "rev-list", f"{base}..{sha}", "--")
    if not ok:
        return [], "could not list this branch's commits to look for a reviewed ancestor"
    found = [
        commit
        for commit in out.split()
        if commit != sha and receipt_path(repo_root, commit).is_file()
    ]
    if not found:
        return [], "and no commit below it on this branch has one either"
    return found, ""


@dataclass(frozen=True)
class _Covering:
    """One receipt that might answer for a commit, and why it is not that commit's.

    A record rather than a `(sha, note)` pair because the third field is the one
    that kept getting re-derived: `receipt_state` computed
    `refused = bool(note) and covering == sha`, which is a second encoding of a
    state this function already knows. Two encodings of one fact is how they
    drift. (Standards lane, round 2.)
    """

    sha: str
    note: str
    #: True when :attr:`sha` is an ANCESTOR standing in for the commit asked
    #: about; False when it is that commit, whether or not a fallback was tried.
    fallback: bool


def _covering_candidates(repo_root: Path, sha: str, require_base: str | None) -> list[_Covering]:
    """Return the receipts that might answer for ``sha``, best first.

    Normally that is one entry — the receipt FOR ``sha``. The exception is #66:
    every rider's P7 mandates `kb-remember` and `kb-goal-outcome`, both of which
    write files (:data:`EXEMPT_PATHS`) that can only exist once the review has
    already happened. Committing them moved HEAD past the receipt and `ship`
    refused, so three rounds running left them uncommitted instead.

    So a receipt at an ancestor covers ``sha`` when the ENTIRE delta between them
    is inside the exempt set. Nothing about the reviewed bytes is relaxed: one
    reviewed path in that delta and that candidate is out. That is the narrower
    of the two options on #66 — the alternative, exempting those paths from
    coverage outright, would also excuse them in a delta full of code.

    EVERY qualifying ancestor is returned, not the first, because a qualifying
    delta is not the same as a valid receipt: the first draft committed to the
    first ancestor whose delta was exempt-only and never tried a later one when
    that ancestor's receipt turned out to be invalid — the same single-candidate
    bug this feature had already fixed one dimension over. Fail-closed, and
    untested, which is why it survived. (Silent-failure lane, round 2.)

    Only offered when ``require_base`` is given, which is what bounds the
    ancestry walk to this branch. Both callers that gate (`ship`, `land`) pass
    it; the receipt writer's own read-back does not, and wants strict identity.
    """
    if require_base is None or receipt_path(repo_root, sha).is_file():
        return [_Covering(sha, "", fallback=False)]

    ancestors, why = _reviewed_ancestors(repo_root, sha, require_base)
    if not ancestors:
        return [_Covering(sha, why, fallback=False)]

    covering: list[_Covering] = []
    refusals: list[tuple[int, str]] = []
    for ancestor in ancestors:
        accepted, note, offending = _exempt_delta_note(repo_root, ancestor, sha)
        if accepted:
            covering.append(_Covering(ancestor, note, fallback=True))
        else:
            refusals.append((offending, note))
    if covering:
        return covering

    # The MOST INFORMATIVE refusal, not the first. Candidates arrive in
    # `git rev-list` order — commit date, which is not distance — so "the first"
    # was an arbitrary choice dressed as a nearest-first one, and `_summarise`'s
    # bound could then hide the file that actually blocks the ship behind
    # `(+N more)` while a candidate with one offending path went unreported.
    # (Silent-failure lane, round 2.)
    refusals.sort(key=lambda item: item[0])
    return [_Covering(sha, refusals[0][1], fallback=False)]


def _exempt_delta_note(repo_root: Path, candidate: str, sha: str) -> tuple[bool, str, int]:
    """Return ``(candidate covers sha, why, how many reviewed paths block it)``."""
    paths = _delta_paths(repo_root, candidate, sha)
    if paths is None:
        # Unreadable ranks WORST among refusals: it is "could not check", and a
        # refusal that names a real file is more actionable than one that cannot.
        return (
            False,
            f"and the delta from reviewed ancestor {candidate[:12]} could not be read",
            _UNREADABLE_RANK,
        )

    reviewed = sorted(p for p in paths if not _is_exempt(p))
    if reviewed:
        return (
            False,
            f"and reviewed ancestor {candidate[:12]} does not cover it: "
            f"{_summarise(reviewed)} changed since, which no lane has read",
            len(reviewed),
        )

    covered = _summarise(sorted(paths)) if paths else "an identical tree"
    return True, f"covered by the receipt for {candidate[:12]}; since then only {covered}", 0


def _summarise(paths: list[str]) -> str:
    """Return ``paths`` joined, bounded by :data:`_MAX_NAMED_PATHS`, stating any remainder.

    Applied to BOTH the refusal list and the accepted list. Bounding only the
    refusal left the permissive branch — the one that lets a commit ship — able
    to print an unbounded path list, which is the branch where a wall of text is
    most likely to go unread. (Standards and spec lanes, independently.)
    """
    shown = ", ".join(_printable(p) for p in paths[:_MAX_NAMED_PATHS])
    extra = len(paths) - _MAX_NAMED_PATHS
    return f"{shown} (+{extra} more)" if extra > 0 else shown


def _printable(path: str) -> str:
    r"""Return ``path`` with control characters escaped, for a terminal message.

    These strings are printed by `ship` and `land`, and every character in them
    comes from a FILENAME in someone's commit. A newline splits the refusal into
    what looks like two lines of tool output; an ANSI escape can repaint or erase
    the lines around it. The gate's own diagnosis is the one piece of its output
    an attacker can influence, so it is escaped rather than trusted.

    `repr`-style escaping via `unicode_escape` would also mangle ordinary
    non-ASCII filenames into `\\xNN` noise, which costs legibility for every
    honest path to defend against a rare one — so only C0/C1 controls and DEL are
    replaced, and everything printable survives as itself. (Cold lane, round 2.)
    """
    return "".join(ch if ch.isprintable() else f"\\x{ord(ch):02x}" for ch in path)


def _load_receipt(path: Path, sha: str, *, note: str = "") -> tuple[dict[str, Any] | None, str]:
    """Return ``(data, "")``, or ``(None, reason)`` if it cannot be read as one.

    Every arm fails CLOSED with a worded reason rather than raising: this is the
    boundary where a receipt stops being bytes and starts being a verdict, and a
    traceback out of here would be a crash where a refusal belongs.

    ``note`` is :func:`_covering_candidates`'s account of why the exempt-delta
    fallback did not rescue this SHA, folded into the message ahead of the
    advice so the reason precedes the remedy.
    """
    if not path.is_file():
        return None, (
            f"no review receipt for {sha[:12]}{f', {note}' if note else ''} — run the "
            f"`kb-review` skill (an amend or rebase moves the SHA and invalidates the old one)"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # `UnicodeDecodeError` is raised by `read_text` BEFORE json ever sees the
        # bytes, and it is NOT an `OSError` — so a truncated or partly-binary
        # receipt escaped as a traceback. `write_receipt` is a non-atomic
        # `write_text`, so partial files are realistic, not theoretical.
        return None, f"receipt for {sha[:12]} is unreadable: {exc}"
    if not isinstance(data, dict):
        return None, f"receipt for {sha[:12]} is not an object"
    return data, ""


def receipt_state(
    repo_root: Path, sha: str, *, require_base: str | None = None
) -> tuple[bool, str]:
    """Return ``(ok, summary)`` for ``sha``'s review receipt.

    ``require_base`` additionally demands that the receipt was written against
    this branch's merge-base with that ref — i.e. that the review covered the
    WHOLE branch, not a suffix of it. **`ship` AND `land` both pass ``"main"``**;
    the receipt writer's own read-back does not, because a receipt reviewed
    against a narrower base is still a truthful record of what it reviewed. It is
    the act of shipping the whole branch that needs the whole branch reviewed.

    `land` was added to that list in `b4d1063` and this sentence was not, so it
    named one caller for four rounds while two were passing it — and the missing
    one is the half that matters, since `gh pr create` is not guard-denied here
    and `land` is documented as the backstop for exactly that bypass. (#57)

    It also enables the :func:`_covering_candidates` fallback, under which an
    ancestor's receipt covers ``sha`` when everything committed since is inside
    :data:`EXEMPT_PATHS`. Every check below then runs against that ancestor
    unchanged — the fallback decides WHICH receipt is asked, never how hard it is
    asked. Each candidate is judged in full, so an ancestor with a qualifying
    delta but an invalid receipt does not consume the branch's only chance.
    """
    if not sha:
        return False, "could not read HEAD"

    first: tuple[bool, str] | None = None
    for covering in _covering_candidates(repo_root, sha, require_base):
        verdict = _judge(repo_root, covering, require_base)
        if verdict[0]:
            return verdict
        first = first or verdict
    # `_covering_candidates` always yields at least one entry, so `first` is set.
    return first if first is not None else (False, "no receipt could be evaluated")


def _judge(repo_root: Path, covering: _Covering, require_base: str | None) -> tuple[bool, str]:
    """Return ``(ok, summary)`` for ONE candidate receipt."""
    # A note on a FALLBACK candidate explains why a non-HEAD SHA is being judged,
    # so it trails every message including the unreadable one — an earlier version
    # built the suffix after the unreadable return and that one path printed an
    # ancestor SHA with nothing to explain it (cold lane, round 2). A note on a
    # NON-fallback candidate is the opposite thing: an account of why the fallback
    # did not rescue this SHA, which belongs INSIDE the "no receipt" message,
    # because "no receipt — run the review skill" reads as "you never reviewed"
    # when the real story is "you reviewed, then committed something no lane has
    # read" — and only the second names the file.
    suffix = f" — {covering.note}" if covering.note and covering.fallback else ""
    sha = covering.sha

    data, unreadable = _load_receipt(
        receipt_path(repo_root, sha),
        sha,
        note="" if covering.fallback else covering.note,
    )
    if data is None:
        return False, f"{unreadable}{suffix}"

    if require_base is not None:
        gap = _base_coverage_gap(repo_root, data, require_base, sha)
        if gap is not None:
            return False, f"receipt for {sha[:12]} {gap}{suffix}"

    reason = _all_reasons(repo_root, data, sha)
    if reason is not None:
        return False, f"receipt for {sha[:12]} {reason}{suffix}"

    ran = data["lanes_ran"]
    skipped = data.get("lanes_skipped", [])
    detail = f"{len(ran)} lane(s): {', '.join(map(str, ran))}"
    if skipped:
        detail += f" | skipped: {', '.join(map(str, skipped))}"
    return True, f"{detail}{suffix}"
