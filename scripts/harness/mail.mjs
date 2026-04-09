#!/usr/bin/env node
/**
 * OpenClaw Mailbox CLI — zero-dep, flock-protected, JSONL per recipient.
 *
 * Why this exists: the skill-based mailbox was unreliable (only installed on
 * 3/5 workspaces, here-doc writes fragile for small models). This is a
 * robust agent-to-agent channel that does NOT go through ClaudeCode —
 * each of the 5 Beatless agents calls it via its `exec` tool.
 *
 * Storage layout:
 *   .openclaw/mailbox/<recipient>.jsonl   — append-only JSONL
 *   .openclaw/mailbox/<recipient>.lock    — advisory lock (flock)
 *
 * Each letter:
 *   { id, from, to, type, subject, body, priority, createdAt, readAt }
 *
 * Commands:
 *   mail send   --from <a> --to <b> --type <t> --subject <s> --body <text> [--priority normal|high|low]
 *   mail read   --agent <name> [--unread] [--limit N]
 *   mail mark   --agent <name> --id <id>
 *   mail count  --agent <name> [--unread]
 *   mail sweep  --agent <name> --keep-days N       # archive old
 *
 * Exit codes: 0 ok, 1 user error, 2 lock timeout, 3 fs error.
 */

import { mkdirSync, existsSync, openSync, closeSync, readFileSync, writeFileSync, appendFileSync, renameSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = dirname(dirname(dirname(__filename))); // .../claw
const MAILBOX_DIR = join(REPO_ROOT, '.openclaw', 'mailbox');
const AGENTS = ['lacia', 'methode', 'satonus', 'snowdrop', 'kouka'];

// ---------- helpers ----------

function die(msg, code = 1) {
  process.stderr.write(`mail: ${msg}\n`);
  process.exit(code);
}

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const k = a.slice(2);
      const v = (argv[i + 1] && !argv[i + 1].startsWith('--')) ? argv[++i] : 'true';
      out[k] = v;
    } else {
      out._.push(a);
    }
  }
  return out;
}

function ensureMailbox(agent) {
  if (!AGENTS.includes(agent)) die(`unknown agent: ${agent}. valid: ${AGENTS.join(', ')}`);
  if (!existsSync(MAILBOX_DIR)) mkdirSync(MAILBOX_DIR, { recursive: true });
  const file = join(MAILBOX_DIR, `${agent}.jsonl`);
  if (!existsSync(file)) writeFileSync(file, '', { mode: 0o644 });
  return file;
}

// Advisory lock via O_EXCL create-then-rename. Retry up to 5s.
// Good enough for a 5-agent system; not POSIX-strict but robust for our scale.
import { unlinkSync } from 'node:fs';
function withLock(file, fn) {
  const lock = file + '.lock';
  const deadline = Date.now() + 5000;
  let acquired = false;
  while (Date.now() < deadline) {
    try {
      const fd = openSync(lock, 'wx');
      closeSync(fd);
      acquired = true;
      break;
    } catch (e) {
      if (e.code !== 'EEXIST') die(`lock error: ${e.message}`, 3);
      // If stale (>30s old), steal it
      try {
        const age = Date.now() - statSync(lock).mtimeMs;
        if (age > 30000) { unlinkSync(lock); continue; }
      } catch {}
      // busy wait 50ms
      execFileSync('sleep', ['0.05']);
    }
  }
  if (!acquired) die('could not acquire mailbox lock (5s timeout)', 2);
  try {
    return fn();
  } finally {
    try { unlinkSync(lock); } catch {}
  }
}

