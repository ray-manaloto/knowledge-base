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
shape here, now FOUR states: READY / BLOCKED / CHAIN COMPLETE / COULD NOT ASK,
each naming itself on its own first line so `/clear-prep` can quote the block
verbatim without deciding which state it is looking at.

NEVER SKIP A BLOCKED TICKET TO REACH A LATER ONE — but DO keep scanning past a
blocked entry, or a CLOSED one, to find the first one that IS ready. Those
sound like the same rule and are not: the ordered walk in :func:`resolve` skips
over blocked entries AND entries whose own tracker state is CLOSED, looking for
the first ready one (an earlier blocked or closed entry never suppresses a
later ready one); what it never does is report some OTHER entry, chosen by
proximity-to-ready or any other heuristic, once the walk concludes NOTHING is
ready. In that case the answer is always the first entry whose own state is
not CLOSED, because if THAT entry were ready the walk would already have
returned it. When EVERY entry is CLOSED there is no such entry — that is CHAIN
COMPLETE, not BLOCKED: "nothing is ready" and "nothing is left to do" are
different sentences too, and collapsing them would report a finished chain as
stuck forever.

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
    """The first non-CLOSED ticket whose blockers are all closed (or has none).

    `stale` names every entry the walk skipped on the way here because ITS OWN
    tracker state was CLOSED — advisory, rendered below the READY line, never
    a reason to withhold the answer.
    """

    issue: int
    title: str
    stale: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Blocked:
    """No ticket is ready; this is the first non-CLOSED one, and what's still open.

    `stale` is the same advisory as :class:`Ready`'s — every entry skipped
    because its own state was CLOSED, encountered anywhere in the walk that
    produced this result.
    """

    issue: int
    title: str
    open_blockers: tuple[IssueInfo, ...]
    stale: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ChainComplete:
    """Every entry in the chain is CLOSED. Not a failure — the chain finished.

    Distinct from :class:`Blocked` on purpose: "no ticket is ready yet" and
    "there is no ticket left" are different sentences, and reporting the second
    as the first would print a finished chain as permanently stuck.
    """


@dataclass(frozen=True, slots=True)
class CouldNotAsk:
    """The tracker lookup could not be trusted. Never rendered as "nothing ready"."""

    detail: str


Outcome = Ready | Blocked | ChainComplete | CouldNotAsk


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


def resolve(tickets: tuple[Ticket, ...], repo_root: Path) -> Outcome:
    """Walk the chain in file order; the FILE decides ordering, the TRACKER decides state.

    Every ticket's OWN issue number enters the lookup alongside its blockers' —
    :data:`needed` can never be empty once `tickets` is non-empty (which
    `read_chain` already guarantees), so a lookup always runs. That is what lets
    the walk below skip an entry whose own tracker state is CLOSED, rather than
    trusting the chain file to have been kept in sync with the tracker.
    """
    needed = sorted({t.issue for t in tickets} | {b for t in tickets for b in t.blockers})
    alias_to_number = _aliases(needed)
    rc, out = _lookup(alias_to_number, repo_root)
    lookup = _parse_lookup(rc, out, alias_to_number)
    if lookup.states is None:
        return CouldNotAsk(lookup.detail)
    states = lookup.states

    stale: list[int] = []
    first_open: Ticket | None = None
    for ticket in tickets:
        if states[ticket.issue].state == "CLOSED":
            stale.append(ticket.issue)
            continue
        if first_open is None:
            first_open = ticket
        open_blockers = tuple(states[b] for b in ticket.blockers if states[b].state != "CLOSED")
        if not open_blockers:
            return Ready(ticket.issue, ticket.title, stale=tuple(stale))

    if first_open is None:
        return ChainComplete()

    # Nothing was ready: the loop above would already have returned the first
    # non-closed entry whose blockers are all closed, so `first_open` is
    # provably blocked.
    open_blockers = tuple(states[b] for b in first_open.blockers if states[b].state != "CLOSED")
    return Blocked(first_open.issue, first_open.title, open_blockers, stale=tuple(stale))


def _stale_lines(stale: tuple[int, ...], chain_path: Path) -> list[str]:
    """Advisory lines for entries the walk skipped because their own state was CLOSED."""
    return [f"stale: #{n} is CLOSED — remove it from {chain_path}" for n in stale]


def render(outcome: Outcome, chain_path: Path) -> str:
    """The paste-ready block. Each state names itself on its first line."""
    if isinstance(outcome, Ready):
        lines = [f"READY — #{outcome.issue} {outcome.title}", f"chain file: {chain_path}"]
        lines.extend(_stale_lines(outcome.stale, chain_path))
        return "\n".join(lines)
    if isinstance(outcome, Blocked):
        lines = [f"BLOCKED — #{outcome.issue} {outcome.title}", "open blockers:"]
        lines.extend(f"  - #{b.number} {b.title}" for b in outcome.open_blockers)
        lines.extend(_stale_lines(outcome.stale, chain_path))
        return "\n".join(lines)
    if isinstance(outcome, ChainComplete):
        return (
            f"CHAIN COMPLETE — every entry in {chain_path} is closed; "
            "remove them and add the next tickets"
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
    """`kb-setup next-ticket` — 0 for any of the three states, 2 on a bad request.

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
