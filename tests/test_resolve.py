"""Tests for the citation-resolution primitive (kb_setup.resolve).

Three states, kept distinct for the reason the currency engine keeps them
distinct: collapsing "I could not tell" into either "wrong" or "fine" is how a
checker starts lying. So RESOLVED / MISSING / AMBIGUOUS are asserted separately
here, and every negative is paired with the positive control that proves the
probe can produce the other answer at all
(`.claude/rules/probes-need-a-control-arm.md`).

Fixtures are built on disk under `tmp_path` rather than mocked, because what is
under test IS filesystem behaviour — which directories get walked and which get
pruned. A mocked walk could only confirm the mock.
"""

from __future__ import annotations

from pathlib import Path

from kb_setup import resolve


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write `{relpath: body}` under tmp_path and return it."""
    for rel, body in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return tmp_path


# ------------------------------------------------- separator-bearing paths ----


def test_relative_path_present_resolves(tmp_path: Path):
    """The positive control for every MISSING assertion below."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    got = resolve.resolve_path(root, "docs/a.md")
    assert got.state is resolve.State.RESOLVED


def test_relative_path_absent_is_missing(tmp_path: Path):
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    got = resolve.resolve_path(root, "docs/b.md")
    assert got.state is resolve.State.MISSING


def test_a_directory_citation_resolves(tmp_path: Path):
    root = _repo(tmp_path, {"docs/sub/a.md": "x\n"})
    assert resolve.resolve_path(root, "docs/sub/").state is resolve.State.RESOLVED


# ------------------------------------------------------- bare filenames ----


def test_bare_filename_with_one_match_resolves_and_names_where(tmp_path: Path):
    root = _repo(tmp_path, {"docs/only-here.md": "x\n"})
    got = resolve.resolve_path(root, "only-here.md")
    assert got.state is resolve.State.RESOLVED
    assert got.detail.endswith("docs/only-here.md")


def test_bare_filename_with_no_match_is_missing(tmp_path: Path):
    root = _repo(tmp_path, {"docs/only-here.md": "x\n"})
    assert resolve.resolve_path(root, "nowhere.md").state is resolve.State.MISSING


def test_bare_filename_with_several_matches_is_ambiguous(tmp_path: Path):
    root = _repo(tmp_path, {"docs/README.md": "x\n", "python/README.md": "y\n"})
    got = resolve.resolve_path(root, "README.md")
    assert got.state is resolve.State.AMBIGUOUS
    assert "2" in got.detail


# ----------------------------------------------------- the pruned trees ----


def test_the_virtualenv_is_not_searched(tmp_path: Path):
    """A name that exists ONLY inside `.venv` does not resolve."""
    root = _repo(tmp_path, {".venv/lib/pkg/setup.py": "x\n"})
    assert resolve.resolve_path(root, "setup.py").state is resolve.State.MISSING


def test_the_same_name_outside_the_virtualenv_does_resolve(tmp_path: Path):
    """Control arm for the test above — the walk works, it is pruning."""
    root = _repo(tmp_path, {".venv/lib/pkg/setup.py": "x\n", "python/setup.py": "y\n"})
    got = resolve.resolve_path(root, "setup.py")
    assert got.state is resolve.State.RESOLVED
    assert got.detail.endswith("python/setup.py")


def test_a_vendored_source_clone_never_shadows_the_authored_tree(tmp_path: Path):
    """A vendored copy must not win against an authored file of the same name."""
    root = _repo(tmp_path, {"sources/agents/README.md": "x\n", "docs/README.md": "y\n"})
    got = resolve.resolve_path(root, "README.md")
    assert got.state is resolve.State.RESOLVED
    assert got.detail.endswith("docs/README.md")


def test_a_vendored_only_name_resolves_and_is_labelled_vendored(tmp_path: Path):
    """`watch.py:1499` names graphify's source, which this repo pins.

    Reporting it broken would be a false positive on a citation that is exactly
    right — and resolving it is what lets the line-number check, the whole point
    of #145, actually run against the file the author meant.
    """
    root = _repo(tmp_path, {"sources/graphify/graphify/watch.py": "x\n"})
    got = resolve.resolve_path(root, "watch.py")
    assert got.state is resolve.State.RESOLVED
    assert "vendored" in got.detail


