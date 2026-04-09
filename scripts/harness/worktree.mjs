#!/usr/bin/env node
/**
 * OpenClaw Worktree Manager — adapted from GSD2 worktree-manager.ts
 *
 * Creates per-agent git worktrees for isolated execution. In our 5-agent
 * decentralized architecture, each agent can have its own worktree for
 * parallel work without stepping on other agents' changes.
 *
 * Layout:
 *   <repo>/.openclaw/worktrees/<agent>-<task>/   → git worktree
 *   Branch: openclaw/<agent>-<task>
 *
 * Unlike GSD2 which creates per-milestone worktrees, we create per-agent
 * worktrees keyed by agent + task slug. Multiple agents can work in the
 * same repo simultaneously.
 *
 * Commands:
 *   worktree create --repo <path> --agent <a> --task <slug>
 *   worktree list --repo <path>
 *   worktree merge --repo <path> --agent <a> --task <slug> [--squash]
 *   worktree remove --repo <path> --agent <a> --task <slug>
 *   worktree cleanup --repo <path> [--keep-days 7]
 */

import { existsSync, mkdirSync, readFileSync, lstatSync, rmSync, readdirSync, statSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const AGENTS = ['lacia', 'methode', 'satonus', 'snowdrop', 'kouka'];

function die(msg, code = 1) { process.stderr.write(`worktree: ${msg}\n`); process.exit(code); }
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
  try { return execSync(`git ${args}`, { cwd, stdio: ['ignore', 'pipe', 'pipe'], timeout: 30000 }).toString().trim(); }
  catch (e) { return null; }
}

function gitOrDie(args, cwd, msg) {
  const result = git(args, cwd);
  if (result === null) die(msg || `git ${args.split(' ')[0]} failed`);
  return result;
}

function slug(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);
}

function worktreeDir(repo, agent, task) {
  return join(repo, '.openclaw', 'worktrees', `${agent}-${slug(task)}`);
}

function branchName(agent, task) {
  return `openclaw/${agent}-${slug(task)}`;
}

// Resolve .git file in worktree → actual gitdir (from GSD2 resolveGitDir)
function resolveGitDir(basePath) {
  const gitPath = join(basePath, '.git');
  if (!existsSync(gitPath)) return gitPath;
  if (lstatSync(gitPath).isDirectory()) return gitPath;
  try {
    const content = readFileSync(gitPath, 'utf-8').trim();
    if (content.startsWith('gitdir: ')) return resolve(basePath, content.slice(8));
  } catch {}
  return gitPath;
}

function cmdCreate(args) {
  const repo = args.repo || die('--repo required');
  const agent = args.agent || die('--agent required');
  const task = args.task || die('--task required');
  if (!AGENTS.includes(agent)) die(`unknown agent: ${agent}`);

  const head = gitOrDie('rev-parse HEAD', repo, 'not a git repo');
  const wdir = worktreeDir(repo, agent, task);
  const branch = branchName(agent, task);

  if (existsSync(wdir)) {
    process.stdout.write(JSON.stringify({ ok: true, action: 'exists', path: wdir, branch }) + '\n');
    return;
  }

  // Create parent dir
  mkdirSync(join(repo, '.openclaw', 'worktrees'), { recursive: true });

  // Create worktree with new branch
  const result = git(`worktree add "${wdir}" -b "${branch}"`, repo);
  if (result === null) {
    // Branch may already exist — try without -b
    const retry = git(`worktree add "${wdir}" "${branch}"`, repo);
    if (retry === null) die(`failed to create worktree at ${wdir}`);
  }

  process.stdout.write(JSON.stringify({
    ok: true, action: 'created', agent, task: slug(task),
    path: wdir, branch, baseSha: head,
  }) + '\n');
}

function cmdList(args) {
  const repo = args.repo || die('--repo required');
  const raw = git('worktree list --porcelain', repo);
  if (!raw) { process.stdout.write(JSON.stringify({ ok: true, worktrees: [] }) + '\n'); return; }

  const worktrees = [];
  let current = {};
  for (const line of raw.split('\n')) {
    if (line.startsWith('worktree ')) {
      if (current.path) worktrees.push(current);
      current = { path: line.slice(9) };
    } else if (line.startsWith('HEAD ')) current.head = line.slice(5);
    else if (line.startsWith('branch ')) current.branch = line.slice(7);
    else if (line === 'bare') current.bare = true;
    else if (line === '') { if (current.path) worktrees.push(current); current = {}; }
  }
  if (current.path) worktrees.push(current);

  // Filter to openclaw worktrees only
  const ours = worktrees.filter(w => w.branch && w.branch.includes('openclaw/'));
  process.stdout.write(JSON.stringify({ ok: true, total: worktrees.length, openclaw: ours }, null, 2) + '\n');
}

