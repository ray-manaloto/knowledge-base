# Copyright (c) 2026 Raymond Manaloto
"""Declarative per-tool currency config (`currency.toml`, one per repo).

One `[tool.<name>]` table per tracked tool. graphify is the pilot; adding mise,
hk, uv, ruff or ty is a config edit, not an engine change — the version source
is inferred from the fields (`pypi` → PyPI, `github` only → GitHub releases,
neither → presence-only like ffmpeg), which is the whole reason this is a config
file rather than hard-coded checks.

Each repo carries its own config and runs independently (decided 2026-07-23):
there is deliberately NO cross-repo assertion, so this repo never learns
anything about a consumer.
"""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = "currency.toml"

# mise spells platforms this way (`os = ["macos"]`); match it so a config author
# writing `os` here does not have to remember a second vocabulary.
_PLATFORM_ALIASES = {"darwin": "macos", "win32": "windows"}


def current_platform() -> str:
    """This host in mise's `os` vocabulary (`macos`, `linux`, `windows`)."""
    return _PLATFORM_ALIASES.get(sys.platform, sys.platform)


@dataclass(frozen=True)
class WatchItem:
    """One thing step 4 re-reads every run: an upstream issue, or a local note.

    `kind = "issue"` is fetched from GitHub; `kind = "local"` is a finding of ours
    with no upstream ticket (the `label_communities` schema gap is the founding
    example) and is carried forward untouched so it cannot be quietly forgotten.
    """

    kind: str
    ref: str
    note: str = ""
    repo: str = ""

    @property
    def key(self) -> str:
        """Stable identity used to diff this run's observation against the last."""
        return f"{self.kind}:{self.repo}#{self.ref}" if self.repo else f"{self.kind}:{self.ref}"


@dataclass(frozen=True)
class RefBinding:
    """One place in the repo that must name the same source revision as the manifest.

    A version bump is not one edit. `sources/<tool>.manifest` moves, and so does
    every CODE CONSTANT and committed artifact that re-states the same revision —
    and nothing checked the second set. Measured 2026-08-15: the manifest, the
    pyproject pin, the installed binary and `graphify_semantic_corpus` all read
    v0.9.43 while `graphify_baseline._ACCEPTED_GRAPHIFY_REF` and
    `sources/graphify.dispositions.json` still read v0.9.42 — and
    `kb-currency-check` reported NO graphify manifest drift, correctly, because
    manifest == pin. The split was real, two releases wide, and invisible to
    every existing check. That is the class issue #225 names.

    `field` says which manifest line this binding must equal — `ref` for a tag
    (`v0.9.44`) or `commit` for the 40-hex SHA. Both are declared because they
    are independent: `_check_manifest_commit` already exists precisely because a
    manifest can pin a correct ref beside the previous release's commit.

    `pattern` is a regex with EXACTLY ONE capture group holding the revision. A
    pattern that matches nothing is DRIFT, never a pass: a binding whose anchor a
    refactor renamed has stopped checking anything, which is the SKIP-over-a-real-
    drift shape this engine refuses everywhere else.
    """

    path: str
    pattern: str
    field: str = "ref"
    note: str = ""
    #: WHICH revision this binding must equal — and the distinction only exists
    #: once a tool is forked (`[tool.<name>.fork]`, 2026-08-24).
    #:
    #: `manifest` (the default, and every binding's behaviour before forks) means
    #: "this states the revision we RUN", so it follows the manifest wherever the
    #: manifest goes — including onto a fork.
    #:
    #: `fork_base` means "this records the revision a PAST, COMPLETED piece of
    #: work was performed against". Those are historical snapshot identities, not
    #: claims about the present, and forcing them onto the fork's head would
    #: falsify the record — the semantic-corpus constants are digested into
    #: authorization ledgers, so moving them silently re-authorizes a run nobody
    #: re-approved, which is the loop `the-graphify-circle-is-mechanical` records.
    #: They are still CHECKED, against the upstream release the fork sits on, so
    #: they cannot rot unnoticed either.
    #:
    #: `frozen` is the third value and it exists because `fork_base` was still one
    #: notch wrong. A constant recording "the release a COMPLETED run was performed
    #: against" does not move when the fork rebases — that run used v0.9.48 and
    #: always will. Tying it to `base_ref` meant the first rebase (v0.9.48 ->
    #: v0.9.49, four hours later) demanded those constants move, which is
    #: re-authorization by side effect: exactly what `fork_base` was introduced to
    #: prevent, one release later.
    #:
    #: A `frozen` binding is compared against `expect`, declared beside it. That
    #: keeps it a REAL check — edit the constant and it fails — while making the
    #: reviewed value visible in config where a diff shows it, rather than
    #: comparing a historical fact against a moving target.
    tracks: str = "manifest"
    #: Required by, and only meaningful for, `tracks = "frozen"`.
    expect: str = ""

    @property
    def label(self) -> str:
        """How this binding names itself in a finding."""
        return f"{self.path} ({self.field})"


