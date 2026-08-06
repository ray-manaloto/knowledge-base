"""Host-agent extraction chunks — validate + assemble into a committed doc chunk.

A *chunk* is the JSON a host-agent extraction produces for one source:
`{"nodes": [...], "edges": [...], "hyperedges": [], "input_tokens", "output_tokens"}`.
`kb-build` replays each committed `sources/extractions/*.json` chunk into the graph
(free, no LLM), so the chunk — not the raw fetched body — is the durable artifact.

This module is the reusable seam that USED to be an inline one-off: per-source
extraction chunks (written by the `kb-extract` Workflow fan-out) are validated
against the schema `_merge_docs.py` expects, then union-assembled into one
committed `sources/extractions/<name>-docs.json`. Driven by the mise tasks
`kb-assemble` / `kb-validate-chunks`; logic here so nothing hand-rolls it.
"""

from __future__ import annotations

import json
from pathlib import Path

# The exact node/edge shape graphify's doc merge (`_merge_docs.py` -> build_merge)
# consumes. Kept in sync with the committed chunks under sources/extractions/.
_NODE_REQUIRED = ("id", "label", "file_type", "source_file", "source_url", "captured_at")
_EDGE_REQUIRED = ("source", "target", "relation", "confidence", "confidence_score", "weight")
#: Edges only. Hyperedges have a NARROWER tier set — see `_HYPEREDGE_CONFIDENCE`
#: below — so widening this tuple (issue #177 will add AMBIGUOUS for edges) must
#: not be done by editing the hyperedge constant to match.
_CONFIDENCE = ("EXTRACTED", "INFERRED")

#: Hyperedges are EXTRACTED|INFERRED ONLY, never AMBIGUOUS — a narrower set than
#: `_CONFIDENCE` above, and DELIBERATELY a separate literal tuple rather than an
#: alias/slice/subset of it. graphify's own extraction schema spells the two
#: tiers differently in the same schema line
#: (`.claude/skills/graphify/references/extraction-spec.md:64`): the edge
#: object reads `"confidence":"EXTRACTED|INFERRED|AMBIGUOUS"` while the
#: hyperedge object two fields later reads `"confidence":"EXTRACTED|INFERRED"`.
#: Issue #177 will widen `_CONFIDENCE` to admit AMBIGUOUS for edges; if this
#: constant were derived from that one instead of standing on its own, the
#: widening would silently start permitting an AMBIGUOUS hyperedge that
#: graphify's schema forbids. Measured against the live corpus 2026-08-05: all
#: 5 committed hyperedges (`graphify-docs.json` x2, `media-docs.json` x3) carry
#: `confidence` and all 5 are EXTRACTED or INFERRED, so this rejects nothing
#: that exists today.
_HYPEREDGE_CONFIDENCE = ("EXTRACTED", "INFERRED")

#: graphify's own extraction spec defines a hyperedge as "3 or more nodes"
#: (`.claude/skills/graphify/references/extraction-spec.md:38`), and
#: `.claude/workflows/kb-extract.js` instructs agents to emit "THREE OR MORE
#: node ids" — so fewer than three members is an agent error under OUR OWN
#: contract. graphify itself tolerates fewer: `build.py` carries a comment
#: saying "single-member hyperedges are legal in this codebase, e.g. a
#: per-file flow". This is deliberately STRICTER than the tool — we control
#: the prompt, and a 2-member "hyperedge" is just an edge wearing a costume.
#: A zero/one/two-member hyperedge also has zero-to-two surviving members by
#: construction once dangling ones are dropped, which is exactly the silent
#: vanishing this validator exists to prevent (#134).
#: Measured backward-compatible 2026-08-05: the five committed hyperedges
#: (`graphify-docs.json` x2, `media-docs.json` x3) carry 3, 4, 5, 6 and 6
#: members, so this rejects nothing that exists today.
_MIN_HYPEREDGE_MEMBERS = 3

