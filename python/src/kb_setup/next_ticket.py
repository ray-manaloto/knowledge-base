# Copyright (c) 2026 Raymond Manaloto
"""`kb-setup next-ticket` — name the next ready ticket, without a guess (#574).

WHAT THIS REPLACES. `/clear-prep`'s "next task" step asked the model to *infer*
one from open issues and the prior handoff — a paraphrase every session, and the
failure this whole round exists to fix: a plan that lives only in a session
scratchpad dies with the session. `docs/roadmap/aggregated-research-chain.toml`
is the tracked ORDERING (a ticket, in the order it should be worked, and which
issue numbers block it); the tracker is the tracked STATUS. Neither alone
answers "which ticket is ready now" — the file has no notion of CLOSED, and the
tracker has no notion of ordering.

A FAILED TRACKER LOOKUP IS ITS OWN STATE, reused from #144's decision
(`session_state.py:19-21`, literal at `:568`): "no ticket is ready" and "could
not ask the tracker" are different sentences, and rendering the second as the
first is exactly the false green `session_state` was built to remove. Same
shape here, now FOUR states: READY / BLOCKED / STALE CHAIN / COULD NOT ASK,
each naming itself on its own first line so `/clear-prep` can quote the block
verbatim without deciding which state it is looking at.

THE WALK KEEPS SCANNING PAST A BLOCKED ENTRY — an earlier blocked entry never
suppresses a later ready one; :func:`resolve`'s loop looks only at BLOCKER
states, in file order, and moves on to the next ticket whenever the current
one has an open blocker. What it NEVER does is report some OTHER entry once
the walk concludes nothing is ready: the fallback always names `tickets[0]`,
never a "closest to ready" pick. What changed here is narrower still: right
before the walk NAMES an entry — the `Ready` return, or the
`Blocked` fallback that reports `tickets[0]` — it checks that ONE entry's own
tracker state, in :func:`_name`. A CLOSED one is refused (STALE CHAIN) rather
than reported READY or BLOCKED. This is deliberately NOT a scan for every
closed entry in the file: `docs/roadmap/aggregated-research-chain.toml`'s
removal convention says a done ticket should already be gone from this file,
and a tool that quietly worked around a forgotten removal — by skipping the
stale entry and reporting the next one anyway — would be the thing most likely
to make that removal never happen. Refusing to name it is the enforcement the
convention needs, one removal-commit at a time; the NEXT run, after that
commit, is what catches the next one.

A SUCCESSFUL JSON PARSE IS NOT A SUCCESSFUL LOOKUP. Measured live against this
repo's own tracker (`gh` 2.98.0): a `gh api graphql` call naming an issue that
does not resolve (a bad number, or a PR number — `issue(number:)` does not
accept one) exits **non-zero** here, but that is not load-bearing, because a
future `gh` or a different partial-failure shape could hand back rc 0 with the
same carcass: parseable JSON, an `errors` array, and a `null` node for the
alias that failed. Checking only "did `json.loads` succeed" would ship a check
that cannot fail — so :func:`_parse_lookup` treats a non-zero rc, an unparsable
body, a present `errors` key, and a missing/`null` state for ANY requested
alias as four INDEPENDENT triggers of the same could-not-ask outcome, not one
derived from another.

WHY ONE `gh api graphql` CALL, ALIASED, RATHER THAN A `gh issue view` PER
TICKET. Confirmed live: a single call with one aliased `issue(number:)` field
per issue number returns state and title for all of them in one round trip —
and the title is the only way to report an OUT-OF-CHAIN blocker's title at all,
since the chain file only carries titles for its own entries. Two mechanics
that are easy to get backwards: a GraphQL alias cannot start with a digit (the
issue number), so aliases carry a letter prefix (:data:`_ALIAS_PREFIX`) and are
mapped back afterwards; and `{owner}`/`{repo}` placeholder substitution — which
resolves the current repository the same way `gh pr` subcommands do, so this
module never hardcodes `ray-manaloto/knowledge-base` — only fires on `-F`
(`--field`) values, not `-f` (`--raw-field`). Tried both live: `-f owner='{owner}'`
sends the seven literal characters `{owner}` to GitHub and gets `NOT_FOUND` for
a repository named that; `-F owner='{owner}'` resolves correctly. `gh api --help`
states the split but says nothing about which flag is required for which.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from kb_setup.result import Err, Ok, Result, exit_code

#: Bound on the `gh` call — a network round trip, matching `session_state._GH_TIMEOUT`.
_GH_TIMEOUT = 120

#: Where the ordering lives, relative to the repo root.
DEFAULT_CHAIN = Path("docs/roadmap/aggregated-research-chain.toml")

#: A GraphQL alias cannot start with a digit; issue numbers always would.
_ALIAS_PREFIX = "i"


@dataclass(frozen=True, slots=True)
class Ticket:
    """One `[[ticket]]` entry: an issue, its title, and what blocks it."""

    issue: int
    title: str
    blockers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class IssueInfo:
    """One resolved tracker issue — state and title, from the SAME lookup."""

    number: int
    state: str  # "OPEN" or "CLOSED" — see `_parse_lookup`, the one place it is checked
    title: str


@dataclass(frozen=True, slots=True)
class Ready:
    """The first ticket whose blockers are all closed (or has none)."""

    issue: int
    title: str


@dataclass(frozen=True, slots=True)
class Blocked:
    """No ticket is ready; this is the FIRST one, and what is still open on it."""

    issue: int
    title: str
    open_blockers: tuple[IssueInfo, ...]


@dataclass(frozen=True, slots=True)
class StaleChain:
    """The entry :func:`resolve` was about to name is itself CLOSED — refused.

    Checked ONLY for the one entry about to be named, never by scanning the
    rest of the chain for other closed entries — see :func:`_name`. This is
    the enforcement pressure behind the chain file's removal convention, not a
    replacement for it: the tool still never infers "done" on its own and
    still never removes the entry itself — it refuses to name it and stops.

    `after_removal` is a PREVIEW, not a skip: what a SECOND run would actually
    report once this entry is gone, per :func:`_preview_after_removal`, using
    the states already in hand (no second lookup). It may itself say "also
    CLOSED, remove it too" — the preview must agree with what the next run
    says, never promise an entry the next run would refuse. The refusal above
    is unchanged — this field only tells the reader what it is worth fixing.
    """

    issue: int
    title: str
    after_removal: str


@dataclass(frozen=True, slots=True)
class CouldNotAsk:
    """The tracker lookup could not be trusted. Never rendered as "nothing ready"."""

    detail: str


Outcome = Ready | Blocked | StaleChain | CouldNotAsk


def _parse_ticket(entry: object, index: int) -> Ticket | str:
    """One `[[ticket]]` entry, or a message naming what is wrong with it.

    Split out of :func:`read_chain` so each function stays under the
    house return-statement ceiling (PLR0911) — a real limit here, not a
    style nit: this is the validation an implementer would otherwise be
    tempted to collapse into one message that names nothing.
    """
    if not isinstance(entry, dict):
        return f"ticket entry {index} is not a table"
    issue = entry.get("issue")
    title = entry.get("title")
    blockers = entry.get("blockers", [])
    if isinstance(issue, bool) or not isinstance(issue, int):
        return f"ticket entry {index} has a non-integer `issue`"
    if not isinstance(title, str) or not title.strip():
        return f"issue #{issue} has no `title`"
    if not isinstance(blockers, list) or not all(
        isinstance(b, int) and not isinstance(b, bool) for b in blockers
    ):
        return f"issue #{issue} has a malformed `blockers` list"
    return Ticket(issue=issue, title=title, blockers=tuple(blockers))


def read_chain(path: Path) -> Result[tuple[Ticket, ...]]:
    """Parse the chain file.

    Any defect names `path` and is `Rc.BAD_REQUEST`. A missing/unreadable file
    and a syntactically-broken one share one branch — both are "this run
    cannot proceed", and `tomllib.TOMLDecodeError` is the house pattern
    (`arms.py:570`, `fetch.py:299`) for the parse half.
    """
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        return Err(f"{path}: {exc}")

    entries = raw.get("ticket")
    if not isinstance(entries, list) or not entries:
        return Err(f"{path}: no [[ticket]] entries")

    tickets: list[Ticket] = []
    for index, entry in enumerate(entries):
        parsed = _parse_ticket(entry, index)
        if isinstance(parsed, str):
            return Err(f"{path}: {parsed}")
        tickets.append(parsed)
    return Ok(tuple(tickets))


def _gh(args: list[str], repo_root: Path) -> tuple[int, str]:
    """Run a `gh` command; return `(rc, stdout+stderr)`.

    The named seam the tests substitute — matching `session_state._gh`'s shape
    exactly (`session_state.py:254-278`): merged stdout+stderr, so any stray
    text alongside the JSON breaks the parse, and a broken parse is
    could-not-ask, fail-closed by design.
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