function cmdMerge(args) {
  const repo = args.repo || die('--repo required');
  const agent = args.agent || die('--agent required');
  const task = args.task || die('--task required');
  const squash = args.squash === 'true';
  const wdir = worktreeDir(repo, agent, task);
  const branch = branchName(agent, task);

  if (!existsSync(wdir)) die(`worktree not found: ${wdir}`);

  // Auto-commit any dirty state in worktree
  const status = git('status --porcelain', wdir);
  if (status) {
    git('add -A', wdir);
    git(`commit -m "auto-commit: ${agent} ${slug(task)} pre-merge"`, wdir);
  }

  // Determine main branch
  const mainBranch = git('symbolic-ref refs/remotes/origin/HEAD', repo)?.replace('refs/remotes/origin/', '') || 'main';
  const currentBranch = gitOrDie('branch --show-current', repo, 'cannot determine current branch');

  // Merge
  const mergeCmd = squash ? `merge --squash "${branch}"` : `merge --no-ff "${branch}" -m "merge: ${agent}/${slug(task)}"`;
  const mergeResult = git(mergeCmd, repo);
  if (mergeResult === null) {
    // Check for conflicts
    const conflicts = git('diff --name-only --diff-filter=U', repo);
    if (conflicts) {
      // Auto-resolve .openclaw/ conflicts (safe, from GSD2 SAFE_AUTO_RESOLVE_PATTERNS)
      for (const f of conflicts.split('\n').filter(Boolean)) {
        if (f.startsWith('.openclaw/') || f.endsWith('.pyc') || f.endsWith('.tsbuildinfo') || f.endsWith('.DS_Store')) {
          git(`checkout --theirs "${f}"`, repo);
          git(`add "${f}"`, repo);
        }
      }
      // Check if conflicts remain
      const remaining = git('diff --name-only --diff-filter=U', repo);
      if (remaining) {
        process.stdout.write(JSON.stringify({
          ok: false, action: 'merge_conflict', agent, task: slug(task),
          conflicts: remaining.split('\n').filter(Boolean),
        }, null, 2) + '\n');
        git('merge --abort', repo);
        return;
      }
    }
    if (squash) {
      git(`commit -m "squash-merge: ${agent}/${slug(task)}"`, repo);
    }
  }

  const newHead = git('rev-parse HEAD', repo);
  process.stdout.write(JSON.stringify({
    ok: true, action: 'merged', agent, task: slug(task),
    branch, strategy: squash ? 'squash' : 'merge', newHead,
  }) + '\n');
}

function cmdRemove(args) {
  const repo = args.repo || die('--repo required');
  const agent = args.agent || die('--agent required');
  const task = args.task || die('--task required');
  const wdir = worktreeDir(repo, agent, task);
  const branch = branchName(agent, task);

  // Remove worktree
  if (existsSync(wdir)) {
    git(`worktree remove --force "${wdir}"`, repo);
    // Fallback if git worktree remove fails
    if (existsSync(wdir)) { try { rmSync(wdir, { recursive: true, force: true }); } catch {} }
  }

  // Prune stale worktree entries
  git('worktree prune', repo);

  // Delete branch
  git(`branch -D "${branch}"`, repo);

  process.stdout.write(JSON.stringify({ ok: true, action: 'removed', agent, task: slug(task), branch }) + '\n');
}

function cmdCleanup(args) {
  const repo = args.repo || die('--repo required');
  const keepDays = parseInt(args['keep-days'] || '7', 10);

  // Prune git worktree metadata
  git('worktree prune', repo);

  // Find old openclaw worktree dirs
  const wtDir = join(repo, '.openclaw', 'worktrees');
  if (!existsSync(wtDir)) { process.stdout.write(JSON.stringify({ ok: true, cleaned: 0 }) + '\n'); return; }

  const cutoff = Date.now() - keepDays * 86400 * 1000;
  let cleaned = 0;
  for (const entry of readdirSync(wtDir)) {
    const p = join(wtDir, entry);
    try {
      if (statSync(p).mtimeMs < cutoff) {
        git(`worktree remove --force "${p}"`, repo);
        if (existsSync(p)) rmSync(p, { recursive: true, force: true });
        cleaned++;
      }
    } catch {}
  }
  process.stdout.write(JSON.stringify({ ok: true, cleaned, cutoffDays: keepDays }) + '\n');
}

function cmdHelp() {
  process.stdout.write(`
OpenClaw Worktree Manager — per-agent isolated git worktrees

Commands:
  worktree create --repo <path> --agent <a> --task <slug>
  worktree list --repo <path>
  worktree merge --repo <path> --agent <a> --task <slug> [--squash]
  worktree remove --repo <path> --agent <a> --task <slug>
  worktree cleanup --repo <path> [--keep-days 7]
  worktree help

Layout: <repo>/.openclaw/worktrees/<agent>-<task>/
Branch: openclaw/<agent>-<task>
`);
}

const args = parseArgs(process.argv.slice(2));
const cmd = args._[0] || 'help';
switch (cmd) {
  case 'create': cmdCreate(args); break;
  case 'list': cmdList(args); break;
  case 'merge': cmdMerge(args); break;
  case 'remove': cmdRemove(args); break;
  case 'cleanup': cmdCleanup(args); break;
  case 'help': case '--help': case '-h': cmdHelp(); break;
  default: die(`unknown command: ${cmd}`);
}
