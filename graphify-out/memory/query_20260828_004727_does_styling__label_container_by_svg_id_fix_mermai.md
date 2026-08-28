---
type: "query"
date: "2026-08-28T00:47:27.549201+00:00"
question: "does styling .label-container by SVG id fix mermaid dark-on-dark text in artifacts"
contributor: "graphify"
outcome: "corrected"
correction: "The mermaid dark-on-dark defect was NOT fixed by the id-targeted rule set that styles `.label-container` — that rule styles the node GROUP, and for stadium `([...])` shapes the renderer emits `<g class=\"basic label-container outer-path\"><path>`: mermaid's theme styles the `path` directly, and a directly styled element beats an inherited group fill every time. Measured 2026-08-27 in the Mermaid Chart MCP's rawSVG. The fix is element-level — `svg[id^=\"claude-mermaid\"] .node :is(rect, path, polygon, circle, ellipse):not([style*=\"fill\"]) { fill:#f2f2f4 !important }` — plus giving every node a classDef so its palette rides inline. Fourth revision of this fix; the first three were each published as fixed. Still BLOCKED on a human reading the render.\n"
---

# Q: does styling .label-container by SVG id fix mermaid dark-on-dark text in artifacts

## Answer

The mermaid dark-on-dark defect was NOT fixed by the id-targeted rule set that styles `.label-container` — that rule styles the node GROUP, and for stadium `([...])` shapes the renderer emits `<g class="basic label-container outer-path"><path>`: mermaid's theme styles the `path` directly, and a directly styled element beats an inherited group fill every time. Measured 2026-08-27 in the Mermaid Chart MCP's rawSVG. The fix is element-level — `svg[id^="claude-mermaid"] .node :is(rect, path, polygon, circle, ellipse):not([style*="fill"]) { fill:#f2f2f4 !important }` — plus giving every node a classDef so its palette rides inline. Fourth revision of this fix; the first three were each published as fixed. Still BLOCKED on a human reading the render.


## Outcome

- Signal: corrected
- Correction: The mermaid dark-on-dark defect was NOT fixed by the id-targeted rule set that styles `.label-container` — that rule styles the node GROUP, and for stadium `([...])` shapes the renderer emits `<g class="basic label-container outer-path"><path>`: mermaid's theme styles the `path` directly, and a directly styled element beats an inherited group fill every time. Measured 2026-08-27 in the Mermaid Chart MCP's rawSVG. The fix is element-level — `svg[id^="claude-mermaid"] .node :is(rect, path, polygon, circle, ellipse):not([style*="fill"]) { fill:#f2f2f4 !important }` — plus giving every node a classDef so its palette rides inline. Fourth revision of this fix; the first three were each published as fixed. Still BLOCKED on a human reading the render.