def test_a_name_matching_several_vendored_copies_is_ambiguous(tmp_path: Path):
    """40 vendored `CONTRIBUTING.md` files is ambiguity, not a broken citation."""
    root = _repo(tmp_path, {"sources/a/CONTRIBUTING.md": "x\n", "sources/b/CONTRIBUTING.md": "y\n"})
    assert resolve.resolve_path(root, "CONTRIBUTING.md").state is resolve.State.AMBIGUOUS


def test_a_name_in_neither_tree_is_still_a_real_miss(tmp_path: Path):
    """Control arm: the vendored tier must not turn every miss into a pass."""
    root = _repo(tmp_path, {"sources/graphify/graphify/watch.py": "x\n"})
    assert resolve.resolve_path(root, "nowhere-at-all.py").state is resolve.State.MISSING


def test_committed_source_subtrees_count_as_authored(tmp_path: Path):
    """`sources/media/` and `sources/extractions/` are authored and committed.

    The control arm that keeps the vendored tests honest: classifying all of
    `sources/` as vendored would label a committed transcript as somebody
    else's file.
    """
    root = _repo(tmp_path, {"sources/media/talk-transcript.md": "x\n"})
    got = resolve.resolve_path(root, "talk-transcript.md")
    assert got.state is resolve.State.RESOLVED
    assert "vendored" not in got.detail


# ------------------------------------------------ the derived-output tier ----


def test_a_top_level_derived_artifact_resolves_and_says_so(tmp_path: Path):
    """`graph.json` is cited constantly and lives only in the derived tree.

    Excluding the derived tree from the main search and then failing the
    citation would make the single most-cited filename in this repo's handoffs a
    permanent false positive.
    """
    root = _repo(tmp_path, {"graphify-out/graph.json": "{}\n"})
    got = resolve.resolve_path(root, "graph.json")
    assert got.state is resolve.State.RESOLVED
    assert "derived" in got.detail


def test_a_top_level_derived_directory_resolves_too(tmp_path: Path):
    """Handoffs write `memory/` and `wiki/` for `graphify-out/memory|wiki/`.

    The derived probe covered files only, so the shorthand every handoff uses
    for the derived tree's own subdirectories read as a broken citation while
    the file beside it resolved — the same tier answering two forms of the same
    claim differently.
    """
    (tmp_path / "graphify-out" / "memory").mkdir(parents=True)
    assert resolve.resolve_path(tmp_path, "memory/").state is resolve.State.RESOLVED


def test_an_absent_top_level_directory_is_still_a_miss_after_the_derived_probe(tmp_path: Path):
    """Control arm: the derived probe must not resolve everything ending in `/`."""
    (tmp_path / "graphify-out" / "memory").mkdir(parents=True)
    assert resolve.resolve_path(tmp_path, "nosuchdir/").state is resolve.State.MISSING


def test_the_derived_probe_is_shallow_and_says_so_when_it_misses(tmp_path: Path):
    """The bound is stated and tested: one level, not a walk of 139k files.

    `.claude/rules/probes-need-a-control-arm.md` calls a bound-limited search
    suspect by construction unless the target is proven to be inside it. This
    pins the bound so a later widening is a deliberate change rather than drift.
    """
    root = _repo(tmp_path, {"graphify-out/wiki/deep.md": "x\n"})
    assert resolve.resolve_path(root, "deep.md").state is resolve.State.MISSING


def test_the_derived_tier_never_shadows_the_authored_tree(tmp_path: Path):
    root = _repo(tmp_path, {"graphify-out/notes.md": "x\n", "docs/notes.md": "y\n"})
    got = resolve.resolve_path(root, "notes.md")
    assert got.state is resolve.State.RESOLVED
    assert got.detail.endswith("docs/notes.md")