def _aliases(numbers: list[int]) -> dict[str, int]:
    """Map a GraphQL alias to the issue number it stands for."""
    return {f"{_ALIAS_PREFIX}{n}": n for n in numbers}


def _build_query(alias_to_number: dict[str, int]) -> str:
    """The batched query: one aliased `issue(number:)` field per issue."""
    fields = "\n".join(
        f"    {alias}: issue(number: {number}) {{ number state title }}"
        for alias, number in alias_to_number.items()
    )
    return (
        "query($owner: String!, $repo: String!) {\n"
        "  repository(owner: $owner, name: $repo) {\n"
        f"{fields}\n"
        "  }\n"
        "}"
    )


def _lookup(alias_to_number: dict[str, int], repo_root: Path) -> tuple[int, str]:
    """Issue the ONE batched `gh api graphql` call. `{owner}`/`{repo}` need `-F`, not `-f`."""
    query = _build_query(alias_to_number)
    return _gh(
        ["api", "graphql", "-f", f"query={query}", "-F", "owner={owner}", "-F", "repo={repo}"],
        repo_root,
    )


@dataclass(frozen=True, slots=True)
class _Lookup:
    """Either every requested issue resolved, or none of them are trusted.

    No partial success: `resolve` needs a state for every blocker it will look
    at, and a lookup that resolved 20 of 21 aliases is still one this module
    cannot act on — the missing one might be the very one deciding readiness.
    """

    states: dict[int, IssueInfo] | None
    detail: str = ""


