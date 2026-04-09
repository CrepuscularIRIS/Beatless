#!/usr/bin/env node
/**
 * OpenClaw Safety Module — ported from GSD2 safety/ components:
 *   - file-change-validator.ts → validate-changes command
 *   - evidence-collector.ts → evidence command (log tool calls per turn)
 *   - evidence-cross-ref concept → audit command
 *
 * These are POST-EXECUTION safety checks. Agents call them via `exec`
 * after a `claude_code_cli` turn to verify the work was correct.
 *
 * Commands:
 *   safety validate-changes --cwd <path> [--expected "file1,file2"]
 *   safety evidence record --agent <a> --kind bash|write|edit --target "<cmd or path>"
 *   safety evidence list --agent <a>
 *   safety evidence clear --agent <a>
 *   safety audit --agent <a> --cwd <path>   # cross-ref evidence vs git diff
 *   safety status
 */

import { mkdirSync, existsSync, readFileSync, writeFileSync, appendFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = dirname(dirname(dirname(__filename)));
const SAFETY_DIR = join(REPO_ROOT, '.openclaw', 'safety');
const AGENTS = ['lacia', 'methode', 'satonus', 'snowdrop', 'kouka'];

function die(msg, code = 1) { process.stderr.write(`safety: ${msg}\n`); process.exit(code); }
function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) { const k = a.slice(2); out[k] = (argv[i+1] && !argv[i+1].startsWith('--')) ? argv[++i] : 'true'; }
    else out._.push(a);
  }
  return out;
}
function ensureDir() { if (!existsSync(SAFETY_DIR)) mkdirSync(SAFETY_DIR, { recursive: true }); }

function git(args, cwd) {
  try { return execSync(`git ${args}`, { cwd, stdio: ['ignore', 'pipe', 'pipe'], timeout: 10000 }).toString().trim(); }
  catch { return null; }
}

// ── File Change Validator (from GSD2 file-change-validator.ts) ──