#: What `RefBinding.tracks` accepts. Validated for the reason every other enum in
#: this repo is: a misspelling would fall through to the `manifest` default and
#: silently demand that a historical record follow the fork.
_BINDING_TRACKS = frozenset({"manifest", "fork_base", "frozen"})


@dataclass(frozen=True)
class ForkSpec:
    """This tool is installed from OUR fork, not from its upstream release.

    Declared when a needed change exists only as an unmerged upstream PR. It is a
    deliberately uncomfortable state and the config says so out loud, because the
    failure it prevents is subtle: a fork can carry the same package NAME and the
    same VERSION STRING as the release it is based on — graphify's does, both
    `graphifyy` and `0.9.48` — so nothing about the version distinguishes a forked
    install from an upstream one. Every check that reasons from the version number
    is therefore blind to the fork, and two of them reported confident false drift
    the moment the pin moved.

    What this does NOT do is silence the upstream check. Ray's ruling (2026-08-24)
    was fork-aware state AND rebase-on-each-release, so a new upstream version is
    still a finding — it is the REBASE trigger. Only the remedy changes, and the
    message has to change with it: telling a reader to "bump the pin" when the
    real work is rebasing a fork branch sends them at the wrong file.
    """

    #: `owner/repo` of the upstream this was forked FROM. Kept so the engine can
    #: keep watching upstream releases while the pin points elsewhere.
    upstream: str
    #: The upstream release tag the fork currently sits on. This is what
    #: `tracks = "fork_base"` bindings are compared against.
    base_ref: str
    #: That tag's commit in upstream.
    base_commit: str
    #: Why the fork exists, in one line. Rendered into findings so a reader meets
    #: the reason at the same moment they meet the anomaly.
    reason: str
    #: What returns this tool to an upstream pin. A fork with no stated exit is
    #: how a temporary state becomes permanent.
    clears_when: str
    #: The upstream PR being carried, if any — `#2981`.
    pr: str = ""


