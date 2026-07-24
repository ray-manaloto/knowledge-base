"""Steps 2 and 3 — is there a newer version, and what do its release notes say?

Deliberately split from judgment: this module *fetches*, it never decides. The
adopt/hold call is `decide.py`'s (mechanically, for the unambiguous case) or the
skill's (via the interview, for everything else).

THREE version sources, picked in `_resolve_source`:

* **PyPI** — the installable truth for pip/pipx tools (graphify). mise installs
  from PyPI, so a version tagged on GitHub but absent from PyPI cannot be pinned:
  on 2026-07-23 graphify had `v1.0.0` tagged while PyPI's latest was 0.9.25.
  PyPI wins whenever a package name is declared.
* **GitHub releases** — for tools that ship on GitHub, not PyPI (mise, hk). The
  latest STABLE release by version order, never `/releases/latest` (which orders
  by publish time and points at a backport).
* **none** — a presence-only tool (ffmpeg) with no version to chase. Not an
  error and not an ambiguity; step 1 still checks it resolves.

Release NOTES always come from GitHub when a repo is declared — PyPI carries no
changelog — so PyPI is the installable truth and GitHub is the narrative even
when GitHub is not the version source.
"""

from __future__ import annotations

import http.client
import json
import re
import subprocess
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import quote

_TIMEOUT_S = 20.0
_PYPI_HOST = "pypi.org"

# Phrases that make a release note non-routine. A hit forces the interview rather
# than an automatic bump. Matched against a NORMALIZED body (see `_normalize`),
# because release notes in the wild decorate these phrases: `**BREAKING**`,
# `BREAKING-CHANGE:`, `### Breaking changes`. A plain substring scan over the raw
# body caught the first spelling and waved the others through.
BREAKING_MARKERS = (
    "breaking",
    "backwards incompatible",
    "backward incompatible",
    "incompatible change",
    "removed support",
    "no longer supported",
    "deprecated",
    "deprecation",
    "migration required",
)

# Conventional Commits marks a breaking change with `!` before the colon:
# `feat!:`, `refactor(api)!:`. No keyword appears, so only a pattern can catch it.
_BANG_RE = re.compile(r"^\s*\w+(\([^)]*\))?!\s*:", re.MULTILINE)

# Phrases that mark a note line as ANNOUNCING A FEATURE — the "should we adopt
# this?" signal (step 3). Unlike the breaking markers these never block a bump;
# they only surface a line to the interview so a human can decide whether the new
# capability is worth a config change. Matched against a raw (not decoration-
# stripped) line so `feat:` / `feat(x):` are caught by the anchored pattern below
# and prose like "you can now" by substring.
_FEATURE_PHRASES = (
    "you can now",
    "now supports",
    "now support",
    "new option",
    "new flag",
    "new command",
    "new subcommand",
    "adds support",
    "added support",
    "introduces",
    "introduce ",
)
# Conventional-commits `feat:` / `feat(scope):` at the start of a line.
_FEAT_RE = re.compile(r"^\s*[-*]?\s*feat(\([^)]*\))?\s*:", re.IGNORECASE | re.MULTILINE)
_MAX_FEATURE_LINES = 12

# Markdown emphasis and the hyphen/underscore variants are decoration, not
# meaning. Collapsing them lets ONE marker cover every spelling.
_DECORATION = str.maketrans({"*": " ", "_": " ", "-": " ", "`": " "})


def _normalize(body: str) -> str:
    """Lower-case the body and strip the decoration that hides a marker."""
    return " ".join(body.lower().translate(_DECORATION).split())


@dataclass(frozen=True)
class Version:
    """A parsed dotted version, comparable and classifiable by bump size."""

    raw: str
    parts: tuple[int, ...]

    @classmethod
    def parse(cls, raw: str) -> Version | None:
        """Parse `1.2.3` / `v1.2.3`; returns None for anything non-numeric."""
        cleaned = raw.strip().lstrip("v")
        if not cleaned:
            return None
        chunks = cleaned.split(".")
        try:
            parts = tuple(int(c) for c in chunks)
        except ValueError:
            return None
        return cls(raw=raw, parts=parts)

    def is_patch_bump_from(self, other: Version) -> bool:
        """True when only the third component moved (0.9.25 -> 0.9.26).

        Pre-1.0 projects use the MINOR slot as their breaking channel, so
        0.9.x -> 0.10.0 is deliberately NOT a patch bump here.

        The "is greater" half delegates to `__gt__` so the two comparisons cannot
        disagree. Comparing `self.parts > other.parts` directly did disagree:
        `1.2 -> 1.2.0` is the SAME version, but the raw tuples `(1, 2, 0) > (1, 2)`
        made it look like a patch bump, which would auto-apply a no-op upgrade.
        """
        return self.parts[:2] == other.parts[:2] and self > other

    def __gt__(self, other: Version) -> bool:
        """Compare numerically, padding the shorter version with zeros."""
        width = max(len(self.parts), len(other.parts))
        return self._padded(width) > other._padded(width)

    def _padded(self, width: int) -> tuple[int, ...]:
        return self.parts + (0,) * (width - len(self.parts))


