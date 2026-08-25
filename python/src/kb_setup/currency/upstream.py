# Copyright (c) 2026 Raymond Manaloto
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
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import quote

from kb_setup.currency import _proc

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
    "can now",
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
    "graduates from experimental",
    "no longer requires",
)
# Conventional-commits `feat:` / `feat(scope):` at the start of a line.
_FEAT_RE = re.compile(r"^\s*[-*]?\s*feat(\([^)]*\))?\s*:", re.IGNORECASE | re.MULTILINE)
_MAX_FEATURE_LINES = 12

# A markdown section heading, at any depth (`## Added`, `### New features`).
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*?)\s*#*\s*$")
# A heading naming a RELEASE rather than a content section — `## v0.9.27`,
# `## 2026.7.16`, `## v1.0.0 — title`, `## 1.2.3 (2026-01-01)`. Matched against the
# NORMALISED heading, and requiring two numeric components so prose like
# `## 2 breaking changes` cannot pass.
#
# This boundary is what makes the format check per-release: without it, one
# release's recognised sections certified an entire multi-version jump.
_VERSION_TOKEN_RE = re.compile(r"^v?\d+\.\d+[\w.+]*")
# Keep-a-Changelog / GitHub-generated-notes section names whose bullets ARE
# features by construction. This is the detector's primary signal, and it exists
# because the phrase/`feat:` heuristics alone matched NOTHING on any real corpus
# this repo tracks: mise v2026.7.16 ships nine `## Added` bullets and scored 0,
# as did graphify 0.9.27-0.9.30 and claude-code 2.1.220 (control-armed
# 2026-07-29 — the same patterns DO fire on a synthetic `feat:` fixture, so the
# zero was the detector's shape, not an absence of features). The unit tests
# passed throughout, because every fixture was written in the one format the
# detector already understood.
_FEATURE_SECTIONS = frozenset(
    {"added", "features", "new features", "highlights", "new", "what's new"}
)
# Sections whose bullets are explicitly NOT new capabilities. Named rather than
# inferred so that recognising a body's FORMAT is separable from finding features
# in it — a fixes-only changelog is a confident zero, which is a different answer
# from "this body has no structure I understand". `new contributors` is here
# because it would otherwise prefix-match `new`.
_NON_FEATURE_SECTIONS = frozenset(
    {
        "fixed",
        "fixes",
        "bug fixes",
        "changed",
        "removed",
        "deprecated",
        "security",
        "documentation",
        "docs",
        "registry",
        "new contributors",
        "chore",
        "internal",
    }
)

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


def bare_version(value: str, prefix: str = "") -> str:
    """A git TAG (`v1.56.1`, `rust-v0.149.1`) reduced to the bare VERSION it names.

    One rule, one place, because the two spellings are genuinely different things
    and the engine writes BOTH: a `mise.toml` pin takes the bare version
    (`hk = "1.56.1"`), while a `sources/*.manifest` `ref` takes the tag verbatim
    (`ref = v1.56.1`). One resolved string cannot be correct for both targets, and
    #499 is what happens when it is used as though it were — `apply` wrote
    `hk = "v1.56.1"` and `mise ls hk` then reported that pin `(missing)`: nothing
    resolved, so `mise run lint` could not find hk for anyone who pulled the commit.

    The `v` survives that far because `Version.parse` keeps `raw` VERBATIM (`:159`)
    and cleans only its comparison key (`:151`), while `github_versions` returns
    `max(stable).raw` (`:544`) after stripping the declared `tag_prefix` and
    nothing else (`:538`). So a tool whose tags carry a bare `v` and which declares
    no `tag_prefix` — hk, agnix, fnox — carries the `v` all the way into the pin. A
    tool that DOES declare one (`codex` = `rust-v`, `firecrawl-cli` = `v`) never
    could, which is why this went unseen: the only two configured tools were the
    only two that could not exhibit it.

    The load-bearing property is that the prefix is stripped BY NAME and not
    guessed: `lstrip("v")` alone leaves `rust-v0.149.1` untouched (it does not
    start with `v`), so the prefix reaches a comparison against an installed
    `0.149.1` and reports drift on a pin that is exactly right — #245, which
    `sync.py` records at its own call site.

    The ORDER of the two reductions is NOT load-bearing, and an earlier draft of
    this docstring claimed it was. Armed and refuted: swapping them leaves every
    real input unchanged, because `lstrip("v")` cannot eat any character of a
    prefix that does not begin with `v`. It would matter only for a prefix like
    `vX-`, which no tracked tool has. Stated because the arm that caught it
    SURVIVED — the mutation was inert, and a surviving arm reads as coverage.
    """
    return value.removeprefix(prefix).lstrip("v")


