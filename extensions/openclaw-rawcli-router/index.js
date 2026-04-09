// OpenClaw RawCli Router - Single Mode (ClaudeCode only)
// Legacy multi-lane code archived to _legacy/index.multi.js

import { spawn } from "node:child_process";
import { runGeminiBridge, shouldDelegateToGemini } from "./adapters/gemini-bridge.js";

const DEFAULTS = {
  cwd: "/home/yarizakurahime/claw",
  timeoutSec: 240,
  model: "claude-sonnet-4-6",
  lanePrompt: [
    "You are the unified ClaudeCode execution entry.",
    "Complete tasks directly; delegate deep research to Gemini (keyword: deep research / 外部大脑);",
    "delegate adversarial review to Codex (keyword: codex review / 审查).",
    "Output must be concise, executable, and grounded.",
  ].join(" "),
};

const TOOL_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    prompt: { type: "string", description: "Instruction text for Claude Code CLI." },
    cwd: { type: "string", description: "Working directory for the CLI call." },
    timeoutSec: { type: "number", minimum: 10, maximum: 1800, description: "Timeout in seconds." },
    model: { type: "string", description: "Optional model override." },
  },
  required: ["prompt"],
};

const asObj = (v) => (v && typeof v === "object" && !Array.isArray(v) ? v : {});
const asStr = (v, fb = "") => (typeof v === "string" && v.trim() ? v.trim() : fb);
const asNum = (v, fb, min = 10, max = 1800) => {
  const n = typeof v === "number" ? v : Number.NaN;
  return Number.isFinite(n) ? Math.max(min, Math.min(max, Math.round(n))) : fb;
};
const norm = (t) => (t ? t.replace(/\r\n/g, "\n").trim() : "");
const short = (t, max = 320) => (norm(t).length > max ? `${norm(t).slice(0, max)}...` : norm(t));

function loadConfig(raw) {
  const cfg = asObj(raw);
  const models = asObj(cfg.models);
  const prompts = asObj(cfg.lanePrompts);
  return {
    enabled: cfg.enabled !== false,
    mode: "single",
    cwd: asStr(cfg.defaultCwd, DEFAULTS.cwd),
    timeoutSec: asNum(cfg.timeoutSec, DEFAULTS.timeoutSec),
    model: asStr(models.claudeCode, DEFAULTS.model),
    lanePrompt: asStr(prompts.claudeCode, DEFAULTS.lanePrompt),
  };
}

function resolvePrompt(params) {
  const p = asObj(params);
  for (const c of [p.prompt, p.task, p.query, p.message]) {
    if (typeof c === "string" && c.trim()) return c.trim();
  }
  throw new Error("prompt is required");
}

function formatContract(payload) {
  const result = norm(payload.result || "") || "(empty)";
  return [`LANE=${payload.lane}`, `BACKEND=${payload.backend}`, `MODEL=${payload.model}`, "RESULT:", result].join("\n");
}

function composeLanePrompt(task, cfg) {
  return cfg.lanePrompt ? `${cfg.lanePrompt}\n\nTask:\n${task}` : task;
}

async function runProcess(command, args, opts) {
  return await new Promise((resolve) => {
    let stdout = "";
    let stderr = "";
    let settled = false;
    const done = (r) => {
      if (!settled) {
        settled = true;
        resolve(r);
      }
    };

    let child;
    try {
      // Clean env: remove placeholder/invalid API keys that override OAuth,
      // and ensure HOME is set for OAuth credential discovery.
      const cleanEnv = { ...process.env };
      for (const [k, v] of Object.entries(cleanEnv)) {
        if (v === "SET_ME" || v === "set_me" || v === "") delete cleanEnv[k];
      }
      // CRITICAL: Remove dummy ANTHROPIC_API_KEY so claude CLI falls back to
      // OAuth (.claude/.credentials.json) instead of trying an invalid key.
      // The gateway env has ANTHROPIC_API_KEY=allgerto (placeholder) which
      // causes every claude_code_cli call to fail with "Invalid API key".
      if (cleanEnv.ANTHROPIC_API_KEY && cleanEnv.ANTHROPIC_API_KEY.length < 20) {
        delete cleanEnv.ANTHROPIC_API_KEY;
      }
      // Ensure claude CLI can find OAuth credentials via HOME
      if (!cleanEnv.HOME) cleanEnv.HOME = process.env.HOME || "/home/" + (process.env.USER || "root");
      child = spawn(command, args, { cwd: opts.cwd, env: cleanEnv, stdio: ["ignore", "pipe", "pipe"] });
    } catch (error) {
      done({ ok: false, stdout: "", stderr: error instanceof Error ? error.message : String(error), code: 1 });
      return;
    }

    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      setTimeout(() => !settled && child.kill("SIGKILL"), 3000).unref();
      done({ ok: false, stdout: norm(stdout), stderr: norm(stderr) || "command timed out", code: 124 });
    }, opts.timeoutMs);
    timer.unref();

    child.stdout?.on("data", (c) => (stdout += c.toString()));
    child.stderr?.on("data", (c) => (stderr += c.toString()));
    child.on("error", (error) => {
      clearTimeout(timer);
      done({ ok: false, stdout: norm(stdout), stderr: error instanceof Error ? error.message : String(error), code: 1 });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      const out = norm(stdout);
      const err = norm(stderr);
      const rc = Number.isFinite(code) ? code : 1;
      done(rc === 0 ? { ok: true, stdout: out, stderr: err, code: 0 } : { ok: false, stdout: out, stderr: err || "command failed", code: rc });
    });
  });
}