def _not_found_culprit(errors: object, alias_to_number: dict[str, int]) -> int | None:
    """The issue number behind a NOT_FOUND error, if the response names one.

    "Name the culprit": a generic could-not-ask sends the reader to check `gh`
    auth when the real defect is a number in the tracked chain file (a PR
    number, or a typo) — this is what turns that into a specific message.
    """
    if not isinstance(errors, list):
        return None
    for err in errors:
        if not isinstance(err, dict) or err.get("type") != "NOT_FOUND":
            continue
        path = err.get("path")
        if isinstance(path, list) and path and path[-1] in alias_to_number:
            return alias_to_number[path[-1]]
    return None


def _errors_detail(errors: object, alias_to_number: dict[str, int]) -> str | None:
    """`None` when there is nothing to report; a could-not-ask message otherwise.

    A NON-EMPTY `errors` array is its OWN could-not-ask trigger — checked
    before any per-alias state, never derived from one. An `errors` key that is
    absent, or present as an empty array, carries no error and falls through to
    the per-alias check below, which is what actually catches it if the lookup
    genuinely failed.
    """
    if not errors:
        return None
    culprit = _not_found_culprit(errors, alias_to_number)
    if culprit is not None:
        return f"issue #{culprit} was NOT_FOUND"
    return "gh reported an error resolving issue state"