#: Every node in a host-agent chunk is semantic BY CONSTRUCTION — a chunk is the
#: output of the LLM extraction wave, and the AST layer never travels this path.
#: Stating it explicitly is not redundancy; it is what keeps graphify from
#: GUESSING, and the guess is wrong for us.
#:
#: graphify 0.9.32 added `_is_ast_tier` (`build.py`), which trusts `_origin` when
#: present and otherwise falls back to SHAPE: a `source_location` matching
#: `^L\d` is read as AST, because deterministic extractors emit `L<line>` and the
#: semantic spec emits null. Our extraction agents emit `L5`, `L13`, … unprompted
#: — `kb-extract.js` never asked for `source_location` at all — so the fallback
#: misread them.
#:
#: Measured on the 0.9.32 rebuild: **629 committed doc nodes** (621 from
#: `claude-docs-docs.json`, 8 from `claude-commands-docs.json`) were stamped
#: `_origin = "ast"` at load and vanished from `graph-prose.json`, taking it from
#: 2,864 nodes to 2,235 — a 22% cut to the surface `kb-query --prose` reads, with
#: no error and no warning. Control arm: chunks carrying `source_location` values
#: that do NOT match `^L\d` (`claude-workflow-blogs-docs` 223/223,
#: `goal-engineering-docs` 290/290) lost nothing, so the predictor is the regex
#: and not the field.
#:
#: Upstream anticipated exactly this — `build_from_json` carries a comment saying
#: fresh semantic chunks "may carry drifted 'L<line>' source_locations … and the
#: shape fallback would misread them as AST" — and guards that one call site with
#: a strict `_origin` check. The LOAD-TIME backfill has no such guard.
#:
#: Requiring it here rather than defaulting it at merge time is deliberate: a
#: default would fix the graph while leaving the committed artifact ambiguous, so
#: the next tool to infer a tier from our chunks would be free to guess again.
_SEMANTIC_ORIGIN = "semantic"


def _node_issues(nodes: list, label: str) -> tuple[list[str], set[str]]:
    """Per-node schema/uniqueness problems; also returns the set of valid ids."""
    issues: list[str] = []
    ids: set[str] = set()
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            issues.append(f"{label}: node[{i}] is not an object")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            issues.append(f"{label}: node[{i}] has no valid string id")
            continue
        if nid in ids:
            issues.append(f"{label}: duplicate node id {nid!r}")
        ids.add(nid)
        missing = [k for k in _NODE_REQUIRED if k not in n]
        if missing:
            issues.append(f"{label}: node {nid!r} missing field(s) {missing}")
        origin = n.get("_origin")
        if origin != _SEMANTIC_ORIGIN:
            issues.append(
                f"{label}: node {nid!r} has _origin={origin!r}, must be "
                f"{_SEMANTIC_ORIGIN!r} — without it graphify 0.9.32+ infers the tier "
                f"from source_location and reads 'L<line>' as AST, which silently "
                f"drops the node from graph-prose.json (629 lost that way)"
            )
    return issues, ids


def _edge_issues(edges: list, ids: set[str], label: str) -> list[str]:
    """Per-edge problems: missing fields, dangling endpoints, bad confidence.

    An endpoint is checked with `isinstance(..., str)` BEFORE the `in ids`
    membership test, not after, and never simply coerced with `str()` into the
    existing dangling message. `x not in ids` against a `set[str]` raises
    `TypeError` when `x` is unhashable (a dict or list) rather than returning
    False — an agent emitting `{"source": {"id": "a"}, ...}` used to crash
    `validate()` out of its own "never raises" contract (see that function's
    docstring) instead of producing an ISSUE. A `str()` coercion would have
    avoided the crash while producing `"{'id': 'a'} dangling"`, which sends the
    reader hunting for a missing node when the real problem is the shape.
    """
    issues: list[str] = []
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            issues.append(f"{label}: edge[{i}] is not an object")
            continue
        missing = [k for k in _EDGE_REQUIRED if k not in e]
        if missing:
            issues.append(f"{label}: edge[{i}] missing field(s) {missing}")
            continue
        src, tgt = e["source"], e["target"]
        if not isinstance(src, str):
            issues.append(f"{label}: edge[{i}] source is not a string id: {src!r}")
        elif src not in ids:
            issues.append(f"{label}: edge[{i}] dangling source {src!r}")
        if not isinstance(tgt, str):
            issues.append(f"{label}: edge[{i}] target is not a string id: {tgt!r}")
        elif tgt not in ids:
            issues.append(f"{label}: edge[{i}] dangling target {tgt!r}")
        if e["confidence"] not in _CONFIDENCE:
            issues.append(f"{label}: edge[{i}] confidence {e['confidence']!r} not in {_CONFIDENCE}")
    return issues