def test_a_nested_derived_tree_is_pruned_too(tmp_path: Path):
    """`graphify-out/` is pruned by NAME, not only at the repo root.

    Measured: this repo carries `python/graphify-out/`, `tests/graphify-out/`,
    `brain/graphify-out/` and `.self-graph/graphify-out/`. Pruning only the root
    one left `graph.json` matching 7 files — reported as ambiguous when it has
    one obvious referent, on the most-cited filename in the whole corpus.
    """
    root = _repo(tmp_path, {"python/graphify-out/graph.json": "{}\n"})
    assert resolve.resolve_path(root, "graph.json").state is resolve.State.MISSING


def test_a_lint_cache_is_pruned(tmp_path: Path):
    """`.rumdl_cache/.gitignore` made a citation of `.gitignore` ambiguous."""
    root = _repo(tmp_path, {".gitignore": "x\n", ".rumdl_cache/.gitignore": "y\n"})
    assert resolve.resolve_path(root, ".gitignore").state is resolve.State.RESOLVED


# ------------------------------------------------------ partial paths ----


def test_a_path_suffix_resolves_when_it_is_unique(tmp_path: Path):
    """`currency/run.py` names `python/src/kb_setup/currency/run.py`.

    Authors cite the distinctive tail of a path, not its full length. Treating
    the tail as a broken repo-relative path is a false positive on a citation
    that is not merely plausible but exactly right.
    """
    root = _repo(tmp_path, {"python/src/kb_setup/currency/run.py": "x\n"})
    got = resolve.resolve_path(root, "currency/run.py")
    assert got.state is resolve.State.RESOLVED
    assert got.detail.endswith("python/src/kb_setup/currency/run.py")


def test_a_path_suffix_matching_several_files_is_ambiguous(tmp_path: Path):
    root = _repo(tmp_path, {"a/x/run.py": "1\n", "b/x/run.py": "1\n"})
    assert resolve.resolve_path(root, "x/run.py").state is resolve.State.AMBIGUOUS


def test_a_suffix_must_align_on_a_segment_boundary(tmp_path: Path):
    """`laude/rules/x.md` must not match `.claude/rules/x.md`.

    Without the boundary the suffix rule degrades into substring matching, and a
    checker that accepts any tail is one that can no longer say no.
    """
    root = _repo(tmp_path, {".claude/rules/x.md": "1\n"})
    assert resolve.resolve_path(root, "laude/rules/x.md").state is not resolve.State.RESOLVED


# ------------------------------------------------ claims about elsewhere ----


def test_a_path_under_an_existing_top_level_entry_is_a_real_miss(tmp_path: Path):
    """`docs/agents/issue-tracker.md` claims something about THIS repo."""
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    assert resolve.resolve_path(root, "docs/agents/issue-tracker.md").state is resolve.State.MISSING


def test_an_absent_top_level_directory_is_a_real_miss_not_unverifiable(tmp_path: Path):
    """`.github/` is one segment, so the first-segment test would be circular.

    Judging it by "does its first segment exist" asks the same question the
    citation itself asks, and answering no both times reported a claim ABOUT
    this repo as a claim about some other one — with a message ("likely another
    repo") that was simply untrue. A checker that explains a finding wrongly
    costs the same trust as one that finds the wrong thing.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    assert resolve.resolve_path(root, ".github/").state is resolve.State.MISSING


def test_a_typo_in_the_leading_segment_is_a_real_miss_and_names_the_near_hit(tmp_path: Path):
    """`pyhton/src/kb_setup/handoff.py` is the failure class this ticket targets.

    Judging "is this about our repo?" purely on whether segment 1 exists let a
    typo IN segment 1 answer its own question: the segment is absent because it
    is misspelled, so the citation was waved through as somebody else's file at
    exit 0. The tail still matches one real path, and that is the evidence the
    first-segment test cannot see.
    """
    root = _repo(tmp_path, {"python/src/kb_setup/handoff.py": "x\n"})
    got = resolve.resolve_path(root, "pyhton/src/kb_setup/handoff.py")
    assert got.state is resolve.State.MISSING
    assert "python/src/kb_setup/handoff.py" in got.detail


def test_a_single_segment_tail_is_not_enough_to_claim_a_near_hit(tmp_path: Path):
    """Control arm: `dotfiles/python/pyproject.toml` really is another repo's.

    Without a floor on how much structure must match, the near-hit rule decays
    into "some file somewhere has this basename" and every cross-repo citation
    becomes a confident false accusation — the exact direction #145 calls fatal.
    """
    root = _repo(tmp_path, {"pyproject.toml": "x\n", "docs/a.md": "x\n"})
    got = resolve.resolve_path(root, "dotfiles/python/pyproject.toml")
    assert got.state is resolve.State.UNVERIFIABLE


def test_a_path_rooted_outside_this_repo_is_unverifiable_not_missing(tmp_path: Path):
    """`graphify/serve.py` and `dotfiles/python/pyproject.toml` name other repos.

    The control arm is the test above: the two differ only in whether the first
    segment names something this repo has, which is the only evidence available
    about whether the claim was ever about this repo. Calling the second one
    broken is asserting a fact about a repository we cannot see.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    got = resolve.resolve_path(root, "graphify/serve.py")
    assert got.state is resolve.State.UNVERIFIABLE