function genId() {
  return `m_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function readJsonl(file) {
  if (!existsSync(file)) return [];
  const raw = readFileSync(file, 'utf8');
  return raw.split('\n').filter(Boolean).map((line, i) => {
    try { return JSON.parse(line); }
    catch { return { _corrupt: true, _line: i + 1, _raw: line }; }
  });
}

// ---------- commands ----------

function cmdSend(args) {
  const from = args.from || die('--from required');
  const to = args.to || die('--to required');
  const type = args.type || 'message';
  const subject = args.subject || '';
  const body = args.body || '';
  const priority = args.priority || 'normal';
  if (!AGENTS.includes(from)) die(`unknown from: ${from}`);
  if (!['message', 'idle_report', 'task_request', 'task_result', 'review_verdict', 'alert', 'ack'].includes(type)) {
    process.stderr.write(`mail: warning: non-standard type "${type}"\n`);
  }

  const file = ensureMailbox(to);
  const letter = {
    id: genId(), from, to, type, subject, body, priority,
    createdAt: new Date().toISOString(),
    readAt: null,
  };
  withLock(file, () => {
    appendFileSync(file, JSON.stringify(letter) + '\n');
  });
  process.stdout.write(JSON.stringify({ ok: true, id: letter.id, to, from }) + '\n');
}

function cmdRead(args) {
  const agent = args.agent || die('--agent required');
  const unread = args.unread === 'true' || args.unread === true;
  const limit = parseInt(args.limit || '20', 10);
  const file = ensureMailbox(agent);
  const letters = readJsonl(file).filter((l) => !l._corrupt);
  const filtered = unread ? letters.filter((l) => !l.readAt) : letters;
  const recent = filtered.slice(-limit);
  process.stdout.write(JSON.stringify({ ok: true, agent, count: recent.length, letters: recent }, null, 2) + '\n');
}

function cmdMark(args) {
  const agent = args.agent || die('--agent required');
  const id = args.id || die('--id required');
  const file = ensureMailbox(agent);
  withLock(file, () => {
    const letters = readJsonl(file);
    let found = false;
    for (const l of letters) {
      if (l.id === id && !l.readAt) { l.readAt = new Date().toISOString(); found = true; }
    }
    if (!found) die(`letter not found or already read: ${id}`);
    const tmp = file + '.tmp';
    writeFileSync(tmp, letters.filter((l) => !l._corrupt).map((l) => JSON.stringify(l)).join('\n') + '\n');
    renameSync(tmp, file);
    process.stdout.write(JSON.stringify({ ok: true, id, agent }) + '\n');
  });
}

function cmdCount(args) {
  const agent = args.agent || die('--agent required');
  const unread = args.unread === 'true' || args.unread === true;
  const file = ensureMailbox(agent);
  const letters = readJsonl(file).filter((l) => !l._corrupt);
  const n = unread ? letters.filter((l) => !l.readAt).length : letters.length;
  process.stdout.write(JSON.stringify({ ok: true, agent, count: n, unread }) + '\n');
}

function cmdSweep(args) {
  const agent = args.agent || die('--agent required');
  const keepDays = parseInt(args['keep-days'] || '30', 10);
  const file = ensureMailbox(agent);
  const cutoff = Date.now() - keepDays * 86400 * 1000;
  withLock(file, () => {
    const letters = readJsonl(file).filter((l) => !l._corrupt);
    const kept = letters.filter((l) => new Date(l.createdAt).getTime() >= cutoff || !l.readAt);
    const archived = letters.length - kept.length;
    if (archived > 0) {
      const archivePath = file + `.archive-${new Date().toISOString().slice(0, 10)}.jsonl`;
      const removed = letters.filter((l) => !kept.includes(l));
      appendFileSync(archivePath, removed.map((l) => JSON.stringify(l)).join('\n') + '\n');
      writeFileSync(file + '.tmp', kept.map((l) => JSON.stringify(l)).join('\n') + (kept.length ? '\n' : ''));
      renameSync(file + '.tmp', file);
    }
    process.stdout.write(JSON.stringify({ ok: true, agent, kept: kept.length, archived }) + '\n');
  });
}

function cmdList(_args) {
  const rows = AGENTS.map((a) => {
    const file = join(MAILBOX_DIR, `${a}.jsonl`);
    if (!existsSync(file)) return { agent: a, total: 0, unread: 0, size: 0 };
    const letters = readJsonl(file).filter((l) => !l._corrupt);
    return {
      agent: a,
      total: letters.length,
      unread: letters.filter((l) => !l.readAt).length,
      size: statSync(file).size,
    };
  });
  process.stdout.write(JSON.stringify({ ok: true, mailboxes: rows }, null, 2) + '\n');
}

function cmdHelp() {
  process.stdout.write(`
OpenClaw Mailbox CLI — agent-to-agent channel

Commands:
  mail send   --from <a> --to <b> --type <t> --subject <s> --body <text> [--priority normal|high|low]
  mail read   --agent <name> [--unread] [--limit N]
  mail mark   --agent <name> --id <id>
  mail count  --agent <name> [--unread]
  mail sweep  --agent <name> --keep-days N
  mail list                                         # all 5 mailboxes summary

Standard types: message, idle_report, task_request, task_result, review_verdict, alert, ack
Agents: ${AGENTS.join(', ')}
Storage: .openclaw/mailbox/<recipient>.jsonl (flock-protected)
`);
}

// ---------- dispatch ----------

const args = parseArgs(process.argv.slice(2));
const cmd = args._[0] || 'help';

switch (cmd) {
  case 'send':  cmdSend(args);  break;
  case 'read':  cmdRead(args);  break;
  case 'mark':  cmdMark(args);  break;
  case 'count': cmdCount(args); break;
  case 'sweep': cmdSweep(args); break;
  case 'list':  cmdList(args);  break;
  case 'help':
  case '--help':
  case '-h':    cmdHelp();      break;
  default:      die(`unknown command: ${cmd}. run 'mail help'`);
}