async function runClaude(prompt, model, opts) {
  const res = await runProcess("claude", ["--permission-mode", "bypassPermissions", "--model", model, "--print", prompt], opts);
  if (!res.ok) {
    const detail = `exit=${res.code} stderr=${short(res.stderr, 200)} stdout=${short(res.stdout, 200)} prompt=${short(prompt, 80)}`;
    throw new Error(`claude failed (${detail})`);
  }
  if (res.stdout) return res.stdout;
  throw new Error(short(res.stderr) ? `claude returned empty output (${short(res.stderr)})` : "claude returned empty output");
}

async function executeClaudeCodeCli(params, cfg, logger) {
  const prompt = resolvePrompt(params);
  const cwd = asStr(asObj(params).cwd, cfg.cwd);
  const timeoutMs = asNum(asObj(params).timeoutSec, cfg.timeoutSec) * 1000;
  const model = asStr(asObj(params).model, cfg.model);
  const lanePrompt = composeLanePrompt(prompt, cfg);

  // Gemini direct bridge DISABLED (2026-04-09): All research now routes through
  // Sonnet 4.6 which has /gemini:review plugin + agents have web_fetch/browser tools.
  // Direct gemini CLI calls bypass OpenClaw's harness and are harder to audit.
  // if (shouldDelegateToGemini(prompt)) { ... }

  const result = await runClaude(lanePrompt, model, { cwd, timeoutMs });
  return { lane: "claude_code_cli", backend: "claude", model, result };
}

function buildTool(cfg, logger) {
  return {
    name: "claude_code_cli",
    label: "Claude Code CLI",
    description: "Unified external coding lane routed through Claude Code",
    parameters: TOOL_SCHEMA,
    async execute(_toolCallId, params) {
      try {
        const outcome = await executeClaudeCodeCli(params, cfg, logger);
        return { content: [{ type: "text", text: formatContract(outcome) }], details: outcome };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error || "unknown error");
        logger.error(`[rawcli-router] claude_code_cli failed: ${message}`);
        return {
          content: [{ type: "text", text: `LANE=claude_code_cli\nERROR=${message}` }],
          details: { lane: "claude_code_cli", error: message },
          isError: true,
        };
      }
    },
  };
}

async function runFromSlash(ctx, cfg, logger) {
  const argsText = asStr(ctx?.args, "");
  if (!argsText) return { text: "rc requires arguments. Example: /rc explain this architecture", isError: true };
  try {
    const outcome = await executeClaudeCodeCli({ prompt: argsText }, cfg, logger);
    return { text: formatContract(outcome) };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error || "unknown error");
    return { text: `LANE=claude_code_cli\nERROR=${message}`, isError: true };
  }
}

const plugin = {
  id: "openclaw-rawcli-router",
  name: "OpenClaw RawCli Router",
  description: "Expose unified ClaudeCode lane as plugin tool for main agents",
  register(api) {
    const cfg = loadConfig(api.pluginConfig || {});
    if (!cfg.enabled) return api.logger.info("[rawcli-router] disabled by config");

    if (typeof api.registerTool === "function") {
      api.registerTool(() => buildTool(cfg, api.logger));
      api.logger.info("[rawcli-router] registered tools: claude_code_cli");
    } else {
      api.logger.warn("[rawcli-router] registerTool API unavailable on this gateway build");
    }

    for (const [name, description] of [["rc_code", "Run unified Claude Code lane"], ["rc", "Alias of rc_code"]]) {
      api.registerCommand({ name, description, acceptsArgs: true, handler: async (ctx) => runFromSlash(ctx, cfg, api.logger) });
    }
    api.logger.info("[rawcli-router] registered commands: rc_code/rc");
  },
};

export default plugin;

