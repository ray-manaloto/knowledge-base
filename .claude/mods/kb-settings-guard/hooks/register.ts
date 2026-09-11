// kb-settings-guard — deny a DELEGATED LANE any write to the files that switch
// this repo's guards off, while leaving the main thread alone, and while leaving
// a lane working inside its OWN WORKTREE completely alone.
//
// Ray's rulings (2026-09-11, four /grilling rounds):
//   - a function hook, not a classic PreToolUse hook;
//   - deny when the call comes from a subagent, allow otherwise;
//   - WORKTREE-SCOPED: "codex should be able to work on any task as we want".
//     A lane has full authority inside its own worktree and is gated at merge.
//     The guard bites only in the MAIN checkout, where a change to the guard
//     config affects every future session instead of one merge-gated branch.
//
// THREE LOADER CONSTRAINTS, each measured on Claude Code 2.1.268. Violating any
// makes this module fail to load, and that is SILENT unless the session was
// started with `--debug-file`:
//
//   1. Imports are limited to relative paths and "claude-code". No node
//      builtins. A `.json` import also fails — the loader compiles every import
//      as TypeScript, so `./x.json` dies with `does not parse: Unexpected token`.
//      A relative `./x.ts` import works; that is how the generated path list
//      below is delivered.
//   2. `$` may not be READ as a value. `Object.keys($ ?? {})` fails the load
//      with `$ itself is used in a LogicalExpression (bound, passed, spread,
//      returned or read); $ is always spelled $.noun.event(...)`.
//      ⚠️ That message OVERSTATES the real check, measured: `inLinkedWorktree($, cwd)`
//      below PASSES `$` to a local function and loads and runs fine. So the
//      enforced rule is narrower than the error text claims — treat the text as
//      the safe envelope, not as the specification, and re-probe before relying
//      on any particular shape it appears to forbid.
//   3. `on` is always `on("<event>", hook)` and `next.to` always
//      `next.to(e, "<tier>")`.
//
// 🔴 THE SPELLING TRAP. The lane marker on a FUNCTION-hook event is `agentId`
// (camelCase). The CLASSIC settings.json hook spells the same concept
// `agent_id` (snake_case), and snake_case is what the public hooks docs show.
// A guard written from those docs reads `e.agent_id`, gets `undefined` on every
// call, concludes "main thread", and ALLOWS EVERYTHING — silently, forever.
// Absence is the ALLOW signal, so this guard CANNOT fail closed on a renamed
// field. The only real protection is the end-to-end arm that dispatches a live
// lane and asserts the deny. A green unit test over this file proves nothing
// about the live wiring.
//
// 🔴 #92533 (open upstream): registering ANY Bash `tool.call` hook breaks every
// Bash call inside an `Agent(isolation: "worktree")` subagent — a pure
// passthrough is enough to trigger it. This module registers `tool.call`, so it
// is exposed. Nothing in this repo uses that isolation today (grepped
// `.claude/` and `.agents/`), but the first use will break, and the failure
// presents as "worktree isolation was lost", not as this guard.

import { PROTECTED_SUFFIXES } from "./protected-paths";

/** Tools whose payload carries a `file_path` this guard cares about. */
const WRITE_TOOLS: ReadonlySet<string> = new Set(["Edit", "Write", "NotebookEdit"]);

/**
 * Match on path SEGMENTS, never a substring of the serialized event.
 *
 * The substring form is the measured false positive: `tool.call` also fires for
 * the assistant's own outgoing message, so a pattern tested against the whole
 * event blocked Claude's reply because the reply QUOTED the path. Same class as
 * a guard that denies `git commit -m "…settings.json…"`.
 */
export function isProtectedPath(filePath: string): boolean {
  if (typeof filePath !== "string" || filePath.length === 0) return false;
  const normalized = filePath.replace(/\\/g, "/");
  return PROTECTED_SUFFIXES.some(
    (suffix) => normalized === suffix || normalized.endsWith("/" + suffix),
  );
}

/**
 * The lane marker, isolated so the spelling exists exactly once in the codebase.
 * Returns the lane id, or null for the main thread.
 */
export function laneOf(event: { agentId?: unknown }): string | null {
  const id = event?.agentId;
  return typeof id === "string" && id.length > 0 ? id : null;
}

/**
 * A linked git worktree has `.git` as a FILE (containing `gitdir: …`); a main
 * checkout has it as a DIRECTORY. Measured, both arms, on real repos.
 *
 * FAIL DIRECTION, stated because it is a real trade: if the listing throws we
 * return false, i.e. "treat this as the main checkout", i.e. the guard stays
 * ACTIVE. A false deny costs a lane one round trip; a false allow costs the
 * guard entirely. `$.fs.stat` and `$.fs.read` both threw when probed, so only
 * `list` is relied on here.
 */
async function inLinkedWorktree($: any, root: string): Promise<boolean> {
  try {
    const entries = await $.fs.list(root);
    if (!Array.isArray(entries)) return false;
    const dotGit = entries.find((entry: any) => entry?.name === ".git");
    return dotGit?.kind === "file";
  } catch {
    return false;
  }
}

export function register(on: any): void {
  on("tool.call", async ($: any, e: any, next: any) => {
    if (e === null || typeof e !== "object") return next(e);
    if (!WRITE_TOOLS.has(e.tool)) return next(e);

    const lane = laneOf(e);
    if (lane === null) return next(e); // the main thread — Ray's own edits pass

    const filePath = typeof e.file_path === "string" ? e.file_path : "";
    if (!isProtectedPath(filePath)) return next(e);

    const cwd = await $.session.cwd();
    if (await inLinkedWorktree($, cwd)) {
      $.ui.log(`kb-settings-guard: allowing ${e.tool} on ${filePath} — lane ${lane} is in a linked worktree`);
      return next(e); // full authority inside its own worktree; gated at merge
    }

    $.ui.log(`kb-settings-guard: denied ${e.tool} on ${filePath} from lane ${lane} in the main checkout`);
    return {
      deny:
        `kb-settings-guard: a delegated lane may not write ${filePath} in the main checkout. ` +
        `This file switches the guard stack off, so a lane that can edit it can disable ` +
        `every other guard for every future session. Two ways forward: do this work in ` +
        `your own worktree, where you have full authority and the change is gated at ` +
        `merge; or report the change you need and let the main session make it.`,
    };
  });
}