@dataclass(frozen=True)
class UpstreamStatus:
    """What upstream currently offers, and whether we could read it at all.

    THREE states, not two — the distinction is safety-critical:

    * `source == "none"` — the tool declares no upstream to chase (ffmpeg is
      presence-tracked, not version-tracked). This is NOT an ambiguity: there is
      simply no bump channel, and `decide` must not manufacture a question from
      it. The old two-state model returned `reachable=False` here, so every run
      of such a tool produced a permanent "upstream could not be checked".
    * `source != "none"` and `reachable is False` — configured, but this run
      could not read it. Fail closed: this IS an ambiguity.
    * `source != "none"` and `reachable is True` — read successfully.
    """

    latest: str = ""
    github_tag: str = ""
    notes: str = ""
    source: str = "pypi"  # "pypi" | "github" | "none"
    reachable: bool = True
    error: str = ""
    # Versions between the pin and `latest` whose notes could NOT be read.
    # A jump of several patches must not be judged on the newest release alone.
    unread_versions: tuple[str, ...] = ()

    @property
    def tracked(self) -> bool:
        """Whether this tool has an upstream version to chase at all."""
        return self.source != "none"

    @property
    def markers(self) -> tuple[str, ...]:
        """Breaking-change markers present in the release notes.

        The gate's job is to ROUTE TO A HUMAN, not to classify precisely, so this
        errs toward matching: a false stop costs one question, a false pass costs
        an unreviewed unattended upgrade.
        """
        body = _normalize(self.notes)
        found = [m for m in BREAKING_MARKERS if m in body]
        if _BANG_RE.search(self.notes):
            found.append("conventional-commits `!`")
        return tuple(found)

    @property
    def feature_highlights(self) -> tuple[str, ...]:
        """Note lines announcing a NEW capability worth a look — step 3's other half.

        Purely advisory: these never gate a bump (that is `markers`' job). They
        exist so "should we adopt this?" reaches the human even on a clean bump
        that no breaking marker stopped — the release-note review Ray asked for.
        A line qualifies via a `feat:` prefix or an adoption phrase; the raw line
        is returned (trimmed of list bullets) so the reader sees the real wording,
        capped so a huge changelog does not flood the interview.
        """
        highlights: list[str] = []
        for raw in self.notes.splitlines():
            line = raw.strip().lstrip("-*").strip()
            if not line:
                continue
            low = line.lower()
            if _FEAT_RE.match(raw) or any(p in low for p in _FEATURE_PHRASES):
                highlights.append(line)
            if len(highlights) >= _MAX_FEATURE_LINES:
                break
        return tuple(highlights)


def _pypi_json(package: str) -> tuple[dict[str, object], str]:
    """One `GET /pypi/<package>/json`, as (payload, error).

    Both the latest version and the full release list live in this single
    document, and `probe()` needs both — so fetching it once per call site meant
    two identical round-trips per run for one payload.

    HTTPSConnection rather than urlopen(url): the scheme is then a property of
    the class, not of an interpolated string, so a package name can never steer
    the request to `file:` or another scheme. Structural, not asserted.
    """
    conn = http.client.HTTPSConnection(_PYPI_HOST, timeout=_TIMEOUT_S)
    try:
        conn.request("GET", f"/pypi/{quote(package, safe='')}/json")
        resp = conn.getresponse()
        if resp.status != HTTPStatus.OK:
            return {}, f"pypi returned HTTP {resp.status} for {package}"
        data = json.loads(resp.read())
    except (OSError, TimeoutError, json.JSONDecodeError) as e:
        return {}, f"pypi lookup failed: {e}"
    finally:
        conn.close()
    if not isinstance(data, dict):
        return {}, "pypi returned an unexpected payload"
    return data, ""


