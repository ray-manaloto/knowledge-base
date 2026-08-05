"""kb_setup.chunks — validate + assemble host-agent extraction chunks.

Control-armed both directions: a clean chunk passes AND a broken one (dangling
edge, duplicate id, missing field, bad confidence, cross-chunk id collision)
FAILS — a validator that can only pass is not a validator.
"""

import json

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


def _edge(src: str, tgt: str, **over: object) -> dict:
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


def _chunk(nodes: list[dict], edges: list[dict]) -> dict:
    return {"nodes": nodes, "edges": edges, "hyperedges": [], "input_tokens": 0, "output_tokens": 0}


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
    c1.write_text(json.dumps(_chunk([_node("x_a"), _node("x_b")], [_edge("x_a", "x_b")])))
    c2.write_text(json.dumps(_chunk([_node("y_a")], [])))
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
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
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
    c = _chunk([_node("a")], [])
    c["hyperedges"] = [{"label": "h", "nodes": ["a", "ghost"]}]
    assert any("hyperedge" in i for i in chunks.validate(c, label="c"))

    # CONTROL ARM: a fully-resolvable hyperedge must still pass, or the fix is
    # "reject all hyperedges" — which would have deleted the two VALID ones in
    # graphify-docs.json alongside the broken one. That over-deletion actually
    # happened during this fix and was caught by re-reading the validator output.
    ok = _chunk([_node("a"), _node("b")], [])
    ok["hyperedges"] = [{"label": "h", "nodes": ["a", "b"]}]
    assert chunks.validate(ok, label="c") == []


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
