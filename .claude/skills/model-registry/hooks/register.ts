import type { Register } from "claude-code";

type ModelsReport = {
  vendors: { vendor: string; verdict: string; findings: string[]; retiring: string[] }[];
  disabled_by_baseline: boolean;
};

type Services = {
  clock: { now: () => Promise<number> };
  session: { root: () => Promise<string> };
  process: {
    run: (
      argv: readonly string[],
      init?: { cwd?: string; timeoutMs?: number; stdin?: string },
    ) => Promise<{ exitCode: number; stdout: string; stderr: string }>;
  };
};

let cachedReport: ModelsReport | null = null;
let resolvedModel: string | undefined;
let lastRefreshAtMs: number | null = null;
const REFRESH_REUSE_MS = 7_500;
const READ_ONLY_TOOLS = new Set(["Read", "Glob", "Grep", "NotebookRead", "TodoWrite"]);
const ESCAPE_HATCH_TOOLS = new Set(["AskUserQuestion", "SendUserMessage"]);

/** JSON is transport only; every verdict and launch judgement belongs to Python. */
function parseReport(text: string): ModelsReport | null {
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== "object") return null;
  const report = value as Record<string, unknown>;
  if (typeof report.disabled_by_baseline !== "boolean" || !Array.isArray(report.vendors)) return null;
  const vendors = report.vendors;
  if (vendors.length !== 3 || !vendors.every((row: unknown) => {
    if (!row || typeof row !== "object") return false;
    const vendor = row as Record<string, unknown>;
    return ["codex", "agy", "claude"].includes(String(vendor.vendor)) &&
      ["ok", "drift", "invalid", "not_checked"].includes(String(vendor.verdict)) &&
      Array.isArray(vendor.findings) && vendor.findings.every((line: unknown) => typeof line === "string") &&
      Array.isArray(vendor.retiring) && vendor.retiring.every((line: unknown) => typeof line === "string");
  })) return null;
  if (new Set(vendors.map((row: { vendor: string }) => row.vendor)).size !== 3) return null;
  // Retain the complete generated report for Python's typed decoder.
  return value as ModelsReport;
}

async function readReport($: Services): Promise<ModelsReport | null> {
  try {
    const argv = ["mise", "run", "models-check", "--", "--json", "--baseline", "doctor.toml"];
    if (resolvedModel) argv.push("--resolved-model", resolvedModel);
    const child = await $.process.run(argv, { cwd: await $.session.root(), timeoutMs: 45_000 });
    return child.exitCode === 0 ? parseReport(child.stdout) : null;
  } catch {
    return null;
  }
}

function hasInvalid(report: ModelsReport | null): boolean {
  return report !== null && !report.disabled_by_baseline &&
    report.vendors.some((vendor) => vendor.verdict === "invalid");
}

async function classify($: Services, tool: string, command?: string, subagentType?: string): Promise<string | null> {
  if (!cachedReport) return null;
  const root = await $.session.root();
  // Each child owns its stdin snapshot; no state file or cross-session race.
  const snapshot = JSON.stringify(cachedReport);
  try {
    const argv = ["mise", "run", "models-classify", "--", "--report-json", "-", "--tool", tool];
    if (command !== undefined) argv.push("--command", command);
    if (subagentType !== undefined) argv.push("--subagent-type", subagentType);
    const child = await $.process.run(argv, { cwd: root, timeoutMs: 45_000, stdin: snapshot });
    if (child.exitCode !== 0) return null;
    const decision = child.stdout.trim();
    return decision === "ALLOW" || decision.startsWith("DENY: ") ? decision : null;
  } catch {
    return null;
  }
}

async function refresh($: Services): Promise<void> {
  try {
    const now = await $.clock.now();
    if (lastRefreshAtMs !== null && now >= lastRefreshAtMs && now - lastRefreshAtMs < REFRESH_REUSE_MS) return;
    lastRefreshAtMs = now;
  } catch {
    lastRefreshAtMs = null;
  }
  const report = await readReport($);
  if (report !== null) cachedReport = report;
}

async function denyReason($: Services, tool: string, command?: string, subagentType?: string): Promise<string | null> {
  if (!hasInvalid(cachedReport)) return null;
  const before = await classify($, tool, command, subagentType);
  if (!before?.startsWith("DENY: ")) return null;
  await refresh($);
  if (!hasInvalid(cachedReport)) return null;
  // An unanswered refresh/classification cannot weaken an established denial.
  const after = await classify($, tool, command, subagentType);
  return after === "ALLOW" ? null : (after ?? before).slice("DENY: ".length);
}

export const register: Register = (on) => {
  on("classic.SessionStart", async ($, e, next) => {
    const result = await next(e);
    resolvedModel = e.model;
    lastRefreshAtMs = null;
    cachedReport = await readReport($);
    const lines = cachedReport ? cachedReport.vendors.flatMap((vendor) => [
      `model-registry ${vendor.vendor}: ${vendor.verdict}${vendor.verdict === "not_checked" ? " (this is not a pass)" : ""}`,
      ...vendor.findings, ...vendor.retiring,
    ]) : ["model-registry: NOT CHECKED (this is not a pass): report unavailable"];
    return { ...result, additionalContext: [...(result.additionalContext ?? []), lines.join("\n")] };
  });

  on("classic.PreToolUse", async ($, e, next) => {
    if (READ_ONLY_TOOLS.has(e.tool) || ESCAPE_HATCH_TOOLS.has(e.tool) || !hasInvalid(cachedReport)) return next(e);
    if (e.tool !== "Bash" && e.tool !== "Agent") return next(e);
    const reason = await denyReason($, e.tool,
      e.tool === "Bash" ? e.command : undefined,
      e.tool === "Agent" ? e.subagent_type : undefined);
    return reason === null ? next(e) : { deny: reason };
  });

  on("agent.spawn", async ($, e, next) => {
    const reason = await denyReason($, "agent.spawn", undefined, e.subagentType);
    return reason === null ? next(e) : { deny: reason };
  });
};