def latest_version(payload: dict[str, object]) -> tuple[str, str]:
    """Latest version from a PyPI payload, as (version, error).

    PyPI is the installable truth: mise's pipx backend resolves from here, so a
    version absent from PyPI cannot be pinned no matter what GitHub has tagged.
    """
    info = payload.get("info", {})
    version = str(info.get("version") or "") if isinstance(info, dict) else ""
    return version, "" if version else "pypi returned no version"


def all_versions(payload: dict[str, object]) -> tuple[str, ...]:
    """Every version a PyPI payload lists (unordered, empty when absent).

    Needed to know which releases sit BETWEEN the pin and the latest: the engine
    must not judge a multi-patch jump on the newest release's notes alone.
    """
    releases = payload.get("releases")
    return tuple(str(v) for v in releases) if isinstance(releases, dict) else ()


def latest_pypi(package: str) -> tuple[str, str]:
    """Fetch-and-read convenience for a single latest-version lookup."""
    payload, err = _pypi_json(package)
    return ("", err) if err else latest_version(payload)


def versions_between(all_versions: tuple[str, ...], current: str, latest: str) -> tuple[str, ...]:
    """Versions strictly after `current` and up to `latest`, oldest first."""
    cur, top = Version.parse(current), Version.parse(latest)
    if cur is None or top is None:
        return ()
    picked = [
        v
        for v in (Version.parse(raw) for raw in all_versions)
        if v is not None and v > cur and not v > top
    ]
    return tuple(v.raw for v in sorted(picked, key=lambda v: v.parts))