@dataclass(frozen=True)
class ToolSpec:
    """Everything the engine needs to assess one tool's currency.

    Only `name` and `mise_key` are required. Every other field switches a check
    ON when present and omits it when absent, so a tool with no source manifest
    or no build artifact simply has fewer checks rather than failing ones.
    """

    name: str
    mise_key: str = ""
    python_package: str = ""
    python_project_dir: str = ""
    binary: str = ""
    pypi: str = ""
    github: str = ""
    extras: tuple[str, ...] = ()
    # Packages that must actually BE INSTALLED for the declared extras to mean
    # anything. Deliberately author-chosen rather than derived: several of
    # graphify's `[all]` deps auto-skip by PEP 508 marker on Python 3.14
    # (graspologic/leidenalg/igraph → Louvain fallback, an accepted state), so a
    # naive "every extra must import" check would report drift that is not drift.
    extra_probes: tuple[str, ...] = ()
    manifest: str = ""
    tag_prefix: str = ""
    """What this project prefixes its release tags with, e.g. `rust-v` for codex.

    Empty for the overwhelming majority: `manifest.resolve_tag` already tries
    both `v<version>` and a bare `<version>`, which covers every other tool
    tracked here. codex tags `rust-v0.147.0`, which neither candidate matches
    and which the manifest check compared literally against an installed
    `0.147.0` — reporting `the corpus describes code we do not run` about a
    manifest pinned exactly right (#245).

    A permanent FALSE drift is worse than a SKIP: it trains a reader to ignore
    the line, which is how the real one gets missed.
    """
    # The PROJECT-SCOPED agent skill this tool ships, and the argv that reinstalls
    # it. A skill is the fourth thing a version bump has to carry — after the pin,
    # the manifest and the clone — and it was the one nothing moved: at 0.9.32 the
    # stamp still read 0.9.23 for eight releases, leaving a skill that documented a
    # tool we no longer ran. Declared here rather than hardcoded in
    # `currency.skill` so this stays a config-not-code engine, like every other
    # per-tool fact.
    #
    # `skill_install` is a full argv, NOT a version-substituted template, and that
    # is deliberate: `--project` is the flag separating "writes ./.claude" from
    # "mutates ~/.claude" (`do-not.md` #1), so it must be visible in the config a
    # human reviews rather than assembled at runtime where a refactor could drop it.
    skill_dir: str = ""
    skill_install: tuple[str, ...] = ()
    # The file the skill installer stamps with the version it installed. Declared
    # separately from `skill_dir` because the filename is the tool's, not the
    # engine's (`.graphify_version`), and a config-not-code engine must not learn
    # a tool name to find it.
    #
    # This is the REPORTER half of `skill_dir` (#315). `currency.apply` refreshes
    # the skill on a bump, but nothing ever ASKED whether the stamp agreed with
    # the pin — so a bump applied by any other route (a hand edit, a
    # `kb-skill-refresh` that was never run) left a skill documenting a version we
    # had stopped running, silently. It sat at 0.9.23 against a 0.9.32 pin for
    # eight releases once, and on 2026-08-15 at 0.9.42 against 0.9.43.
    #
    # `.graphify_version` is gitignored, so the drift leaves NO tracked trace and
    # a reviewer reading the diff cannot see it. That is exactly why it needs a
    # check rather than a convention.
    skill_stamp: str = ""
    # Every other place in this repo that re-states the manifest's revision.
    ref_bindings: tuple[RefBinding, ...] = ()
    # Set when this tool is installed from OUR fork rather than an upstream
    # release (see `ForkSpec`). `None` — the overwhelming majority — leaves every
    # check exactly as it was, so forks cost nothing to the tools that have none.
    fork: ForkSpec | None = None
    # `artifact` is the PRIMARY build output — the one whose `built_at_commit` is
    # read for identity (graphify writes it only into graph.json). `artifacts` is
    # the wider set of GENERATED outputs (wiki/graphml/svg/GRAPH_REPORT.md) that
    # `kb-artifacts` regenerates from it. Ray's step 1 said "in sync with the
    # graph AND generated outputs", so the stamp fingerprints all of them — a
    # stat, so covering the derived set is cheap.
    artifact: str = ""
    artifacts: tuple[str, ...] = ()
    # Repo-relative GLOBS naming the committed INPUTS the build reads. The
    # mirror image of `artifacts`, and deliberately a separate field: outputs are
    # fingerprinted by a stat (`size:mtime_ns`) because they run to hundreds of
    # megabytes, while inputs are digested (sha256) because a stat cannot tell a
    # content change from an ordinary git operation — measured over eight rows in
    # `docs/research/reports/2026-07-31-size-mtime-false-drift.md`, where
    # `git checkout --`, a branch round-trip and a stash+pop each moved the stat
    # on byte-identical files. Left EMPTY here by default: a repo with no
    # declared inputs simply has no staleness check, exactly like a tool with no
    # manifest has no manifest check.
    inputs: tuple[str, ...] = ()
    stamp: str = ""
    # The reviewed version of a SELF-MANAGED tool — one that bootstraps the
    # toolchain and therefore cannot honestly be pinned in `[tools]`. mise is the
    # case: `ubi:jdx/mise` installs fine, but the pinned copy then SHADOWS the
    # ambient binary that actually runs every task, so the check would compare
    # pinned-against-pinned and report in sync forever (measured 2026-07-27 —
    # `which(mise)` moved from `~/.local/bin/mise` to the install dir the moment
    # the pin was added). Setting `expected` switches the tool onto a path that
    # reads the version from the binary and compares it against THIS value.
    #
    # Bump it deliberately, after reviewing the release notes — that act is the
    # gap analysis. Drift here means "the tool changed underfoot", which for a
    # self-updating tool is a statement about the host, not about the config.
    expected: str = ""
    # A tracked thing that is INGESTED, not installed: a `sources/<name>.manifest`
    # whose upstream we want to hear about, with no binary on PATH and no
    # `[tools]` pin. `microsoft/SkillOpt` is the founding case — its Claude Code
    # plugin runs from a git checkout and never `pip install`s, so every
    # binary-shaped check is inapplicable by construction.
    #
    # Without this flag such a tool cannot be declared honestly. `binary` defaults
    # to the tool's own name, and `_check_resolution` reports a missing binary as
    # DRIFT rather than SKIP — correctly, for something that SHOULD be installed.
    # So declaring SkillOpt would emit `skillopt is not installed on this host`
    # forever: a permanent red that is not a defect, which is how a check earns
    # being ignored and then earns being deleted.
    #
    # What still runs is the part Ray actually asked for (2026-08-03): steps 2-4,
    # the new-release probe off `github`, its notes, and the watch items. The
    # remedy is `mise run kb-update -- <name>`, never a pin edit, so an auto-apply
    # is refused in `currency.apply`.
    source_only: bool = False
    # Regex with ONE capture group pulling the version out of `--version` output.
    # Needed because the default heuristic (last whitespace field) is wrong for
    # any tool that prints more than "<name> <version>": mise prints
    # `2026.7.15 macos-arm64 (2026-07-27)`, whose last field is the build DATE.
    # That silently produced `observed_version("mise") == "(2026-07-27)"`.
    version_pattern: str = ""
    # Most tools expose `--version`; ffmpeg is the live counterexample (`-version`).
    # Keeping argv declarative avoids tool-name branches in the shared engine.
    version_args: tuple[str, ...] = ("--version",)
    os: tuple[str, ...] = ()
    watch: tuple[WatchItem, ...] = ()
    # Documentation pages whose CONTENT is the interface, fingerprinted so a
    # revision is detectable without a version bump. Needed for anything whose
    # semantics are documented rather than installed — `/goal` is the case: its
    # behaviour lives at code.claude.com/docs/en/goal.md and Anthropic can revise
    # that page any day without a release that looks relevant, silently staling
    # every skill built on it. See `currency.docs` for the offline/network split.
    docs_watch: tuple[str, ...] = ()

    @property
    def self_managed(self) -> bool:
        """Whether this tool is checked against `expected` rather than a mise pin.

        Driven off `expected` rather than a separate flag: the two would only
        ever be set together, and a flag that can disagree with the field it
        guards is one more thing to keep consistent.
        """
        return bool(self.expected)

    @property
    def all_artifacts(self) -> tuple[str, ...]:
        """Every output to fingerprint: the primary graph plus the derived set.

        De-duplicated and order-stable, so a config that lists `graph.json` in
        both `artifact` and `artifacts` fingerprints it once.
        """
        seen: dict[str, None] = {}
        for path in (self.artifact, *self.artifacts):
            if path:
                seen.setdefault(path, None)
        return tuple(seen)

    @property
    def tracks_upstream(self) -> bool:
        """Whether this tool has a release channel to be behind at all.

        ffmpeg declares neither `pypi` nor `github`: it is presence-tracked, so
        "no upstream version recorded" is the correct and permanent state rather
        than something to nag about. Mirrors `UpstreamStatus.tracked`, which draws
        the same line one layer out.
        """
        return bool(self.pypi or self.github)

    def applies_here(self) -> bool:
        """Whether this tool is expected to exist on the current host.

        A macOS-only tool on an Ubuntu CI runner must report NOT-APPLICABLE, never
        FAIL: "cannot check here" and "checked and it is wrong" are different
        answers, and conflating them is the silent-false-negative shape
        `.claude/rules/probes-need-a-control-arm.md` exists to prevent.
        """
        return not self.os or current_platform() in self.os


