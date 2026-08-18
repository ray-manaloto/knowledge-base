# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.chunks — validate + assemble host-agent extraction chunks.

Control-armed both directions: a clean chunk passes AND a broken one (dangling
edge, duplicate id, missing field, bad confidence, cross-chunk id collision)
FAILS — a validator that can only pass is not a validator.
"""

import json
from pathlib import Path

import pytest
from kb_setup import chunks


def _node(nid: str, **over: object) -> dict:
    n = {
        "id": nid,
        # Every host-agent chunk node is semantic by construction. Without this
        # literal, graphify 0.9.32+ infers the tier from `source_location` shape
        # and reads an "L<line>" value as AST — which silently deleted 629 doc
        # nodes from graph-prose.json on the first 0.9.32 build.
        "_origin": "semantic",
        "label": nid.title(),
        "file_type": "concept",
        "source_file": "src.md",
        "source_url": "https://example.com/src",
        "captured_at": "2026-07-23",
        "author": None,
        "contributor": None,
        "rationale": "A test concept.",
    }
    n.update(over)
    return n


def _edge(src: object, tgt: object, **over: object) -> dict:
    # `src`/`tgt` are `object`, not `str` — a real chunk's shape is only ever
    # promised by the JSON schema graphify's doc-merge expects, never enforced
    # by Python's type system, and some tests in this module deliberately
    # construct a malformed endpoint (a dict/list where a string id belongs)
    # to prove `_edge_issues` reports it rather than raising.
    e = {
        "source": src,
        "target": tgt,
        "relation": "relates_to",
        "confidence": "EXTRACTED",
        "confidence_score": 1,
        "source_file": "src.md",
        "weight": 1,
    }
    e.update(over)
    return e


def _chunk(nodes: list[dict], edges: list[dict], hyperedges: list[dict] | None = None) -> dict:
    return {
        "nodes": nodes,
        "edges": edges,
        "hyperedges": hyperedges if hyperedges is not None else [],
        "input_tokens": 0,
        "output_tokens": 0,
    }


def _hyperedge(hid: str, members: list[object], **over: object) -> dict:
    # `members` is `list[object]`, not `list[str]` — same reason as `_edge`'s
    # `src`/`tgt` above: some tests here deliberately construct a member that
    # is not a string id, to prove `_hyperedge_member_issues` reports it.
    h = {
        "id": hid,
        "label": hid.title(),
        "nodes": members,
        "relation": "participate_in",
        "confidence": "EXTRACTED",
        # 1 for EXTRACTED, 0.5 for INFERRED, per kb-extract.js's own prompt —
        # this fixture is the thing that documents the chunk shape, so it must
        # not encode a value the prompt forbids. A test needing a different
        # value sets it explicitly via `**over`.
        "confidence_score": 1,
        "source_file": "src.md",
    }
    h.update(over)
    return h


def test_validate_clean_chunk_has_no_issues() -> None:
    c = _chunk([_node("a"), _node("b")], [_edge("a", "b")])
    assert chunks.validate(c) == []


def test_validate_flags_dangling_edge() -> None:
    c = _chunk([_node("a")], [_edge("a", "ghost")])
    issues = chunks.validate(c)
    assert any("dangling target" in i for i in issues)


def test_validate_flags_duplicate_id() -> None:
    c = _chunk([_node("a"), _node("a")], [])
    assert any("duplicate node id" in i for i in chunks.validate(c))


def test_validate_flags_missing_node_field() -> None:
    bad = _node("a")
    del bad["source_url"]
    assert any("missing field" in i for i in chunks.validate(_chunk([bad], [])))


def test_validate_flags_bad_confidence() -> None:
    c = _chunk([_node("a"), _node("b")], [_edge("a", "b", confidence="MADE_UP")])
    assert any("confidence" in i for i in chunks.validate(c))


def test_assemble_writes_combined_chunk(tmp_path) -> None:
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c1 = tmp_path / "c1.json"
    c2 = tmp_path / "c2.json"
    # DISTINCT `source_file` per chunk, matching `kb-extract`'s one-agent-per-source
    # fan-out. These fixtures always modelled two sources via the `x_`/`y_` id
    # prefixes and left `source_file` at the shared default — a fidelity gap that
    # went unnoticed until `assembly_overlaps` (#198 item 2) started reading it.
    c1.write_text(json.dumps(_chunk([_node("x_a"), _node("x_b")], [_edge("x_a", "x_b")])))
    c2.write_text(json.dumps(_chunk([_node("y_a", source_file="other.md")], [])))
    out = chunks.assemble(tmp_path, "mytopic", [c1, c2])
    assert out == tmp_path / "sources" / "extractions" / "mytopic-docs.json"
    got = json.loads(out.read_text())
    assert len(got["nodes"]) == 3
    assert len(got["edges"]) == 1
    assert got["hyperedges"] == []
    assert got["input_tokens"] == 0


def test_assemble_strips_docs_suffix_from_name(tmp_path) -> None:
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_chunk([_node("a")], [])))
    out = chunks.assemble(tmp_path, "topic-docs.json", [c])
    assert out.name == "topic-docs.json"


def test_assemble_raises_on_dangling_edge(tmp_path) -> None:
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_chunk([_node("a")], [_edge("a", "ghost")])))
    with pytest.raises(ValueError, match="dangling"):
        chunks.assemble(tmp_path, "bad", [c])
    assert not (tmp_path / "sources" / "extractions" / "bad-docs.json").exists()


def test_assemble_raises_on_cross_chunk_id_collision(tmp_path) -> None:
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c1 = tmp_path / "c1.json"
    c2 = tmp_path / "c2.json"
    c1.write_text(json.dumps(_chunk([_node("dup")], [])))
    c2.write_text(json.dumps(_chunk([_node("dup")], [])))
    with pytest.raises(ValueError, match="collision"):
        chunks.assemble(tmp_path, "clash", [c1, c2])


def test_assemble_sees_an_id_collision_between_identically_named_chunks(tmp_path) -> None:
    """The gate must key on the chunk's PATH, not its basename (2026-08-17).

    `seen[nid] != p.name` made this whole class invisible whenever a batch's inputs
    shared a filename — which is exactly the semantic-corpus runner's output, 58
    chunks all staged as `<chunk-dir>/semantic-fragment.json`. The two other
    cross-chunk gates do not cover for it: `source_file` differs per chunk here, so
    `assembly_overlaps` stays quiet, and the hyperedge ids differ too. Measured
    before the fix: assembled CLEAN, both node sets written, 0 problems.
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    paths = []
    for i, source_file in enumerate(("a.md", "b.md"), start=1):
        p = tmp_path / f"chunk-{i:04d}" / "semantic-fragment.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(_chunk([_node("dup", source_file=source_file)], [])))
        paths.append(p)
    with pytest.raises(ValueError, match="id collision 'dup'") as excinfo:
        chunks.assemble(tmp_path, "clash", paths)
    # The label must DISAMBIGUATE, or the message names one file twice and reads as
    # a chunk colliding with itself.
    assert "chunk-0001/semantic-fragment.json" in str(excinfo.value)
    assert "chunk-0002/semantic-fragment.json" in str(excinfo.value)


