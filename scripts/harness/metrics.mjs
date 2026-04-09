#!/usr/bin/env node
/**
 * OpenClaw Metrics Ledger — ported from GSD2 metrics.ts
 *
 * Tracks per-agent per-turn token usage, cost, and model selection.
 * Agents call this via `exec` after each claude_code_cli invocation.
 *
 * Storage: .openclaw/metrics/<agent>.jsonl (append-only)
 * Summary: .openclaw/metrics/summary.json (rebuilt on `report`)
 *
 * Commands:
 *   metrics record --agent <a> --model <m> --input <n> --output <n> --duration <ms> [--cost <usd>] [--tier <t>]
 *   metrics report [--agent <a>] [--since <iso-date>]
 *   metrics budget [--agent <a>]    # remaining daily budget estimate
 */

import { mkdirSync, existsSync, readFileSync, appendFileSync, writeFileSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = dirname(dirname(dirname(__filename)));
const METRICS_DIR = join(REPO_ROOT, '.openclaw', 'metrics');
const AGENTS = ['lacia', 'methode', 'satonus', 'snowdrop', 'kouka'];

// ── Cost table (ported from GSD2 model-cost-table.ts) ──
const COST_TABLE = {
  'claude-opus-4-6':         { input: 0.015,   output: 0.075 },
  'claude-sonnet-4-6':       { input: 0.003,   output: 0.015 },
  'claude-haiku-4-5':        { input: 0.0008,  output: 0.004 },
  'step-3.5-flash':          { input: 0.0001,  output: 0.0004 },  // StepFun pricing
  'MiniMax-M2.7':            { input: 0.0002,  output: 0.0008 },  // MiniMax pricing
  'gpt-5':                   { input: 0.01,    output: 0.04 },
  'gpt-5-mini':              { input: 0.0003,  output: 0.0012 },
  'gpt-5.4':                 { input: 0.005,   output: 0.02 },
  'gemini-3.1-pro-preview':  { input: 0.00125, output: 0.005 },
  'gemini-2.0-flash':        { input: 0.0001,  output: 0.0004 },
};

function lookupCost(model, inputTokens, outputTokens) {
  const bare = model.includes('/') ? model.split('/').pop() : model;
  const entry = COST_TABLE[bare] || Object.entries(COST_TABLE).find(([k]) => bare.includes(k) || k.includes(bare))?.[1];
  if (!entry) return null;
  return ((inputTokens / 1000) * entry.input) + ((outputTokens / 1000) * entry.output);
}

// ── Helpers ──
function die(msg, code = 1) { process.stderr.write(`metrics: ${msg}\n`); process.exit(code); }
function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) { const k = a.slice(2); out[k] = (argv[i+1] && !argv[i+1].startsWith('--')) ? argv[++i] : 'true'; }
    else out._.push(a);
  }
  return out;
}

function ensureDir() { if (!existsSync(METRICS_DIR)) mkdirSync(METRICS_DIR, { recursive: true }); }

function readJsonl(file) {
  if (!existsSync(file)) return [];
  return readFileSync(file, 'utf8').split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
}

// ── Commands ──
function cmdRecord(args) {
  const agent = args.agent || die('--agent required');
  const model = args.model || 'unknown';
  const input = parseInt(args.input || '0', 10);
  const output = parseInt(args.output || '0', 10);
  const duration = parseInt(args.duration || '0', 10);
  const tier = args.tier || 'standard';
  const cost = args.cost ? parseFloat(args.cost) : lookupCost(model, input, output);
  if (!AGENTS.includes(agent)) die(`unknown agent: ${agent}`);

  ensureDir();
  const file = join(METRICS_DIR, `${agent}.jsonl`);
  const record = {
    agent, model, tier,
    tokens: { input, output, total: input + output },
    cost: cost ?? 0,
    durationMs: duration,
    recordedAt: new Date().toISOString(),
  };
  appendFileSync(file, JSON.stringify(record) + '\n');
  process.stdout.write(JSON.stringify({ ok: true, ...record }) + '\n');
}

function cmdReport(args) {
  ensureDir();
  const filterAgent = args.agent;
  const since = args.since ? new Date(args.since).getTime() : 0;

  const agentList = filterAgent ? [filterAgent] : AGENTS;
  const rows = [];
  for (const a of agentList) {
    const file = join(METRICS_DIR, `${a}.jsonl`);
    const records = readJsonl(file).filter(r => new Date(r.recordedAt).getTime() >= since);
    const totalIn = records.reduce((s, r) => s + (r.tokens?.input || 0), 0);
    const totalOut = records.reduce((s, r) => s + (r.tokens?.output || 0), 0);
    const totalCost = records.reduce((s, r) => s + (r.cost || 0), 0);
    const totalDur = records.reduce((s, r) => s + (r.durationMs || 0), 0);
    const models = [...new Set(records.map(r => r.model))];
    rows.push({
      agent: a, turns: records.length, models,
      tokens: { input: totalIn, output: totalOut, total: totalIn + totalOut },
      cost: Math.round(totalCost * 10000) / 10000,
      totalDurationMs: totalDur,
      avgTurnMs: records.length ? Math.round(totalDur / records.length) : 0,
    });
  }

  // Save summary
  const summary = { generatedAt: new Date().toISOString(), since: since ? new Date(since).toISOString() : 'all', agents: rows };
  writeFileSync(join(METRICS_DIR, 'summary.json'), JSON.stringify(summary, null, 2));
  process.stdout.write(JSON.stringify(summary, null, 2) + '\n');
}

function cmdBudget(args) {
  ensureDir();
  const today = new Date().toISOString().slice(0, 10);
  const agentList = args.agent ? [args.agent] : AGENTS;
  const rows = [];
  for (const a of agentList) {
    const file = join(METRICS_DIR, `${a}.jsonl`);
    const records = readJsonl(file).filter(r => r.recordedAt?.startsWith(today));
    const spent = records.reduce((s, r) => s + (r.cost || 0), 0);
    rows.push({ agent: a, todayTurns: records.length, todaySpent: Math.round(spent * 10000) / 10000 });
  }
  process.stdout.write(JSON.stringify({ ok: true, date: today, agents: rows }, null, 2) + '\n');
}

function cmdHelp() {
  process.stdout.write(`
OpenClaw Metrics Ledger — per-agent token & cost tracking

Commands:
  metrics record --agent <a> --model <m> --input <n> --output <n> --duration <ms> [--cost <usd>] [--tier <t>]
  metrics report [--agent <a>] [--since <iso-date>]
  metrics budget [--agent <a>]
  metrics help

Storage: .openclaw/metrics/<agent>.jsonl
`);
}

// ── Dispatch ──
const args = parseArgs(process.argv.slice(2));
const cmd = args._[0] || 'help';
switch (cmd) {
  case 'record': cmdRecord(args); break;
  case 'report': cmdReport(args); break;
  case 'budget': cmdBudget(args); break;
  case 'help': case '--help': case '-h': cmdHelp(); break;
  default: die(`unknown command: ${cmd}`);
}
