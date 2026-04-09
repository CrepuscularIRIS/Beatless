#!/usr/bin/env node
/**
 * OpenClaw Harness — unified pre/post execution wrapper for agent turns.
 *
 * Ported from GSD2's safety harness + auto-post-unit + auto-timeout-recovery.
 * This is the single entry point agents call AROUND each claude_code_cli invocation.
 *
 * Usage (agent calls via exec):
 *   harness pre  --agent <a> --task "<description>"   # before rc call
 *   harness post --agent <a> --task "<description>" --status ok|fail --input <n> --output <n> --model <m> --duration <ms>
 *   harness status                                    # system health summary
 *   harness config                                    # show harness settings
 *
 * pre:  acquire session lock → create git checkpoint → record start time
 * post: record metrics → run verification (if cwd has tests) → release lock → push idle/result to mailbox
 */

import { execSync } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const SCRIPTS = dirname(__filename);
const REPO_ROOT = dirname(dirname(dirname(__filename)));

function die(msg, code = 1) { process.stderr.write(`harness: ${msg}\n`); process.exit(code); }
function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) { const k = a.slice(2); out[k] = (argv[i+1] && !argv[i+1].startsWith('--')) ? argv[++i] : 'true'; }
    else out._.push(a);
  }
  return out;
}

function run(script, args) {
  const cmd = `node ${join(SCRIPTS, script)} ${args}`;
  try {
    return JSON.parse(execSync(cmd, { stdio: ['ignore', 'pipe', 'pipe'], timeout: 15000 }).toString().trim());
  } catch (e) {
    const stderr = e.stderr?.toString().slice(0, 500) || '';
    return { ok: false, error: `${script} failed: ${stderr}` };
  }
}

// ── Harness config (ported from GSD2 safety-harness.ts defaults) ──
const CONFIG = {
  session_locking: true,
  git_checkpoints: true,
  metrics_recording: true,
  post_verification: false,  // opt-in: set true when repo has tests
  mailbox_reporting: true,
  timeout_recovery: true,
  idle_timeout_retries: 2,
  hard_timeout_retries: 1,
  stale_window_minutes: 30,
  max_loop_iterations: 500,
  budget_ceiling_usd: null,  // no ceiling by default
};

function cmdPre(args) {
  const agent = args.agent || die('--agent required');
  const task = args.task || 'unknown';
  const results = { agent, task, phase: 'pre', steps: [] };

  // 1. Session lock
  if (CONFIG.session_locking) {
    const lock = run('session-lock.mjs', `acquire --agent ${agent} --unit-type task --unit-id "${task.slice(0, 40)}"`);
    results.steps.push({ step: 'session_lock', ...lock });
    if (!lock.acquired) {
      results.blocked = true;
      results.reason = `lock held by PID ${lock.existingPid || 'unknown'}`;
      process.stdout.write(JSON.stringify(results, null, 2) + '\n');
      return;
    }
  }

  // 2. Git checkpoint
  if (CONFIG.git_checkpoints) {
    const cp = run('checkpoint.mjs', `create --agent ${agent} --label "pre: ${task.slice(0, 60)}"`);
    results.steps.push({ step: 'git_checkpoint', ...cp });
  }

  // 3. Activity log
  const logEntry = JSON.stringify({ event: 'turn_start', task: task.slice(0, 200), model: args.model || 'unknown' });
  const log = run('checkpoint.mjs', `log --agent ${agent} --entry '${logEntry.replace(/'/g, "\\'")}'`);
  results.steps.push({ step: 'activity_log', ok: log.ok });

  results.ok = true;
  results.startedAt = new Date().toISOString();
  process.stdout.write(JSON.stringify(results, null, 2) + '\n');
}

function cmdPost(args) {
  const agent = args.agent || die('--agent required');
  const task = args.task || 'unknown';
  const status = args.status || 'ok';
  const model = args.model || 'unknown';
  const input = args.input || '0';
  const output = args.output || '0';
  const duration = args.duration || '0';
  const results = { agent, task, phase: 'post', status, steps: [] };

  // 1. Record metrics
  if (CONFIG.metrics_recording) {
    const m = run('metrics.mjs', `record --agent ${agent} --model ${model} --input ${input} --output ${output} --duration ${duration}`);
    results.steps.push({ step: 'metrics', ...m });
  }

  // 2. Post-verification (if enabled and status=ok)
  if (CONFIG.post_verification && status === 'ok') {
    const cwd = args.cwd || REPO_ROOT;
    const v = run('verify.mjs', `run --cwd ${cwd} --timeout 60`);
    results.steps.push({ step: 'verification', verdict: v.verdict || 'ERROR', summary: v.summary });
    if (v.verdict === 'FAIL') {
      results.verification_failed = true;
    }
  }

  // 3. Activity log
  const logEntry = JSON.stringify({ event: 'turn_end', task: task.slice(0, 200), status, model, tokens: { input, output }, durationMs: duration });
  run('checkpoint.mjs', `log --agent ${agent} --entry '${logEntry.replace(/'/g, "\\'")}'`);

  // 4. Release session lock
  if (CONFIG.session_locking) {
    const rel = run('session-lock.mjs', `release --agent ${agent}`);
    results.steps.push({ step: 'release_lock', ...rel });
  }

  // 5. Mailbox reporting (send result to lacia if task completed)
  if (CONFIG.mailbox_reporting && status === 'ok') {
    const body = `${agent} completed: ${task.slice(0, 100)} (${model}, ${duration}ms)`;
    run('mail.mjs', `send --from ${agent} --to lacia --type task_result --subject "turn complete" --body "${body.replace(/"/g, '\\"')}"`);
  }

  results.ok = true;
  results.completedAt = new Date().toISOString();
  process.stdout.write(JSON.stringify(results, null, 2) + '\n');
}

function cmdStatus(_args) {
  // Aggregate system health
  const locks = run('session-lock.mjs', 'status-all');
  const mailboxes = run('mail.mjs', 'list');
  const budget = run('metrics.mjs', 'budget');

  process.stdout.write(JSON.stringify({
    ok: true,
    harness_config: CONFIG,
    locks: locks.locks || [],
    mailboxes: mailboxes.mailboxes || [],
    budget: budget.agents || [],
    checkedAt: new Date().toISOString(),
  }, null, 2) + '\n');
}

function cmdConfig(_args) {
  process.stdout.write(JSON.stringify({ ok: true, config: CONFIG }, null, 2) + '\n');
}

function cmdHelp() {
  process.stdout.write(`
OpenClaw Harness — unified pre/post execution wrapper

Commands:
  harness pre   --agent <a> --task "<description>"
  harness post  --agent <a> --task "<description>" --status ok|fail --input <n> --output <n> --model <m> --duration <ms>
  harness status
  harness config
  harness help

Flow: pre (lock → checkpoint → log) → agent work → post (metrics → verify → unlock → report)
`);
}

const args = parseArgs(process.argv.slice(2));
const cmd = args._[0] || 'help';
switch (cmd) {
  case 'pre': cmdPre(args); break;
  case 'post': cmdPost(args); break;
  case 'status': cmdStatus(args); break;
  case 'config': cmdConfig(args); break;
  case 'help': case '--help': case '-h': cmdHelp(); break;
  default: die(`unknown command: ${cmd}`);
}
