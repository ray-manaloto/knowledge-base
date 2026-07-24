"""Steps 2 and 3 — is there a newer version, and what do its release notes say?

Deliberately split from judgment: this module *fetches*, it never decides. The
adopt/hold call is `decide.py`'s (mechanically, for the unambiguous case) or the
skill's (via the interview, for everything else).

Two upstreams are consulted because they disagree, and the disagreement matters:
mise installs from **PyPI**, while release notes live on **GitHub**. On
2026-07-23 graphify had `v1.0.0` tagged on GitHub while PyPI's latest was
0.9.25 — tracking the newest tag would have pinned a version mise cannot
install. Every check here treats PyPI as the installable truth and GitHub as the
narrative.
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
    """What upstream currently offers, and whether we could read it at all."""

    pypi_latest: str = ""
    github_tag: str = ""
    notes: str = ""
    reachable: bool = True
    error: str = ""
    # Versions between the pin and `pypi_latest` whose notes could NOT be read.
    # A jump of several patches must not be judged on the newest release alone.
    unread_versions: tuple[str, ...] = ()

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


def latest_pypi(package: str) -> tuple[str, str]:
    """Latest version of `package` on PyPI, as (version, error).

    PyPI is the installable truth: mise's pipx backend resolves from here, so a
    version absent from PyPI cannot be pinned no matter what GitHub has tagged.
    """
    # HTTPSConnection rather than urlopen(url): the scheme is then a property of
    # the class, not of an interpolated string, so a package name can never steer
    # the request to `file:` or another scheme. Structural, not asserted.
    conn = http.client.HTTPSConnection(_PYPI_HOST, timeout=_TIMEOUT_S)
    try:
        conn.request("GET", f"/pypi/{quote(package, safe='')}/json")
        resp = conn.getresponse()
        if resp.status != HTTPStatus.OK:
            return "", f"pypi returned HTTP {resp.status} for {package}"
        data = json.loads(resp.read())
    except (OSError, TimeoutError, json.JSONDecodeError) as e:
        return "", f"pypi lookup failed: {e}"
    finally:
        conn.close()
    if not isinstance(data, dict):
        return "", "pypi returned an unexpected payload"
    info = data.get("info", {})
    version = str(info.get("version") or "") if isinstance(info, dict) else ""
    return version, "" if version else "pypi returned no version"


def pypi_versions(package: str) -> tuple[str, ...]:
    """Every version PyPI lists for `package` (unordered, "" on failure).

    Needed to know which releases sit BETWEEN the pin and the latest: the engine
    must not judge a multi-patch jump on the newest release's notes alone.
    """
    conn = http.client.HTTPSConnection(_PYPI_HOST, timeout=_TIMEOUT_S)
    try:
        conn.request("GET", f"/pypi/{quote(package, safe='')}/json")
        resp = conn.getresponse()
        if resp.status != HTTPStatus.OK:
            return ()
        data = json.loads(resp.read())
    except OSError, TimeoutError, json.JSONDecodeError:
        return ()
    finally:
        conn.close()
    releases = data.get("releases") if isinstance(data, dict) else None
    return tuple(str(v) for v in releases) if isinstance(releases, dict) else ()


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


def probe(*, pypi: str, github: str, current: str) -> UpstreamStatus:
    """Fetch the upstream picture for one tool: every release we would be adopting.

    Returns `reachable=False` rather than raising when the network or `gh` is
    unavailable, so an offline run reports "could not check" instead of
    manufacturing a finding.

    Crucially this collects notes for EVERY version between the pin and the
    latest, not just the newest. The patch gate accepts any distance within the
    patch slot, so `0.9.25 -> 0.9.28` is auto-apply-eligible — and reading only
    0.9.28's body would wave through a breaking change announced in 0.9.26.
    """
    if not pypi:
        return UpstreamStatus(reachable=False, error="no `pypi` name configured for this tool")

    latest, err = latest_pypi(pypi)
    if err:
        return UpstreamStatus(reachable=False, error=err)
    if latest == current or not github:
        return UpstreamStatus(pypi_latest=latest)

    pending = versions_between(pypi_versions(pypi), current, latest) or (latest,)
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
        pypi_latest=latest,
        github_tag=newest_tag,
        notes="\n\n".join(bodies),
        reachable=True,
        error=last_error,
        unread_versions=tuple(unread),
    )
