import { spawn } from "node:child_process";

const DEFAULT_MODEL = process.env.OPENCLAW_GEMINI_BRIDGE_MODEL || "gemini-3.1-pro-preview";
const DEFAULT_TIMEOUT_MS = Number.parseInt(process.env.OPENCLAW_GEMINI_BRIDGE_TIMEOUT_MS || "900000", 10);

const TRIGGERS = [
  /\bgemini\b.*\bresearch\b/i,
  /\bdeep\s*research\b/i,
  /\biterative\s*search\b/i,
  /\brecursive\s*retrieval\b/i,
  /外部大脑|深度调研|递归检索|迭代搜索|学术调研/u,
];

function normalize(text) {
  return text ? text.replace(/\r\n/g, "\n").trim() : "";
}

export function shouldDelegateToGemini(prompt) {
  const text = normalize(prompt);
  if (!text) return false;
  return TRIGGERS.some((re) => re.test(text));
}

function buildPrompt(task) {
  return [
    "你是 GeminiResearchCli（外部大脑）。",
    "执行 Iterative Search + Recursive Retrieval：",
    "1) 先给出研究问题分解",
    "2) 给出关键证据、冲突证据与不确定性",
    "3) 输出可执行建议与下一步验证路径",
    "4) 尽量使用简洁结构，避免无关格式噪声",
    "",
    "Task:",
    task,
  ].join("\n");
}

function runGemini(args, { cwd, timeoutMs }) {
  return new Promise((resolve) => {
    let stdout = "";
    let stderr = "";
    let settled = false;

    const finish = (payload) => {
      if (settled) return;
      settled = true;
      resolve(payload);
    };

    let child;
    try {
      child = spawn("gemini", args, { cwd, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error || "gemini spawn failed");
      finish({ ok: false, stdout: "", stderr: message, code: 1 });
      return;
    }

    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      setTimeout(() => {
        if (!settled) child.kill("SIGKILL");
      }, 3000).unref();
      finish({ ok: false, stdout: normalize(stdout), stderr: normalize(stderr) || "gemini timed out", code: 124 });
    }, timeoutMs);
    timer.unref();

    child.stdout?.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr?.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (error) => {
      clearTimeout(timer);
      const message = error instanceof Error ? error.message : String(error || "gemini failed");
      finish({ ok: false, stdout: normalize(stdout), stderr: message, code: 1 });
    });

    child.on("close", (code) => {
      clearTimeout(timer);
      const out = normalize(stdout);
      const err = normalize(stderr);
      if ((code ?? 1) !== 0) {
        finish({ ok: false, stdout: out, stderr: err || "gemini failed", code: code ?? 1 });
        return;
      }
      finish({ ok: true, stdout: out, stderr: err, code: 0 });
    });
  });
}

export async function runGeminiBridge({ prompt, cwd, timeoutMs, model, logger }) {
  const effectiveModel = model || DEFAULT_MODEL;
  const effectiveTimeout = Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : DEFAULT_TIMEOUT_MS;
  const taskPrompt = buildPrompt(prompt);
  const args = ["--yolo", "--model", effectiveModel, "--output-format", "text", "-p", taskPrompt];
  const res = await runGemini(args, { cwd, timeoutMs: effectiveTimeout });
  if (!res.ok) {
    const detail = normalize(res.stderr || res.stdout) || "gemini bridge failed";
    throw new Error(detail);
  }
  if (!res.stdout) {
    throw new Error("gemini bridge returned empty output");
  }
  if (logger && typeof logger.info === "function") {
    logger.info(`[rawcli-router] gemini-bridge success model=${effectiveModel}`);
  }
  return { result: res.stdout, model: effectiveModel };
}