def test_assemble_accepts_a_clean_batch_of_identically_named_chunks(tmp_path) -> None:
    """The other direction: distinguishing the chunks must not invent a collision."""
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    paths = []
    for i, (prefix, source_file) in enumerate((("x", "a.md"), ("y", "b.md")), start=1):
        p = tmp_path / f"chunk-{i:04d}" / "semantic-fragment.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(_chunk([_node(f"{prefix}_a", source_file=source_file)], [])))
        paths.append(p)
    out = chunks.assemble(tmp_path, "clean", paths)
    assert len(json.loads(out.read_text())["nodes"]) == 2


def test_assemble_resolves_relative_chunk_paths(tmp_path, monkeypatch) -> None:
    """`resolve()` is load-bearing for a caller that passes relative paths.

    `_labels` keys on the resolved path, so the loop must resolve too or the label
    lookup misses. Added because a mutation dropping the `resolve()` SURVIVED: the
    two tests above hand in absolute paths, so no fixture there could exhibit it —
    a bound in the probe, not coverage of the property.
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    paths = []
    for i, source_file in enumerate(("a.md", "b.md"), start=1):
        p = tmp_path / f"chunk-{i:04d}" / "semantic-fragment.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(_chunk([_node("dup", source_file=source_file)], [])))
        paths.append(Path(p.relative_to(tmp_path)))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="id collision 'dup'"):
        chunks.assemble(tmp_path, "clash", paths)


def test_assemble_labels_stay_bare_while_basenames_are_unique(tmp_path) -> None:
    """Every existing message keeps its wording — the suffix appears only on a clash."""
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c1 = tmp_path / "left" / "c1.json"
    c2 = tmp_path / "right" / "c2.json"
    for p in (c1, c2):
        p.parent.mkdir(parents=True)
    c1.write_text(json.dumps(_chunk([_node("dup")], [])))
    c2.write_text(json.dumps(_chunk([_node("dup", source_file="other.md")], [])))
    with pytest.raises(ValueError, match=r"id collision 'dup' \(c2\.json vs c1\.json\)"):
        chunks.assemble(tmp_path, "clash", [c1, c2])


def test_assemble_refuses_two_chunks_claiming_one_source_file(tmp_path) -> None:
    """#198 item 2. The ids DO NOT collide — which is the whole point.

    Extraction prefixes ids per source, so two extractions of one page collide on
    no id at all and the existing `seen` map reported them clean. What they share
    is the FILE THEY DESCRIBE, and concatenating them puts both node sets in one
    committed chunk: two descriptions of one page, indistinguishable afterwards.
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c1 = tmp_path / "c1.json"
    c2 = tmp_path / "c2.json"
    c1.write_text(json.dumps(_chunk([_node("x_a", source_file="dup.md")], [])))
    c2.write_text(json.dumps(_chunk([_node("y_a", source_file="dup.md")], [])))

    with pytest.raises(ValueError, match="duplicate claim") as e:
        chunks.assemble(tmp_path, "clash", [c1, c2])

    assert "id collision" not in str(e.value)  # the OTHER axis stayed silent
    assert not (tmp_path / "sources" / "extractions" / "clash-docs.json").exists()