def _watch_items(raw: object) -> tuple[WatchItem, ...]:
    if not isinstance(raw, list):
        return ()
    items: list[WatchItem] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        fields: dict[str, object] = {str(k): v for k, v in entry.items()}
        ref = fields.get("ref")
        if ref is None:
            continue
        items.append(
            WatchItem(
                kind=str(fields.get("kind", "issue")),
                ref=str(ref),
                note=str(fields.get("note", "")),
                repo=str(fields.get("repo", "")),
            )
        )
    return tuple(items)


_REF_BINDING_FIELDS = frozenset({"ref", "commit"})


def _ref_binding(name: str, entry: object) -> RefBinding:
    """Validate ONE `[[tool.<name>.ref_binding]]` row, or raise saying why.

    Split out of `_ref_bindings` so the loop and the row-validation are separate
    things to read: the caller says "every row, in order, all-or-nothing", and
    this says what makes a row valid. Extracted after a code-health check
    measured the combined function at cyclomatic complexity 10 — at this repo's
    `max-complexity` limit, so ruff passed it and the shape was still worth
    fixing on its own terms.

    Every failure raises rather than skipping the row. A silently dropped binding
    is a check that reports nothing while looking declared — the failure mode this
    whole engine is built against — and unlike `watch`, a binding costs nothing to
    state correctly.
    """
    where = f"{CONFIG_NAME}: [[tool.{name}.ref_binding]]"
    if not isinstance(entry, dict):
        raise TypeError(f"{where} must be a table")
    fields = {str(k): v for k, v in entry.items()}
    path = str(fields.get("path", ""))
    pattern = str(fields.get("pattern", ""))
    field = str(fields.get("field", "ref"))
    if not path or not pattern:
        raise ValueError(f"{where} needs both 'path' and 'pattern'")
    if field not in _REF_BINDING_FIELDS:
        raise ValueError(
            f"{where} field must be one of {sorted(_REF_BINDING_FIELDS)}, got {field!r}"
        )
    tracks = str(fields.get("tracks", "manifest"))
    if tracks not in _BINDING_TRACKS:
        raise ValueError(
            f"{where} tracks must be one of {sorted(_BINDING_TRACKS)}, got {tracks!r} — "
            "an unrecognised value would fall through to 'manifest' and silently demand "
            "that a historical record follow the fork"
        )
    expect = str(fields.get("expect", ""))
    if tracks == "frozen" and not expect:
        raise ValueError(
            f"{where} tracks = 'frozen' requires `expect` — a frozen binding compared "
            "against nothing is a check that can only pass"
        )
    if tracks != "frozen" and expect:
        raise ValueError(
            f"{where} `expect` is set but tracks = {tracks!r} — it would be silently "
            "ignored, which reads as a declared check that is not running"
        )
    _assert_one_capture_group(where, path, pattern)
    return RefBinding(
        path=path,
        pattern=pattern,
        field=field,
        note=str(fields.get("note", "")),
        tracks=tracks,
        expect=expect,
    )