# ------------------------------------------------------- declared tasks ----


def test_declared_tasks_reads_this_repos_own_declarations(tmp_path: Path):
    root = _repo(tmp_path, {"mise.toml": "[tasks.alpha]\nrun = 'true'\n"})
    assert "alpha" in resolve.declared_tasks(root)


def test_a_task_absent_from_the_repo_is_rejected_even_if_it_exists_globally(tmp_path: Path):
    """The whole point of parsing the file instead of asking the tool.

    Measured on this machine 2026-08-04, `mise tasks ls` reports 4 MORE tasks
    than this repo declares (46 vs 42) — the extras come from the user's global
    config, so a handoff naming one would pass here and fail on every other
    machine. The delta is the durable fact; both totals move whenever this repo
    adds a task.
    `lint` is a real task in this repo and deliberately absent from the fixture.
    """
    root = _repo(tmp_path, {"mise.toml": "[tasks.alpha]\nrun = 'true'\n"})
    assert "lint" not in resolve.declared_tasks(root)


def test_an_alias_counts_as_declared(tmp_path: Path):
    root = _repo(tmp_path, {"mise.toml": "[tasks.alpha]\nrun = 'true'\nalias = 'a'\n"})
    tasks = resolve.declared_tasks(root)
    assert {"alpha", "a"} <= tasks


def test_a_list_of_aliases_counts_as_declared(tmp_path: Path):
    root = _repo(tmp_path, {"mise.toml": "[tasks.alpha]\nrun = 'true'\nalias = ['a', 'b']\n"})
    assert {"alpha", "a", "b"} <= resolve.declared_tasks(root)


def test_no_mise_file_yields_no_tasks_rather_than_raising(tmp_path: Path):
    assert resolve.declared_tasks(tmp_path) == frozenset()


def test_a_malformed_mise_file_yields_no_tasks_rather_than_raising(tmp_path: Path):
    root = _repo(tmp_path, {"mise.toml": "[tasks.alpha\n"})
    assert resolve.declared_tasks(root) == frozenset()


# ---------------------------------------------------------- line counts ----


def test_line_count_counts_lines(tmp_path: Path):
    root = _repo(tmp_path, {"a.md": "one\ntwo\nthree\n"})
    assert resolve.line_count(root / "a.md") == 3


def test_line_count_of_a_final_line_without_a_newline(tmp_path: Path):
    """A file not ending in a newline still has that last line."""
    root = _repo(tmp_path, {"a.md": "one\ntwo"})
    assert resolve.line_count(root / "a.md") == 2


def test_line_count_of_an_unreadable_file_is_none_not_zero(tmp_path: Path):
    """Zero would make every line reference into it read as out of range.

    "Could not measure" and "measured, and it is empty" are different answers;
    returning 0 for the first turns an unreadable file into a pile of confident
    failures.
    """
    assert resolve.line_count(tmp_path / "does-not-exist.md") is None


# ------------------------------------------------------- containment ----