def _hyperedge_member_issues(members: object, ids: set[str], i: int, label: str) -> list[str]:
    """Problems with one hyperedge's `nodes`/`members` list: arity, shape, resolution.

    Split out of `_hyperedge_issues`'s loop body so that function stays under
    this repo's complexity gate (`C901`/`PLR0912`) — the check content and
    order are unchanged from when they lived inline. All independent: a
    non-list, a too-short list, a non-string member, and a dangling member are
    each reported without any of the others short-circuiting.
    """
    if not isinstance(members, list):
        return [f"{label}: hyperedge[{i}] has no 'nodes' list"]
    issues: list[str] = []
    if len(members) < _MIN_HYPEREDGE_MEMBERS:
        issues.append(
            f"{label}: hyperedge[{i}] has {len(members)} member(s), needs "
            f"at least {_MIN_HYPEREDGE_MEMBERS} — fewer than that is just "
            f"an edge, and graphify drops the hyperedge outright once "
            f"member resolution leaves it with none"
        )
    non_string = [m for m in members if not isinstance(m, str)]
    if non_string:
        issues.append(f"{label}: hyperedge[{i}] member(s) are not string ids: {non_string!r}")
    missing = [m for m in members if isinstance(m, str) and m not in ids]
    if missing:
        issues.append(f"{label}: hyperedge[{i}] dangling member(s) {missing}")
    return issues


def _hyperedge_issues(hyperedges: object, ids: set[str], label: str) -> list[str]:
    """Members of a hyperedge must resolve, exactly as an edge's endpoints must.

    `validate()` read only `nodes` and `edges` until 2026-08-03, while the chunk
    shape this module documents has always included `hyperedges` — so a whole
    relationship class was outside the gate. Measured, and it was not theoretical:
    `graphify-docs.json` carries `graphify_pipeline_stages` naming SEVEN members
    (`graphify_detect`/`extract`/`build`/`cluster`/`analyze`/`report`/`export`),
    none of which exists in that chunk's 43 nodes — and the validator returned
    clean. graphify drops unresolved members and then drops the hyperedge once
    none survive, so a green gate was permitting a committed relationship to
    vanish at ingestion. That is a large part of why the corpus's own description
    of graphify's pipeline is disconnected (#134). Found by the cold lane, round 2.

    Extended 2026-08-05 (#170, #176) with several more checks, each independent
    of the member-resolution check above — a hyperedge missing its id can still
    have dangling members, and both are reported:

    - `id` must be a non-empty string and unique within `hyperedges`. Without a
      usable id, a duplicate is unnameable and `assemble()`'s combined re-check
      (the only place a CROSS-chunk id collision can be caught) has nothing to
      key on.
    - `confidence` must be present and in `_HYPEREDGE_CONFIDENCE`
      (EXTRACTED|INFERRED). This function never checked `confidence` at all
      before — AMBIGUOUS is an edge-only tier in graphify's schema, and nothing
      stopped a hyperedge from carrying it.
    - `nodes` must have at least `_MIN_HYPEREDGE_MEMBERS` entries — see that
      constant's own docstring for why fewer is an agent error here even
      though graphify itself tolerates it.
    - a member that is not a string (an agent emitting `{"id": "a"}` where a
      bare id belongs) is reported as "not a string id" rather than compared
      against `ids` with `in`. `m not in ids` against a `set[str]` raises
      `TypeError`, not False, when `m` is unhashable — that used to escape
      `validate()`'s own "never raises" contract (see that function's
      docstring) through all three of its callers: `kb-validate-chunks`,
      `kb-assemble` (a `TypeError` instead of the documented `ValueError`), and
      `graphify_ops.merge_chunk` (`mise run kb-merge` printing a traceback
      instead of its `rc=2` refusal).

    A hyperedge that is not a dict skips every further check on it (there is
    nothing to check); every other combination of problems is reported
    together rather than stopping at the first one found.
    """
    if hyperedges is None:
        return []
    if not isinstance(hyperedges, list):
        return [f"{label}: 'hyperedges' is not a list"]
    issues: list[str] = []
    seen_ids: set[str] = set()
    for i, h in enumerate(hyperedges):
        if not isinstance(h, dict):
            issues.append(f"{label}: hyperedge[{i}] is not an object")
            continue
        hid = h.get("id")
        if not isinstance(hid, str) or not hid:
            issues.append(f"{label}: hyperedge[{i}] has no valid string id")
        elif hid in seen_ids:
            issues.append(f"{label}: duplicate hyperedge id {hid!r}")
        else:
            seen_ids.add(hid)
        members = h.get("nodes", h.get("members"))
        issues.extend(_hyperedge_member_issues(members, ids, i, label))
        confidence = h.get("confidence")
        if confidence not in _HYPEREDGE_CONFIDENCE:
            issues.append(
                f"{label}: hyperedge[{i}] confidence {confidence!r} not in "
                f"{_HYPEREDGE_CONFIDENCE} — AMBIGUOUS is an edge tier, never a "
                f"hyperedge one"
            )
    return issues


