import type { Register } from "claude-code";

const ESCAPE_HATCH_TOOLS = new Set(["AskUserQuestion", "SendUserMessage"]);

export const register: Register = (on) => {
  on("classic.PreToolUse", { tool: "Read" }, async (_$, e, next) => {
    const result = await next(e);
    if (ESCAPE_HATCH_TOOLS.has(e.tool)) {
      return result;
    }
    return { ...result, additionalContext: "not-an-array" };
  });
};
