# Copyright (c) 2026 Raymond Manaloto
"""Step 4 — have any tracked issues or local watch items moved since last run?

"Tracked" covers two kinds deliberately. Upstream GitHub issues are fetched and
diffed; **local** watch items are findings of ours with no upstream ticket (the
`label_communities` JSON-schema gap is the founding example) and are carried
forward verbatim so they cannot decay into folklore.

The previous observation lives in the committed report, not in a cache: the
whole point of step 6 is that this history is reviewable, and a diff against an
untracked `~/.cache` would be neither reviewable nor reproducible on a fresh
clone.

A local item's OPEN status (gate 5, second half, `decide._gate_local`) used to
close only via a hand-appended `currency.toml` note — prose nothing read, and
indistinguishable from one written for THIS release or six releases ago.
`Reviewed` / `load_reviewed` / `record_reviewed` / `cleared_for` (#486) make
that a checkable claim instead: a re-probe is recorded AGAINST a version, and
it clears the gate only when that is the SAME RELEASE as the one being adopted.

That closed the RELEASE axis and left the FINDING axis open (cold review of
`dd90e64f`, B1): `Reviewed` bound only `(key, version)`, and `key` is
`kind:ref` — the `note`, the only place a local finding's content actually
lives, was not part of the identity. Rewrite a watch item's `note` (or delete
it and let a new finding reuse the same free-text `ref`) and an old clearance
at the same version kept passing, on the strength of a re-probe of a finding
that no longer existed. `finding_digest` closes that: a `Reviewed` record now
also carries a content digest of the note it was recorded against, and
`cleared_for` requires that to match the watch item's CURRENT note before it
ever reaches the version comparison.

A first cut at the sibling hygiene gap — pruning a clearance for a key no
longer configured — folded it into `record_reviewed` as an automatic side
effect, on the strength of `save_current`'s (superficially similar, actually
unrelated) pruning of network-re-fetched observations. Cold review of
`8a02b82d` (MAJ-1): `config._watch_items` fails soft, so "absent from a
config parse" is not proof an item was genuinely removed, and the automatic
prune deleted a sibling item's clearance — a human assertion nothing can
re-derive — on nothing more than a config typo. `prune_reviewed` is now its
own function, called only when a caller explicitly asks; `record_reviewed`
never prunes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from kb_setup.currency import _proc
from kb_setup.currency.upstream import Version, same_release
from kb_setup.fetch import content_hash

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from kb_setup.currency.config import ToolSpec, WatchItem

_TIMEOUT_S = 20.0
STATE_FILE = "watch-state.json"
REVIEWED_FILE = "watch-reviewed.json"


@dataclass(frozen=True)
class Observation:
    """What one watch item looked like on one run."""

    key: str
    state: str = ""
    updated_at: str = ""
    comments: int = 0
    title: str = ""
    error: str = ""

    @property
    def usable(self) -> bool:
        """Whether this observation is fit to become the next run's baseline.

        NOT the same as "did not error". A 200 whose body lacks the watched
        fields parses cleanly and yields blanks with `error=""`, so keying
        carry-forward on `error` alone let a degraded success overwrite a good
        baseline, report a spurious "issue moved", and then report it a SECOND
        time on the next healthy run — because the baseline it compared against
        had been wiped by the first.
        """
        return not self.error and bool(self.state)

    def differs_from(self, other: Observation | None) -> bool:
        """True when the fields we watch changed. An unreadable run never counts.

        An errored observation is explicitly NOT a change: a rate-limited or
        offline run would otherwise manufacture movement on every tracked issue
        and drown the real signal.
        """
        if other is None or not self.usable or other.error:
            return False
        return (
            self.state != other.state
            or self.updated_at != other.updated_at
            or self.comments != other.comments
        )


def _as_int(value: object) -> int:
    """Coerce an untyped JSON field to int; anything unusable becomes 0."""
    try:
        if isinstance(value, (int, str)):
            return int(value)
    except TypeError, ValueError:
        return 0
    return 0


def _fetch_issue(repo: str, ref: str) -> tuple[dict[str, object], str]:
    """One `gh api` issue read, as (payload, error)."""
    return _proc.run_json(
        [
            "gh",
            "api",
            f"repos/{repo}/issues/{ref}",
            "--jq",
            "{state:.state,updated_at:.updated_at,comments:.comments,title:.title}",
        ],
        timeout=_TIMEOUT_S,
        label=f"gh api repos/{repo}/issues/{ref}",
    )


def observe(item: WatchItem, *, default_repo: str) -> Observation:
    """Fetch the current state of one watch item.

    A `local` item has no upstream to read, so it observes as itself — present,
    unchanged, and still owed a decision.
    """
    if item.kind != "issue":
        return Observation(key=item.key, state="local", title=item.note)

    repo = item.repo or default_repo
    if not repo:
        return Observation(key=item.key, error="no repo configured for this issue")

    data, err = _fetch_issue(repo, item.ref)
    if err:
        return Observation(key=item.key, error=err)

    # EVERY diffed field must be readable, not just `state`. A 200 carrying
    # `state="open"` with a null `updated_at` used to parse into a blank string
    # with no error, so it counted as usable, overwrote a good baseline, and
    # reported "moved" — then reported it a SECOND time on the next healthy run,
    # because the value it should have compared against had been wiped. A
    # partially-read issue is an unread issue.
    missing = [field for field in ("state", "updated_at", "comments") if data.get(field) is None]
    if missing:
        return Observation(key=item.key, error=f"response lacked {', '.join(missing)}")
    state = str(data.get("state") or "")
    if not state:
        return Observation(key=item.key, error="response lacked a `state` field")
    return Observation(
        key=item.key,
        state=state,
        updated_at=str(data.get("updated_at") or ""),
        comments=_as_int(data.get("comments")),
        title=str(data.get("title") or ""),
    )


def observe_all(spec: ToolSpec) -> tuple[Observation, ...]:
    """Observe every watch item declared for this tool."""
    return tuple(observe(item, default_repo=spec.github) for item in spec.watch)


def _state_path(report_dir: Path, tool: str) -> Path:
    return report_dir / f"{tool}-{STATE_FILE}"


def load_previous(report_dir: Path, tool: str) -> dict[str, Observation]:
    """Last run's observations, keyed by watch-item key ({} on first ever run)."""
    path = _state_path(report_dir, tool)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Observation] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            out[str(key)] = Observation(
                key=str(key),
                state=str(value.get("state") or ""),
                updated_at=str(value.get("updated_at") or ""),
                comments=int(value.get("comments", 0) or 0),
                title=str(value.get("title") or ""),
            )
    return out