def validate(
    chunk: object, *, label: str = "chunk", known_ids: set[str] | None = None
) -> list[str]:
    """Return a list of schema/integrity problems in one chunk (empty == clean).

    Checks: the chunk is an object; nodes/edges are lists; every node carries the
    required fields, a non-empty string id and `_origin="semantic"`; ids are
    unique WITHIN the chunk; every edge and hyperedge member resolves; confidence
    is EXTRACTED|INFERRED. Never raises — the caller decides.

    `known_ids` widens endpoint resolution beyond this chunk, and exists because
    the strict per-chunk rule does not match how graphify actually merges.
    `build_merge` loads the nodes already in the graph, prepends them as a base
    chunk, and resolves endpoints against the COMBINED set — so an edge pointing
    at a node contributed by an earlier chunk is legitimate, not dangling.
    Without this, `validate_files` reported four real cross-chunk relationships in
    `goal-and-skills-workflow-docs.json` as dangling; acting on that report
    DELETED them, which is a fix causing the damage it was cleaning up after.
    (Cold lane, round 2 — the round-1 fix was the defect.)

    A single fresh chunk still gets the strict reading: `kb-extract.js` instructs
    agents to "only connect nodes that exist in THIS chunk", so `kb-merge` passes
    no `known_ids` and an unresolved endpoint there is a genuine agent error.
    """
    if not isinstance(chunk, dict):
        # `validate_files` used to hand whatever `json.loads` produced straight
        # to `.get()`, so a valid-JSON array crashed with AttributeError against
        # this function's own "never raises" contract — harmless while only the
        # CLI called it, and an unhandled traceback the moment `build()` and
        # `merge_chunk` did. (Cold lane, round 2.)
        return [f"{label}: top level is {type(chunk).__name__}, expected a JSON object"]
    nodes = chunk.get("nodes")
    edges = chunk.get("edges")
    if not isinstance(nodes, list):
        return [f"{label}: 'nodes' is not a list"]
    if not isinstance(edges, list):
        return [f"{label}: 'edges' is not a list"]
    issues, ids = _node_issues(nodes, label)
    resolvable = ids | (known_ids or set())
    issues.extend(_edge_issues(edges, resolvable, label))
    issues.extend(_hyperedge_issues(chunk.get("hyperedges"), resolvable, label))
    return issues