def _resolve_states(data: object, alias_to_number: dict[str, int]) -> dict[int, IssueInfo] | str:
    """Every requested alias's state and title, or a message naming the first one that failed."""
    repository = data.get("repository") if isinstance(data, dict) else None
    if not isinstance(repository, dict):
        return "gh could not resolve the repository"

    states: dict[int, IssueInfo] = {}
    for alias, number in alias_to_number.items():
        node = repository.get(alias)
        state = node.get("state") if isinstance(node, dict) else None
        if state not in ("OPEN", "CLOSED"):
            return f"issue #{number} returned no state"
        title = node.get("title") if isinstance(node.get("title"), str) else ""
        states[number] = IssueInfo(number=number, state=state, title=title)
    return states


def _parse_lookup(rc: int, out: str, alias_to_number: dict[str, int]) -> _Lookup:
    """Classify a `gh api graphql` response.

    The four could-not-ask triggers are independent — see the module
    docstring's "a successful parse is not a successful lookup" paragraph.
    Checked in order: rc, parse, `errors`, then per-alias state.
    """
    if rc != 0:
        # Keep `out`, truncated, exactly as the sibling this module mirrors does
        # (`session_state.py:458`). rc != 0 is the MOST LIKELY real failure —
        # no network, expired auth, a rate limit, a timeout — and `_gh` merges
        # stderr into `out` precisely so the reason survives. Reporting only
        # "gh exited 1" throws away the one thing that tells an operator which
        # of those it was, and sends them to re-run it by hand to find out.
        return _Lookup(None, f"gh exited {rc}: {out.strip()[:200]}")
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        return _Lookup(None, "gh returned an unparsable response")
    if not isinstance(parsed, dict):
        return _Lookup(None, "gh returned an unparsable response")

    detail = _errors_detail(parsed.get("errors"), alias_to_number)
    if detail is not None:
        return _Lookup(None, detail)

    states = _resolve_states(parsed.get("data"), alias_to_number)
    if isinstance(states, str):
        return _Lookup(None, states)
    return _Lookup(states)


def _open_blockers(ticket: Ticket, states: dict[int, IssueInfo]) -> tuple[IssueInfo, ...]:
    """`ticket`'s blockers that are not (yet) CLOSED — the walk's own readiness rule.

    Factored out so :func:`resolve` and :func:`_preview_after_removal` apply the
    exact same rule rather than retyping the expression twice more.
    """
    return tuple(states[b] for b in ticket.blockers if states[b].state != "CLOSED")


def _preview_after_removal(
    tickets: tuple[Ticket, ...], removed: Ticket, states: dict[int, IssueInfo]
) -> str:
    """What a SECOND run of :func:`resolve` would actually report once `removed` is gone.

    Applies the exact same two rules :func:`_name` applies to the entry it
    names — first entry (file order, `removed` excluded) with no open
    blockers; CLOSED is refused, not reported — because that is what the next
    run does. `removed` must be excluded explicitly (not just relied on being
    CLOSED and therefore skipped below): once this function stops skipping
    CLOSED candidates, `removed` itself — always CLOSED, that is why it is
    `removed` — would otherwise be the first candidate found.

    A candidate that is ALSO CLOSED is named, not skipped past: an earlier
    version of this function chased past it to find a later OPEN entry, which
    made the preview promise something the next run would not agree with —
    `[#1 CLOSED, #2 CLOSED, #3 OPEN]` previewed "#3" after removing #1, but a
    real second run reports `STALE CHAIN — #2`, not #3. No second lookup: pure
    over the `states` dict `_name` already has.
    """
    for ticket in tickets:
        if ticket.issue == removed.issue:
            continue
        if _open_blockers(ticket, states):
            continue
        if states[ticket.issue].state == "CLOSED":
            return f"#{ticket.issue} {ticket.title} — also CLOSED, remove it too"
        return f"#{ticket.issue} {ticket.title}"
    return "nothing ready after cleanup"


