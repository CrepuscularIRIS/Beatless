#!/usr/bin/env node
/**
 * OpenClaw Verification Gate — ported from GSD2 verification-gate.ts
 *
 * Discovers and runs post-execution verification commands for a project.
 * Agents call this after each `claude_code_cli` invocation to confirm
 * the work didn't break anything.
 *
 * Discovery order (matches GSD2 D003):
 *   1. Explicit --commands flag
 *   2. package.json scripts: typecheck → lint → test
 *   3. Makefile targets: check → lint → test
 *   4. Python: mypy, ruff check, pytest
 *
 * Commands:
 *   verify run --cwd <path> [--commands "cmd1;cmd2"] [--timeout 60]
 *   verify discover --cwd <path>
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { execSync } from 'node:child_process';

function die(msg, code = 1) { process.stderr.write(`verify: ${msg}\n`); process.exit(code); }
function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) { const k = a.slice(2); out[k] = (argv[i+1] && !argv[i+1].startsWith('--')) ? argv[++i] : 'true'; }
    else out._.push(a);
  }
  return out;
}

function discoverCommands(cwd) {
  const found = [];

  // package.json scripts
  const pkgPath = join(cwd, 'package.json');
  if (existsSync(pkgPath)) {
    try {
      const pkg = JSON.parse(readFileSync(pkgPath, 'utf8'));
      const scripts = pkg.scripts || {};
      for (const key of ['typecheck', 'type-check', 'tsc', 'lint', 'test']) {
        if (scripts[key]) found.push({ name: key, cmd: `npm run ${key}`, source: 'package.json' });
      }
    } catch {}
  }

  // Makefile
  const makePath = join(cwd, 'Makefile');
  if (existsSync(makePath)) {
    try {
      const mk = readFileSync(makePath, 'utf8');
      for (const target of ['check', 'lint', 'test']) {
        if (mk.includes(`${target}:`)) found.push({ name: target, cmd: `make ${target}`, source: 'Makefile' });
      }
    } catch {}
  }

  // Python
  const pyproject = join(cwd, 'pyproject.toml');
  const setupPy = join(cwd, 'setup.py');
  if (existsSync(pyproject) || existsSync(setupPy)) {
    found.push({ name: 'ruff', cmd: 'ruff check .', source: 'python-default' });
    found.push({ name: 'pytest', cmd: 'pytest --tb=short -q', source: 'python-default' });
  }

  // Go
  if (existsSync(join(cwd, 'go.mod'))) {
    found.push({ name: 'go-vet', cmd: 'go vet ./...', source: 'go-default' });
    found.push({ name: 'go-test', cmd: 'go test -race ./...', source: 'go-default' });
  }

  return found;
}

function runCommand(cmd, cwd, timeoutSec) {
  const start = Date.now();
  try {
    const output = execSync(cmd, {
      cwd,
      timeout: timeoutSec * 1000,
      stdio: ['ignore', 'pipe', 'pipe'],
      maxBuffer: 10 * 1024 * 1024,
    });
    return { cmd, ok: true, durationMs: Date.now() - start, output: output.toString().slice(-2048) };
  } catch (err) {
    const stderr = err.stderr?.toString().slice(-2048) || '';
    const stdout = err.stdout?.toString().slice(-2048) || '';
    return { cmd, ok: false, durationMs: Date.now() - start, exitCode: err.status, stderr, stdout };
  }
}

function cmdDiscover(args) {
  const cwd = args.cwd || process.cwd();
  const commands = discoverCommands(cwd);
  process.stdout.write(JSON.stringify({ ok: true, cwd, commands }, null, 2) + '\n');
}

function cmdRun(args) {
  const cwd = args.cwd || process.cwd();
  const timeoutSec = parseInt(args.timeout || '60', 10);

  let commands;
  if (args.commands) {
    commands = args.commands.split(';').map(c => ({ name: c.trim(), cmd: c.trim(), source: 'explicit' }));
  } else {
    commands = discoverCommands(cwd);
  }

  if (commands.length === 0) {
    process.stdout.write(JSON.stringify({ ok: true, cwd, verdict: 'SKIP', reason: 'no verification commands discovered', results: [] }) + '\n');
    return;
  }

  const results = [];
  let allPassed = true;
  for (const c of commands) {
    const result = runCommand(c.cmd, cwd, timeoutSec);
    results.push({ ...c, ...result });
    if (!result.ok) allPassed = false;
  }

  const verdict = allPassed ? 'PASS' : 'FAIL';
  const failedCount = results.filter(r => !r.ok).length;
  process.stdout.write(JSON.stringify({
    ok: true, cwd, verdict,
    summary: `${results.length - failedCount}/${results.length} passed`,
    results: results.map(r => ({ name: r.name, cmd: r.cmd, ok: r.ok, durationMs: r.durationMs, ...(r.ok ? {} : { exitCode: r.exitCode, stderr: r.stderr?.slice(0, 500) }) })),
  }, null, 2) + '\n');
}

function cmdHelp() {
  process.stdout.write(`
OpenClaw Verification Gate — post-execution check runner

Commands:
  verify run --cwd <path> [--commands "cmd1;cmd2"] [--timeout 60]
  verify discover --cwd <path>
  verify help

Discovery: package.json scripts → Makefile targets → Python (ruff/pytest) → Go (vet/test)
`);
}

const args = parseArgs(process.argv.slice(2));
const cmd = args._[0] || 'help';
switch (cmd) {
  case 'run': cmdRun(args); break;
  case 'discover': cmdDiscover(args); break;
  case 'help': case '--help': case '-h': cmdHelp(); break;
  default: die(`unknown command: ${cmd}`);
}
