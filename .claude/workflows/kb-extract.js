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
//       capturedAt: '2026-08-02',             // REQUIRED — see below
//       sources: [
//         { key: 'addyosmani', path: '/abs/raw/addyosmani.md',
//           url: 'https://addyosmani.com/blog/agent-harness-engineering/',
//           kind: 'article', note: 'optional context' },
//         // kind ∈ article | doc | designdoc | research_json | inventory | article_partial
//       ],
//     },
//   })
// Returns { total, succeeded, results:[{key,wrote,node_count,edge_count,notes}] }.
//
// `capturedAt` is REQUIRED and has no default, deliberately (#93). It was the
// literal "2026-07-23" in both prompts, so every node any run emitted carried
// that date regardless of when it ran. A default cannot be computed here —
// `Date.now()` / `new Date()` THROW inside a Workflow script (they would break
// resume) — so the only honest options are "passed in" or "silently wrong", and
// this throws rather than stamping a lie onto every node.

export const meta = {
  name: 'kb-extract',
  description: 'Host-agent semantic extraction of source docs into graphify {nodes,edges} chunks',
  phases: [{ title: 'Extract', detail: 'one agent per source -> schema-valid chunk written to scratchDir' }],
}

// Accept args as an object OR as a JSON-encoded string. The Workflow tool documents
// that objects should be passed verbatim, but some invocation paths serialize args
// to a string before the script sees it — in which case `cfg.sources` is undefined
// and the guard below fires with a message that (misleadingly) blames the caller's
// shape. Parsing a string arg first makes the contract hold either way.
// Observed 2026-07-24: two consecutive `name: 'kb-extract'` invocations with a
// well-formed object both arrived as strings and threw here.
let cfg = args || {}
if (typeof cfg === 'string') {
  try {
    cfg = JSON.parse(cfg)
  } catch (e) {
    throw new Error(`kb-extract: args arrived as a string that is not valid JSON: ${e.message}`)
  }
}
const scratchDir = cfg.scratchDir
const sources = cfg.sources
const capturedAt = cfg.capturedAt
if (!scratchDir || !Array.isArray(sources) || sources.length === 0) {
  throw new Error(
    `kb-extract: args must be {scratchDir, capturedAt, sources:[{key,path,url,kind?,note?}]} ` +
      `(got typeof=${typeof cfg}, scratchDir=${JSON.stringify(scratchDir)}, ` +
      `sources=${Array.isArray(sources) ? `array(${sources.length})` : typeof sources})`,
  )
}
// Fail CLOSED on a missing/malformed date. The defect this replaces was a
// hardcoded literal that stamped every node with one date forever; falling back
// to any default here would reproduce it with extra steps.
// Shape THEN calendar. A digit-shape regex alone accepts 2026-13-40 and 0000-00-00,
// which would then be stamped onto every node of the whole fan-out — the same
// silently-wrong-date failure this check exists to prevent, just harder to spot
// than the frozen literal it replaced. `new Date()` is unavailable here, so the
// range check is explicit arithmetic including the leap-year rule.
const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(capturedAt ?? '')
let calendarOk = false
if (typeof capturedAt === 'string' && m) {
  const y = +m[1], mo = +m[2], d = +m[3]
  const leap = (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0
  const dim = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  calendarOk = y >= 1970 && mo >= 1 && mo <= 12 && d >= 1 && d <= dim[mo - 1]
}
if (!calendarOk) {
  throw new Error(
    `kb-extract: args.capturedAt is REQUIRED and must be a REAL ISO date "YYYY-MM-DD" ` +
      `(got ${JSON.stringify(capturedAt)}). It cannot be defaulted — Date.now()/new Date() ` +
      `throw inside a Workflow script — so the invoking session must pass today's date.`,
  )
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['key', 'wrote', 'node_count', 'edge_count', 'hyperedge_count'],
  properties: {
    key: { type: 'string' },
    wrote: { type: 'boolean' },
    node_count: { type: 'integer' },
    edge_count: { type: 'integer' },
    hyperedge_count: { type: 'integer' },
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
  { "nodes": [...], "edges": [...], "hyperedges": [...], "input_tokens": 0, "output_tokens": 0 }

NODE object (exact keys):
  id          : globally-unique slug, MUST start with "${s.key}_" then a short concept slug (snake_case). Never reuse an id.
  label       : short human name of the concept/entity.
  _origin     : "semantic"   <- EXACTLY this literal on EVERY node. Not optional.
  file_type   : "concept"
  source_file : "${file}"
  source_url  : "${s.url}"
  captured_at : "${capturedAt}"
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

EDGE DIRECTION — read every edge aloud as the sentence "<source> <relation> <target>".
If that sentence is FALSE, you have the edge backwards. Emit it in the direction
that makes the sentence true. The rules that decide it:
  part_of                  : MEMBER -> CONTAINER. "retry_policy part_of http_client",
                             NEVER "http_client part_of retry_policy". This is the one
                             most often inverted — a previous run emitted all 22 of its
                             part_of edges backwards — so check each one individually.
  requires / depends_on    : DEPENDENT -> DEPENDENCY. "cache requires redis".
  enables / defines /
  mitigates / verifies /
  routes_to                : the ACTOR -> the thing it acts on. "gate verifies receipt".
  contrasts_with           : symmetric in meaning — emit exactly ONE edge, not both.
Do NOT flip a whole relation type at the end as a batch. Direction is decided per
edge from the source text; a blanket flip breaks the ones that were already right.

HYPEREDGE object (exact keys) — emit these now; the array is no longer suppressed:
  id               : snake_case, MUST start with "${s.key}_" then a short slug. The
                     prefix is what makes a collision between two sources'
                     hyperedge ids IMPOSSIBLE in the first place — kb-assemble
                     unions every chunk's hyperedges into one file and REFUSES a
                     duplicate id across chunks if one happens anyway, but the
                     prefix is what stops it from happening. An unprefixed name
                     like "three_pass_extraction" is exactly the kind two
                     sources both reach for — it is a REAL committed id in
                     sources/extractions/graphify-docs.json today, with no
                     prefix, because it predates this rule (all five committed
                     hyperedge ids do). The rule binds NEW chunks; the
                     committed five are grandfathered, not a model to copy.
  label            : short human name of the shared concept.
  nodes            : THREE OR MORE node ids, every one of them defined in THIS
                     chunk. A member that does not resolve is rejected by
                     kb-assemble (kb-validate-chunks only catches it too when
                     checking this chunk alone — its normal multi-file
                     invocation resolves endpoints against the UNION of every
                     chunk passed to it, so a member dangling in this chunk but
                     defined in a sibling chunk would pass there), and graphify
                     drops the whole hyperedge once no member survives.
  relation         : participate_in | implement | form
  confidence       : "EXTRACTED" | "INFERRED" — never AMBIGUOUS. That tier exists
                     for edges only; graphify's hyperedge schema does not have it
                     and kb-validate-chunks refuses one that carries it.
  confidence_score : 1 for EXTRACTED, 0.5 for INFERRED (same as edges).
  source_file      : "${file}"

WHEN to emit one: only when 3+ nodes genuinely co-participate in ONE concept,
flow, or pattern that the pairwise edges do not already capture — a pipeline
whose stages are each a node, a threat model and the mitigations that together
address it, a decision and the constraints that jointly force it. If the group
is fully described by the edges you already wrote, the hyperedge adds nothing:
leave it out. MAXIMUM 3 per chunk, and \`[]\` is a perfectly good answer.

WHY \`_origin: "semantic"\` IS MANDATORY: graphify 0.9.32+ decides a node's tier from
\`_origin\` when present, and otherwise GUESSES from shape — a \`source_location\` that
looks like \`L<line>\` is read as AST. Extraction agents have emitted \`source_location\`
values like "L5" unprompted (this prompt never asked for the field), and that guess
silently deleted **629 nodes** from the prose graph in one build, with no error. The
literal marker makes the guess unreachable. \`mise run kb-validate-chunks\` REJECTS a
chunk whose nodes lack it.

Rules: only connect nodes that exist in THIS chunk (hyperedge members included); prefer faithful EXTRACTED edges; mark reasoned links INFERRED honestly; never invent facts not in the source.

After building the chunk, WRITE it (Write tool) to:
  ${scratchDir}/${s.key}.json
Then your FINAL output is ONLY the StructuredOutput {key:"${s.key}", wrote:true, node_count, edge_count, hyperedge_count (how many hyperedges you emitted, 0 if none), notes (any quality caveat, e.g. paywalled/partial/truncated)}.`
}

function inventoryPrompt(s) {
  const file = basename(s.path)
  return `You are a knowledge-graph extractor. Read the ENTIRE file at:
  ${s.path}
It is a curated inventory (one entry per item, e.g. marketplace plugins).${s.note ? `\nContext: ${s.note}` : ''}

Produce a graphify chunk { "nodes":[...], "edges":[...], "hyperedges":[], "input_tokens":0, "output_tokens":0 }.
Leave "hyperedges" EMPTY here even though the general extraction prompt now populates it:
an inventory is item -> category and nothing else, which the pairwise part_of edges below
already say in full. A hyperedge over "every item in this category" would restate them.
- One NODE per item: id "${s.key}_" + item-slug (snake_case, globally unique); label = item name; **_origin "semantic"** (exactly this literal, on every node, mandatory); file_type "concept"; source_file "${file}"; source_url "${s.url}"; captured_at "${capturedAt}"; author null; contributor null; rationale = the item's one-line purpose/category.
- ALSO create category NODES (id "${s.key}_cat_<slug>") for the main categories present.
- EDGES: each item -> its category node, relation "part_of", confidence "EXTRACTED", confidence_score 1, source_file "${file}", weight 1.
  DIRECTION: source = the ITEM, target = the CATEGORY (member -> container). Read it
  aloud — "<item> part_of <category>" must be a true sentence; the reverse is not.
Capture as many items as the file lists; do not invent entries.

WRITE the chunk (Write tool) to ${scratchDir}/${s.key}.json.
FINAL output = ONLY the StructuredOutput {key:"${s.key}", wrote:true, node_count, edge_count, hyperedge_count:0 (this prompt emits none), notes}.`
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