def _fork(name: str, entry: object) -> ForkSpec | None:
    """Parse `[tool.<name>.fork]`, or `None` when the tool is not forked.

    Every field is REQUIRED except `pr`, and a missing one raises. A fork
    declaration exists to make an uncomfortable state legible; one that omits why
    it exists or what clears it does the opposite, and would let a temporary pin
    become permanent with the config still reading as deliberate.
    """
    if entry is None:
        return None
    where = f"{CONFIG_NAME}: [tool.{name}.fork]"
    if not isinstance(entry, dict):
        raise TypeError(f"{where} must be a table")
    fields = {str(k): v for k, v in entry.items()}
    required = ("upstream", "base_ref", "base_commit", "reason", "clears_when")
    missing = [k for k in required if not str(fields.get(k, "")).strip()]
    if missing:
        raise ValueError(
            f"{where} is missing required field(s): {missing} — a fork must state what it "
            "was forked from, what release it sits on, why it exists, and what returns it "
            "to upstream"
        )
    return ForkSpec(
        upstream=str(fields["upstream"]),
        base_ref=str(fields["base_ref"]),
        base_commit=str(fields["base_commit"]),
        reason=str(fields["reason"]),
        clears_when=str(fields["clears_when"]),
        pr=str(fields.get("pr", "")),
    )


def _assert_one_capture_group(where: str, path: str, pattern: str) -> None:
    """A binding's pattern must compile AND capture exactly the revision."""
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"{where} pattern for {path} is not a valid regex: {exc}") from exc
    if compiled.groups != 1:
        raise ValueError(
            f"{where} pattern for {path} must have exactly one capture group "
            f"holding the revision, got {compiled.groups}"
        )