def save_current(report_dir: Path, tool: str, observations: tuple[Observation, ...]) -> Path:
    """Persist this run's observations so the next run can diff against them.

    An errored observation does not overwrite its entry — but its PRIOR value is
    carried forward rather than dropped. Dropping it would silently erase the
    baseline: the next run would see no previous value, treat the item as
    first-ever-observed, and report no change even if the issue had moved. A
    transient rate-limit would therefore hide exactly one real change, which is
    the worst possible moment to be blind.

    Items no longer in the config are pruned, so a removed watch entry does not
    linger forever.
    """
    path = _state_path(report_dir, tool)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = load_previous(report_dir, tool)

    payload: dict[str, dict[str, object]] = {}
    for o in observations:
        source = o if o.usable else previous.get(o.key)
        if source is None:  # errored on its very first observation — nothing to keep
            continue
        payload[o.key] = {k: v for k, v in asdict(source).items() if k not in {"key", "error"}}

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def changes(
    observations: tuple[Observation, ...], previous: dict[str, Observation]
) -> tuple[Observation, ...]:
    """Watch items whose watched fields moved since the previous run."""
    return tuple(o for o in observations if o.differs_from(previous.get(o.key)))


@dataclass(frozen=True)
class Reviewed:
    """One local watch item, asserted re-probed against a specific release (#486).

    `finding_digest` is required, not defaulted, deliberately: it is
    `finding_digest(<the watch item's CURRENT note>)` at record time, and
    `cleared_for` refuses to clear unless a fresh digest of the item's note
    matches it. That is what stops a clearance from surviving the finding it
    cleared being redefined — see the module docstring, B1. Making it optional
    would let a caller silently reconstruct the pre-fix, note-blind behaviour;
    a required field forces every construction site to state what it was
    reviewed against.
    """

    key: str
    version: str
    at: str
    finding_digest: str
    note: str = ""