def _name(
    ticket: Ticket,
    tickets: tuple[Ticket, ...],
    states: dict[int, IssueInfo],
    open_blockers: tuple[IssueInfo, ...],
) -> Outcome:
    """The outcome for naming `ticket` — refuses to name one the tracker says is CLOSED.

    Checked ONLY here, for the one entry :func:`resolve` is about to report —
    never by scanning the rest of the chain for other closed entries. That is
    deliberate laziness, not an oversight: the next run, after the commit that
    removes this entry, is what catches the next one. `tickets` is used only
    for the STALE CHAIN preview lookahead below — it plays no part in deciding
    which entry is being named.
    """
    if states[ticket.issue].state == "CLOSED":
        preview = _preview_after_removal(tickets, ticket, states)
        return StaleChain(ticket.issue, ticket.title, preview)
    if not open_blockers:
        return Ready(ticket.issue, ticket.title)
    return Blocked(ticket.issue, ticket.title, open_blockers)


def resolve(tickets: tuple[Ticket, ...], repo_root: Path) -> Outcome:
    """Walk the chain in file order; the FILE decides ordering, the TRACKER decides state.

    The walk itself looks only at BLOCKER states, exactly as before. Every
    ticket's OWN issue number still enters the lookup alongside its blockers' —
    :data:`needed` can never be empty once `tickets` is non-empty (which
    `read_chain` already guarantees) — because `resolve` cannot know in advance
    which entry it will end up naming, and a second lookup for just that one
    entry is exactly the partial-success shape :class:`_Lookup` forbids.
    """
    needed = sorted({t.issue for t in tickets} | {b for t in tickets for b in t.blockers})
    alias_to_number = _aliases(needed)
    rc, out = _lookup(alias_to_number, repo_root)
    lookup = _parse_lookup(rc, out, alias_to_number)
    if lookup.states is None:
        return CouldNotAsk(lookup.detail)
    states = lookup.states

    for ticket in tickets:
        open_blockers = _open_blockers(ticket, states)
        if not open_blockers:
            return _name(ticket, tickets, states, open_blockers)

    # Nothing was ready: the loop above would already have returned the first
    # entry whose blockers are all closed, so `tickets[0]` is provably blocked.
    first = tickets[0]
    open_blockers = _open_blockers(first, states)
    return _name(first, tickets, states, open_blockers)


def render(outcome: Outcome, chain_path: Path) -> str:
    """The paste-ready block. Each state names itself on its first line."""
    if isinstance(outcome, Ready):
        return f"READY — #{outcome.issue} {outcome.title}\nchain file: {chain_path}"
    if isinstance(outcome, Blocked):
        lines = [f"BLOCKED — #{outcome.issue} {outcome.title}", "open blockers:"]
        lines.extend(f"  - #{b.number} {b.title}" for b in outcome.open_blockers)
        return "\n".join(lines)
    if isinstance(outcome, StaleChain):
        return (
            f"STALE CHAIN — #{outcome.issue} {outcome.title} is CLOSED but still "
            f"listed in {chain_path}; remove it, then re-run\n"
            f"next after removal: {outcome.after_removal}"
        )
    return f"COULD NOT ASK — {outcome.detail}\nchain file: {chain_path} — re-derive once resolved"


def evaluate(chain_path: Path, repo_root: Path) -> Result[str]:
    """The boundary (§2 R5): read the chain, resolve it, render it — or say why not."""
    chain = read_chain(chain_path)
    if not isinstance(chain, Ok):
        return Err(chain.message)
    return Ok(render(resolve(chain.value, repo_root), chain_path))


def check_next_ticket(args: list[str], repo_root: Path) -> Result[str]:
    """`kb-setup next-ticket` takes no arguments; anything given is refused."""
    if args:
        return Err(f"takes no arguments, got {', '.join(args)}")
    return evaluate(repo_root / DEFAULT_CHAIN, repo_root)


def main(args: list[str], repo_root: Path) -> int:
    """`kb-setup next-ticket` — 0 for any of the four states, 2 on a bad request.

    Never non-zero for what it FINDS: BLOCKED and COULD NOT ASK are both
    successful reports, matching `session_state.main`'s reasoning exactly — a
    snapshot has no opinion to fail on.
    """
    result = check_next_ticket(args, repo_root)
    if not isinstance(result, Ok):
        print(f"kb-next-ticket: {result.message}", file=sys.stderr)
        return exit_code(result)
    print(result.value)
    return exit_code(result)