def _gh_api(path: str) -> tuple[dict[str, object], str]:
    """One authenticated `gh api` call, returning (payload, error).

    `gh` rather than a raw request so the user's existing auth and rate limit
    apply; a missing/unauthenticated `gh` degrades to an error string, never an
    exception, because an unreachable upstream must read as SKIP and not as a
    finding about the tool.
    """
    try:
        res = subprocess.run(
            ["gh", "api", path],
            capture_output=True,
            text=True,
            check=False,
            timeout=_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {}, f"gh api {path} failed: {e}"
    if res.returncode != 0:
        return {}, f"gh api {path} exited {res.returncode}: {res.stderr.strip()[:200]}"
    try:
        payload = json.loads(res.stdout or "{}")
    except json.JSONDecodeError as e:
        return {}, f"gh api {path} returned non-JSON: {e}"
    return payload if isinstance(payload, dict) else {}, ""


def _gh_api_list(path: str) -> tuple[list[object], str]:
    """One `gh api` call that returns a JSON array, as (items, error).

    Separate from `_gh_api` because the releases endpoint returns a list, and a
    list arriving where a dict is expected must read as "empty + error", never as
    an exception that a caller might mistake for "no releases".
    """
    try:
        res = subprocess.run(
            ["gh", "api", path],
            capture_output=True,
            text=True,
            check=False,
            timeout=_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return [], f"gh api {path} failed: {e}"
    if res.returncode != 0:
        return [], f"gh api {path} exited {res.returncode}: {res.stderr.strip()[:200]}"
    try:
        payload = json.loads(res.stdout or "[]")
    except json.JSONDecodeError as e:
        return [], f"gh api {path} returned non-JSON: {e}"
    return payload if isinstance(payload, list) else [], ""


def github_versions(repo: str) -> tuple[str, tuple[str, ...], str]:
    """Latest stable release version and every release version, as (latest, all, err).

    The version source for tools that ship on GitHub but not PyPI — mise and hk,
    which is what makes `currency.toml`'s "same shape, no engine change" claim
    true rather than aspirational.

    "Latest" is the greatest by VERSION order among non-draft, non-prerelease
    releases — deliberately NOT `/releases/latest`, which GitHub orders by
    publish TIME and will therefore point at a backport patch to an older line
    the day one is published. Draft and prerelease releases are excluded so a
    release-candidate never auto-applies. Fail closed: any read error yields
    `("", (), error)` so `probe` reports unreachable rather than inventing a
    version.
    """
    items, err = _gh_api_list(f"repos/{repo}/releases?per_page=100")
    if err:
        return "", (), err
    stable: list[Version] = []
    raw: list[str] = []
    for item in items:
        if not isinstance(item, dict) or item.get("draft") or item.get("prerelease"):
            continue
        tag = str(item.get("tag_name") or "")
        parsed = Version.parse(tag)
        if parsed is not None:
            stable.append(parsed)
            raw.append(tag)
    if not stable:
        return "", (), f"no stable, version-shaped releases found for {repo}"
    return max(stable).raw, tuple(raw), ""


def release_for_tag(repo: str, tag: str) -> tuple[str, str, str]:
    """GitHub release for `tag`, as (tag_name, body, error).

    A tag with no release is not an error — plenty of projects tag without
    publishing notes — so the caller distinguishes "no notes" from "unreachable"
    by looking at the error string.
    """
    last_error = "no tag candidates tried"
    for candidate in (tag, f"v{tag}"):
        payload, err = _gh_api(f"repos/{repo}/releases/tags/{candidate}")
        if not err:
            # `... or <default>`, never `.get(k, default)`: GitHub returns the key
            # PRESENT with a JSON **null** for a release published without notes, so
            # the default never fires and `str(None)` yields the 4-char string "None"
            # — which is non-empty and therefore sails past the empty-notes gate.
            # Default to "", NEVER to `candidate`: `_gh_api` returns ({}, "")
            # for any exit-0 response whose JSON is not an object, so defaulting
            # to the tag we asked for INVENTS a release that was never confirmed
            # to exist — and a truthy `github_tag` then passes gate 2.
            tag_name = str(payload.get("tag_name") or "")
            if not tag_name:
                last_error = f"release payload for {candidate} had no tag_name"
                continue
            return tag_name, str(payload.get("body") or ""), ""
        last_error = err
    return "", "", last_error


def _resolve_source(pypi: str, github: str) -> tuple[str, str, tuple[str, ...], str]:
    """Pick the version source and read it: (source, latest, all_versions, error).

    PyPI wins when both are declared, because mise installs from PyPI — a version
    on GitHub but not PyPI cannot be pinned (graphify's v1.0.0 on 2026-07-23).
    GitHub releases are the source only when there is no PyPI package, which is
    the mise/hk case. `source == "none"` means neither is declared: a
    presence-only tool with nothing to chase, not an error.
    """
    if pypi:
        payload, err = _pypi_json(pypi)
        if err:
            return "pypi", "", (), err
        latest, err = latest_version(payload)
        return "pypi", latest, all_versions(payload), err
    if github:
        latest, versions, err = github_versions(github)
        return "github", latest, versions, err
    return "none", "", (), ""


def probe(*, pypi: str, github: str, current: str) -> UpstreamStatus:
    """Fetch the upstream picture for one tool: every release we would be adopting.

    Three shapes, matching `UpstreamStatus`'s three states:

    * neither `pypi` nor `github` declared — `source="none"`, tracked=False. A
      presence-only tool (ffmpeg). Not an error, not an ambiguity.
    * a source declared but unreadable — `reachable=False` with the error. Fail
      closed.
    * a source read — the latest, and notes for EVERY version between the pin and
      it (not just the newest: the patch gate accepts any distance within the
      patch slot, so `0.9.25 -> 0.9.28` is auto-apply-eligible, and reading only
      0.9.28's body would wave through a breaking change announced in 0.9.26).

    Release NOTES always come from GitHub when `github` is set, regardless of
    which source supplied the version list — PyPI carries no changelog.
    """
    source, latest, versions, err = _resolve_source(pypi, github)
    if source == "none":
        return UpstreamStatus(source="none")
    if err:
        return UpstreamStatus(source=source, reachable=False, error=err)
    if latest == current or not github:
        return UpstreamStatus(latest=latest, source=source)

    pending = versions_between(versions, current, latest) or (latest,)
    bodies: list[str] = []
    unread: list[str] = []
    newest_tag = ""
    last_error = ""
    for version in pending:
        tag, body, tag_err = release_for_tag(github, version)
        if tag_err or not tag:
            unread.append(version)
            last_error = tag_err or f"no release found for {version}"
            continue
        if version == latest:
            newest_tag = tag
        bodies.append(
            f"## {tag}\n\n{body.strip()}" if body.strip() else f"## {tag}\n\n_(no notes)_"
        )

    return UpstreamStatus(
        latest=latest,
        github_tag=newest_tag,
        notes="\n\n".join(bodies),
        source=source,
        reachable=True,
        error=last_error,
        unread_versions=tuple(unread),
    )
