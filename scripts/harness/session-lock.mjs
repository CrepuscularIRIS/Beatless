#!/usr/bin/env node
/**
 * OpenClaw Session Lock — ported from GSD2 session-lock.ts
 *
 * OS-level exclusive locking for agent sessions. Prevents parallel
 * heartbeat/cron/manual collisions on the same agent workspace.
 *
 * Lock file: .openclaw/locks/<agent>.lock (JSON metadata + O_EXCL sentinel)
 * Stale window: 30 minutes (laptop sleep recovery)
 *
 * Commands:
 *   session-lock acquire --agent <a> [--unit-type <t>] [--unit-id <id>]
 *   session-lock validate --agent <a>
 *   session-lock release --agent <a>
 *   session-lock status --agent <a>
 *   session-lock status-all
 */

import { mkdirSync, existsSync, readFileSync, writeFileSync, unlinkSync, statSync, openSync, closeSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = dirname(dirname(dirname(__filename)));
const LOCKS_DIR = join(REPO_ROOT, '.openclaw', 'locks');
const AGENTS = ['lacia', 'methode', 'satonus', 'snowdrop', 'kouka'];
const STALE_WINDOW_MS = 30 * 60 * 1000; // 30 minutes

function die(msg, code = 1) { process.stderr.write(`session-lock: ${msg}\n`); process.exit(code); }
function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) { const k = a.slice(2); out[k] = (argv[i+1] && !argv[i+1].startsWith('--')) ? argv[++i] : 'true'; }
    else out._.push(a);
  }
  return out;
}

function ensureDir() { if (!existsSync(LOCKS_DIR)) mkdirSync(LOCKS_DIR, { recursive: true }); }

function lockPath(agent) { return join(LOCKS_DIR, `${agent}.lock`); }
function sentinelPath(agent) { return join(LOCKS_DIR, `${agent}.sentinel`); }

function isPidAlive(pid) {
  try { process.kill(pid, 0); return true; }
  catch (e) { return e.code === 'EPERM'; } // EPERM = process exists, no permission
}

function readLockData(agent) {
  const path = lockPath(agent);
  if (!existsSync(path)) return null;
  try { return JSON.parse(readFileSync(path, 'utf8')); }
  catch { return null; }
}

function writeLockData(agent, data) {
  writeFileSync(lockPath(agent), JSON.stringify(data, null, 2));
}

// ── Commands ──

function cmdAcquire(args) {
  const agent = args.agent || die('--agent required');
  if (!AGENTS.includes(agent)) die(`unknown agent: ${agent}`);
  ensureDir();

  const sentinel = sentinelPath(agent);
  const existing = readLockData(agent);

  // Check for existing lock
  if (existing && existsSync(sentinel)) {
    if (isPidAlive(existing.pid)) {
      // Lock held by live process
      const age = Date.now() - new Date(existing.acquiredAt).getTime();
      if (age < STALE_WINDOW_MS) {
        process.stdout.write(JSON.stringify({
          acquired: false, reason: 'held_by_active_process',
          existingPid: existing.pid, age: Math.round(age / 1000),
        }) + '\n');
        return;
      }
      // Stale — process alive but exceeded stale window
      process.stderr.write(`session-lock: stealing stale lock from PID ${existing.pid} (${Math.round(age/60000)}m old)\n`);
    }
    // Dead process or stale — clean up
    try { unlinkSync(sentinel); } catch {}
  }

  // Acquire via O_EXCL sentinel
  try {
    const fd = openSync(sentinel, 'wx');
    closeSync(fd);
  } catch (e) {
    if (e.code === 'EEXIST') {
      // Race condition: another process created sentinel between our check and create
      process.stdout.write(JSON.stringify({ acquired: false, reason: 'race_condition' }) + '\n');
      return;
    }
    throw e;
  }

  const lockData = {
    pid: process.pid,
    agent,
    acquiredAt: new Date().toISOString(),
    unitType: args['unit-type'] || 'unknown',
    unitId: args['unit-id'] || 'unknown',
    hostname: process.env.HOSTNAME || 'localhost',
  };
  writeLockData(agent, lockData);

  process.stdout.write(JSON.stringify({ acquired: true, ...lockData }) + '\n');
}

function cmdValidate(args) {
  const agent = args.agent || die('--agent required');
  const data = readLockData(agent);
  const sentinel = sentinelPath(agent);

  if (!data || !existsSync(sentinel)) {
    process.stdout.write(JSON.stringify({ valid: false, reason: 'no_lock' }) + '\n');
    return;
  }

  // Check PID ownership
  if (data.pid !== process.pid && !isPidAlive(data.pid)) {
    process.stdout.write(JSON.stringify({ valid: false, reason: 'holder_dead', pid: data.pid }) + '\n');
    return;
  }

  // Check stale window (laptop sleep recovery from GSD2)
  const age = Date.now() - new Date(data.acquiredAt).getTime();
  if (age > STALE_WINDOW_MS && !isPidAlive(data.pid)) {
    process.stdout.write(JSON.stringify({ valid: false, reason: 'stale', ageMs: age }) + '\n');
    return;
  }

  process.stdout.write(JSON.stringify({ valid: true, pid: data.pid, agent, ageMs: age }) + '\n');
}

function cmdRelease(args) {
  const agent = args.agent || die('--agent required');
  const sentinel = sentinelPath(agent);
  const lock = lockPath(agent);
  let released = false;
  try { unlinkSync(sentinel); released = true; } catch {}
  try { unlinkSync(lock); } catch {}
  process.stdout.write(JSON.stringify({ released, agent }) + '\n');
}

function cmdStatus(args) {
  const agent = args.agent || die('--agent required');
  const data = readLockData(agent);
  if (!data) {
    process.stdout.write(JSON.stringify({ agent, locked: false }) + '\n');
    return;
  }
  const alive = isPidAlive(data.pid);
  const age = Date.now() - new Date(data.acquiredAt).getTime();
  process.stdout.write(JSON.stringify({
    agent, locked: true, pid: data.pid, alive, ageMs: age,
    unitType: data.unitType, unitId: data.unitId, acquiredAt: data.acquiredAt,
  }) + '\n');
}

function cmdStatusAll(_args) {
  ensureDir();
  const results = AGENTS.map(agent => {
    const data = readLockData(agent);
    if (!data) return { agent, locked: false };
    return {
      agent, locked: true, pid: data.pid,
      alive: isPidAlive(data.pid),
      ageMs: Date.now() - new Date(data.acquiredAt).getTime(),
      unitType: data.unitType,
    };
  });
  process.stdout.write(JSON.stringify({ ok: true, locks: results }, null, 2) + '\n');
}

function cmdHelp() {
  process.stdout.write(`
OpenClaw Session Lock — prevent parallel agent collisions

Commands:
  session-lock acquire --agent <a> [--unit-type <t>] [--unit-id <id>]
  session-lock validate --agent <a>
  session-lock release --agent <a>
  session-lock status --agent <a>
  session-lock status-all
  session-lock help

Stale window: 30 minutes. Storage: .openclaw/locks/<agent>.{lock,sentinel}
`);
}

const args = parseArgs(process.argv.slice(2));
const cmd = args._[0] || 'help';
switch (cmd) {
  case 'acquire': cmdAcquire(args); break;
  case 'validate': cmdValidate(args); break;
  case 'release': cmdRelease(args); break;
  case 'status': cmdStatus(args); break;
  case 'status-all': cmdStatusAll(args); break;
  case 'help': case '--help': case '-h': cmdHelp(); break;
  default: die(`unknown command: ${cmd}`);
}
