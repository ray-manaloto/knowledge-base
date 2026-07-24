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
import subprocess
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import quote

_TIMEOUT_S = 20.0
_PYPI_HOST = "pypi.org"

# Words that make a release note non-routine. Matched case-insensitively against
# the note body; a hit forces the interview rather than an automatic bump.
BREAKING_MARKERS = (
    "breaking change",
    "breaking:",
    "backwards incompatible",
    "backward incompatible",
    "incompatible change",
    "removed support",
    "no longer supported",
    "deprecated",
    "deprecation",
    "migration required",
)


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
        """
        return self.parts[:2] == other.parts[:2] and self.parts > other.parts

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

    @property
    def markers(self) -> tuple[str, ...]:
        """Breaking-change markers present in the release notes."""
        body = self.notes.lower()
        return tuple(m for m in BREAKING_MARKERS if m in body)


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
    version = str(info.get("version", "")) if isinstance(info, dict) else ""
    return version, "" if version else "pypi returned no version"


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
            return str(payload.get("tag_name", candidate)), str(payload.get("body", "")), ""
        last_error = err
    return "", "", last_error


def probe(*, pypi: str, github: str, current: str) -> UpstreamStatus:
    """Fetch the upstream picture for one tool: latest release + its notes.

    Returns `reachable=False` rather than raising when the network or `gh` is
    unavailable, so an offline run reports "could not check" instead of
    manufacturing a finding.
    """
    if not pypi:
        return UpstreamStatus(reachable=False, error="no `pypi` name configured for this tool")

    latest, err = latest_pypi(pypi)
    if err:
        return UpstreamStatus(reachable=False, error=err)
    if latest == current or not github:
        return UpstreamStatus(pypi_latest=latest)

    tag, body, tag_err = release_for_tag(github, latest)
    return UpstreamStatus(
        pypi_latest=latest,
        github_tag=tag,
        notes=body,
        reachable=True,
        error=tag_err,
    )
