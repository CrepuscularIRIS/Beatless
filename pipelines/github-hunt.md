---
name: github-hunt
description: "Deep autonomous bug hunting for 1K-10K star agent/LLM repos. Clones repos, sets up environment (uv/npm/go), runs existing tests to find real crashes, debugs failures to root cause, then performs parallel static security scan (Codex + Gemini + Claude). Files issues only for confirmed P0/P1 bugs with reproduction commands and stack traces. Use whenever the user mentions hunting bugs, scanning GitHub repos, finding issues in open source projects, automated code auditing, or deep testing of agent/LLM repositories."
---

# GitHub Deep Hunt Pipeline v3

Discover repos → clone → **set up environment** → **run tests to find crashes** → **debug failures** → parallel static security scan → cross-validate → file issues.

## Why v3

v1 relied on `claude --print` which skipped Codex/Gemini. v2 added real Agent subagents but only did static code reading. v3 adds **dynamic testing** — build the project, run its test suite, catch real crashes, then debug them. Security issues remain static-analysis-only since they don't need runtime to detect.

## Execution Model

- **Claude**: Orchestrator + direct analysis (Read/Grep/Glob) + GSD2-style debug
- **Codex** (`codex:codex-rescue` agent): Independent security audit
- **Gemini** (`gemini:gemini-consult` agent): Architecture-level security review + research
- **gh CLI**: Repo search, clone, issue creation
- **uv / npm / go**: Environment setup and test execution

## Context

- Archive: `~/workspace/archive/`
- Staging: `~/workspace/pr-stage/`
- GitHub: `gh` authenticated as CrepuscularIRIS
- Python venvs: use `uv` (fast, isolated)

---

## Phase 1: DISCOVERY

```bash
gh search repos --stars=1000..10000 --sort=updated --limit=30 \
  --json fullName,stargazersCount,description,updatedAt,hasIssuesEnabled,language \
  -- "agent OR llm OR langchain OR autogen OR crewai OR swarm OR rag OR embedding OR inference OR serving"
```

Filter:
- Issues enabled, not archived, pushed in last 30 days
- Not already in `~/workspace/archive/`
- AI agents, LLM frameworks, inference, RAG pipelines
- Prefer: Python, TypeScript, Go, Rust with active communities
- Avoid: tutorials, awesome-lists, thin wrappers

Select TOP 2. Clone:
```bash
gh repo clone <owner/repo> ~/workspace/archive/<repo-name> -- --depth=1
```

---

## Phase 2: ENVIRONMENT SETUP

This phase is critical — without a working environment you can only do static analysis, missing the most valuable dynamic bugs.

```bash
cd ~/workspace/archive/<repo-name>

# Python
if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f requirements.txt ]; then
  uv venv .venv && source .venv/bin/activate
  # Try dev/test extras first for test dependencies
  uv pip install -e ".[dev,test]" 2>&1 || uv pip install -e ".[dev]" 2>&1 || uv pip install -e . 2>&1
  [ -f requirements.txt ] && uv pip install -r requirements.txt 2>&1
  [ -f requirements-dev.txt ] && uv pip install -r requirements-dev.txt 2>&1
fi

# Go
if [ -f go.mod ]; then
  go mod download 2>&1
  go build ./... 2>&1
fi

# Node.js
if [ -f package.json ]; then
  npm install 2>&1
  npm run build 2>&1 || true
fi

# Rust
if [ -f Cargo.toml ]; then
  cargo build 2>&1
fi
```

Record the build outcome:
- **BUILD PASS**: Proceed to dynamic testing (Phase 3)
- **BUILD FAIL**: Log the error, proceed to static-only analysis (skip Phase 3, go to Phase 5)

---

## Phase 3: DYNAMIC TEST EXECUTION

Run the project's existing test suite. Test failures are the **strongest evidence** of real bugs — the project's own tests prove them.

```bash
cd ~/workspace/archive/<repo-name>

# Python
if [ -f pyproject.toml ] || [ -f setup.py ]; then
  source .venv/bin/activate 2>/dev/null
  # Run with verbose output to capture stack traces
  pytest --tb=long -v 2>&1 | tee /tmp/hunt-test-$(basename $PWD).log
fi

# Go (with race detector)
if [ -f go.mod ]; then
  go test -race -count=1 -v ./... 2>&1 | tee /tmp/hunt-test-$(basename $PWD).log
fi

# Node.js
if [ -f package.json ]; then
  npm test 2>&1 | tee /tmp/hunt-test-$(basename $PWD).log
fi

# Rust
if [ -f Cargo.toml ]; then
  cargo test 2>&1 | tee /tmp/hunt-test-$(basename $PWD).log
fi
```

Parse results:
- **ALL PASS**: Bugs are in untested code paths. Move to static analysis (Phase 5).
- **SOME FAIL**: Each failure is a potential finding. Capture test name, stack trace, error. Move to Phase 4 (debug).
- **NO TESTS**: No test suite. Move to static analysis (Phase 5).

---

## Phase 4: DEBUG FAILURES

For each test failure from Phase 3, apply a lightweight GSD2-style debug workflow:

### 4a. Isolate the failure

Run the failing test alone to get a clean stack trace:
```bash
pytest tests/test_foo.py::test_failing_case -v --tb=long 2>&1
```

### 4b. Trace the root cause

Read the stack trace bottom-up:
1. What exception/panic was thrown?
2. Which file:line triggered it?
3. Read that code — what input causes the failure?
4. Is this a real bug (wrong logic) or a test environment issue (missing mock, network dependency)?

### 4c. Classify