def _collect_ids(paths: list[Path]) -> set[str]:
    """Every node id across `paths`, for cross-chunk endpoint resolution."""
    ids: set[str] = set()
    for p in paths:
        try:
            chunk = json.loads(p.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        if not isinstance(chunk, dict):
            continue
        for n in chunk.get("nodes") or []:
            if isinstance(n, dict) and isinstance(n.get("id"), str):
                ids.add(n["id"])
    return ids


def validate_files(paths: list[Path]) -> dict[Path, list[str]]:
    """Validate each chunk file; return {path: issues} (issues empty == clean).

    Endpoints resolve against the UNION of every path passed in, matching what
    graphify does at merge time. Validating a SET is a different question from
    validating one chunk, and conflating them is what made a correct cross-chunk
    edge look like corruption.
    """
    known = _collect_ids(paths) if len(paths) > 1 else None
    out: dict[Path, list[str]] = {}
    for p in paths:
        try:
            chunk = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            out[p] = [f"{p.name}: unreadable/invalid JSON: {e}"]
            continue
        out[p] = validate(chunk, label=p.name, known_ids=known)
    return out


def chunk_captured_at(path: Path) -> str:
    """The chunk's newest node-level `captured_at`, or `""` when none carries one.

    ISO `YYYY-MM-DD` strings, so lexical `max`/`sort` IS date order. An
    unreadable file returns `""` rather than raising: this feeds an ORDERING,
    and `validate_files` (which `build()` runs first) is where a broken chunk
    gets refused with a real message — failing here would just report the same
    defect worse.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return ""
    nodes = data.get("nodes") or []
    dates = [str(n.get("captured_at") or "") for n in nodes if isinstance(n, dict)]
    return max((d for d in dates if d), default="")


def replay_order(paths: list[Path]) -> list[Path]:
    """Committed chunks in the order `build()` must replay them: oldest capture FIRST.

    `build_merge` makes the LAST chunk to name a `source_file` that file's
    owner — it prunes every existing node carrying the same `source_file`
    before adding its own (re-extraction idempotence). Replaying in glob order
    therefore made supersession a NAMING accident, measured on the 2026-08-05
    rebuild: the hooks/skills re-extraction chunk sorts before
    `goal-engineering-docs.json`, whose nodes also say `source_file: hooks.md`,
    so the rebuild silently replaced the fresh page's 69 nodes with the older
    chunk's 13 (`[merge]` line arithmetic: +290 printed, total rose 221) —
    while the incremental `kb-merge`, which runs the new chunk last, did the
    exact reverse to the older chunk. Same committed corpus, two different
    graphs, chosen by the alphabet: invariant 3's precise failure shape.

    Capture date is the order supersession MEANS: a newer extraction of a file
    replaces an older one, identically in the rebuild and the incremental
    path. The key is the chunk's max node `captured_at`; a chunk with none
    sorts first (it can never supersede a dated one), and the filename breaks
    ties so the order stays total and deterministic.
    """
    return sorted(paths, key=lambda p: (chunk_captured_at(p), p.name))


def _out_path(repo_root: Path, name: str) -> Path:
    stem = name.removesuffix(".json").removesuffix("-docs")
    return repo_root / "sources" / "extractions" / f"{stem}-docs.json"


def assemble(repo_root: Path, name: str, chunk_paths: list[Path]) -> Path:
    """Validate + union-merge per-source chunks into one committed doc chunk.

    Each input chunk is validated on its own; then ids are checked for collisions
    ACROSS the set (extraction prefixes ids per source, so a collision is a bug);
    nodes/edges/hyperedges are concatenated (no cross-source dedup — the aggregate
    graph spans many sources, so `_merge_docs.py` merges with dedup=False by
    design). Writes `sources/extractions/<name>-docs.json` and returns its path.
    Raises ValueError on any validation/collision problem — fail loud, never
    write a broken chunk.

    Hyperedges are checked TWICE, at two different levels, and each catches
    something the other cannot (#170, #176):

    - Per-chunk, inside `validate(chunk, ...)` above — an agent error INSIDE one
      chunk: a dangling member, a bad confidence tier, a malformed id. This was
      the only check that existed before 2026-08-05, and it ran on data that was
      then thrown away (`chunks.py:266` used to hardcode `"hyperedges": []` in
      the output, deleting every hyperedge an extraction agent had emitted).
    - Combined, after the loop below, against `_hyperedge_issues(hyperedges,
      set(seen), ...)` — the ARTIFACT THAT ACTUALLY GETS WRITTEN. `seen`'s keys
      are exactly the valid node ids across every input chunk, a SUPERSET of
      what each chunk validated its own hyperedges against above (the per-chunk
      `validate()` call below is passed no `known_ids`), so for a chunk whose
      nodes/edges validated cleanly, this pass cannot surface a NEW dangling
      member — anything still unresolved here was already unresolved
      per-chunk, and `problems` already holds it. That guarantee has one
      exception, and it is not an edge case: `validate()` returns EARLY, before
      `_hyperedge_issues` ever runs, when a chunk's own `nodes` or `edges` key
      is not a list — so that chunk's hyperedges are never checked per-chunk at
      all, and the combined pass here is the FIRST thing to see them. What ONLY
      the combined pass can catch unconditionally, even for a chunk that
      validated perfectly: a hyperedge id collision BETWEEN two different
      chunks — the hyperedge-level analogue of the node `seen` map below, which
      exists for exactly the same reason.
    """
    nodes: list = []
    edges: list = []
    hyperedges: list = []
    seen: dict[str, str] = {}
    problems: list[str] = []

    for p in chunk_paths:
        try:
            chunk = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            problems.append(f"{p.name}: unreadable/invalid JSON: {e}")
            continue
        problems.extend(validate(chunk, label=p.name))
        if not isinstance(chunk, dict):
            # `validate()` already recorded the type-mismatch problem above (the
            # `problems` check below will raise on it) — but `chunk.get(...)`
            # itself is only valid on a dict, so a top-level JSON array/string/
            # number/null reached here and crashed with AttributeError instead
            # of the documented `ValueError` refusal. Same defect class as the
            # non-dict-chunk fix in `validate()` above, one function over and
            # three lines past where that fix stopped (#176 cold review round 2).
            continue
        for n in chunk.get("nodes", []):
            nid = n.get("id") if isinstance(n, dict) else None
            if isinstance(nid, str) and nid:
                if nid in seen and seen[nid] != p.name:
                    problems.append(f"id collision {nid!r} ({p.name} vs {seen[nid]})")
                seen[nid] = p.name
            nodes.append(n)
        edges.extend(chunk.get("edges", []))
        hyperedges.extend(chunk.get("hyperedges") or [])

    # Re-validate the COMBINED hyperedge list against the union of node ids the
    # written artifact will actually contain. Calling `_hyperedge_issues`
    # directly rather than re-running `validate()` on a synthetic combined dict
    # is deliberate: `validate()` would re-report every per-chunk NODE and EDGE
    # problem a second time on top of the hyperedge ones. It does NOT avoid
    # double-reporting a hyperedge problem itself — a hyperedge that was
    # already invalid per-chunk above is reported AGAIN here, once under its
    # own chunk's label and once under "(combined)". That duplication is the
    # accepted cost of also validating the artifact that actually gets written
    # against its own final node set, not something this call sidesteps.
    problems.extend(_hyperedge_issues(hyperedges, set(seen), f"{name} (combined)"))

    if problems:
        raise ValueError(
            f"assemble '{name}': {len(problems)} problem(s):\n  " + "\n  ".join(problems)
        )

    out = _out_path(repo_root, name)
    out.parent.mkdir(parents=True, exist_ok=True)
    combined = {
        "nodes": nodes,
        "edges": edges,
        "hyperedges": hyperedges,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    out.write_text(json.dumps(combined, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
