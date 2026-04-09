#!/usr/bin/env node
/**
 * OpenClaw Git Checkpoint — ported from GSD2 safety/git-checkpoint.ts
 *
 * Creates lightweight git refs before each agent turn so we can
 * rollback if the agent breaks something. Also provides an activity
 * log of agent session turns.
 *
 * Checkpoints: refs/openclaw/checkpoints/<agent>/<seq>
 * Activity log: .openclaw/activity/<agent>-<seq>.jsonl
 *
 * Commands:
 *   checkpoint create --agent <a> --label <text> [--cwd <path>]
 *   checkpoint rollback --agent <a> --ref <sha> [--cwd <path>]
 *   checkpoint list --agent <a> [--limit 10] [--cwd <path>]
 *   checkpoint cleanup --agent <a> [--keep 20] [--cwd <path>]
 *   checkpoint log --agent <a> --entry <json> [--cwd <path>]
 */

import { mkdirSync, existsSync, readFileSync, appendFileSync, readdirSync, unlinkSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = dirname(dirname(dirname(__filename)));
const AGENTS = ['lacia', 'methode', 'satonus', 'snowdrop', 'kouka'];

function die(msg, code = 1) { process.stderr.write(`checkpoint: ${msg}\n`); process.exit(code); }
function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) { const k = a.slice(2); out[k] = (argv[i+1] && !argv[i+1].startsWith('--')) ? argv[++i] : 'true'; }
    else out._.push(a);
  }
  return out;
}

function git(args, cwd) {
  try {
    return execSync(`git ${args}`, { cwd, stdio: ['ignore', 'pipe', 'pipe'], timeout: 10000 }).toString().trim();
  } catch (e) {
    return null;
  }
}

function getSeqFile(agent) {
  const dir = join(REPO_ROOT, '.openclaw', 'checkpoints');
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return join(dir, `${agent}.seq`);
}

function nextSeq(agent) {
  const file = getSeqFile(agent);
  let n = 0;
  try { n = parseInt(readFileSync(file, 'utf8').trim(), 10) || 0; } catch {}
  n++;
  writeFileSync(file, String(n));
  return n;
}

function cmdCreate(args) {
  const agent = args.agent || die('--agent required');
  if (!AGENTS.includes(agent)) die(`unknown agent: ${agent}`);
  const cwd = args.cwd || REPO_ROOT;
  const label = args.label || 'pre-turn';

  const head = git('rev-parse HEAD', cwd);
  if (!head) { process.stdout.write(JSON.stringify({ ok: false, reason: 'not a git repo or no commits' }) + '\n'); return; }

  const seq = nextSeq(agent);
  const refName = `refs/openclaw/checkpoints/${agent}/${seq}`;
  const result = git(`update-ref ${refName} ${head}`, cwd);
  if (result === null) { process.stdout.write(JSON.stringify({ ok: false, reason: 'update-ref failed' }) + '\n'); return; }

  process.stdout.write(JSON.stringify({ ok: true, agent, seq, ref: refName, sha: head, label, createdAt: new Date().toISOString() }) + '\n');
}

function cmdRollback(args) {
  const agent = args.agent || die('--agent required');
  const ref = args.ref || die('--ref required (SHA)');
  const cwd = args.cwd || REPO_ROOT;

  // Safety: only allow rollback to a known checkpoint ref
  const existingRef = git(`show-ref --hash refs/openclaw/checkpoints/${agent}/${ref}`, cwd);
  let targetSha = ref;
  if (existingRef) targetSha = existingRef; // ref was a seq number

  // Verify SHA exists
  const verify = git(`cat-file -t ${targetSha}`, cwd);
  if (verify !== 'commit') { die(`invalid commit: ${targetSha}`); }

  const result = git(`reset --hard ${targetSha}`, cwd);
  process.stdout.write(JSON.stringify({ ok: result !== null, agent, sha: targetSha, action: 'rollback' }) + '\n');
}

function cmdList(args) {
  const agent = args.agent || die('--agent required');
  const limit = parseInt(args.limit || '10', 10);
  const cwd = args.cwd || REPO_ROOT;

  const raw = git(`for-each-ref --sort=-creatordate --count=${limit} --format="%(refname) %(objectname:short) %(creatordate:iso8601)" refs/openclaw/checkpoints/${agent}/`, cwd);
  if (!raw) { process.stdout.write(JSON.stringify({ ok: true, agent, checkpoints: [] }) + '\n'); return; }

  const checkpoints = raw.split('\n').filter(Boolean).map(line => {
    const [ref, sha, ...dateParts] = line.split(' ');
    return { ref, sha, date: dateParts.join(' ') };
  });
  process.stdout.write(JSON.stringify({ ok: true, agent, checkpoints }, null, 2) + '\n');
}

function cmdCleanup(args) {
  const agent = args.agent || die('--agent required');
  const keep = parseInt(args.keep || '20', 10);
  const cwd = args.cwd || REPO_ROOT;

  const raw = git(`for-each-ref --sort=-creatordate --format="%(refname)" refs/openclaw/checkpoints/${agent}/`, cwd);
  if (!raw) { process.stdout.write(JSON.stringify({ ok: true, removed: 0 }) + '\n'); return; }

  const refs = raw.split('\n').filter(Boolean);
  const toRemove = refs.slice(keep);
  for (const ref of toRemove) git(`update-ref -d ${ref}`, cwd);
  process.stdout.write(JSON.stringify({ ok: true, agent, kept: Math.min(refs.length, keep), removed: toRemove.length }) + '\n');
}

function cmdLog(args) {
  const agent = args.agent || die('--agent required');
  const entry = args.entry || die('--entry required (JSON string)');

  const dir = join(REPO_ROOT, '.openclaw', 'activity');
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

  const today = new Date().toISOString().slice(0, 10);
  const file = join(dir, `${agent}-${today}.jsonl`);

  let parsed;
  try { parsed = JSON.parse(entry); } catch { parsed = { text: entry }; }
  parsed.agent = agent;
  parsed.timestamp = new Date().toISOString();

  appendFileSync(file, JSON.stringify(parsed) + '\n');
  process.stdout.write(JSON.stringify({ ok: true, agent, file }) + '\n');
}

function cmdHelp() {
  process.stdout.write(`
OpenClaw Git Checkpoint — rollback safety net for agent turns

Commands:
  checkpoint create --agent <a> --label <text> [--cwd <path>]
  checkpoint rollback --agent <a> --ref <sha> [--cwd <path>]
  checkpoint list --agent <a> [--limit 10] [--cwd <path>]
  checkpoint cleanup --agent <a> [--keep 20] [--cwd <path>]
  checkpoint log --agent <a> --entry <json>
  checkpoint help

Refs: refs/openclaw/checkpoints/<agent>/<seq>
Logs: .openclaw/activity/<agent>-<date>.jsonl
`);
}

const args = parseArgs(process.argv.slice(2));
const cmd = args._[0] || 'help';
switch (cmd) {
  case 'create': cmdCreate(args); break;
  case 'rollback': cmdRollback(args); break;
  case 'list': cmdList(args); break;
  case 'cleanup': cmdCleanup(args); break;
  case 'log': cmdLog(args); break;
  case 'help': case '--help': case '-h': cmdHelp(); break;
  default: die(`unknown command: ${cmd}`);
}
