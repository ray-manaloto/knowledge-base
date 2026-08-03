"""`scope = study` sources are ingested, but never into the corpus aggregate.

Why this exists. P2 pinned three peer retrieval tools for a gap analysis and the
build died:

    graph.json : 544,865,898 bytes  (519.6 MiB)
    cap        : 536,870,912 bytes  (512 MiB)
    OVER by    :   7,994,986 bytes  (7.6 MiB)

The estimate that authorised the ingestion was ~3x light, and the reason is
worth keeping: it measured *source -> sub-graph* expansion (1.3x) and never
measured *sub-graph -> aggregate growth*. Merging 71.0 MB of sub-graphs into a
364 MiB aggregate added >=155 MiB, because `merge-graphs` re-namespaces ids and
expands edges on every merge — the same mechanism that made a repeated
self-merge duplicate rather than dedupe.

So a repo can be an OBJECT OF STUDY without being corpus. `scope = study` keeps
it fully ingested — no exclusions, which was the standing instruction — while
routing it to its own graph. Nothing in a gap analysis needs those nodes ranked
alongside the corpus; it needs to read and query them, which a separate graph
does equally well.
"""

from __future__ import annotations

from pathlib import Path

from conftest import merge_recorder
from kb_setup import graph
from kb_setup import manifest as mf


def _manifest(tmp_path: Path, name: str, scope: str = "corpus") -> None:
    src = tmp_path / "sources"
    (src / name).mkdir(parents=True, exist_ok=True)
    (src / f"{name}.manifest").write_text(
        f"url = https://example.invalid/o/{name}\n"
        f"ref = main\n"
        f"commit = 03853a019423ffb5c5082e24c39ac20e38a7cfb1\n"
        f"kind = code\n"
        f"scope = {scope}\n",
        encoding="utf-8",
    )


def _build(monkeypatch, tmp_path: Path) -> list[list[str]]:
    calls: list[list[str]] = []
    # `aaa-corpus` sorts first. Since #120 there is no SEED — every corpus source
    # goes into one `merge-graphs` call — but sort order is still load-bearing:
    # it is what the ordering test below manipulates to try to get a study source
    # in ahead of the corpus.
    _manifest(tmp_path, "aaa-corpus")
    _manifest(tmp_path, "mmm-corpus2")
    _manifest(tmp_path, "zzz-study", scope="study")
    (tmp_path / "sources" / "extractions").mkdir(parents=True, exist_ok=True)

    for name in ("aaa-corpus", "mmm-corpus2", "zzz-study"):
        sub = tmp_path / "sources" / name / "graphify-out" / "graph.json"
        sub.parent.mkdir(parents=True, exist_ok=True)
        # Content differs PER SOURCE so the seeding test can name which one won.
        # Identical bytes would make "the corpus was seeded correctly" unfalsifiable.
        sub.write_text(f'{{"nodes": [], "edges": [], "from": "{name}"}}', encoding="utf-8")

    monkeypatch.setattr(graph, "_clear_stamp", lambda _root: None)
    monkeypatch.setattr(graph, "_ensure_clone", lambda _m: None)
    monkeypatch.setattr(graph, "_extract_code", lambda _root, _name: True)
    monkeypatch.setattr(graph, "_stamp_build", lambda _root, _inputs: None)
    monkeypatch.setattr(graph.prose, "derive_for", lambda _root: None)
    monkeypatch.setattr(graph, "_run", merge_recorder(calls))

    graph.build(tmp_path)
    return calls


def test_a_study_source_never_reaches_the_corpus_graph(monkeypatch, tmp_path):
    """The whole point: study nodes must not land in graphify-out/graph.json.

    Realistic break: dropping the scope partition from `build()`, so every
    manifest merges into the aggregate again — which is exactly the state that
    blew the 512 MiB cap.
    """
    calls = _build(monkeypatch, tmp_path)
    into_corpus = [
        c for c in calls if "merge-graphs" in c and c[-1].endswith("graphify-out/graph.json")
    ]
    joined = " ".join(a for c in into_corpus for a in c)

    assert "mmm-corpus2" in joined, (
        f"a normal corpus source stopped being merged — the partition is too "
        f"greedy, not too lax; merge argv were {into_corpus}"
    )
    assert "zzz-study" not in joined, (
        f"a scope=study source was merged into the CORPUS graph; merge argv were "
        f"{into_corpus}. That is what took graph.json 7.6 MiB past the 512 MiB cap."
    )


def test_a_study_source_is_still_ingested_into_the_study_graph(monkeypatch, tmp_path):
    """CONTROL ARM: excluding is not the same as ingesting elsewhere.

    Without this, `build()` could satisfy the test above by simply DROPPING every
    study source — the cheapest wrong fix, and one that silently discards the
    repos P2 exists to analyse while every gate stays green. Ray's instruction was
    "ingest all three, NO exclusions"; this is the assertion that holds us to it.
    """
    _build(monkeypatch, tmp_path)
    study_graph = tmp_path / "graphify-out" / graph.STUDY_GRAPH_NAME

    # An ARTIFACT claim, not an argv one. With a single study source there is no
    # `merge-graphs` call at all — it is seeded by copy, exactly as the corpus is
    # — so an argv-based assertion would fail against a correct implementation.
    # Asserting the file's content covers both the one-source and many-source
    # shapes, which is what makes it the right level to assert at.
    assert study_graph.is_file(), (
        "no study graph was written — the study source was dropped rather than "
        "routed, which discards the repos this scope exists to ingest"
    )
    content = study_graph.read_text(encoding="utf-8")
    assert "zzz-study" in content, (
        f"the study graph did not come from the study source: {content!r}"
    )
    assert "aaa-corpus" not in content, f"a corpus source leaked into the study graph: {content!r}"


def test_a_study_source_never_seeds_the_corpus_graph(monkeypatch, tmp_path):
    """A study repo must not reach the corpus graph by sorting first.

    Originally: `build()` seeded graph.json by copying the FIRST code-bearing
    source, so a partition applied only to the merge loop would still let a study
    repo seed the aggregate whenever it sorted ahead of the corpus ones — silently
    and totally, because the corpus would then simply BE the study repo.

    THE SEED IS GONE since #120 — every corpus source is composed in one
    `merge-graphs` call — so that specific mechanism can no longer fire. The test
    is kept rather than deleted because the property it guards did not go away
    with its mechanism: the partition is still computed from a sorted source list,
    and a future edit that partitions the merge inputs but not the list they are
    drawn from would reintroduce it in a new shape. The name is kept too, so the
    history stays greppable from the issue that produced it.
    """
    name = "a-study-sorts-first"
    _manifest(tmp_path, name, scope="study")
    sub = tmp_path / "sources" / name / "graphify-out" / "graph.json"
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_text(f'{{"nodes": [], "edges": [], "from": "{name}"}}', encoding="utf-8")

    assert mf.load(tmp_path / "sources" / f"{name}.manifest").scope == "study", (
        "fixture is wrong: this manifest must be scope=study for the arm to mean anything"
    )
    assert name < "aaa-corpus", "fixture is wrong: it must sort ahead of every corpus source"

    _build(monkeypatch, tmp_path)

    composed = (tmp_path / "graphify-out" / "graph.json").read_text(encoding="utf-8")
    assert name not in composed, (
        f"a scope=study source reached the corpus graph by sorting ahead of every "
        f"corpus one; graph.json holds {composed!r}. Partitioning the merge inputs "
        f"is not enough if the list they are drawn from is not partitioned too."
    )
    assert "aaa-corpus" in composed, (
        f"graph.json did not receive the first CORPUS source; it holds {composed!r}"
    )