function cmdValidateChanges(args) {
  const cwd = args.cwd || REPO_ROOT;
  const expectedRaw = args.expected || '';
  const expected = expectedRaw ? expectedRaw.split(',').map(f => f.trim().replace(/^\.\//, '').replace(/^\//, '')) : [];

  // Get changed files from last commit
  const diffRaw = git('diff --name-only HEAD~1 HEAD', cwd);
  if (diffRaw === null) {
    process.stdout.write(JSON.stringify({ ok: true, verdict: 'SKIP', reason: 'no git history or diff failed' }) + '\n');
    return;
  }
  const actual = diffRaw.split('\n').filter(Boolean).filter(f => !f.startsWith('.openclaw/') && !f.startsWith('.gsd/'));

  if (expected.length === 0) {
    // No expected list — just report what changed
    process.stdout.write(JSON.stringify({ ok: true, verdict: 'INFO', actual, count: actual.length }) + '\n');
    return;
  }

  const expectedSet = new Set(expected);
  const unexpected = actual.filter(f => !expectedSet.has(f));
  const missing = expected.filter(f => !actual.includes(f));
  const violations = [
    ...unexpected.map(f => ({ severity: 'warning', file: f, reason: 'modified but not in expected list' })),
    ...missing.map(f => ({ severity: 'info', file: f, reason: 'expected but not modified' })),
  ];

  const verdict = violations.some(v => v.severity === 'warning') ? 'FLAG' : 'PASS';
  process.stdout.write(JSON.stringify({
    ok: true, verdict, expected, actual, unexpected, missing, violations,
  }, null, 2) + '\n');
}

// ── Evidence Collector (from GSD2 evidence-collector.ts) ──

function evidencePath(agent) { return join(SAFETY_DIR, `${agent}-evidence.jsonl`); }

function cmdEvidenceRecord(args) {
  const agent = args.agent || die('--agent required');
  if (!AGENTS.includes(agent)) die(`unknown agent: ${agent}`);
  ensureDir();
  const kind = args.kind || 'bash';
  const target = args.target || '';
  const entry = {
    kind,
    target: target.slice(0, 500),
    exitCode: args['exit-code'] ? parseInt(args['exit-code'], 10) : null,
    output: (args.output || '').slice(0, 500),
    timestamp: new Date().toISOString(),
  };
  appendFileSync(evidencePath(agent), JSON.stringify(entry) + '\n');
  process.stdout.write(JSON.stringify({ ok: true, agent, ...entry }) + '\n');
}

function cmdEvidenceList(args) {
  const agent = args.agent || die('--agent required');
  const file = evidencePath(agent);
  if (!existsSync(file)) { process.stdout.write(JSON.stringify({ ok: true, agent, entries: [] }) + '\n'); return; }
  const entries = readFileSync(file, 'utf8').split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  process.stdout.write(JSON.stringify({ ok: true, agent, count: entries.length, entries: entries.slice(-20) }, null, 2) + '\n');
}

function cmdEvidenceClear(args) {
  const agent = args.agent || die('--agent required');
  ensureDir();
  writeFileSync(evidencePath(agent), '');
  process.stdout.write(JSON.stringify({ ok: true, agent, cleared: true }) + '\n');
}

// ── Evidence Audit (cross-ref: evidence log vs actual git diff) ──

function cmdAudit(args) {
  const agent = args.agent || die('--agent required');
  const cwd = args.cwd || REPO_ROOT;

  // Load evidence
  const file = evidencePath(agent);
  let entries = [];
  if (existsSync(file)) {
    entries = readFileSync(file, 'utf8').split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  }

  const claimed = new Set(entries.filter(e => e.kind === 'write' || e.kind === 'edit').map(e => e.target));
  const bashCmds = entries.filter(e => e.kind === 'bash').length;

  // Git diff (unstaged + staged)
  const diffRaw = git('diff --name-only HEAD', cwd);
  const stagedRaw = git('diff --cached --name-only', cwd);
  const actual = new Set([
    ...(diffRaw ? diffRaw.split('\n').filter(Boolean) : []),
    ...(stagedRaw ? stagedRaw.split('\n').filter(Boolean) : []),
  ]);

  // Cross-reference
  const claimedNotChanged = [...claimed].filter(f => !actual.has(f));
  const changedNotClaimed = [...actual].filter(f => !claimed.has(f) && !f.startsWith('.openclaw/'));

  const verdict = (claimedNotChanged.length === 0 && changedNotClaimed.length === 0) ? 'CLEAN' :
    changedNotClaimed.length > 0 ? 'FLAG' : 'INFO';

  process.stdout.write(JSON.stringify({
    ok: true, agent, verdict,
    evidence: { totalEntries: entries.length, bashCommands: bashCmds, claimedFiles: [...claimed] },
    gitState: { changedFiles: [...actual] },
    crossRef: { claimedNotChanged, changedNotClaimed },
  }, null, 2) + '\n');
}

function cmdStatus(_args) {
  ensureDir();
  const results = AGENTS.map(agent => {
    const file = evidencePath(agent);
    if (!existsSync(file)) return { agent, entries: 0, lastActivity: null };
    const lines = readFileSync(file, 'utf8').split('\n').filter(Boolean);
    let last = null;
    if (lines.length > 0) { try { last = JSON.parse(lines[lines.length - 1]).timestamp; } catch {} }
    return { agent, entries: lines.length, lastActivity: last };
  });
  process.stdout.write(JSON.stringify({ ok: true, safety_status: results }, null, 2) + '\n');
}

function cmdHelp() {
  process.stdout.write(`
OpenClaw Safety Module — post-execution verification

Commands:
  safety validate-changes --cwd <path> [--expected "file1,file2"]
  safety evidence record --agent <a> --kind bash|write|edit --target "<cmd or path>"
  safety evidence list --agent <a>
  safety evidence clear --agent <a>
  safety audit --agent <a> --cwd <path>
  safety status
  safety help

Verdict scale: PASS > INFO > FLAG > FAIL
Storage: .openclaw/safety/<agent>-evidence.jsonl
`);
}

const args = parseArgs(process.argv.slice(2));
const cmd = args._[0] || 'help';
const sub = args._[1] || '';
switch (cmd) {
  case 'validate-changes': cmdValidateChanges(args); break;
  case 'evidence':
    switch (sub) {
      case 'record': cmdEvidenceRecord(args); break;
      case 'list': cmdEvidenceList(args); break;
      case 'clear': cmdEvidenceClear(args); break;
      default: die(`evidence subcommand required: record|list|clear`);
    }
    break;
  case 'audit': cmdAudit(args); break;
  case 'status': cmdStatus(args); break;
  case 'help': case '--help': case '-h': cmdHelp(); break;
  default: die(`unknown command: ${cmd}`);
}