def finding_digest(note: str) -> str:
    """Content fingerprint of a watch item's note — the identity `cleared_for` binds to.

    Same primitive `docs_reviewed` already uses for its own content baseline
    (`fetch.content_hash`, SHA-256), reused rather than re-invented: both are
    "does this content still match what a human reviewed" checks, just keyed
    differently (a URL there, a watch-item key here).
    """
    return content_hash(note)


class ReviewedStoreUnreadableError(Exception):
    """The reviewed-record store exists but could not be parsed.

    Raised only from the paths that are about to WRITE the store back —
    `record_reviewed` — never from `load_reviewed`, which must stay
    fail-closed-as-empty for the GATE (an unreadable store there correctly
    means "every local item is un-reviewed"). Merging into an empty dict and
    writing it back is that same fail-closed read turned destructive on a
    WRITE: it would silently discard every other tool's other clearances the
    moment the file was truncated or hand-edited badly (cold review, M2).
    """


def _reviewed_path(report_dir: Path, tool: str) -> Path:
    return report_dir / f"{tool}-{REVIEWED_FILE}"


def _read_reviewed_raw(report_dir: Path, tool: str) -> dict[str, object] | None:
    """The raw parsed JSON object at this tool's store, or `None` if genuinely absent.

    Raises `ReviewedStoreUnreadableError` when the file EXISTS but is not valid JSON
    or not a JSON object. Absence and unreadability are different facts on
    purpose: `load_reviewed` treats both as "nothing recorded" (fail-closed for
    the gate), but `record_reviewed` must tell them apart — a genuinely-first
    write is fine to create; a write over a file it could not parse is not.

    Catches `(OSError, ValueError)`, not `(OSError, json.JSONDecodeError)` —
    `json.JSONDecodeError` IS a `ValueError` subclass, so this already covered
    it, but a store containing non-UTF-8 bytes raises `UnicodeDecodeError` from
    `read_text`, which is ALSO a `ValueError` subclass and was NOT covered: it
    escaped uncaught and crashed both `load_reviewed` and `record_reviewed`,
    which is the exact corruption class this handler exists to turn into a
    controlled fail-closed / refusal instead of a traceback (cold review, MAJ-2).
    """
    path = _reviewed_path(report_dir, tool)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ReviewedStoreUnreadableError(f"{path}: {e}") from e
    if not isinstance(raw, dict):
        raise ReviewedStoreUnreadableError(f"{path}: not a JSON object")
    return raw


def _parse_reviewed_entries(raw: dict[str, object]) -> dict[str, Reviewed]:
    """Coerce a raw JSON object into `Reviewed` records, skipping unusable entries.

    An entry missing `version` is dropped (unusable by `cleared_for` anyway); a
    missing `finding_digest` parses to `""`, which can never equal a real
    `finding_digest(note)` (a SHA-256 hex digest, never empty) — so a
    pre-#486-shape record, or one hand-edited to drop the field, fails the
    identity check and reads as un-reviewed rather than as a wildcard match.
    """
    out: dict[str, Reviewed] = {}
    for key, value in raw.items():
        if isinstance(value, dict) and value.get("version"):
            out[str(key)] = Reviewed(
                key=str(key),
                version=str(value.get("version") or ""),
                at=str(value.get("at") or ""),
                finding_digest=str(value.get("finding_digest") or ""),
                note=str(value.get("note") or ""),
            )
    return out


