// kb-extract — reusable host-agent extraction fan-out.
//
// The Claude-only semantic-extraction step of the kb-curator pipeline, saved so
// the skill COMPOSES it instead of hand-rolling a one-off each ingestion. One
// `agent()` per source reads the raw/vendored file, extracts a graphify
// doc-chunk {nodes, edges}, and WRITES it to <scratchDir>/<key>.json. The caller
// then runs `mise run kb-assemble` to validate + combine, and `mise run kb-merge`
// / `kb-build` to fold into the graph. This is the ONLY LLM path and it is Claude.
//
// Invoke (from a Claude session; args is a plain JSON value):
//   Workflow({
//     name: 'kb-extract',                     // or scriptPath to this file cross-repo
//     args: {
//       scratchDir: '/abs/scratch/extractions',
//       sources: [
//         { key: 'addyosmani', path: '/abs/raw/addyosmani.md',
//           url: 'https://addyosmani.com/blog/agent-harness-engineering/',
//           kind: 'article', note: 'optional context' },
//         // kind ∈ article | doc | designdoc | research_json | inventory | article_partial
//       ],
//     },
//   })
// Returns { total, succeeded, results:[{key,wrote,node_count,edge_count,notes}] }.

export const meta = {
  name: 'kb-extract',
  description: 'Host-agent semantic extraction of source docs into graphify {nodes,edges} chunks',
  phases: [{ title: 'Extract', detail: 'one agent per source -> schema-valid chunk written to scratchDir' }],
}

const cfg = args || {}
const scratchDir = cfg.scratchDir
const sources = cfg.sources
if (!scratchDir || !Array.isArray(sources) || sources.length === 0) {
  throw new Error('kb-extract: args must be {scratchDir, sources:[{key,path,url,kind?,note?}]}')
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'wrote', 'node_count', 'edge_count'],
  properties: {
    key: { type: 'string' },
    wrote: { type: 'boolean' },
    node_count: { type: 'integer' },
    edge_count: { type: 'integer' },
    notes: { type: 'string' },
  },
}

function basename(p) {
  return p.split('/').pop()
}

function commonPrompt(s) {
  const file = basename(s.path)
  return `You are a knowledge-graph extractor for a graphify KB. Read the ENTIRE file at:
  ${s.path}
(use the Read tool; read ALL of it — it may be long).${s.note ? `\nContext: ${s.note}` : ''}

Produce a graphify DOC-EXTRACTION CHUNK: a JSON object
  { "nodes": [...], "edges": [...], "hyperedges": [], "input_tokens": 0, "output_tokens": 0 }

NODE object (exact keys):
  id          : globally-unique slug, MUST start with "${s.key}_" then a short concept slug (snake_case). Never reuse an id.
  label       : short human name of the concept/entity.
  file_type   : "concept"
  source_file : "${file}"
  source_url  : "${s.url}"
  captured_at : "2026-07-23"
  author      : the author name if the doc states one, else null
  contributor : null
  rationale   : 1-3 sentences of SUBSTANCE — the actual claim/definition/decision, self-contained and faithful to the source.

EDGE object (exact keys):
  source, target   : node ids that BOTH exist in this chunk's nodes.
  relation         : snake_case verb (enables, requires, part_of, contrasts_with, mitigates, defines, verifies, routes_to, ...).
  confidence       : "EXTRACTED" if stated verbatim in the source; "INFERRED" if you reasoned it across concepts.
  confidence_score : 1 for EXTRACTED, 0.5 for INFERRED.
  source_file      : "${file}"
  weight           : 1

Rules: only connect nodes that exist in THIS chunk; prefer faithful EXTRACTED edges; mark reasoned links INFERRED honestly; never invent facts not in the source.

After building the chunk, WRITE it (Write tool) to:
  ${scratchDir}/${s.key}.json
Then your FINAL output is ONLY the StructuredOutput {key:"${s.key}", wrote:true, node_count, edge_count, notes (any quality caveat, e.g. paywalled/partial/truncated)}.`
}

function inventoryPrompt(s) {
  const file = basename(s.path)
  return `You are a knowledge-graph extractor. Read the ENTIRE file at:
  ${s.path}
It is a curated inventory (one entry per item, e.g. marketplace plugins).${s.note ? `\nContext: ${s.note}` : ''}

Produce a graphify chunk { "nodes":[...], "edges":[...], "hyperedges":[], "input_tokens":0, "output_tokens":0 }.
- One NODE per item: id "${s.key}_" + item-slug (snake_case, globally unique); label = item name; file_type "concept"; source_file "${file}"; source_url "${s.url}"; captured_at "2026-07-23"; author null; contributor null; rationale = the item's one-line purpose/category.
- ALSO create category NODES (id "${s.key}_cat_<slug>") for the main categories present.
- EDGES: each item -> its category node, relation "part_of", confidence "EXTRACTED", confidence_score 1, source_file "${file}", weight 1.
Capture as many items as the file lists; do not invent entries.

WRITE the chunk (Write tool) to ${scratchDir}/${s.key}.json.
FINAL output = ONLY the StructuredOutput {key:"${s.key}", wrote:true, node_count, edge_count, notes}.`
}

const KIND_NOTE = {
  designdoc:
    '\n\nNOTE: this is one of OUR OWN design docs. Extract the DECISIONS, invariants, components, and their rationales so the design is graph-queryable. Faithful rationales.',
  research_json:
    '\n\nNOTE: this file is JSON of structured research agent-outputs. Extract the DESIGN PATTERNS and findings as concept nodes with faithful rationales; connect related patterns.',
  article_partial:
    '\n\nNOTE: this fetch is PARTIAL (JS-rendered; body may be thin but the section TABLE OF CONTENTS came through). Extract section-level concepts from the TOC with the best rationale the titles + surrounding text support, and flag notes as TOC-only/partial. Do not fabricate claims the text does not contain.',
}

function promptFor(s) {
  if (s.kind === 'inventory') return inventoryPrompt(s)
  return commonPrompt(s) + (KIND_NOTE[s.kind] || '')
}

phase('Extract')
const results = await parallel(
  sources.map((s) => () =>
    agent(promptFor(s), {
      label: 'extract:' + s.key,
      phase: 'Extract',
      schema: SCHEMA,
      agentType: 'general-purpose',
    }),
  ),
)
const ok = results.filter(Boolean)
return { total: sources.length, succeeded: ok.length, results: ok }