def test_a_citation_that_escapes_the_repo_does_not_resolve(tmp_path: Path):
    """`python/../../other/README.md` names a file OUTSIDE this repository.

    `Path.exists()` happily follows `..` out of the tree, so such a token was
    reported RESOLVED — a citation about a sibling checkout read as verified
    here, and `line_count` then opened a file this checker has no business
    reading. A false GREEN, which is the one direction a checker must not fail
    in.
    """
    outside = tmp_path / "other"
    outside.mkdir()
    (outside / "README.md").write_text("x\n", encoding="utf-8")
    root = _repo(tmp_path / "repo", {"python/a.md": "x\n"})
    assert resolve.resolve_path(root, "python/../../other/README.md").state is not (
        resolve.State.RESOLVED
    )


def test_a_relative_traversal_that_stays_inside_still_resolves(tmp_path: Path):
    """Control arm: containment must reject escapes, not every `..`."""
    root = _repo(tmp_path, {"python/a.md": "x\n", "docs/b.md": "y\n"})
    assert resolve.resolve_path(root, "python/../docs/b.md").state is resolve.State.RESOLVED


# -------------------------------------------- the sources/ root itself ----


def test_a_committed_sources_subdirectory_is_reachable_as_a_directory(tmp_path: Path):
    """`media/` names `sources/media/`, which is committed and authored.

    The vendored test read the CONTAINING directory, so at `sources/` itself the
    second path segment was the empty string — never in the kept set, so the
    whole level was classified vendored and `sources/media` and
    `sources/extractions` never entered the authored directory index at all.
    """
    root = _repo(tmp_path, {"sources/media/talk.md": "x\n"})
    assert resolve.resolve_path(root, "media/").state is resolve.State.RESOLVED


def test_a_vendored_clone_directory_is_still_not_authored(tmp_path: Path):
    """Control arm: fixing the `sources/` root must not un-vendor the clones."""
    root = _repo(tmp_path, {"sources/agnix/docs/x.md": "y\n"})
    assert resolve.resolve_path(root, "agnix/docs/").state is not resolve.State.RESOLVED


def test_a_source_manifest_beside_the_clones_is_authored(tmp_path: Path):
    """`sources/*.manifest` files are committed; they sit at the same level."""
    root = _repo(tmp_path, {"sources/agnix.manifest": "url=x\n"})
    got = resolve.resolve_path(root, "agnix.manifest")
    assert got.state is resolve.State.RESOLVED
    assert "vendored" not in got.detail


# ------------------------------------------------- directory citations ----


def test_a_trailing_slash_on_a_plain_file_does_not_resolve(tmp_path: Path):
    """`docs/a.md/` claims a DIRECTORY, and `docs/a.md` is a file.

    `Path.exists()` normalises the trailing slash away, so the citation's own
    claim about what kind of thing it names was never checked.
    """
    root = _repo(tmp_path, {"docs/a.md": "x\n"})
    assert resolve.resolve_path(root, "docs/a.md/").state is not resolve.State.RESOLVED


def test_a_trailing_slash_on_a_real_directory_still_resolves(tmp_path: Path):
    """Control arm for the test above."""
    root = _repo(tmp_path, {"docs/sub/a.md": "x\n"})
    assert resolve.resolve_path(root, "docs/sub/").state is resolve.State.RESOLVED


def test_a_symlink_pointing_outside_the_repo_does_not_resolve(tmp_path: Path):
    """The other half of containment, and the same false-GREEN class.

    Lexical normalisation cannot see a symlink, so `link/README.md` where
    `link` -> a sibling checkout resolved as verified — exactly what the `..`
    fix was for, reached by a different route.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "README.md").write_text("x\n", encoding="utf-8")
    root = _repo(tmp_path / "repo", {"docs/a.md": "x\n"})
    (root / "link").symlink_to(outside, target_is_directory=True)
    assert resolve.resolve_path(root, "link/README.md").state is not resolve.State.RESOLVED


def test_a_symlink_staying_inside_the_repo_still_resolves(tmp_path: Path):
    """Control arm: containment rejects escapes, not symlinks as such."""
    root = _repo(tmp_path / "repo", {"real/README.md": "x\n"})
    (root / "link").symlink_to(root / "real", target_is_directory=True)
    assert resolve.resolve_path(root, "link/README.md").state is resolve.State.RESOLVED


def test_a_single_dotdot_escape_is_also_rejected(tmp_path: Path):
    """Discriminates containment from a bogus "reject two or more `..`" rule.

    The existing escape/control pair differed only in how many `..` segments
    each had, so a fix that counted them would pass both and check nothing.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "README.md").write_text("x\n", encoding="utf-8")
    root = _repo(tmp_path / "repo", {"docs/a.md": "x\n"})
    assert resolve.resolve_path(root, "../outside/README.md").state is not (resolve.State.RESOLVED)