def test_assemble_refuses_a_declared_overlap_too(tmp_path) -> None:
    """A `supersedes` declaration does not rescue an overlap during ASSEMBLY.

    This is the arm for the decision that separates `assembly_overlaps` from
    `collision_issues`, which excuses exactly this case. The declaration takes
    effect when the combined chunk MERGES — by which point it is a single chunk
    with nothing left to supersede, and both node sets are already inside it. An
    implementation that reused `collision_issues` passes every other arm in this
    file and lets this one through.
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c1 = tmp_path / "c1.json"
    c2 = tmp_path / "c2.json"
    c1.write_text(json.dumps(_chunk([_node("x_a", source_file="dup.md")], [])))
    declared = _chunk([_node("y_a", source_file="dup.md")], [])
    declared["supersedes"] = ["dup.md"]
    c2.write_text(json.dumps(declared))

    with pytest.raises(ValueError, match="duplicate claim"):
        chunks.assemble(tmp_path, "clash", [c1, c2])


def test_assembly_overlaps_is_silent_on_the_ordinary_batch() -> None:
    """One chunk per source is what `kb-extract` produces, and it must be clean.

    A gate that fires on the normal fan-out is one people route around. Covered
    here rather than only through `assemble` so the quiet direction has an arm of
    its own — a check verified only where it fires is half-verified.
    """
    assert chunks.assembly_overlaps([]) == []


def test_assembly_overlaps_reports_every_claimant(tmp_path) -> None:
    """Three chunks on one file name all three, not just the losing pair."""
    paths = []
    for i in range(3):
        p = tmp_path / f"c{i}.json"
        p.write_text(json.dumps(_chunk([_node(f"n{i}", source_file="shared.md")], [])))
        paths.append(p)

    issues = chunks.assembly_overlaps(paths)

    assert len(issues) == 1
    for name in ("c0.json", "c1.json", "c2.json"):
        assert name in issues[0], name


def test_assembly_overlaps_ignores_a_single_chunk(tmp_path) -> None:
    """A lone chunk claiming a file many times over is not an OVERLAP.

    Intra-chunk repetition is normal — every node of a page names that page — and
    reporting it would fire on literally every chunk this repo has.
    """
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(_chunk([_node("a", source_file="x.md"), _node("b", source_file="x.md")], []))
    )

    assert chunks.assembly_overlaps([p]) == []
    assert chunks.assembly_overlaps([p, p]) == []  # same file passed twice


def test_validate_files_maps_path_to_issues(tmp_path) -> None:
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    good.write_text(json.dumps(_chunk([_node("a")], [])))
    bad.write_text("{ not json")
    res = chunks.validate_files([good, bad])
    assert res[good] == []
    assert res[bad]
    assert "JSON" in res[bad][0]


def test_a_node_without_the_semantic_origin_marker_is_rejected() -> None:
    r"""The 0.9.32 defect, made unrepresentable (#135).

    graphify 0.9.32's `_is_ast_tier` trusts `_origin` when present and otherwise
    GUESSES from shape: a `source_location` matching `^L\d` is read as AST,
    because deterministic extractors emit `L<line>` and the semantic spec emits
    null. Our extraction agents emit `L5`, `L13`, ... unprompted — `kb-extract.js`
    never asked for the field — so 629 committed doc nodes were stamped
    `_origin="ast"` at load and vanished from `graph-prose.json`, taking it from
    2,864 nodes to 2,235. No error, no warning: the corpus simply answered 22%
    less well.

    Realistic break: an extraction agent omits the marker. That is not a
    hypothesis — it is what every one of the 18 committed chunks did until
    2026-08-03, and what a future wave will do again the moment the prompt drifts.
    """
    n = _node("a")
    del n["_origin"]
    issues = chunks.validate(_chunk([n], []), label="c")
    assert any("_origin" in i for i in issues), (
        f"an unstamped node passed validation; issues were {issues}. graphify would "
        f"then infer its tier from source_location shape and could drop it from the "
        f"prose graph silently."
    )


def test_the_marker_must_be_semantic_and_not_merely_present() -> None:
    """CONTROL ARM: `_origin` present is not the property that matters.

    A check for presence alone would pass a node carrying `_origin="ast"` — which
    is precisely the value the 0.9.32 backfill wrote onto the 629 lost nodes. So
    the assertion above could be satisfied by a chunk in exactly the broken state,
    and the gate would certify the defect it exists to prevent.
    """
    issues = chunks.validate(_chunk([_node("a", _origin="ast")], []), label="c")
    assert any("_origin" in i for i in issues), (
        f"a node marked _origin='ast' passed validation; issues were {issues}. That "
        f"is the exact state 0.9.32 left the 629 dropped nodes in."
    )


def _valid_chunk_file(path, nid: str = "a") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_chunk([_node(nid)], [])), encoding="utf-8")


def test_kb_build_refuses_a_chunk_that_fails_validation(monkeypatch, tmp_path) -> None:
    """The consumer must enforce it — a validator only `kb-validate-chunks` calls is not a gate.

    THE DEFECT THIS EXISTS FOR, found by the cold lane. `chunks.validate` was
    reachable only from `mise run kb-setup validate-chunks`, i.e. only when a
    human remembered — and #134 established on the same day that nobody had:
    37 dangling edges had ridden through every build in two committed chunks.
    So the `_origin` rule added beside it would have protected nothing.

    Realistic break: an extraction agent omits `_origin`, or emits an edge whose
    target it never created. Both are things agents demonstrably do here.

    The graphify runner is replaced with a recorder that FAILS if reached: the
    contract is refusal BEFORE the merge subprocess, not a non-zero exit after
    it has already written to the graph.
    """
    from kb_setup import graph

    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    (tmp_path / "sources" / "demo").mkdir(parents=True)
    (tmp_path / "sources" / "demo.manifest").write_text(
        "url = https://example.invalid/o/demo\nref = main\n"
        "commit = 03853a019423ffb5c5082e24c39ac20e38a7cfb1\nkind = code\n",
        encoding="utf-8",
    )
    sub = tmp_path / "sources" / "demo" / "graphify-out" / "graph.json"
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_text('{"nodes": [], "edges": []}', encoding="utf-8")

    bad = _node("a")
    del bad["_origin"]
    (tmp_path / "sources" / "extractions" / "bad-docs.json").write_text(
        json.dumps(_chunk([bad], [])), encoding="utf-8"
    )

    def _must_not_merge(argv: list, _root: object) -> None:
        joined = " ".join(str(a) for a in argv)
        if "_merge_docs" in joined:
            pytest.fail(f"build() merged an invalid chunk instead of refusing: {joined}")

    monkeypatch.setattr(graph, "_clear_stamp", lambda _root: None)
    monkeypatch.setattr(graph, "_required_input_fingerprints", lambda _root: {})
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
    monkeypatch.setattr(graph, "_detect_preflight", lambda _manifests: None)
    monkeypatch.setattr(graph, "_extract_code", lambda _root, _name: True)
    monkeypatch.setattr(graph, "_stamp_build", lambda _root, _inputs: None)
    monkeypatch.setattr(graph, "_run", _must_not_merge)

    # Seeded BEFORE the call: the refusal must be atomic with respect to the
    # artifact it protects. Round 1 validated AFTER `_merge_sources_into` had
    # already replaced the aggregate with a code-only composition, so one bad
    # chunk cost the working graph and left a partial one that `kb-query` will
    # serve — it checks only that the file exists. (Cold lane, round 2.)
    agg = tmp_path / "graphify-out" / "graph.json"
    agg.parent.mkdir(parents=True, exist_ok=True)
    agg.write_text('{"nodes": [], "SENTINEL_PREEXISTING": true}', encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        graph.build(tmp_path)
    assert "failed validation" in str(exc.value), (
        f"build() exited for some other reason: {exc.value!r}"
    )
    assert "SENTINEL_PREEXISTING" in agg.read_text(encoding="utf-8"), (
        "build() overwrote the existing graph before refusing — a refusal that is "
        "not atomic has already done the damage it exists to prevent"
    )


def test_kb_merge_refuses_a_chunk_that_fails_validation(monkeypatch, tmp_path) -> None:
    """CONTROL ARM's sibling: `kb-merge` is the SHARPER door and had only an is-file check.

    `build()` replays chunks that are already committed and reviewed; `kb-merge`
    takes a FRESH one straight off an extraction agent — the input least likely
    to be well-formed, and the one that used to reach the merge subprocess on
    nothing more than "the path exists".
    """
    from kb_setup import graphify_ops

    bad = _node("a")
    del bad["_origin"]
    p = tmp_path / "fresh.json"
    p.write_text(json.dumps(_chunk([bad], [])), encoding="utf-8")

    def _must_not_spawn(*_a: object, **_k: object) -> None:
        pytest.fail("merge_chunk spawned the merge subprocess for an invalid chunk")

    monkeypatch.setattr(graphify_ops.subprocess, "run", _must_not_spawn)
    assert graphify_ops.merge_chunk(tmp_path, str(p)) == 2


def test_kb_merge_still_accepts_a_valid_chunk(monkeypatch, tmp_path) -> None:
    """CONTROL ARM: refusing everything would satisfy both tests above for free.

    Without this, `merge_chunk` returning 2 unconditionally — the cheapest wrong
    fix — passes the sibling test and breaks every real ingestion.
    """
    from kb_setup import graphify_ops

    p = tmp_path / "good.json"
    _valid_chunk_file(p)
    spawned: list[bool] = []

    class _OK:
        returncode = 0

    monkeypatch.setattr(graphify_ops, "graphify_python", lambda _r: "/usr/bin/true")
    monkeypatch.setattr(
        graphify_ops.subprocess, "run", lambda *_a, **_k: (spawned.append(True), _OK())[1]
    )
    graphify_ops.merge_chunk(tmp_path, str(p))

    # Asserts REACHABILITY, not the return code, and that is the honest level.
    # `merge_chunk` also re-derives the prose graph afterwards and returns 1 when
    # that fails — which it does here, because a tmp_path has no built
    # `graphify-out/graph.json`. Asserting `rc == 0` would therefore be asserting
    # that an unrelated post-merge step succeeded, and the only way to make it
    # pass would be to stub that step too — piling fixture on fixture to test
    # something this case is not about. What the gate owes is: a valid chunk
    # REACHES the merge. That is exactly what `spawned` records.
    assert spawned, (
        "a VALID chunk was refused before the merge subprocess — the gate is too "
        "greedy, and `merge_chunk` returning 2 unconditionally would pass the "
        "sibling refusal test while breaking every real ingestion"
    )


def test_a_cross_chunk_edge_is_not_reported_as_dangling(tmp_path) -> None:
    """Validating a SET is a different question from validating one chunk.

    THE ROUND-1 FIX WAS THE DEFECT. `validate_files` applied the strict
    per-chunk rule to every file independently, so four edges in
    `goal-and-skills-workflow-docs.json` whose targets live in
    `claude-docs-docs.json` were reported dangling — and acting on that report
    DELETED four real relationships. graphify does not work that way:
    `build_merge` loads the nodes already in the graph, prepends them as a base
    chunk, and resolves endpoints against the COMBINED set, so an edge pointing
    at an earlier chunk's node is legitimate. (Cold lane, round 2.)
    """
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps(_chunk([_node("target_in_a")], [])), encoding="utf-8")
    b.write_text(
        json.dumps(_chunk([_node("src_in_b")], [_edge("src_in_b", "target_in_a")])),
        encoding="utf-8",
    )

    together = chunks.validate_files([a, b])
    assert together[b] == [], (
        f"a cross-chunk edge was reported as dangling when the whole set was "
        f"validated: {together[b]}. Deleting on that report is what removed four "
        f"real relationships."
    )

    # CONTROL ARM: the strict reading must survive for a SINGLE chunk, because
    # `kb-merge` takes one fresh chunk and `kb-extract.js` tells agents to
    # "only connect nodes that exist in THIS chunk". If widening leaked into the
    # single-file path, a genuine agent error would stop being caught.
    alone = chunks.validate_files([b])
    assert any("dangling" in i for i in alone[b]), (
        f"widening leaked into single-chunk validation; issues were {alone[b]}"
    )


def test_a_dangling_hyperedge_member_is_caught() -> None:
    """Hyperedges were outside the gate entirely, and one was really broken.

    `validate()` read only `nodes` and `edges`, while the chunk shape this module
    documents has always included `hyperedges`. Measured on real committed data:
    `graphify-docs.json` carried `graphify_pipeline_stages` naming seven members
    that existed in no chunk, and the validator returned CLEAN. graphify drops
    unresolved members and then the whole hyperedge, so a green gate permitted a
    committed relationship to vanish at ingestion (#134).
    """
    c = _chunk([_node("a")], [], [_hyperedge("h", ["a", "ghost", "also_ghost"])])
    assert any("hyperedge" in i for i in chunks.validate(c, label="c"))

    # CONTROL ARM: a fully-resolvable hyperedge must still pass, or the fix is
    # "reject all hyperedges" — which would have deleted the two VALID ones in
    # graphify-docs.json alongside the broken one. That over-deletion actually
    # happened during this fix and was caught by re-reading the validator output.
    # Three members, not two — `_MIN_HYPEREDGE_MEMBERS` (#176) refuses a
    # fully-resolvable hyperedge with fewer than that.
    ok = _chunk([_node("a"), _node("b"), _node("c")], [], [_hyperedge("h", ["a", "b", "c"])])
    assert chunks.validate(ok, label="c") == []


def test_assemble_carries_hyperedges_regression_for_170(tmp_path) -> None:
    """THE REGRESSION TEST for #170: hyperedges used to be silently discarded.

    `assemble()` used to hardcode `"hyperedges": []` in the combined chunk
    regardless of what any input chunk carried, deleting every hyperedge an
    extraction agent had emitted. This must go red if the carry is ever
    deleted again.
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    # Three members, not two — `_MIN_HYPEREDGE_MEMBERS` (#176) refuses fewer,
    # and this test needs the hyperedge to validate cleanly so it survives
    # into the combined output for the assertion below to find.
    h = _hyperedge("h_pair", ["x_a", "x_b", "x_c"])
    c1 = tmp_path / "c1.json"
    c2 = tmp_path / "c2.json"
    c1.write_text(
        json.dumps(_chunk([_node("x_a"), _node("x_b"), _node("x_c")], [_edge("x_a", "x_b")], [h]))
    )
    c2.write_text(json.dumps(_chunk([_node("y_a", source_file="other.md")], [])))
    out = chunks.assemble(tmp_path, "mytopic", [c1, c2])
    got = json.loads(out.read_text())
    assert got["hyperedges"] == [h], (
        f"assemble() discarded the input hyperedge; got {got['hyperedges']!r}"
    )


def test_assemble_hyperedges_empty_or_absent_both_assemble_cleanly(tmp_path) -> None:
    """All 18 committed chunks look like one of these two shapes today."""
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c1 = tmp_path / "c1.json"
    c2 = tmp_path / "c2.json"
    c1.write_text(json.dumps(_chunk([_node("a")], [], [])))  # explicit "hyperedges": []
    absent = {
        "nodes": [_node("b", source_file="other.md")],
        "edges": [],
        "input_tokens": 0,
        "output_tokens": 0,
    }
    c2.write_text(json.dumps(absent))  # "hyperedges" key absent entirely
    out = chunks.assemble(tmp_path, "cleantopic", [c1, c2])
    got = json.loads(out.read_text())
    assert got["hyperedges"] == []


def test_hyperedge_confidence_extracted_and_inferred_accepted() -> None:
    for tier in ("EXTRACTED", "INFERRED"):
        # Three members — `_MIN_HYPEREDGE_MEMBERS` (#176) refuses fewer, and
        # this test asserts a fully clean `validate()`, so the fixture must
        # clear every other check too.
        nodes = [_node("a"), _node("b"), _node("c")]
        c = _chunk(nodes, [], [_hyperedge("h", ["a", "b", "c"], confidence=tier)])
        assert chunks.validate(c, label="c") == [], f"{tier} was unexpectedly refused"


def test_hyperedge_arity_boundary() -> None:
    """A hyperedge needs at least 3 members (#176) — boundary tested both ways.

    graphify's own extraction spec defines a hyperedge as "3 or more nodes"
    (`.claude/skills/graphify/references/extraction-spec.md:38`), and
    `.claude/workflows/kb-extract.js` instructs agents to emit "THREE OR MORE
    node ids". A hyperedge with fewer members is just an edge, and it has
    zero-to-two surviving members by construction once any dangling ones drop
    — the same silent vanishing this validator exists to catch (#134).
    """
    nodes = [_node("a"), _node("b"), _node("c")]

    three = _chunk(nodes, [], [_hyperedge("h", ["a", "b", "c"])])
    assert chunks.validate(three, label="c") == [], "3 members was unexpectedly refused"

    two = _chunk(nodes, [], [_hyperedge("h", ["a", "b"])])
    issues = chunks.validate(two, label="c")
    assert any("member(s), needs at least 3" in i for i in issues), (
        f"2 members was accepted; issues were {issues}"
    )

    zero = _chunk(nodes, [], [_hyperedge("h", [])])
    issues = chunks.validate(zero, label="c")
    assert any("member(s), needs at least 3" in i for i in issues), (
        f"0 members was accepted; issues were {issues}"
    )


def test_hyperedge_confidence_ambiguous_refused() -> None:
    """AMBIGUOUS is an EDGE tier in graphify's own extraction schema.

    Never a hyperedge one — the schema line for hyperedges reads
    `"confidence":"EXTRACTED|INFERRED"` with no third option.
    """
    c = _chunk([_node("a"), _node("b")], [], [_hyperedge("h", ["a", "b"], confidence="AMBIGUOUS")])
    issues = chunks.validate(c, label="c")
    assert any("AMBIGUOUS" in i and "edge tier" in i for i in issues), (
        f"an AMBIGUOUS hyperedge was accepted, or refused without explaining why "
        f"it's wrong; issues were {issues}"
    )


def test_hyperedge_confidence_absent_refused() -> None:
    h = _hyperedge("h", ["a", "b"])
    del h["confidence"]
    c = _chunk([_node("a"), _node("b")], [], [h])
    issues = chunks.validate(c, label="c")
    assert any("confidence" in i for i in issues), (
        f"a hyperedge with no confidence field at all was accepted; issues were {issues}"
    )


def test_hyperedge_confidence_tuple_is_independent_of_edge_confidence() -> None:
    """CONTROL ARM: `_HYPEREDGE_CONFIDENCE` must be standalone, not derived.

    Not an alias/slice/subset of `_CONFIDENCE`. Issue #177 will widen
    `_CONFIDENCE` (edges) to admit AMBIGUOUS; if `_HYPEREDGE_CONFIDENCE` were
    derived from it instead of standing alone, that widening would silently
    start permitting an AMBIGUOUS hyperedge the moment it landed — this test
    is what makes the separation survive that edit.
    """
    assert "AMBIGUOUS" not in chunks._HYPEREDGE_CONFIDENCE
    assert chunks._HYPEREDGE_CONFIDENCE == ("EXTRACTED", "INFERRED")


def test_hyperedge_missing_empty_or_non_string_id_refused() -> None:
    for bad_id, make in (
        (None, lambda h: h.pop("id")),
        ("", lambda h: h.update(id="")),
        (42, lambda h: h.update(id=42)),
    ):
        h = _hyperedge("placeholder", ["a", "b"])
        make(h)
        c = _chunk([_node("a"), _node("b")], [], [h])
        issues = chunks.validate(c, label="c")
        assert any("valid string id" in i for i in issues), (
            f"bad hyperedge id {bad_id!r} was accepted; issues were {issues}"
        )


def test_validate_flags_duplicate_hyperedge_id_within_one_chunk() -> None:
    c = _chunk(
        [_node("a"), _node("b")],
        [],
        [_hyperedge("dup", ["a"]), _hyperedge("dup", ["b"])],
    )
    issues = chunks.validate(c, label="c")
    assert any("duplicate hyperedge id" in i and "dup" in i for i in issues), (
        f"two hyperedges sharing an id within one chunk were not flagged; issues were {issues}"
    )


def test_assemble_still_refuses_a_dangling_hyperedge_member_per_chunk(tmp_path) -> None:
    """Existing behaviour, must not regress now that hyperedges are carried through."""
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_chunk([_node("a")], [], [_hyperedge("h", ["a", "ghost"])])))
    with pytest.raises(ValueError, match="dangling"):
        chunks.assemble(tmp_path, "baddangle", [c])


