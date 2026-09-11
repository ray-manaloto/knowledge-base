// kb-settings-guard — deny a DELEGATED LANE any write to the files that switch
// this repo's guards off, while leaving the main thread alone, and while leaving
// a lane working inside its OWN WORKTREE completely alone.
//
// Ray's rulings (2026-09-11, four /grilling rounds):
//   - a function hook, not a classic PreToolUse hook;
//   - deny when the call comes from a subagent, allow otherwise;
//   - WORKTREE-SCOPED: "codex should be able to work on any task as we want".
//     A lane has full authority inside its own worktree and is gated at merge.
//
// ⚠️ NOT YET REGISTERED. This plugin is in neither `extraKnownMarketplaces` nor
// `enabledPlugins`, so nothing here runs. Registration, readiness and liveness
// are ticket G04 (#757) — and note that since Claude Code v2.1.195 an
// external-source plugin enabled only by PROJECT settings does not load until
// each user runs `claude plugin install`, so a `git clone` alone never arms it.
//
// LOADER CONSTRAINTS, each measured on 2.1.268. Violating one makes the module
// fail to load, and that is SILENT unless the session was started with
// `--debug-file`:
//
//   1. Imports are relative paths and "claude-code" only. No node builtins. A
//      `.json` import also fails — the loader compiles every import as
//      TypeScript — while a relative `.ts` import works, which is how the
//      generated path list below arrives.
//   2. `$` may not be READ as a value. `Object.keys($ ?? {})` fails the load.
//      The error text also says "bound, passed, spread, returned" but that
//      OVERSTATES the enforced check: passing `$` to a local function works and
//      is measured. Treat the text as the safe envelope, not the specification.
//   3. `next.to` is always `next.to(e, "<tier>")`.
//
// 🔴 THE SPELLING TRAP. The lane marker on a FUNCTION-hook event is `agentId`
// (camelCase). The CLASSIC hook — and the public docs — spell the same concept
// `agent_id` (snake_case). A guard written from those docs reads `e.agent_id`,
// gets `undefined` on every call, concludes "main thread", and ALLOWS
// EVERYTHING, silently, forever. Absence is the ALLOW signal, so this guard
// CANNOT fail closed on a renamed field; only an end-to-end arm that dispatches
// a real lane and asserts the deny can catch it. A green unit test over this
// file proves nothing about the live wiring.

import { PROTECTED_SUFFIXES } from "./protected-paths";

/**
 * Registered as ONE LITERAL MATCHER PER TOOL, never as a bare `on("tool.call",
 * hook)`.
 *
 * 🔴 This is the `anthropics/claude-code#92533` mitigation and it is not
 * optional. Registering ANY hook that reaches the Bash dispatch breaks every
 * Bash call inside an `Agent(isolation: "worktree")` subagent — a pure
 * passthrough is enough to trigger it. A bare registration sees every tool,
 * Bash included.
 *
 * Measured on 2.1.268: `on(event, matcher, hook)` is real, the matcher is a
 * partial of the event, and `{ tool: "Edit" }` fired on Edit ONLY while an
 * unmatched control registration in the same module saw Bash, Read, Edit and
 * SendUserMessage. Literals rather than one anchored RegExp so the covered
 * inventory is reviewable and each entry is independently armable.
 */
const WRITE_TOOLS: readonly string[] = ["Edit", "Write", "NotebookEdit"];

/**
 * Match on path SEGMENTS, never a substring of the serialized event.
 *
 * The substring form is the measured false positive: `tool.call` also fires for
 * the assistant's own outgoing message, so a pattern tested against the whole
 * event blocked Claude's reply because the reply QUOTED the path.
 *
 * ⚠️ Known limit: this is an exact suffix test, so a case-insensitive alias or a
 * symlinked path reaching the same file is not matched.
 */
export function isProtectedPath(filePath: string): boolean {
  if (typeof filePath !== "string" || filePath.length === 0) return false;
  const normalized = filePath.replace(/\\/g, "/");
  return PROTECTED_SUFFIXES.some(
    (suffix) => normalized === suffix || normalized.endsWith("/" + suffix),
  );
}

