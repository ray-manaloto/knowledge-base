// kb-extract — retired host-agent route.
//
// This saved Workflow cannot launch the managed subscription CLI with the
// capture, receipt, cache, and path-boundary contract required by this KB.
// It remains as an explicit migration guard for callers that remember its name.

export const meta = {
  name: 'kb-extract',
  description: 'Retired: migrate prose extraction to mise run kb-graphify-ingest',
}

throw new Error(
  'kb-extract: this host-agent Workflow is retired. Write a graphify-ingest request JSON ' +
    'as documented by the kb-graphify-ingest skill, then run ' +
    '`mise run kb-graphify-ingest -- REQUEST.json` from the knowledge-base worktree.',
)