- **P0**: Crash, data loss, uncaught exception in production code path
- **P1**: Wrong result, race condition, resource leak
- **TEST_ENV**: Failure due to missing test fixture, network dependency, or flaky timing — skip these
- **KNOWN**: Already reported as open issue — skip

### 4d. Draft fix suggestion

For each P0/P1 failure, write a 1-10 line suggested fix with explanation of why it works.

### 4e. Save findings

```
~/workspace/pr-stage/<date>-<repo>-test-failure-<N>.md
```

Include: test command, full stack trace, root cause analysis, severity, suggested fix.

---

## Phase 5: STATIC SECURITY SCAN (Parallel Agents)

Spawn THREE independent agents in a SINGLE message. Security vulnerabilities can be found without running code — static analysis is sufficient and often better for security.

### Codex (`codex:codex-rescue` agent)

```
Security audit of ~/workspace/archive/<repo-name>.

Focus ONLY on exploitable security vulnerabilities:
1. RCE: eval(), exec(), subprocess with shell=True, unsandboxed code execution
2. Injection: SQL injection, command injection, SSTI, XSS
3. Path traversal: user-controlled file paths, symlink attacks, directory escape
4. SSRF: HTTP requests with user-controlled URLs hitting internal services
5. Auth bypass: missing auth checks, hardcoded credentials, token exposure

For each finding provide: file:line, vulnerability type, exploitation scenario, suggested fix.
P0 (directly exploitable) and P1 (requires specific conditions) only.
```

### Gemini (`gemini:gemini-consult` agent)

```
Architecture-level security and reliability review of ~/workspace/archive/<repo-name>.

Focus on design-level issues:
1. Trust boundaries: where does user input enter? Validated before sensitive operations?
2. Concurrency: race conditions, TOCTOU, shared mutable state without locks
3. Resource management: unclosed connections, unbounded queues, memory leaks on error paths
4. API contracts: endpoints accepting more than intended, missing rate limits, open redirects

For each finding: file:line, description, reproduction scenario, severity P0/P1.
```

### Claude Direct Analysis (Read/Grep/Glob)

Grep for dangerous patterns and read the surrounding code to confirm:
- `eval(`, `exec(`, `os.system(`, `subprocess.run(.*shell=True`
- `trust_remote_code`, `pickle.load`, `yaml.load(` without SafeLoader
- `tar.extractall(` without filter, `zipfile.extractall(` without validation
- Hardcoded API keys, passwords, tokens in source files
- HTTP handlers with no input validation

Read the entry point files to understand the attack surface.

---

## Phase 6: CROSS-VALIDATION MERGE

### Dynamic findings (from test failures in Phase 3-4)
- Automatically confirmed — the test suite itself proves the bug
- No >=2/3 agreement needed
- Include: exact test command, stack trace, root cause, fix suggestion

### Static findings (from security scan in Phase 5)
- Require **>=2/3 reviewer agreement** (Claude + Codex + Gemini)
- Verified by reading the actual code at file:line
- Not already reported as an open issue

### Dedup against existing issues
```bash
gh issue list --repo <owner/repo> --state open --limit 200 --json title,body,labels | head -500
```

Remove findings matching existing issues.

---

## Phase 7: FILE ISSUES

For each validated finding:

```bash
gh issue create --repo <owner/repo> \
  --title "<type>: <concise bug title>" \
  --body "$(cat <<'EOF'
## Bug Description

<2-3 sentences: what's broken>

## Location

`<file>:<line>`

## Reproduction

```bash
# For dynamic bugs — exact test command:
pytest tests/test_foo.py::test_failing -v

# For security bugs — exploitation steps:
curl -X POST http://localhost:8000/api/exec -d '{"code":"import os; os.system(\"id\")"}'
```

## Stack Trace

```
<paste stack trace for dynamic bugs, or code snippet showing the vulnerability for static bugs>
```

## Impact

<crash? data loss? RCE? information disclosure?>

## Suggested Fix

```<language>
<1-10 line minimal fix>
```

---
Found via automated testing and codebase analysis. Happy to submit a PR if confirmed.
EOF
)"
```

### Quality Rules (from mention.md)
- No internal jargon — no mention of "triple review", agents, or orchestration
- Problem → Evidence → Fix format
- For test failures: include the exact `pytest`/`go test` command (strongest evidence)
- One issue per bug, minimal scope

---

## Phase 8: SUMMARY REPORT

Write to `~/workspace/pr-stage/hunt-summary-<date>.md`:

```markdown
# Hunt Summary — <date>

## Repos Scanned
- <repo> (<stars>⭐, <lang>) — build: PASS/FAIL, tests: X pass / Y fail / Z skip

## Dynamic Findings (from test execution)
- <N> test failures analyzed
- <M> confirmed as P0/P1 bugs
- Evidence: test commands + stack traces

## Static Findings (from security scan)
- Codex: <N> findings
- Gemini: <N> findings  
- Claude: <N> findings
- Passed >=2/3: <M> findings

## Issues Filed
| # | Repo | Title | Severity | Source |
|---|------|-------|----------|--------|
| 1 | owner/repo#N | title | P0 | dynamic/static |

## Rejected
- <finding>: <reason>
```

---

## Rules

1. **Set up environment first** — build the project before analyzing it
2. **Run tests** — test failures are the strongest bug evidence
3. **Debug crashes to root cause** — don't just report "test failed", explain why
4. **Parallel Codex + Gemini for security** — static analysis is sufficient for security
5. **Dynamic findings auto-confirmed** — test failure IS the proof, no agreement needed
6. **Static findings need >=2/3** — cross-validation still required for security claims
7. **Include reproduction commands** — every issue should have a runnable test/curl command
8. **Professional format** — no internal jargon, follow mention.md guidelines