/**
 * The lane marker, isolated so the spelling exists exactly once in this module.
 */
export function laneOf(event: { agentId?: unknown }): string | null {
  const id = event?.agentId;
  return typeof id === "string" && id.length > 0 ? id : null;
}

/** Every ancestor directory of a path, nearest first. */
export function ancestorsOf(filePath: string): string[] {
  const parts = filePath.split("/");
  const out: string[] = [];
  for (let i = parts.length - 1; i > 1; i--) out.push(parts.slice(0, i).join("/"));
  return out;
}

/**
 * Is the TARGET FILE inside a linked git worktree?
 *
 * 🔴 This asks about `e.file_path`, NOT about `$.session.cwd()`. An earlier
 * version of this module derived the verdict from the session's cwd alone, so a
 * lane whose session sat in a worktree could write an ABSOLUTE path into the
 * main checkout and be allowed. Worktree authority belongs to the DESTINATION,
 * not to the caller's location.
 *
 * A linked worktree's `.git` is a FILE (holding `gitdir: …`); a main checkout's
 * is a DIRECTORY. Measured both ways on real repos.
 *
 * Returns null when no repo root is found. FAIL DIRECTION: the caller treats
 * null as "main checkout", i.e. the guard stays ACTIVE. A false deny costs a
 * lane one round trip; a false allow costs the guard entirely.
 */
async function targetInLinkedWorktree($: any, filePath: string): Promise<boolean | null> {
  for (const dir of ancestorsOf(filePath)) {
    try {
      const entries = await $.fs.list(dir);
      if (!Array.isArray(entries)) continue;
      const dotGit = entries.find((entry: any) => entry?.name === ".git");
      if (dotGit) return dotGit.kind === "file";
    } catch {
      // unreadable directory — keep walking upward
    }
  }
  return null;
}

/**
 * The hook body, declared at MODULE TOP LEVEL.
 *
 * 🔴 Required by the loader, measured: a hook defined as a local `const`
 * inside `register()` is refused with `the hook "handler" is not a function
 * declared at the top of this file (a function declaration, or a const bound
 * to a function), nor imported from one of the module's own files`.
 */
async function handler($: any, e: any, next: any): Promise<any> {
  try {
    if (e === null || typeof e !== "object") return next(e);

    const lane = laneOf(e);
    if (lane === null) return next(e); // the main thread — Ray's own edits pass

    const filePath = typeof e.file_path === "string" ? e.file_path : "";
    if (!isProtectedPath(filePath)) return next(e);

    const inWorktree = await targetInLinkedWorktree($, filePath);
    if (inWorktree === true) {
      // full authority inside its own worktree; gated at merge
      try {
        $.ui.log(`kb-settings-guard: allowing ${e.tool} on ${filePath} — target is in a linked worktree`);
      } catch {
        // logging must never decide the outcome
      }
      return next(e);
    }

    // Compute the refusal BEFORE logging: an exception thrown by $.ui.log on
    // the critical path would return no denial at all.
    const refusal = {
      deny:
        `kb-settings-guard: a delegated lane may not write ${filePath} in the main checkout. ` +
        `This file switches the guard stack off, so a lane that can edit it can disable ` +
        `every other guard for every future session. Two ways forward: do this work in ` +
        `your own worktree, where you have full authority and the change is gated at ` +
        `merge; or report the change you need and let the main session make it.`,
    };
    try {
      $.ui.log(`kb-settings-guard: denied ${e.tool} on ${filePath} from lane ${lane}`);
    } catch {
      // logging must never decide the outcome
    }
    return refusal;
  } catch (err) {
    // Fail closed on our own error for a protected target, never open. An
    // exception here must not read as permission to proceed.
    try {
      $.ui.log(`kb-settings-guard: internal error, failing closed: ${String(err)}`);
    } catch {
      // nothing left to do
    }
    return {
      deny:
        "kb-settings-guard: the guard errored while deciding this write and is failing " +
        "closed. Report this rather than retrying.",
    };
  }
}

export function register(on: any): void {
  for (const tool of WRITE_TOOLS) {
    on("tool.call", { tool }, handler);
  }
}