def _ref_bindings(name: str, raw: object) -> tuple[RefBinding, ...]:
    """Parse every `[[tool.<name>.ref_binding]]` row, in order, all-or-nothing."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise TypeError(f"{CONFIG_NAME}: [tool.{name}] ref_binding must be a list of tables")
    return tuple(_ref_binding(name, entry) for entry in raw)


def _tool_spec(name: str, table: dict[str, object]) -> ToolSpec:
    # One of the two must be present, and they are alternatives: `mise_key` says
    # "mise installs this, read the pin from mise.toml"; `expected` says "this
    # tool manages itself, compare the binary against the reviewed version".
    # Demanding `mise_key` from a self-managed tool would force a fake pin
    # pointing at a `[tools]` entry that must not exist.
    owners = bool(table.get("mise_key")) + bool(table.get("python_package"))
    if owners > 1:
        raise ValueError(
            f"{CONFIG_NAME}: [tool.{name}] must have one dependency owner, not both "
            "'mise_key' and 'python_package'"
        )
    if not owners and not table.get("expected") and not table.get("source_only"):
        raise ValueError(
            f"{CONFIG_NAME}: [tool.{name}] needs one of 'mise_key' (mise-managed), "
            f"'python_package' (pyproject/uv-managed), 'expected' (self-managed) or "
            "'source_only' (ingested, not installed)"
        )
    if table.get("source_only") and not table.get("manifest"):
        # A source-only tool with no manifest has nothing whatsoever to check, and
        # would report a cheerful all-clear over an empty set of checks. Refuse the
        # config rather than let it render as green.
        raise ValueError(f"{CONFIG_NAME}: [tool.{name}] is source_only and needs a 'manifest'")

    def _str(key: str) -> str:
        value = table.get(key, "")
        return str(value) if value else ""

    def _tuple(key: str) -> tuple[str, ...]:
        value = table.get(key, [])
        return tuple(str(v) for v in value) if isinstance(value, list) else ()

    project_dir = _str("python_project_dir")
    project_path = Path(project_dir or ".")
    if project_path.is_absolute() or ".." in project_path.parts:
        raise ValueError(
            f"{CONFIG_NAME}: [tool.{name}] python_project_dir must stay inside the repository"
        )

    return ToolSpec(
        name=name,
        mise_key=_str("mise_key"),
        python_package=_str("python_package"),
        python_project_dir=project_dir,
        binary=_str("binary") or name,
        pypi=_str("pypi"),
        github=_str("github"),
        extras=_tuple("extras"),
        extra_probes=_tuple("extra_probes"),
        skill_dir=_str("skill_dir"),
        skill_install=_tuple("skill_install"),
        skill_stamp=_str("skill_stamp"),
        ref_bindings=_ref_bindings(name, table.get("ref_binding")),
        fork=_fork(name, table.get("fork")),
        manifest=_str("manifest"),
        tag_prefix=_str("tag_prefix"),
        artifact=_str("artifact"),
        artifacts=_tuple("artifacts"),
        inputs=_tuple("inputs"),
        stamp=_str("stamp"),
        expected=_str("expected"),
        source_only=bool(table.get("source_only", False)),
        version_pattern=_str("version_pattern"),
        version_args=_tuple("version_args") or ("--version",),
        os=_tuple("os"),
        watch=_watch_items(table.get("watch")),
        docs_watch=_tuple("docs_watch"),
    )


def load(repo_root: Path) -> tuple[ToolSpec, ...]:
    """Parse `<repo_root>/currency.toml` into ToolSpecs, sorted by tool name.

    A missing config is an empty tuple, not an error — a repo that has not adopted
    the engine yet must not fail its own session-start hook.
    """
    path = repo_root / CONFIG_NAME
    if not path.exists():
        return ()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    tools = data.get("tool", {})
    if not isinstance(tools, dict):
        raise TypeError(f"{path}: expected a [tool.<name>] table")
    specs: list[ToolSpec] = []
    for raw_name, table in sorted(tools.items(), key=lambda kv: str(kv[0])):
        if not isinstance(table, dict):
            continue
        # Re-key explicitly: tomllib hands back `dict[Unknown, Unknown]`, and dict
        # is invariant, so passing it straight through does not type-check.
        specs.append(_tool_spec(str(raw_name), {str(k): v for k, v in table.items()}))
    return tuple(specs)