def same_release(left: str, right: str) -> bool:
    """Do these two strings name the SAME release, decoration and padding aside?

    `v2.1.220` and `2.1.220` are one release; so are `1.2` and `1.2.0`. Raw `==`
    says otherwise on both, which is the bug: `probe()` fetched release notes for a
    "new" release we were already running, and `decide()` then ran the tag/marker/
    local gates against them and could surface a spurious "Adopt it?" about it.
    `_gate_patch` and `_has_upgrade` had already been moved onto parsed `Version`
    comparison for exactly this reason; these two call sites were left behind.
    (Cold lane, round 2.)

    NOT `Version.__eq__` — `Version` is a frozen dataclass carrying `raw`, so its
    generated equality compares the decoration this function exists to ignore.
    Unparsable on either side falls back to string equality: nothing better is
    available, and every caller already treats an unparsable version as an
    ambiguity a human must settle.
    """
    a, b = Version.parse(left), Version.parse(right)
    if a is None or b is None:
        return left == right
    return not (a > b or b > a)


def _is_version_heading(heading: str) -> bool:
    r"""Is this NORMALISED heading naming a release, rather than prose about one?

    `## v0.9.27`, `## 2026.7.16`, `## v1.0.0 — title`, `## 1.2.3 (2026-01-01)` and
    the Keep-a-Changelog `## 1.0.0 - 2026-01-01` are releases. `## 2 breaking
    changes` is not (the token needs two numeric components), and neither is
    `## 2.0 migration guide`.

    That last case is the round-2 fix. The predecessor was a lone
    `re.match(r"^v?\d+\.\d+", …)` — anchored only on the LEFT, so it asked the
    heading to *start* with a version and never asked what came after. A prose
    section headed `## 2.0 migration guide` therefore opened a new release span,
    splitting one release in two and letting the per-release `all(...)` mark a
    fully-readable release partially unrecognised.

    Deliberately a function rather than one cleverer regex: every right-anchored
    pattern tried here matched `0.9.30 hotfix` through BACKTRACKING (`\d+\.\d+`
    settling for `0.9`, leaving `.` to satisfy the punctuation branch), so the
    regex answered a different question than the one it appeared to ask. Splitting
    "read the version token" from "judge what follows it" removes the ambiguity.

    The accepted cost: a real heading with a bare one-word title (`## 0.9.30
    hotfix`, or `## v1.0.0-rc1` once `_normalize` has turned the hyphen into a
    space) reads as prose and merges into the previous release. Both directions
    are wrong somewhere; this one degrades to the coarser pre-round-1 grouping
    rather than to a false "could not tell", and GitHub's tag-only headings plus
    Keep-a-Changelog's dated form — the two shapes this repo actually meets — are
    both still recognised. (Cold lane, round 2.)
    """
    token = _VERSION_TOKEN_RE.match(heading)
    if token is None:
        return False
    rest = heading[token.end() :].strip()
    return not rest or not rest[0].isalpha()


def _release_spans(notes: str) -> list[list[str]]:
    """Split concatenated release notes into one line-list per release.

    A version heading is a RELEASE BOUNDARY rather than a content section, so it
    also stops the previous release's `## Added` from leaking onto the next
    release's bullets. The leading span (the preamble before the first version
    heading) is returned too, and is usually empty.
    """
    spans: list[list[str]] = []
    current: list[str] = []
    for raw in notes.splitlines():
        heading = _HEADING_RE.match(raw)
        if heading and _is_version_heading(_normalize(heading.group(1)).rstrip(":.")):
            spans.append(current)
            current = []
            continue
        current.append(raw)
    spans.append(current)
    return spans