def test_the_committed_extractions_subtree_counts_as_authored(tmp_path: Path):
    """`sources/extractions/` had no fixture at all.

    Only `media` was ever exercised, so dropping `extractions` from the kept set
    left every test green — a constant half-covered by a suite that looked
    complete.
    """
    root = _repo(tmp_path, {"sources/extractions/chunk-one.json": "{}\n"})
    got = resolve.resolve_path(root, "chunk-one.json")
    assert got.state is resolve.State.RESOLVED
    assert "vendored" not in got.detail


# ------------------------------------------------- mistyped extensions ----
#
# The resolution half of #154. `citations` proposes the repairs; this decides
# whether any of them names something real. Returning None means STAY SILENT —
# not "resolved", not "missing" — because the whole mechanism only earns its
# place by promoting a token the allowlist would otherwise have dropped, and a
# promotion nobody can act on is the false positive the checker must not emit.


def test_a_mistyped_extension_reports_the_one_repair_that_resolves(tmp_path: Path):
    root = _repo(tmp_path, {"mise.toml": "x\n"})
    got = resolve.resolve_extension_typo(root, "mise.tomlx", ("mise.toml",))
    assert got is not None
    assert got.state is resolve.State.MISSING
    assert "mise.toml" in got.detail


def test_an_unlisted_extension_that_really_exists_stays_silent(tmp_path: Path):
    """THE control arm for the whole mechanism.

    `notes.org` is an unknown-but-VALID extension, not a typo. It is exactly the
    case the allowlist was built to stay quiet about, and repairing it to a
    file that happens to exist beside it would turn a correct citation into a
    finding — the regression criterion 2 forbids.
    """
    root = _repo(tmp_path, {"notes.org": "x\n", "notes.md": "x\n"})
    assert resolve.resolve_extension_typo(root, "notes.org", ("notes.md",)) is None


def test_a_repair_that_names_nothing_stays_silent(tmp_path: Path):
    """`codegraph.db` repairs to `.md` at one edit, and `codegraph.md` does not exist.

    The resolve step is the gate, not the edit distance. Measured over the
    corpus this is the row that separates the two: a distance rule alone would
    have reported it.
    """
    root = _repo(tmp_path, {"other.md": "x\n"})
    assert resolve.resolve_extension_typo(root, "codegraph.db", ("codegraph.md",)) is None


def test_two_repairs_that_both_resolve_stay_silent(tmp_path: Path):
    """`exactly one` is the discipline `_near_hit` already keeps.

    Two plausible referents is not one obvious referent, and naming either would
    be a guess presented as a finding.
    """
    root = _repo(tmp_path, {"notes.md": "x\n", "notes.py": "x\n"})
    got = resolve.resolve_extension_typo(root, "notes.pk", ("notes.md", "notes.py"))
    assert got is None


def test_a_repair_never_resolves_against_a_vendored_clone(tmp_path: Path):
    """`runner.os` is a GitHub Actions expression, not a mistyped filename.

    It repaired to `.rs` and suffix-matched `sources/hk/src/step/runner.rs`
    inside the pinned hk clone — the one false positive the corpus measurement
    found, and the reason repair resolution is restricted to the AUTHORED tree.
    The original criterion already said `authored`; this is what enforcing it
    costs.
    """
    root = _repo(tmp_path, {"sources/hk/src/step/runner.rs": "x\n"})
    assert resolve.resolve_extension_typo(root, "runner.os", ("runner.rs",)) is None


def test_a_repair_resolving_in_the_authored_tree_is_the_control(tmp_path: Path):
    """Paired with the arm above: the same shape, authored, DOES report.

    Without this the vendored arm proves only that the probe can say None.
    """
    root = _repo(tmp_path, {"src/step/runner.rs": "x\n"})
    got = resolve.resolve_extension_typo(root, "runner.os", ("runner.rs",))
    assert got is not None
    assert got.state is resolve.State.MISSING


