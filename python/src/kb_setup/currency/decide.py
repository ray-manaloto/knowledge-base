"""Step 5 — the six-gate bar, and the questions a human still has to answer.

Ray chose (2026-07-23) that an unambiguous bump may apply itself. That makes the
definition of "unambiguous" the safety-critical part of this engine, so it is
written once, here, as six explicit gates rather than distributed through the
code as conditionals.

The bar is conservative on purpose, and it **fails closed**: anything this module
cannot read — an unreachable upstream, an unparsable version, absent release
notes — is ambiguity, never consent. A bump only proceeds unattended when all six
gates positively pass.

This module produces the *questions*; it never asks them. `AskUserQuestion` can
only be called by the model, which is why step 5 lives in the skill and can never
live in the SessionStart hook (a hook is a shell command).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kb_setup.currency import views as views_mod
from kb_setup.currency.upstream import UpstreamStatus, Version, same_release

if TYPE_CHECKING:
    from kb_setup.currency.issues import Observation
    from kb_setup.currency.sync import SyncStatus
    from kb_setup.currency.views import ViewStatus

GATES = (
    "patch-level bump",
    # NOT "PyPI latest has a matching GitHub tag". What `_gate_tag` actually checks
    # is `upstream.github_tag` — did a readable GitHub release exist for `latest` —
    # and that is the same check whether the version came from PyPI or from GitHub
    # itself. The old label hardcoded PyPI, so a GitHub-only tool's PASSING gate
    # rendered as a check it never ran: `docs/currency/runs/2026-07-29-mise.md`
    # committed `✅ PyPI latest has a matching GitHub tag` for mise, whose
    # `currency.toml` block has no `pypi` key at all. (Cold lane, round 2.)
    "latest version has a readable GitHub release",
    "no breaking/removal/deprecation marker",
    "extras unchanged",
    "no tracked issue moved",
    "step 1 currently green",
)


@dataclass(frozen=True)
class Ambiguity:
    """One thing a human must decide, shaped for an AskUserQuestion prompt."""

    gate: str
    question: str
    detail: str
    recommendation: str = ""


def _has_upgrade(current: str, latest: str) -> bool:
    """Whether `latest` is a different RELEASE from `current`, not a different string.

    Module-level so `decide` can consult it while building the verdict and
    `Verdict.has_upgrade` can expose it afterwards — one implementation, because
    two would be free to disagree about the case that caused the bug. It now
    delegates to `upstream.same_release` for the same reason, one level up: the
    early-return in `decide` and the one in `upstream.probe` were still comparing
    raw strings, so three call sites could disagree about whether `v2.1.220` and
    `2.1.220` are the same release. (Cold lane, round 2.)
    """
    if not latest:
        return False
    return not same_release(current, latest)


@dataclass(frozen=True)
class Verdict:
    """The outcome of a run: what happens next, and why."""

    tool: str
    current: str
    latest: str
    auto_apply: bool
    gates_passed: tuple[str, ...]
    ambiguities: tuple[Ambiguity, ...]
    tracked: bool = True
    # Advisory (step 3): new-capability lines from the release notes. NEVER gates
    # a bump — surfaced so "should we adopt this?" reaches the human even when no
    # breaking marker fired. Empty when there is no upgrade or the notes announce
    # nothing feature-shaped.
    feature_review: tuple[str, ...] = ()
    # How many feature lines the cap discarded, and whether the notes' format was
    # recognisable at all. Both exist so an empty `feature_review` is never read as
    # "there was nothing to adopt" — see `UpstreamStatus.feature_scan_unrecognised`.
    features_dropped: int = 0
    features_unreadable: bool = False

    @property
    def has_upgrade(self) -> bool:
        """True when upstream offers a version we are not on.

        Compared as PARSED VERSIONS, not as strings. `latest` carries whatever
        decoration upstream ships — GitHub hands back the tag, so claude-code's
        `2.1.220` was measured against `v2.1.220` and a plain `!=` called the same
        release an upgrade. That one character then propagated: the landing page
        rendered an arrow between two identical versions, `has_content` earned a
        detail page for a run with no content, and notes were fetched for a bump
        that did not exist. Falls back to string inequality only when a side will
        not parse, where nothing better is available.
        """
        return _has_upgrade(self.current, self.latest)

    @property
    def needs_interview(self) -> bool:
        """True when the model must run AskUserQuestion before anything proceeds.

        `feature_review` is deliberately NOT here: a feature to consider is an
        FYI, not a blocker, so an otherwise-clean auto-apply stays auto-apply.
        """
        return bool(self.ambiguities)

    def summary(self) -> str:
        """One line for the landing page.

        A version being current is NOT the same as everything being fine: the
        install can be out of sync, or a tracked issue can have moved, with no
        upgrade pending at all. Reporting only the version would let the landing
        page read "current" through exactly the drift this engine exists to find.
        """
        if self.auto_apply:
            return f"{self.tool} {self.current} → {self.latest}: auto-applying (6/6 gates)"
        if self.has_upgrade:
            version = f"{self.current} → {self.latest}"
        elif self.latest:
            version = f"{self.current}, current"
        elif not self.tracked:
            # A presence-only tool (ffmpeg): installed and checked, but with no
            # upstream version to chase. "UNKNOWN" would wrongly imply a failed
            # lookup; there is nothing to look up.
            version = f"{self.current or 'present'}, not version-tracked"
        else:
            # We never reached upstream. "current" would be a committed assertion
            # that this IS the newest version, made by a run that never asked.
            version = f"{self.current}, latest UNKNOWN"
        if self.ambiguities:
            return f"{self.tool} {version}: {len(self.ambiguities)} question(s) for review"
        return f"{self.tool} {version}: clean"


def _gate_patch(current: str, latest: str) -> Ambiguity | None:
    cur, new = Version.parse(current), Version.parse(latest)
    if cur is None or new is None:
        return Ambiguity(
            gate=GATES[0],
            question=f"Version {current!r} → {latest!r} could not be parsed. Adopt it?",
            detail="A non-numeric version cannot be classified as patch/minor/major.",
            recommendation="Hold — read the release manually before adopting.",
        )
    if not (cur > new) and not (new > cur):
        # SAME version, differing only in decoration (`2.1.220` vs the `v2.1.220`
        # tag). There is nothing to adopt, so there is nothing to ask about — and
        # asking anyway is worse than noise: claude-code sat exactly on its latest
        # release and this gate demanded a decision on the non-bump every single
        # run, which trains the reader to skip the one output this engine exists to
        # produce. `is_patch_bump_from` already refuses the no-op in the APPLY
        # direction (its docstring names the `1.2` vs `1.2.0` case); this is the
        # same equality seen from the interview side, where it has to be silence.
        return None
    if not new.is_patch_bump_from(cur):
        return Ambiguity(
            gate=GATES[0],
            question=f"{current} → {latest} is not a patch bump. Adopt it?",
            detail=(
                "Only the patch component may move unattended. Pre-1.0 projects use the "
                "MINOR slot as their breaking channel, so 0.9.x → 0.10.0 stops here."
            ),
            recommendation="Read the release notes, then decide.",
        )
    return None


def _gate_tag(upstream: UpstreamStatus, latest: str) -> Ambiguity | None:
    if upstream.unread_versions:
        # A multi-patch jump adopts EVERY release in between. Judging it on the
        # ones we could read would be the absence-of-evidence trap again.
        return Ambiguity(
            gate=GATES[1],
            question=(
                f"Notes for {', '.join(upstream.unread_versions)} could not be read. "
                f"Adopt {latest} anyway?"
            ),
            detail=(
                "This bump adopts every release between the pin and the latest, so a "
                "breaking change announced in one of the unread ones would be invisible."
            ),
            recommendation="Read the missing releases, or bump one release at a time.",
        )
    if upstream.github_tag:
        return None
    # Name the source that actually supplied the version. Saying "PyPI has X" about
    # a GitHub-only tool describes a lookup that never happened — the same
    # mislabelling the `GATES[1]` comment records. (Cold lane, round 2.)
    where = "PyPI" if upstream.source == "pypi" else "upstream"
    return Ambiguity(
        gate=GATES[1],
        question=f"{where} has {latest} but no matching GitHub release was found. Adopt it?",
        detail=(
            f"Could not read a release for {latest}"
            + (f" ({upstream.error})" if upstream.error else "")
            + ". Without notes there is nothing to review, and the PyPI/tag split is a "
            "known trap here: graphify v1.0.0 was tagged while PyPI's latest was 0.9.25."
        ),
        recommendation="Hold until the release exists or you have read the diff.",
    )


def _gate_markers(upstream: UpstreamStatus) -> Ambiguity | None:
    # An EMPTY release body is not a clean bill of health. "No breaking marker
    # found" in a document that does not exist is the absence-of-evidence trap
    # (`probes-need-a-control-arm.md`: a 0-result search is not an answer), and
    # it contradicts this module's own fail-closed rule. A release published
    # with no notes is precisely a release nobody has described, so it stops.
    if not upstream.notes.strip():
        return Ambiguity(
            gate=GATES[2],
            question="The release has no notes at all. Adopt it unreviewed?",
            detail=(
                "An empty release body cannot be scanned for breaking changes, so "
                "'no marker found' here means 'nothing was read', not 'nothing to worry about'."
            ),
            recommendation="Read the upstream diff or changelog before adopting.",
        )
    markers = upstream.markers
    if not markers:
        return None
    return Ambiguity(
        gate=GATES[2],
        question="The release notes flag a breaking change. Adopt it anyway?",
        detail=f"Markers found: {', '.join(markers)}.",
        recommendation="Read the notes; plan a rebuild and a re-verify before adopting.",
    )


def _gate_extras(sync: SyncStatus) -> Ambiguity | None:
    bad = [f for f in sync.drifted if f.check == "extras"]
    if not bad:
        return None
    return Ambiguity(
        gate=GATES[3],
        question="The declared extras disagree with the pin. Fix before bumping?",
        detail=bad[0].detail,
        recommendation="Reconcile currency.toml and mise.toml first.",
    )


def _gate_issues(
    moved: tuple[Observation, ...], observations: tuple[Observation, ...]
) -> Ambiguity | None:
    """Gate 5. Needs BOTH the movers and the raw observations.

    `moved` alone cannot express "we could not read it". `differs_from` rightly
    refuses to call an errored observation movement — a rate-limit must not
    manufacture movement on every item — so an unreadable issue and an issue that
    provably did not move both arrive here as absence. Reading that absence as a
    PASS is the inversion of this module's contract: gate 5's entire job is to
    stop a bump, and it was passing on issues nobody had read.
    """
    unread = [o for o in observations if o.error]
    if unread:
        return Ambiguity(
            gate=GATES[4],
            question=(
                f"{len(unread)} tracked item(s) could not be read. Bump without checking them?"
            ),
            detail="; ".join(f"{o.key}: {o.error}" for o in unread),
            recommendation=(
                "Retry when GitHub is reachable — an expired token or a rate limit "
                "leaves this gate blind, not satisfied."
            ),
        )
    if not moved:
        return None
    names = ", ".join(o.key for o in moved)
    return Ambiguity(
        gate=GATES[4],
        question="Tracked issues moved since the last run. Review before bumping?",
        detail=f"Changed: {names}.",
        recommendation="Read each change — one of them may be the reason to bump, or not to.",
    )


def _gate_local(observations: tuple[Observation, ...]) -> Ambiguity | None:
    """Gate 5, second half — local watch items, which movement can never surface.

    A `kind = "local"` item is a finding of ours with no upstream ticket, so it
    observes as itself every run: same key, same `state="local"`, no timestamp.
    `differs_from` therefore returns False forever, and gate 5 could never block
    on one — while `currency.toml`'s founding local item says in as many words
    "Re-probe on each bump". The claim and the machinery disagreed, and the
    machinery was silent, which is the worse of the two failure directions.

    Resolved in favour of the claim: a local item is an OPEN question by
    construction (it exists precisely because nobody has closed it), so a pending
    bump always stops for it. Only reached on the upgrade path — a local item is
    not a reason to interrupt a run with no bump pending.
    """
    local = [o for o in observations if o.state == "local"]
    if not local:
        return None
    return Ambiguity(
        gate=GATES[4],
        question=f"{len(local)} local watch item(s) must be re-probed against this release. Done?",
        detail="; ".join(f"{o.key}: {o.title}".replace("\n", " ") for o in local),
        recommendation=(
            "Re-probe each against the new version, then record the result in "
            "currency.toml — an untested local finding is folklore, not a finding."
        ),
    )


def _gate_sync(sync: SyncStatus, views: ViewStatus | None = None) -> Ambiguity | None:
    """Gate 6. Blocks on drift, and equally on a check that never got to run.

    `views` is the derived-views verdict (#182), and it belongs to THIS gate rather
    than a seventh one. The gate is named "step 1 currently green" and a stale view
    is a step-1 finding — it was simply reported under its own header, so this
    function, reading only `sync.drifted`/`sync.blind`, could not see it. A cold
    review caught that: a genuinely stale `wiki/` could not block an otherwise-6/6
    AUTO-APPLY, on a gate whose name says it would.

    It is deliberately not fatal-by-itself-forever: like every other ambiguity here
    it raises a question the human answers. What it must not do is stay silent,
    because silence on this path is consent.

    **BOTH loud states, and the first fix shipped only one.** It took a `tuple` of
    stale lines, which is empty for every `NOT_VERIFIABLE` verdict — so a views
    check that could not verify anything was invisible to the gate, on the very
    change whose purpose was closing that class of gap. The cold lane rated the
    second round P1 and quoted the paragraph above back: silence is consent, and
    *not verifiable* is silence. It takes the whole `ViewStatus` now, so a state
    this gate has not been taught about cannot arrive looking like a pass — the
    same reason `sync` splits SKIP from BLIND two paragraphs up.

    This used to name the checks that had to pass (`("resolution", "build-stamp")`)
    and let everything else SKIP. Two things were wrong with that. It omitted
    `extra-probes` and `manifest`, so a run that could not locate the install at
    all still auto-applied. And the fix cannot be "add those two names": `manifest`
    and `build-stamp` SKIP legitimately in a repo that declares neither, so
    demanding them would have permanently blocked a repo with nothing to check —
    a false stop replacing a false pass.

    The distinction that actually holds is not WHICH check but WHY it is silent,
    which is why `sync.py` splits SKIP ("nothing configured to check") from BLIND
    ("configured, and this run could not read it"). Only BLIND is disqualifying,
    and it disqualifies whatever check it lands on.
    """
    others = [f for f in sync.drifted if f.check != "extras"]
    if others:
        return Ambiguity(
            gate=GATES[5],
            question="The current install is already out of sync. Fix that before bumping?",
            detail="; ".join(f"{f.check}: {f.detail}" for f in others),
            recommendation=(
                "Resolve the drift first — bumping on top of an unknown state makes the "
                "result unattributable."
            ),
        )
    if blind := sync.blind:
        return Ambiguity(
            gate=GATES[5],
            question="Step 1 could not actually verify this install. Bump anyway?",
            detail=(
                "Not checked: "
                + "; ".join(f"{f.check} ({f.detail})" for f in blind)
                + ". Nothing disagreed, but these checks never ran."
            ),
            recommendation="Run where the tool is installed, so the bump is made on evidence.",
        )
    if views is not None and views.stale:
        return Ambiguity(
            gate=GATES[5],
            question="Derived views describe an earlier graph. Bump anyway?",
            detail=(
                "Generated outputs out of date with the graph they came from: "
                + "; ".join(views.stale)
            ),
            recommendation=(
                "Run `mise run kb-artifacts` first — NOT `kb-build`, which does not "
                "regenerate them. A bump made over stale views leaves it unclear "
                "afterwards whether a difference came from the new version or the "
                "old outputs."
            ),
        )
    if views is not None and views.state == views_mod.NOT_VERIFIABLE:
        return Ambiguity(
            gate=GATES[5],
            question="The derived views could not be verified at all. Bump anyway?",
            detail=(
                f"{views.detail or 'no reason recorded'}"
                + ("; " + "; ".join(views.blind) if views.blind else "")
                + ". Nothing disagreed, but this check never ran."
            ),
            recommendation=(
                "Run `mise run kb-artifacts` so the stamp records what each view was "
                "generated from, then re-run. Bumping now would rest on a check that "
                "produced no answer."
            ),
        )
    return None


def decide(
    *,
    sync: SyncStatus,
    upstream: UpstreamStatus,
    moved: tuple[Observation, ...],
    observations: tuple[Observation, ...] = (),
    views: ViewStatus | None = None,
) -> Verdict:
    """Apply the six gates and return what should happen next.

    A run with no available upgrade still reports its ambiguities: an out-of-sync
    install or a moved issue is worth surfacing whether or not a bump is pending.
    """
    current = sync.pinned
    latest = upstream.latest

    always = [
        g
        for g in (
            _gate_extras(sync),
            _gate_issues(moved, observations),
            _gate_sync(sync, views),
        )
        if g
    ]

    # A presence-only tool (ffmpeg: source="none") has no version to chase, so an
    # unread upstream is a NON-event, not an ambiguity. This is the whole reason
    # `tracked` exists: the old model returned reachable=False here and
    # manufactured a permanent "upstream could not be checked" for a tool that
    # was never version-tracked to begin with.
    if upstream.tracked and not upstream.reachable:
        always.append(
            Ambiguity(
                gate="upstream reachable",
                question="Upstream could not be checked. Retry, or proceed without it?",
                detail=upstream.error or "unknown error",
                recommendation="Retry when online; do not adopt anything on an unread upstream.",
            )
        )
        return Verdict(
            tool=sync.tool,
            current=current,
            latest="",
            auto_apply=False,
            gates_passed=(),
            ambiguities=tuple(always),
            tracked=upstream.tracked,
        )

    # `same_release`, not `==` — see `_has_upgrade`. A decoration-only mismatch has
    # no upgrade to gate, so it must take this early return rather than fall through
    # to `_gate_tag`/`_gate_markers`/`_gate_local`, none of which check that a real
    # version delta exists before asking a human about it. (Cold lane, round 2.)
    if not latest or same_release(current, latest):
        return Verdict(
            tool=sync.tool,
            current=current,
            latest=latest,
            auto_apply=False,
            gates_passed=(),
            ambiguities=tuple(always),
            tracked=upstream.tracked,
        )

    upgrade_gates = [
        gate
        for gate in (
            _gate_patch(current, latest),
            _gate_tag(upstream, latest),
            _gate_markers(upstream),
            _gate_local(observations),
        )
        if gate
    ]
    ambiguities = tuple(upgrade_gates + always)
    failed = {a.gate for a in ambiguities}
    passed = tuple(g for g in GATES if g not in failed)
    return Verdict(
        tool=sync.tool,
        current=current,
        latest=latest,
        # An upgrade must actually EXIST to be auto-applied. `apply()` already
        # refuses a no-op ("no upgrade pending"), so without this the verdict and
        # the applier disagreed, and the landing page published the verdict's
        # version: `claude-code 2.1.220 → v2.1.220: auto-applying (6/6 gates)`,
        # which announces work on a release we are already running.
        auto_apply=not ambiguities and _has_upgrade(current, latest),
        gates_passed=passed,
        ambiguities=ambiguities,
        tracked=upstream.tracked,
        feature_review=upstream.feature_highlights,
        features_dropped=upstream.features_dropped,
        features_unreadable=upstream.feature_scan_unrecognised,
    )