def _scan_release(lines: list[str], already: int) -> tuple[list[str], int, bool, bool]:
    """Scan ONE release: `(highlights, dropped, recognised, had_content)`.

    `already` is how many highlights the caller has collected across earlier
    releases, so the display cap applies to the whole span rather than resetting
    per release — a four-release jump must not quietly return 4x the cap.
    """
    highlights: list[str] = []
    dropped = 0
    section = ""
    recognised = False
    had_content = False
    for raw in lines:
        heading = _HEADING_RE.match(raw)
        if heading:
            section = _normalize(heading.group(1)).rstrip(":.")
            had_content = True
            if section in _FEATURE_SECTIONS or section in _NON_FEATURE_SECTIONS:
                recognised = True
            continue
        line = raw.strip().lstrip("-*").strip()
        if not line:
            continue
        had_content = True
        phrased = any(p in line.lower() for p in _FEATURE_PHRASES)
        is_feat = bool(_FEAT_RE.match(raw))
        if is_feat or phrased:
            recognised = True
        if section in _NON_FEATURE_SECTIONS:
            continue
        bulleted_feature = raw.strip().startswith(("-", "*")) and section in _FEATURE_SECTIONS
        if bulleted_feature or is_feat or phrased:
            if already + len(highlights) >= _MAX_FEATURE_LINES:
                dropped += 1
                continue
            highlights.append(line)
    return highlights, dropped, recognised, had_content


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

    def _scan_features(self) -> tuple[tuple[str, ...], int, bool]:
        """Walk the notes: `(highlights, dropped, format_recognised)`.

        Section state is what makes this reliable. A bullet under `## Added` is a
        feature because of WHERE it sits, which needs no phrase to match — and
        phrases are suppressed under a known non-feature section so a fix reading
        "no longer requires X" does not arrive labelled as a capability.

        `format_recognised` exists so an empty result stays TWO answers rather
        than one: a fixes-only changelog is a confident "no features", while a
        body whose structure we do not understand is "could not tell". Collapsing
        those is the same absence-of-evidence trap `UpstreamStatus`'s three-state
        docstring above already avoids for reachability.

        It is computed PER RELEASE. `probe()` concatenates the notes of every
        release in a multi-patch jump (graphify 0.9.26 -> 0.9.30 arrives as four
        bodies in one string), so one flag over the whole string let a single
        `## Added` certify the entire span: a later release written in a style this
        scan does not understand, with real features in it, was reported as a
        confident zero. Recognised means EVERY release carrying content was
        recognised. (Cold lane.)
        """
        highlights: list[str] = []
        dropped = 0
        per_release: list[bool] = []
        for lines in _release_spans(self.notes):
            found, cut, recognised, had_content = _scan_release(lines, len(highlights))
            highlights.extend(found)
            dropped += cut
            # Spans with nothing in them are not evidence either way. The preamble
            # before the first version heading is one, and counting it would make
            # every sectioned changelog unrecognised.
            if had_content:
                per_release.append(recognised)
        return tuple(highlights), dropped, bool(per_release) and all(per_release)

    @property
    def feature_highlights(self) -> tuple[str, ...]:
        """Note lines announcing a NEW capability worth a look — step 3's other half.

        Purely advisory: these never gate a bump (that is `markers`' job). They
        exist so "should we adopt this?" reaches the human even on a clean bump
        that no breaking marker stopped — the release-note review Ray asked for.
        A line qualifies by sitting under a feature section, by a `feat:` prefix,
        or by an adoption phrase; the raw line is returned (trimmed of list
        bullets) so the reader sees the real wording, capped so a huge changelog
        does not flood the interview. When the cap bites, `features_dropped` says
        by how much — a silent truncation would read as "that was all of them".
        """
        return self._scan_features()[0]

    @property
    def features_dropped(self) -> int:
        """How many feature lines the cap discarded. Never truncate silently."""
        return self._scan_features()[1]

    @property
    def feature_scan_unrecognised(self) -> bool:
        """True when there are notes, no features found, and no format we know.

        The honest third state. `feature_highlights == ()` alone cannot tell
        "this release adds nothing" from "these notes are prose we cannot parse",
        and rendering the second as the first is how a whole release went unread:
        graphify 0.9.27-0.9.30 groups its bullets under bold subheads rather than
        `## Added`, so section detection finds no purchase there.
        """
        # Deliberately NOT `and not highlights`. That extra condition was the same
        # masking bug one level up: in a multi-release jump, ONE readable release
        # yielding a single feature suppressed the warning for the whole span, so
        # "found 1 feature, and could not read 3 of the 4 releases" rendered as a
        # confident list of 1. Whether the FORMAT was understood is independent of
        # whether anything was found, and the reader needs both. (Cold lane.)
        return bool(self.notes.strip()) and not self._scan_features()[2]


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
    return _proc.run_json(["gh", "api", path], timeout=_TIMEOUT_S, label=f"gh api {path}")


