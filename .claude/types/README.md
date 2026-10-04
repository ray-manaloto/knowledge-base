# Claude function-hook types

The one upstream pin is the `claude-code` row in `schemas/sources.toml`.
The declarations are refreshed through `mise run claude-types-refresh`.
Do not hand-edit `claude-code.d.ts`; the sha check fails closed without its pin.

Refresh fetches the pinned upstream file and runs hk trailing-whitespace,
end-of-file-fixer, mixed-line-ending, and fix-smart-quotes before hashing.
Only the row's sha256 value is rewritten; its field order and spacing stay bound.

`claude-code-mcp.d.ts` is an authored empty merge, intentionally independent
of any generating session's connected MCP servers.

The shared gate and normalization live in `kb_setup.fnhook_gates`;
`kb_setup.claude_types` owns pin reading and refresh for both consumers.