def load_reviewed(report_dir: Path, tool: str) -> dict[str, Reviewed]:
    """Recorded re-probe claims for this tool's local items ({} on missing/unreadable).

    Same shape as `load_previous`: a missing or corrupt store reads as empty
    rather than raising. That is what makes this fail-closed — a store this
    function cannot read leaves every local item looking un-reviewed, never
    silently clears a gate it could not actually check. (`record_reviewed`
    below needs the OPPOSITE behaviour on unreadable — see `ReviewedStoreUnreadableError`.)
    """
    try:
        raw = _read_reviewed_raw(report_dir, tool)
    except ReviewedStoreUnreadableError:
        return {}
    return _parse_reviewed_entries(raw) if raw is not None else {}


def record_reviewed(report_dir: Path, tool: str, record: Reviewed) -> Path:
    """Persist one local watch item's re-probe claim, merged with what is already stored.

    Takes a whole `Reviewed` rather than its fields spread across the call
    site — `record.key` already carries everything the merge needs, so the
    caller builds one value instead of several loose parameters.

    Raises `ReviewedStoreUnreadableError` rather than overwriting a store it could
    not parse (M2): unlike `load_reviewed`, this function is about to WRITE the
    merged result back as the WHOLE file, so treating "could not read" as
    "empty" here would silently destroy every other recorded clearance the
    moment the file was corrupted — the fail-closed read direction turned
    destructive on the write direction. A genuinely first-ever write (no file
    yet) is unaffected; only an EXISTING, unparsable file refuses.

    Deliberately does NOT prune (cold review, MAJ-1). An earlier cut folded a
    `valid_keys` parameter in here and pruned every stored key absent from it
    as a side effect of recording — automatically, silently, on every ordinary
    call. `config._watch_items` fails SOFT (an entry missing `ref` is silently
    skipped, pre-existing and out of scope here), so "absent from one
    `config.load()`" is not proof a watch item was genuinely REMOVED; it may be
    a parse that could not complete. That deleted a sibling item's clearance —
    a human assertion nothing can re-derive, unlike `save_current`'s
    network-re-fetched observations, which is why that precedent never applied
    here — on nothing more than a config typo three lines away, with no
    message. Recording a clearance and pruning stale ones are now two
    functions with two different risk profiles: this one is never destructive;
    `prune_reviewed` below is, and can only run when a caller deliberately
    calls it.

    Never writes to `currency.toml` — the claim is engine state, keyed like every
    other per-tool store under the report root, not repo config a human hand-authors
    (this repo's pins/config move by their owning tool, and a programmatic edit to a
    hand-authored TOML has already been measured here to eat the comment above the
    key it touches).
    """
    path = _reviewed_path(report_dir, tool)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _read_reviewed_raw(report_dir, tool)
    current = _parse_reviewed_entries(raw) if raw is not None else {}
    current[record.key] = record
    payload: dict[str, dict[str, object]] = {
        k: {kk: vv for kk, vv in asdict(v).items() if kk != "key"} for k, v in current.items()
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def prune_reviewed(
    report_dir: Path, tool: str, valid_keys: Iterable[str]
) -> tuple[Path, tuple[str, ...]]:
    """Remove stored clearances whose key is not in `valid_keys`; returns (path, removed).

    The ONLY place pruning happens (cold review, MAJ-1) — never as a side effect
    of `record_reviewed`. This function still trusts whatever `valid_keys` it is
    given; it does not and cannot know whether an absence means "genuinely
    removed" or "this run's config parse could not complete" — that judgment
    belongs entirely to the caller, which is why `run.prune_reviewed` is its own
    command, requiring an explicit `--tool` and never invoked as a side effect
    of recording a clearance.

    Raises `ReviewedStoreUnreadableError` on an existing-but-unparsable store,
    for the same M2 reason `record_reviewed` does: refusing to write over data
    it could not read, rather than treating "unreadable" as "empty" and
    silently discarding every clearance the store held.

    Returns `removed = ()` and writes NOTHING when there is nothing to prune —
    a no-op call must not touch the file's mtime or rewrite it byte-identical.
    """
    path = _reviewed_path(report_dir, tool)
    raw = _read_reviewed_raw(report_dir, tool)
    current = _parse_reviewed_entries(raw) if raw is not None else {}
    keep = frozenset(valid_keys)
    removed = tuple(sorted(k for k in current if k not in keep))
    if not removed:
        return path, ()
    kept = {k: v for k, v in current.items() if k in keep}
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, dict[str, object]] = {
        k: {kk: vv for kk, vv in asdict(v).items() if kk != "key"} for k, v in kept.items()
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, removed


@dataclass(frozen=True)
class ClearanceCheck:
    """The full two-axis verdict on one clearance check — not just pass/fail.

    `cleared_for` collapses this to a single bool for `_gate_local`, which only
    ever needs to know whether to block. `report._reviewed_cell` needs the
    REASON: rendering a note-mismatch identically to a version-mismatch (both
    as bare `STALE @ <version> — target is <target>`) hid exactly the
    distinction B1 exists to draw — a redefined finding read as ordinary
    version staleness (cold review, MAJ-3).
    """

    version_matches: bool
    note_matches: bool

    @property
    def cleared(self) -> bool:
        """Both axes agree — the bool `cleared_for` collapses this to."""
        return self.version_matches and self.note_matches


def check_clearance(
    reviewed: dict[str, Reviewed], key: str, target: str, *, current_note: str
) -> ClearanceCheck:
    """The full two-axis verdict — see `ClearanceCheck` and `cleared_for`.

    TWO axes, both required. `current_note` is keyword-ONLY with NO default
    (cold review, MIN-1) — a defaulted `""` let a caller that forgot to pass it
    silently reconstruct the exact pre-B1, note-blind behaviour for any item
    with `finding_digest(current_note="")` on file, which is a real, reachable
    stored shape (an item declared with no `note` at all). Both production call
    sites (`decide._gate_local`, `report._watch_table`) already pass it; making
    it required turns a future omission into an immediate `TypeError` instead
    of a silent regression.

    Fail-closed by construction on the version axis, and deliberately does not
    lean on `same_release`'s documented fallback for an unparsable string (that
    fallback's behaviour on an EMPTY or unparsable version was never read for
    this change): both `record.version` and `target` must parse as a `Version`
    before `same_release` is even consulted — `and` short-circuits, so an
    unparsable side never reaches `same_release` at all. A record at "1.56.0"
    must not clear a target of "1.56.1" — that comparison is the entire reason
    this exists instead of the prose note it replaces.
    """
    record = reviewed.get(key)
    if record is None or not record.version or not target:
        return ClearanceCheck(version_matches=False, note_matches=False)
    parses = Version.parse(record.version) is not None and Version.parse(target) is not None
    return ClearanceCheck(
        version_matches=parses and same_release(record.version, target),
        note_matches=record.finding_digest == finding_digest(current_note),
    )


def cleared_for(reviewed: dict[str, Reviewed], key: str, target: str, *, current_note: str) -> bool:
    """Whether `key`'s recorded re-probe covers `target` AND still describes the same finding.

    The bool the GATE consumes (`decide._gate_local`) — see `check_clearance`
    for the two-axis detail the REPORT consumes, and for why `current_note` has
    no default.
    """
    return check_clearance(reviewed, key, target, current_note=current_note).cleared