def _gh_api_list(path: str) -> tuple[list[object], str]:
    """One `gh api` call that returns a JSON array, as (items, error).

    Separate from `_gh_api` because the releases endpoint returns a list, and a
    list arriving where a dict is expected must read as "empty + error", never as
    an exception that a caller might mistake for "no releases".
    """
    return _proc.run_json(
        ["gh", "api", path], list_shape=True, timeout=_TIMEOUT_S, label=f"gh api {path}"
    )


def github_versions(repo: str, *, tag_prefix: str = "") -> tuple[str, tuple[str, ...], str]:
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
        if tag_prefix and not tag.startswith(tag_prefix):
            continue
        tag = tag.removeprefix(tag_prefix)
        parsed = Version.parse(tag)
        if parsed is not None:
            stable.append(parsed)
            raw.append(tag)
    if not stable:
        return "", (), f"no stable, version-shaped releases found for {repo}"
    return max(stable).raw, tuple(raw), ""


def release_for_tag(repo: str, tag: str, *, tag_prefix: str = "") -> tuple[str, str, str]:
    """GitHub release for `tag`, as (tag_name, body, error).

    A tag with no release is not an error — plenty of projects tag without
    publishing notes — so the caller distinguishes "no notes" from "unreachable"
    by looking at the error string.
    """
    last_error = "no tag candidates tried"
    candidates = tuple(
        dict.fromkeys(
            candidate
            for candidate in (f"{tag_prefix}{tag}" if tag_prefix else "", tag, f"v{tag}")
            if candidate
        )
    )
    for candidate in candidates:
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


def _resolve_source(
    pypi: str, github: str, tag_prefix: str = ""
) -> tuple[str, str, tuple[str, ...], str]:
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
        latest, versions, err = (
            github_versions(github)
            if not tag_prefix
            else github_versions(github, tag_prefix=tag_prefix)
        )
        return "github", latest, versions, err
    return "none", "", (), ""


def probe(*, pypi: str, github: str, current: str, tag_prefix: str = "") -> UpstreamStatus:
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
    source, latest, versions, err = _resolve_source(pypi, github, tag_prefix)
    if source == "none":
        return UpstreamStatus(source="none")
    if err:
        return UpstreamStatus(source=source, reachable=False, error=err)
    # `same_release`, not `==`: a decoration-only mismatch (`v2.1.220` vs `2.1.220`)
    # is not a pending release, and reading notes for it is what produced an
    # "Adopt it?" about a version already installed. (Cold lane, round 2.)
    if same_release(latest, current) or not github:
        return UpstreamStatus(latest=latest, source=source)

    pending = versions_between(versions, current, latest) or (latest,)
    bodies: list[str] = []
    unread: list[str] = []
    newest_tag = ""
    last_error = ""
    for version in pending:
        tag, body, tag_err = (
            release_for_tag(github, version)
            if not tag_prefix
            else release_for_tag(github, version, tag_prefix=tag_prefix)
        )
        if tag_err or not tag:
            unread.append(version)
            last_error = tag_err or f"no release found for {version}"
            continue
        if version == latest:
            newest_tag = tag
        # Use the normalized release identity for the internal span boundary.
        # The exact upstream tag remains in `github_tag`; a project-specific
        # prefix here would make `_release_spans` merge adjacent releases.
        bodies.append(
            f"## {version}\n\n{body.strip()}" if body.strip() else f"## {version}\n\n_(no notes)_"
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