def test_a_repair_may_resolve_against_the_derived_root(tmp_path: Path):
    """`graph.jsom` is the ticket's own motivating example.

    `graph.json` exists nowhere but `graphify-out/`, so a repair that could not
    see the derived tier would stay silent on the most-cited filename in the
    corpus — losing the case the ticket was filed about.
    """
    root = _repo(tmp_path, {"graphify-out/graph.json": "{}\n"})
    got = resolve.resolve_extension_typo(root, "graph.jsom", ("graph.json",))
    assert got is not None
    assert got.state is resolve.State.MISSING
    assert "graph.json" in got.detail


def test_a_repair_naming_several_files_is_not_a_unique_hit(tmp_path: Path):
    """An AMBIGUOUS repair is not a referent either — silence, not a finding."""
    root = _repo(tmp_path, {"a/x/run.py": "1\n", "b/x/run.py": "1\n"})
    assert resolve.resolve_extension_typo(root, "run.pyy", ("run.py",)) is None


def test_the_suggestion_names_a_bare_path_not_a_resolver_label(tmp_path: Path):
    """The suggestion has to read like something you can paste back.

    `Resolution.detail` is tier-dependent — the derived tier renders
    `derived output: graphify-out/graph.json` — so interpolating it produced
    "did you mean derived output: graphify-out/graph.json?". `_near_hit`, the
    machinery this generalises from, names a bare path. Without this test the fix
    is unarmed: the older assertion (`"graph.json" in detail`) passes either way.
    (Spec lane, F2.)
    """
    root = _repo(tmp_path, {"graphify-out/graph.json": "{}\n"})
    got = resolve.resolve_extension_typo(root, "graph.jsom", ("graph.json",))
    assert got is not None
    assert "did you mean graphify-out/graph.json?" in got.detail
    assert "derived output" not in got.detail


def test_a_token_that_is_ambiguous_under_its_own_spelling_stays_silent(tmp_path: Path):
    """Several real files match, which is the OPPOSITE of absent.

    The narrower `is RESOLVED` test let AMBIGUOUS fall through to the repair gate
    and emit `no file named Program.cs` — a sentence the index directly
    contradicts. `State` has four members precisely so "could not tell" is never
    rendered as a verdict, and this was that collapse pointed at a confident
    FAIL. (Silent-failure lane, F2.)
    """
    root = _repo(tmp_path, {"a/Program.cs": "x\n", "b/Program.cs": "x\n", "a/Program.c": "x\n"})
    assert resolve.resolve_path(root, "Program.cs").state is resolve.State.AMBIGUOUS
    assert resolve.resolve_extension_typo(root, "Program.cs", ("Program.c",)) is None


def test_a_token_naming_a_real_vendored_file_stays_silent(tmp_path: Path):
    """`watch.pyi` inside a pinned clone is a file we can actually open.

    The token's own existence test used the authored-only index, so this was
    reported `no file named watch.pyi` while `resolve_path` resolved it. Reading
    graphify's and mise's own source is the entire reason the vendored tier
    exists. `authored_only()` belongs to the REPAIRS, not to this question.
    (Silent-failure lane, F3.)
    """
    root = _repo(tmp_path, {"sources/upstream/pkg/watch.pyi": "x\n", "python/watch.py": "x\n"})
    assert resolve.resolve_path(root, "watch.pyi").state is resolve.State.RESOLVED
    assert resolve.resolve_extension_typo(root, "watch.pyi", ("watch.py",)) is None


def test_a_repair_still_ignores_the_vendored_tier_control(tmp_path: Path):
    """Control arm for the two above: the narrowing must SURVIVE on the repairs.

    Widening the token's own test to the full index must not widen the repair
    search with it, or the `runner.os` false positive comes straight back.
    """
    root = _repo(tmp_path, {"sources/hk/src/step/runner.rs": "x\n"})
    assert resolve.resolve_extension_typo(root, "runner.os", ("runner.rs",)) is None
