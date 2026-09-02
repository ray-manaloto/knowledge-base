# Copyright (c) 2026 Raymond Manaloto
"""Source manifests — `sources/<name>.manifest` pins an external repo by SHA.

The external repo is NEVER committed; the manifest (url + ref + commit) plus the
committed graph outputs make the KB reproducible without vendoring source.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

#: `build` states that exclude a source from `kb-build`, each for its own reason
#: (see `Manifest.build`). Defined here rather than beside `_ENUMS` because
#: `Manifest.is_built` reads it — a module-level name used from a class body must
#: already exist when the checker walks it, and `ty` says so out loud.
#:
#: Membership is the whole predicate: adding a fourth exclusion state means adding
#: it here and nowhere else, which is the property `is_built` exists to buy.
_EXCLUDED_BUILDS = frozenset({"skip", "defer"})


@dataclass(frozen=True)
class Manifest:
    """A parsed `sources/<name>.manifest`: an external repo pinned by SHA."""

    name: str  # derived from the file stem (sources/graphify.manifest -> "graphify")
    path: Path
    url: str
    ref: str  # branch/tag to clone
    commit: str  # pinned SHA
    kind: str = "code"
    #: Which graph this source lands in. `corpus` (default) merges into the
    #: aggregate `graphify-out/graph.json`; `study` merges into
    #: `graphify-out/study-graph.json` instead.
    #:
    #: A SECOND axis from `kind`, deliberately. `kind` says what the content IS
    #: (code -> AST pass, docs -> no AST); `scope` says what it is FOR. A peer
    #: tool being reverse-engineered is ordinary code — it needs the same AST
    #: pass — but it is an object of study, not corpus, and collapsing the two
    #: would force a choice between "don't extract it" and "put it in the
    #: corpus". Both are wrong. Introduced when three pinned peer tools took
    #: graph.json 7.6 MiB past the 512 MiB cap.
    scope: str = "corpus"
    #: Whether `kb-build` extracts this source at all. `include` (default) builds
    #: it; `skip` leaves it registered — the pin, and therefore the provenance
    #: Invariant 3 is about, are untouched — but no clone, no detect preflight and
    #: no AST pass happen for it.
    #:
    #: A THIRD axis, for the same reason `scope` is a second one. `scope` says
    #: which graph a source lands IN; this says whether it is built AT ALL, and a
    #: source can be excluded from the build while remaining, on the record, an
    #: object of study. Collapsing the two would force a choice between "forget
    #: what it was for" and "keep failing the build", and both are wrong.
    #:
    #: `skip` is deliberately expensive to use: `skip_reason` is REQUIRED and the
    #: build prints one line per skipped source. A silent exclusion is a way to
    #: make a red build green by dropping the source that was telling the truth.
    #:
    #: `defer` is the THIRD value, and it exists because `skip` was carrying two
    #: unrelated meanings (Ray, 2026-08-24). Every one of the five sources excluded
    #: before it existed was excluded by a DEFECT — #409's reviewed-warning
    #: inventories, #417's zero-node `Cargo.toml`. But a source can also be
    #: perfectly healthy and merely not worth its extraction cost yet, which is a
    #: BUDGET decision and not a blocker. Recording that as `skip` makes a cost
    #: choice read as a broken source forever: the backlog cannot tell which
    #: entries are waiting on a fix and which are waiting on a decision, so the
    #: healthy ones get re-diagnosed by every session that meets them.
    #:
    #: The two differ in what CLEARS them. A `skip` clears when someone fixes the
    #: defect; a `defer` clears when the economics change — a cheaper backend, a
    #: bigger budget, a ruling that the content is worth it. Neither is a
    #: soft-delete: both keep the pin committed and fingerprinted, and both are
    #: announced by name on every build.
    build: str = "include"
    #: Why this source is `build = skip`. Required and non-empty when it is.
    skip_reason: str = ""
    #: Why this source is `build = defer`. Required and non-empty when it is.
    #: A separate field from `skip_reason` on purpose: one field would let a
    #: state change silently inherit the other state's justification, and the
    #: whole point of the split is that the two reasons are not interchangeable.
    defer_reason: str = ""

    @property
    def clone_dir(self) -> Path:
        """Gitignored directory the source is cloned into (sibling of the manifest)."""
        return self.path.parent / self.name

    @property
    def is_built(self) -> bool:
        """Whether `kb-build` extracts this source at all.

        Ask THIS, never `build == "skip"`. When `defer` was added, the two live
        call sites in `kb_setup.graph` both spelled the test as `!= "skip"`, which
        silently returns True for `defer` — a new exclusion state that excludes
        nothing. Both were fixed, but the durable fix is that consumers stop
        re-deriving the predicate: a fourth state should not require finding every
        comparison again. (`a-fix-at-one-layer-leaves-the-next`.)
        """
        return self.build not in _EXCLUDED_BUILDS

    @property
    def is_ast_scanned(self) -> bool:
        """Whether `kb-build` runs an AST pass over this source's clone.

        STRICTLY NARROWER than `is_built`, and the difference is the whole
        reason this exists. `is_built` answers "does the build touch this source
        at all"; the build then asks a SECOND question — `kind == "docs"` sources
        get no AST pass, because `--code-only` over a docs mirror is a
        guaranteed-empty scan and, more importantly, because "a docs manifest
        that never ran" and "a code repo that ran and produced nothing" are
        DIFFERENT ANSWERS (`kb_setup.graph`, the `docs_only` split).

        `is_built`'s docstring says to ask it rather than re-derive it, and that
        advice was followed literally by `extract_census`, which therefore swept
        8 docs manifests the build never opens and reported one of them
        (`codex-docs`) as a blocked source. The predicate was not wrong; it was
        INCOMPLETE for a caller asking "what does the build actually read", and
        the answer to that is a second named predicate, not a second inline
        comparison at each call site. (Cold review of `69c126cbaef8`.)
        """
        return self.is_built and self.kind != "docs"

    @property
    def exclusion_reason(self) -> str:
        """The stated reason this source is excluded, or `""` when it is built.

        Reads whichever field the current `build` state requires, so a caller
        never has to know which of the two reason fields is populated.
        """
        if self.build == "skip":
            return self.skip_reason
        if self.build == "defer":
            return self.defer_reason
        return ""


def _parse(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        fields[key.strip()] = val.strip()
    return fields


#: Every value each enumerated manifest field accepts. These are VALIDATED, and
#: were not until 2026-08-20: `scope` had exactly one reader (`m.scope == "study"`)
#: and no check, so any misspelling of `study` silently fell through to the
#: `corpus` default and merged a peer tool into the aggregate — the precise
#: outcome the field was introduced to prevent, reachable by one keystroke and
#: visible in no output. (The misspelling is described rather than written: the
#: `typos` step corrects one written literally, which is how the test covering
#: this first shipped asserting that a VALID value raises.)
#: A field whose typo is indistinguishable from its default is not a setting.
_ENUMS: dict[str, frozenset[str]] = {
    "kind": frozenset({"code", "docs"}),
    "scope": frozenset({"corpus", "study"}),
    "build": frozenset({"include", "skip", "defer"}),
}


def load(path: Path) -> Manifest:
    """Parse and validate one manifest file into a Manifest (raises on missing fields)."""
    f = _parse(path.read_text(encoding="utf-8"))
    missing = {"url", "ref", "commit"} - f.keys()
    if missing:
        raise ValueError(f"{path}: manifest missing required field(s): {sorted(missing)}")
    for field, allowed in _ENUMS.items():
        value = f.get(field)
        if value is not None and value not in allowed:
            raise ValueError(
                f"{path}: {field} = {value!r} is not one of {sorted(allowed)} — "
                "an unrecognised value would otherwise fall through to the default"
            )
    build = f.get("build", "include")
    skip_reason = f.get("skip_reason", "")
    defer_reason = f.get("defer_reason", "")
    if build == "skip" and not skip_reason:
        raise ValueError(
            f"{path}: build = skip requires a non-empty `skip_reason` — a source dropped "
            "from the build without a stated reason is indistinguishable from one nobody "
            "noticed was missing"
        )
    if build == "defer" and not defer_reason:
        raise ValueError(
            f"{path}: build = defer requires a non-empty `defer_reason` — a source deferred "
            "on cost must say what would bring it back, or it is indistinguishable from one "
            "that is broken"
        )
    # The reason fields are state-specific, so a reason attached to a state that
    # is not current is not a harmless leftover: it is a justification for an
    # exclusion nobody is applying, and it survives a state change to silently
    # justify the WRONG state later. `skip`/`defer` differ precisely in what
    # clears them, so borrowing one's reason for the other is the failure this
    # split exists to prevent.
    if build != "skip" and skip_reason:
        raise ValueError(
            f"{path}: `skip_reason` is set but build = {build!r} — a stale reason from a "
            "state this manifest is no longer in will read as the justification for the "
            "state it IS in. Move it to the matching field or delete it"
        )
    if build != "defer" and defer_reason:
        raise ValueError(
            f"{path}: `defer_reason` is set but build = {build!r} — a stale reason from a "
            "state this manifest is no longer in will read as the justification for the "
            "state it IS in. Move it to the matching field or delete it"
        )
    return Manifest(
        name=path.stem,
        path=path,
        url=f["url"],
        ref=f["ref"],
        commit=f["commit"],
        kind=f.get("kind", "code"),
        scope=f.get("scope", "corpus"),
        build=build,
        skip_reason=skip_reason,
        defer_reason=defer_reason,
    )


def load_all(sources_dir: Path) -> list[Manifest]:
    """Load every `*.manifest` under `sources_dir`, sorted by path."""
    return [load(p) for p in sorted(sources_dir.glob("*.manifest"))]


def latest_commit(m: Manifest) -> str:
    """Upstream HEAD of the manifest's ref (a `git ls-remote`, no clone).

    Shares `_resolve_ref` with `resolve_tag` (#500), so the two can never again
    disagree on what a ref names. `m.ref` may itself be a branch, a tag, an
    already-qualified refname, or `HEAD` — this repo pins the first two under
    one field, and `_resolve_ref` accepts all four — so the call omits
    `--tags` (baking it in would return EMPTY for every branch source,
    silently). See `_resolve_ref`'s own docstring for exactly which candidate
    refnames get checked and in what order; that rule is stated there once,
    not restated here, so it cannot drift out of sync with the code again
    (#500 respec round 2, finding 2 — a prior revision of THIS docstring
    restated it and went stale when `_resolve_ref`'s was corrected).
    """
    sha = _resolve_ref(m.url, m.ref, tags=False)
    if sha is None:
        raise RuntimeError(f"{m.name}: ref {m.ref!r} not found at {m.url}")
    return sha


def write_commit(m: Manifest, commit: str) -> Manifest:
    """Rewrite the manifest's `commit =` line in place; return the updated Manifest."""
    lines = m.path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.lstrip().startswith("commit"):
            nl = "\n" if line.endswith("\n") else ""
            lines[i] = f"commit = {commit}{nl}"
            break
    m.path.write_text("".join(lines), encoding="utf-8")
    return replace(m, commit=commit)


def _tag_candidates(version: str, prefix: str) -> tuple[str, ...]:
    """The refs to try for `version`, most specific first, each named once.

    De-duplicated because a `tag_prefix = "v"` would otherwise spend a second
    network round trip re-asking a question already answered, and then print a
    "tried" list naming the same ref twice — which reads as a bug in the caller.
    """
    ordered = ([f"{prefix}{version}"] if prefix else []) + [f"v{version}", version]
    return tuple(dict.fromkeys(ordered))


def _resolve_ref(url: str, ref: str, *, tags: bool) -> str | None:
    """One `git ls-remote` for `ref` (+ its dereference), resolved to a commit sha.

    Returns the PEELED commit when `ref` names an annotated tag, the ref's own
    sha for a lightweight tag, a branch, or `HEAD`, or `None` — a MISS — when
    `ref` matches nothing at `url`. Shared by `resolve_tag` and `latest_commit`
    (#500) so the two can never again disagree on what a ref names.

    `tags=True` passes `--tags`, restricting the remote search to
    `refs/tags/*` — which also disambiguates a GUESSED tag name from a
    same-named branch — so only that one namespace needs checking.
    `resolve_tag`'s candidate loop always uses this shape. `tags=False` omits
    the flag: the search is UNRESTRICTED, so the match is checked against
    `refs/heads/` and `refs/tags/` both, at no extra network cost (`--tags`
    only narrows what git returns, not how many of the returned lines get
    compared afterwards). `latest_commit` uses this shape, because a
    manifest's `ref` may name either kind of pin.

    PRECEDENCE (#500 respec round 2, finding 1 — the CODE below has not
    changed since round 1; a claim in THIS paragraph was overgeneralised from
    one fixture and is corrected here): every namespace's PEELED form is
    checked before ANY namespace's plain form; within each of those two
    passes, `refs/heads/` is checked before `refs/tags/` (the `namespaces`
    tuple order), and the namespace-qualified forms before the raw `ref`.
    This only matters when a branch and a tag share a name, and it splits by
    tag KIND:

    For an ANNOTATED collision the peel pass decides, before either plain
    form is ever reached, and that agrees with `git rev-parse`:

        git rev-parse <name>          -> the TAG object   (git warns: ambiguous)
        git rev-parse <name>^{commit} -> the TAG's peeled commit  <- this function

    For a LIGHTWEIGHT collision there is no peel entry, so the plain pass
    decides — and it checks `refs/heads/` first, returning the BRANCH, while
    `git rev-parse` prefers `refs/tags/` there (`gitrevisions`(7)'s
    disambiguation order) and resolves to the TAG instead. Armed on a second,
    separate fixture:

        refs/heads/dup -> b5c142aa…            refs/tags/dup -> 4c3af257…  (lightweight)
        git rev-parse dup          -> 4c3af257…   (the TAG; git warns: ambiguous)
        _resolve_ref(url,"dup",tags=False) -> b5c142aa…   (the BRANCH — disagrees)

    So this function agrees with `git rev-parse` for an annotated collision
    and DISAGREES for a lightweight one — never "exactly what git rev-parse
    resolves" unconditionally, which is what round 1 of this paragraph said.
    Returning the branch for a branch-shaped pin is a defensible choice on its
    own, and no manifest in this repo can reach either collision shape, so
    this is documenting a resolved ambiguity, not a live bug.

    `ref` itself is ALSO tried unprefixed, alongside the namespace-qualified
    forms, because `git ls-remote` reports some refs with no `refs/…/` prefix
    at all — `HEAD` chief among them — and a caller may already pass a fully
    qualified name (`refs/heads/main`). Namespace-prefixing an already
    qualified `ref` would look for `refs/heads/refs/heads/main`, which can
    never exist; checking the raw `ref` too costs nothing, because git never
    reports an ordinary short tag/branch name with no namespace at all, so the
    raw form only ever matches `HEAD` or an already-qualified input.

    `git ls-remote` patterns are TAIL matches on `/` boundaries, not exact
    names — a repo holding `sub/v1.0.0` and no `v1.0.0` answers a `v1.0.0`
    pattern too (`refs/tags/sub/v1.0.0`). So a non-empty result is not itself a
    match: every candidate refname below is checked for EXACT equality, and a
    non-empty output with no exact match is still a MISS.
    """
    namespaces = ("refs/tags/",) if tags else ("refs/heads/", "refs/tags/")
    argv = ["git", "ls-remote", *(["--tags"] if tags else []), url, ref, f"{ref}^{{}}"]
    out = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout.strip()
    by_refname: dict[str, str] = {}
    for line in out.splitlines():
        sha, _, refname = line.partition("\t")
        by_refname[refname] = sha
    # Every refname this call could legitimately match: namespace-qualified
    # (the ordinary case) plus the raw `ref` itself (HEAD, or an
    # already-qualified input — see the docstring).
    candidates = (*(f"{namespace}{ref}" for namespace in namespaces), ref)
    # Peeled entries first, across every candidate, THEN plain ones — an
    # annotated tag's dereference always outranks its own tag-object line.
    for candidate in candidates:
        sha = by_refname.get(f"{candidate}^{{}}")
        if sha is not None:
            return sha
    for candidate in candidates:
        sha = by_refname.get(candidate)
        if sha is not None:
            return sha
    return None


def resolve_tag(url: str, version: str, *, prefix: str = "") -> tuple[str, str]:
    """Resolve a release version to its (ref, commit) via `git ls-remote --tags`.

    Tries the caller's `prefix` first when given, then `v<version>`, then the
    bare `<version>` — projects tag all three ways. Raises if NONE exists at the
    remote, so the currency engine can never pin a manifest to a version that was
    published to PyPI but tagged nowhere in git (the mirror of graphify's
    v1.0.0-tagged-not-on-PyPI trap). Each candidate resolves through
    `_resolve_ref(..., tags=True)`, which returns the PEELED commit for an
    annotated tag — never the tag object `write_pin` used to record (#500).

    The old call carried `--refs`, which strips exactly that dereference line.
    It never had anything to strip: the exact-ref pattern this function has
    always used never matched `<ref>^{}` in the first place, so `--refs` was
    dead weight, not a fix, under the old shape. It is removed here precisely
    BECAUSE the new shape asks for the peel on purpose — keeping `--refs` would
    turn this fix into a silent no-op that passes its own test.

    `prefix` exists because the two halves of #245 were fixed in different
    places and only one of them landed: `ToolSpec.tag_prefix` taught the *sync*
    check to strip `rust-v` before comparing versions, while this function — the
    one an authorized auto-apply actually calls — still knew only the two
    unprefixed candidates. So the reporting half stopped lying about codex and
    the acting half would still have aborted the bump, under a comment claiming
    it was fixed (cold lane, 2026-08-08).

    The v-prefixed and bare candidates are kept as FALLBACKS rather than
    replaced, so a stale or wrong `tag_prefix` degrades to today's behaviour
    instead of turning a resolvable tag into a hard failure.
    """
    candidates = _tag_candidates(version, prefix)
    for ref in candidates:
        try:
            sha = _resolve_ref(url, ref, tags=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
            # An unreachable host, a bad URL, or a timeout is a resolution
            # FAILURE, not a "tag not found" — but the currency engine's apply()
            # catches RuntimeError, so surface every failure mode as one, or a
            # raw traceback escapes instead of the clean "[currency] apply failed".
            raise RuntimeError(f"git ls-remote failed for {url} @ {ref}: {e}") from e
        if sha is not None:
            return ref, sha
    # Name EVERY candidate actually tried. The old wording hard-coded two, so a
    # prefixed miss would have reported that `rust-v` was never attempted when it
    # was — a failure message that misdescribes its own probe sends the reader to
    # add config that is already there.
    raise RuntimeError(f"no tag found at {url}; tried {list(candidates)}")


def write_pin(m: Manifest, *, ref: str, commit: str) -> Manifest:
    """Rewrite BOTH the `ref =` and `commit =` lines in place; return the update.

    `write_commit` moves only the SHA, which is right for advancing a branch
    source. A version bump also moves the tag the manifest tracks, so both lines
    change together — otherwise the manifest would claim a new SHA under the old
    tag name, an internally inconsistent pin.
    """
    lines = m.path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        nl = "\n" if line.endswith("\n") else ""
        if line.lstrip().startswith("ref"):
            lines[i] = f"ref = {ref}{nl}"
        elif line.lstrip().startswith("commit"):
            lines[i] = f"commit = {commit}{nl}"
    m.path.write_text("".join(lines), encoding="utf-8")
    return replace(m, ref=ref, commit=commit)


def name_from_url(url: str) -> str:
    """Derive the manifest stem from a repo URL (last path segment, no `.git`)."""
    return url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")


@dataclass(frozen=True)
class NewSource:
    """A repo source to pin: url (required) + optional ref/kind/name/comment.

    Bundled so `add()` stays a small (sources_dir, source, *, force) call. `name`
    defaults to the URL's last path segment; set it to disambiguate two repos that
    share a basename (e.g. two `antigravity-plugin-cc` forks).
    """

    url: str
    ref: str = "main"
    kind: str = "code"
    name: str | None = None
    comment: str | None = None

    @property
    def stem(self) -> str:
        """The manifest file stem (explicit name, else derived from the url)."""
        return self.name or name_from_url(self.url)


def add(sources_dir: Path, source: NewSource, *, force: bool = False) -> Manifest:
    """Create `sources/<stem>.manifest` for a new repo, SHA-pinned at upstream HEAD.

    The reusable replacement for hand-writing a manifest: resolve the pinned commit
    via `latest_commit` (a `git ls-remote`, no clone — same path `kb-update` uses),
    then write the file. Raises `FileExistsError` if the manifest already exists
    unless `force` (so re-adds don't silently clobber a deliberately-pinned SHA —
    advance an existing source with `kb-update`).
    """
    stem = source.stem
    path = sources_dir / f"{stem}.manifest"
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists (use kb-update to advance, or --force)")
    probe = Manifest(
        name=stem, path=path, url=source.url, ref=source.ref, commit="", kind=source.kind
    )
    commit = latest_commit(probe)
    header = "# Source manifest — reproducible-by-reference (Invariant 3)."
    body = f"# {source.comment}\n" if source.comment else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{header}\n{body}url = {source.url}\nref = {source.ref}\n"
        f"commit = {commit}\nkind = {source.kind}\n",
        encoding="utf-8",
    )
    return Manifest(
        name=stem, path=path, url=source.url, ref=source.ref, commit=commit, kind=source.kind
    )
