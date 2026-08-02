# Verifier report — graphify vector path and BM25/FTS5 claims

Persisted verbatim from the `kb-adversarial-verifier` lane, 2026-08-02, during
the Navigable round. Delivered by message rather than written to disk by the
agent itself, so it is captured here before `/clear`. Read against the **pinned
0.9.31** install.

## CLAIM A

**claim:** "graphify has no vector path at all" (no semantic/embedding-based retrieval)
**refuted: FALSE** — claim upheld

**probe** (`~/.local/share/mise/installs/pipx-graphifyy/0.9.31/graphifyy/lib/python3.14/site-packages/graphify`;
PATH `graphify --version` = 0.9.31, so no wrong-artifact hazard):

24 alternate spellings, `grep -rlIiE ... --include='*.py'`:

```
faiss->0  hnsw->0  annoy->0  sentence.transformers->0  np\.dot->0
dot_product->0  knn->0  cosine->0  qdrant->0  chroma->0  pgvector->0
milvus->0  weaviate->0  lancedb->0  usearch->0  sqlite_vec->0  sqlite-vss->0
similarity->19  nearest->20  semantic->114  vector->5  openai->34  embed->50  scann->25
```

Every non-zero one read line-by-line rather than trusted as a count:
`similarity` = rapidfuzz Jaro/JaroWinkler in `dedup.py`; `vector` =
`std::vector`, "SSRF vectors", "vector icons"; `embed` = the English word plus
Go's `"embeds"` edge type; `scann` = substring of "scanned". No vector index in
any of them.

`grep -rniE 'embeddings|\.embed\(|text-embedding|/v1/embeddings' --include='*.py'` → **0**

**control:** token arm `rapidfuzz`→1, `networkx`→21, `jieba`→1 (same command
shape). Endpoint arm `chat.completions|messages.create` → **5 hits**
(`llm.py:1254,1307,1613,2550,2644`), so the endpoint-shaped pattern
discriminates. Corpus arm: 80 `.py` files, not an empty tree.

### OPTIONAL EXTRAS — checked in two forms

*Declared* (`graphifyy-0.9.31.dist-info/METADATA`, all `Provides-Extra`):
`mcp neo4j falkordb pdf watch svg leiden office google postgres video kimi
ollama bedrock anthropic gemini openai chinese sql pascal dm terraform all`.
**No vector/embedding library in any extra, including `all`.** `openai` appears
only under `kimi`/`ollama`/`gemini`/`openai` as a chat client.

*Physically installed* under `extras=["all"]` (255 top-level packages) — and this
found something a metadata-only check would have missed:

```
ctranslate2            ctranslate2-4.8.1.dist-info
onnxruntime            onnxruntime-1.28.0.dist-info
```

onnxruntime is a common embedding runtime, so it was run down:

```
--> Name: faster-whisper
Requires-Dist: ctranslate2<5,>=4.0
Requires-Dist: onnxruntime<2,>=1.14
```

They belong to the `video` extra (transcription + VAD —
`faster_whisper/transcribe.py`, `faster_whisper/vad.py`). graphify's own code:
`grep -rniE 'onnxruntime|ctranslate2|import onnx' --include='*.py'` → **ZERO**,
against a control of `import networkx` → 16 files via the identical shape.

Also cleared: `numpy` is a *core* dep (could host a hand-rolled cosine) but its
only import site is `_minhash.py`, consumed solely by `dedup.py:13` — MinHash/LSH
over *sets* for entity dedup, not a dense-vector retrieval index.

## CLAIM B

**claim:** "graphify has no BM25/FTS5 lexical ranking"
**refuted: TRUE**

**probe:** `grep -rnIi 'idf' --include='*.py'` over the pinned package.

**control:** same shape → 0 for `bm25`, `fts5`, `rank_bm25`, `whoosh`, `okapi`,
`import sqlite3`, `CREATE VIRTUAL TABLE`, `tf.?idf`, `inverted.index`; non-zero
for `rapidfuzz`/`networkx`/`jieba`. Discriminates both directions. stdlib
`sqlite3` was checked explicitly because FTS5 needs no declared dependency —
dependency metadata alone could not have settled this claim.

**evidence** — verbatim, `serve.py`:

```
275:def _compute_idf(G: nx.Graph, terms: list[str]) -> dict[str, float]:
276:    """IDF weights for query terms, cached in G.graph['_idf_cache'].
295:            cache[t] = math.log(1 + N / (1 + df[t]))
468:    idf = _compute_idf(G, norm_terms)
540:            w = idf.get(t, 1.0)
330:def _get_trigram_index(G: nx.Graph) -> dict:
331:    """Lazily build and cache a trigram -> node-position postings map on the graph.
```

Plus `_QUERY_STOPWORDS`, diacritic stripping, jieba CJK segmentation (`serve.py:177`).

Reachable from the CLI, not just the MCP server: `cli.py:852 elif cmd == "query"`
→ `cli.py:856 from graphify.serve import _query_graph_text` → `serve.py:1033` →
`_score_query` → `:468 _compute_idf` → `_pick_seeds`. (`cli.py:1182` also imports
`_score_nodes` directly.)

The literal tokens `bm25`/`fts5` are genuinely absent — the original grep was
**true**, the inference from it inverted. graphify implements IDF-weighted
lexical scoring over a character-trigram inverted index; it just never spells it
"BM25". Textbook token-spelling bound, same shape as `LM Studio`.

0.9.32 cross-check: `_compute_idf`→1, `_trigram_index`→1, vector tokens 0 —
identical in both. Not a pinned-version artifact.

## The verifier's correction to its own probe

Its first 0.9.32 differential reported `_compute_idf → 0`, i.e. "IDF was removed
in 0.9.32". **False.** A `python3.*` glob was placed inside a shell variable; zsh
does not glob-expand variable contents, so grep received a nonexistent literal
path, and `2>/dev/null` swallowed the error into a clean-looking zero. The
uniform negative across *every* token in that column is what gave it away.
Re-run with the literal `python3.14` path and errors visible, both versions
agree. Recorded because it is the same failure class as the claim under test.

## Reconciliation by the orchestrator

The claim handed to this verifier — *"graphify has no BM25/FTS5 lexical
ranking"* — was a loose paraphrase written by the orchestrator, not the wording
of the report it was checking.
`docs/research/reports/code-review-graph-retrieval-gap.md` already credits
graphify with *"IDF-weighted tiered label match"* and scopes its own claim to
BM25 **with Porter stemming**. So the report survives; the paraphrase did not.

Accurate split: **no BM25, no FTS5, no stemming — true; no lexical ranking —
false.**

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — installed
  0.9.31 and 0.9.32 source read directly to settle both claims.