def test_assemble_raises_on_combined_hyperedge_id_collision(tmp_path) -> None:
    """ONLY the combined pass can catch this.

    Each chunk validates clean alone, and the collision exists only once the
    two chunks are unioned into the artifact that actually gets written.
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    # Three members each — `_MIN_HYPEREDGE_MEMBERS` (#176) refuses fewer, and
    # the assertions immediately below require BOTH fixtures to validate
    # clean alone.
    c1_data = _chunk(
        [_node("a1"), _node("a2"), _node("a3")], [], [_hyperedge("dup", ["a1", "a2", "a3"])]
    )
    c2_data = _chunk(
        [_node("b1"), _node("b2"), _node("b3")], [], [_hyperedge("dup", ["b1", "b2", "b3"])]
    )
    assert chunks.validate(c1_data, label="c1") == [], "fixture chunk 1 must validate clean alone"
    assert chunks.validate(c2_data, label="c2") == [], "fixture chunk 2 must validate clean alone"

    c1 = tmp_path / "c1.json"
    c2 = tmp_path / "c2.json"
    c1.write_text(json.dumps(c1_data))
    c2.write_text(json.dumps(c2_data))
    with pytest.raises(ValueError, match="dup") as exc:
        chunks.assemble(tmp_path, "clashhyper", [c1, c2])
    msg = str(exc.value)
    assert "dup" in msg, f"expected the colliding id in the error; got: {msg}"
    assert "(combined)" in msg, f"expected the '(combined)' label in the error; got: {msg}"


def test_assemble_refuses_a_non_object_chunk_without_crashing(tmp_path) -> None:
    """`assemble()`'s own non-dict-chunk crash, three lines past `validate()`'s fix.

    `validate()` correctly reports "top level is X, expected a JSON object" and
    `assemble()` appended that to `problems` — then called `chunk.get("nodes",
    [])` on the SAME non-dict value, in the accumulation loop, BEFORE ever
    reaching `if problems: raise ValueError`. Confirmed on all four top-level
    non-object JSON shapes: array/string/number/null each raised
    `AttributeError` (`'list'`/`'str'`/`'int'`/`'NoneType' object has no
    attribute 'get'`) instead of the documented refusal, so `cli.py`'s
    `except ValueError` never caught it and `mise run kb-assemble` printed a
    raw traceback instead of its `[kb-assemble]` rc=1 message. Same defect
    class as `test_a_valid_json_non_object_refuses_instead_of_raising` below,
    one function over (#176 cold review round 2).
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    for label, payload in (
        ("array", "[]"),
        ("string", '"oops"'),
        ("number", "42"),
        ("null", "null"),
    ):
        p = tmp_path / f"{label}.json"
        p.write_text(payload, encoding="utf-8")
        with pytest.raises(ValueError, match="expected a JSON object") as exc:
            chunks.assemble(tmp_path, f"bad-{label}", [p])
        msg = str(exc.value)
        assert p.name in msg, f"{label}: the refusal did not name the offending file: {msg}"
        assert "expected a JSON object" in msg, (
            f"{label}: assemble() did not report the type-mismatch problem: {msg}"
        )


def test_a_valid_json_non_object_refuses_instead_of_raising(tmp_path) -> None:
    """`validate()` promises it never raises; a JSON array made it AttributeError.

    Harmless while only the CLI called it, and an unhandled traceback the moment
    `build()` and `merge_chunk` did — which this round is precisely the round
    that wired them up. (Cold lane, round 2.)
    """
    p = tmp_path / "arr.json"
    p.write_text("[]", encoding="utf-8")
    issues = chunks.validate_files([p])[p]
    assert issues, "a top-level array produced no issue at all — it raised instead"
    assert "expected a JSON object" in issues[0], (
        f"a top-level array did not produce a controlled refusal: {issues}"
    )


def test_an_unhashable_edge_endpoint_is_reported_not_raised() -> None:
    """`validate()` promises it never raises — an unhashable endpoint broke that.

    An unhashable `source`/`target` broke that promise too, the same class of
    defect `test_a_valid_json_non_object_refuses_instead_of_raising` fixed
    eight lines above it in this module for the non-dict-chunk case.

    `e["source"] not in ids` against a `set[str]` raises `TypeError` rather
    than returning False when `source` is a dict or list — an agent emitting
    `{"source": {"id": "a"}, ...}` used to crash `kb-validate-chunks`,
    `kb-assemble` (a `TypeError` instead of the documented `ValueError`), and
    `graphify_ops.merge_chunk` (a traceback instead of `mise run kb-merge`'s
    `rc=2` refusal) instead of producing an issue.
    """
    bad_source = _chunk([_node("a")], [_edge({"id": "a"}, "a")])
    issues = chunks.validate(bad_source, label="c")
    assert any("source is not a string id" in i for i in issues), (
        f"an unhashable edge source raised instead of being reported; issues were {issues}"
    )

    bad_target = _chunk([_node("a")], [_edge("a", ["a"])])
    issues = chunks.validate(bad_target, label="c")
    assert any("target is not a string id" in i for i in issues), (
        f"an unhashable edge target raised instead of being reported; issues were {issues}"
    )

    # CONTROL ARM: this must not become "any non-dangling-looking value passes" —
    # a well-formed string endpoint must still resolve cleanly.
    clean = _chunk([_node("a"), _node("b")], [_edge("a", "b")])
    assert chunks.validate(clean, label="c") == []


def test_an_unhashable_hyperedge_member_is_reported_not_raised() -> None:
    """The hyperedge-member analogue of the test above.

    `missing = [m for m in members if m not in ids]` raised `TypeError` for
    the same reason — a member that is a dict or list is unhashable against
    the `set[str]` of known ids. Found alongside FIX 1's edge-endpoint case
    (#176 cold review round 1), same defect class as the `validate()`
    non-dict-chunk fix eight lines above `_hyperedge_issues` in this module.
    """
    c = _chunk(
        [_node("a"), _node("b"), _node("c")],
        [],
        [_hyperedge("h", ["a", "b", {"id": "c"}])],
    )
    issues = chunks.validate(c, label="c")
    assert any("member(s) are not string ids" in i for i in issues), (
        f"an unhashable hyperedge member raised instead of being reported; issues were {issues}"
    )

    # CONTROL ARM: three well-formed string members must still resolve cleanly.
    clean = _chunk([_node("a"), _node("b"), _node("c")], [], [_hyperedge("h", ["a", "b", "c"])])
    assert chunks.validate(clean, label="c") == []


def test_hyperedge_reports_bad_id_dangling_member_and_bad_confidence_together() -> None:
    """The docstring promises 'every other combination ... reported together'.

    Every OTHER existing hyperedge test exercises one defect at a time, so a
    `continue` slipped in right after the bad-id `issues.append(...)` in
    `_hyperedge_issues` would still pass the whole suite — the members and
    confidence checks below it would simply never run for that hyperedge, and
    nothing would notice. This test — and its sibling below — are what such a
    `continue` regression must fail. Verified live: inserting `continue` after
    the bad-id append turns this test red; restoring it turns it green again.
    """
    h = _hyperedge("", ["a", "ghost", "c"], confidence="AMBIGUOUS")
    c = _chunk([_node("a"), _node("b"), _node("c")], [], [h])
    issues = chunks.validate(c, label="c")
    assert any("valid string id" in i for i in issues), issues
    assert any("dangling member" in i for i in issues), issues
    assert any("AMBIGUOUS" in i for i in issues), issues


def test_hyperedge_reports_missing_nodes_list_and_bad_confidence_together() -> None:
    """Pins that a missing 'nodes' list does not suppress the confidence check.

    This docstring used to claim "verified live: inserting `continue` [after
    the 'no nodes list' append] turns this test red" — true when it was
    written, false since `_hyperedge_member_issues` was split out of
    `_hyperedge_issues`'s loop body (#176). The 'no nodes list' case is now a
    `return` from that separate function, not an `append` inside the caller's
    loop, so there is no longer a `continue` insertion point that isolates
    THIS test from its sibling above. Measured (#176 cold review round 2): the
    nearest constructible mutation — a `continue` right after
    `issues.extend(_hyperedge_member_issues(...))` in `_hyperedge_issues` — is
    unconditional and reddens BOTH this test and
    `test_hyperedge_reports_bad_id_dangling_member_and_bad_confidence_together`
    together, not this one alone. It is kept anyway because it still pins a
    real property (a missing 'nodes' list must not short-circuit the
    confidence check) — it is just not an INDEPENDENT control arm on that
    property. A deleted "verified live" claim is safer than one re-pointed at
    a mutation nobody has actually run.
    """
    h = _hyperedge("h", ["a", "b", "c"], confidence="AMBIGUOUS")
    del h["nodes"]
    c = _chunk([_node("a"), _node("b"), _node("c")], [], [h])
    issues = chunks.validate(c, label="c")
    assert any("no 'nodes' list" in i for i in issues), issues
    assert any("AMBIGUOUS" in i for i in issues), issues


def test_assemble_handles_a_null_hyperedges_key(tmp_path) -> None:
    """The `or []` guard is the only thing stopping a `TypeError` here.

    `chunk.get("hyperedges") or []` is the only thing stopping
    `list.extend(None)` raising `TypeError` when a chunk carries an explicit
    JSON `null` for `hyperedges`. `validate()` treats `"hyperedges": null` as
    clean (`_hyperedge_issues` returns `[]` when its argument is `None`), so
    nothing upstream of `assemble()` catches this shape — this is the
    regression test for that `or []` staying in place.
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    c = tmp_path / "c.json"
    payload = _chunk([_node("a")], [])
    payload["hyperedges"] = None
    c.write_text(json.dumps(payload))
    out = chunks.assemble(tmp_path, "nullhyper", [c])
    got = json.loads(out.read_text())
    assert got["hyperedges"] == []


def test_the_same_chunk_passed_twice_is_refused(tmp_path) -> None:
    """A file never collides with itself, so the id gate cannot see this at all.

    Measured before the fix: `assemble(root, 'dupe', [p, p])` returned 0 problems
    and wrote TWO nodes carrying one id. `assembly_overlaps` could not cover for
    it either — it dedups on `resolve()` BEFORE its two-chunk minimum, so `[p, p]`
    collapses to one path and it returns `[]`, which is what the docstring
    claiming otherwise had made nobody check.
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    p = tmp_path / "p.json"
    p.write_text(json.dumps(_chunk([_node("n1")], [])))

    assert chunks.assembly_overlaps([p, p]) == [], (
        "PRECONDITION: assembly_overlaps is silent here, which is why assemble must not be"
    )
    with pytest.raises(ValueError, match="passed more than once"):
        chunks.assemble(tmp_path, "dupe", [p, p])


def test_a_repeat_is_refused_by_its_spelling_not_its_string(tmp_path) -> None:
    """CONTROL on the identity: two spellings of one file are still one file.

    Comparing the raw arguments would miss this and let the duplicate through,
    which is the same too-narrow identity the `_labels` fix was about.

    The second spelling uses `..` and NOT `.`, and that is the whole test. A `.`
    component is removed by `PurePath` at construction, so `tmp_path / "." /
    "p.json"` is already EQUAL to `tmp_path / "p.json"` and a raw-argument
    comparison would pass — the first version of this arm used it, the mutation
    survived, and the mutant was inert rather than the code being covered. `..`
    cannot be normalised without touching the filesystem, so only `resolve()`
    collapses it, which is exactly the property under test.
    """
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    (tmp_path / "sub").mkdir()
    p = tmp_path / "p.json"
    p.write_text(json.dumps(_chunk([_node("n1")], [])))
    detour = tmp_path / "sub" / ".." / "p.json"
    assert detour != p, "PRECONDITION: the two spellings must differ before resolve()"
    assert detour.resolve() == p.resolve()

    with pytest.raises(ValueError, match="passed more than once"):
        chunks.assemble(tmp_path, "dupe", [p, detour])


def test_two_different_chunks_are_still_assembled(tmp_path) -> None:
    """CONTROL ARM: the refusal must not have made ordinary assembly refuse."""
    (tmp_path / "sources" / "extractions").mkdir(parents=True)
    p = tmp_path / "p.json"
    q = tmp_path / "q.json"
    # Distinct `source_file` values, or `assembly_overlaps` refuses for its own
    # (correct) reason and this arm would pass without testing the new refusal.
    p.write_text(json.dumps(_chunk([_node("n1", source_file="one.md")], [])))
    q.write_text(json.dumps(_chunk([_node("n2", source_file="two.md")], [])))

    out = chunks.assemble(tmp_path, "twochunks", [p, q])
    assert sorted(n["id"] for n in json.loads(out.read_text())["nodes"]) == ["n1", "n2"]


# --- replay_order: capture-date supersession, not the alphabet (#186) ---------
#
# build_merge gives a source_file to the LAST chunk that names it, so replay
# order IS the supersession rule. The fixture names are chosen so alphabetical
# order and capture order fully DISAGREE — an accidental revert to the sorted()
# glob cannot pass these by coincidence.


def _dated_chunk(tmp_path: Path, name: str, dates: list[str | None]) -> Path:
    p = tmp_path / name
    nodes = [
        {"id": f"{name}_{i}", **({"captured_at": d} if d else {})} for i, d in enumerate(dates)
    ]
    p.write_text(json.dumps({"nodes": nodes, "edges": []}))
    return p


def test_replay_order_is_capture_date_order_newest_last(tmp_path) -> None:
    a = _dated_chunk(tmp_path, "a-newest.json", ["2026-08-05"])
    b = _dated_chunk(tmp_path, "b-oldest.json", ["2026-07-01"])
    c = _dated_chunk(tmp_path, "c-middle.json", ["2026-07-20"])

    assert chunks.replay_order([a, b, c]) == [b, c, a]


def test_replay_order_key_is_the_chunks_newest_node_date(tmp_path) -> None:
    """A chunk assembled across days sorts by its newest capture, not its first."""
    mixed = _dated_chunk(tmp_path, "a-mixed.json", ["2026-07-01", "2026-08-04"])
    single = _dated_chunk(tmp_path, "b-single.json", ["2026-07-20"])

    assert chunks.replay_order([mixed, single]) == [single, mixed]


def test_replay_order_undated_sorts_first_and_ties_break_by_name(tmp_path) -> None:
    """A chunk with no capture date can never supersede a dated one.

    It sorts FIRST (every dated chunk replays after it, and wins), and two
    equal keys fall back to the filename so the order stays total — the same
    corpus must produce the same replay sequence on every machine.
    """
    undated = _dated_chunk(tmp_path, "z-undated.json", [None])
    tie_b = _dated_chunk(tmp_path, "b-tie.json", ["2026-07-20"])
    tie_a = _dated_chunk(tmp_path, "a-tie.json", ["2026-07-20"])

    assert chunks.replay_order([tie_b, undated, tie_a]) == [undated, tie_a, tie_b]


def test_chunk_captured_at_unreadable_file_is_empty_not_an_error(tmp_path) -> None:
    """Ordering must not crash on a broken file.

    `validate_files` is where a broken chunk gets refused with a real message,
    and `build()` runs it first.
    """
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")

    assert chunks.chunk_captured_at(bad) == ""


def test_validate_flags_a_malformed_captured_at() -> None:
    """A malformed date must die in validation, not win the sort.

    "zzz" compares greater than any year lexically, so it would take the
    last-writer supersession win from a real date (cold lane round 2, P2).
    """
    c = _chunk([_node("a", captured_at="zzz")], [])
    assert any("captured_at" in i for i in chunks.validate(c))


def test_validate_flags_a_non_string_captured_at() -> None:
    c = _chunk([_node("a", captured_at=20260805)], [])
    assert any("captured_at" in i for i in chunks.validate(c))


def test_a_null_captured_at_stays_legal() -> None:
    """CONTROL ARM: graphify-docs.json predates the field and carries nulls.

    A null sorts FIRST via `chunk_captured_at`'s `or ""` — the harmless
    direction, since it can never supersede — so refusing it would break a
    committed chunk for no protective gain.
    """
    c = _chunk([_node("a", captured_at=None)], [])
    assert chunks.validate(c) == []
