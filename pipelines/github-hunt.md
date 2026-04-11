---
description: "Hunt critical GitHub issues in 1K-10K star agent/LLM repos. Deep scan with Codex+Gemini+Claude triple analysis. Output proposals only, no auto-submit."
---

# GitHub Issue Hunt Pipeline

Autonomous pipeline: discover repos → clone → deep scan → triple review → output proposals.

**This pipeline does NOT file issues or submit PRs. It only produces validated issue proposals.**

## Execution Model

Claude Code is the main executor. For each repo analysis:
- **Claude**: Primary code analysis, bug hunting, vulnerability scanning
- **Codex** (via `/codex:review`): Code quality audit, security review, structural analysis
- **Gemini** (via `/gemini:consult`): Architecture analysis, whole-repo context, external knowledge

All three MUST be called for every repo. Do not skip or fake any review.

## Context

- Archive directory: `~/workspace/archive/`
- Staging directory: `~/workspace/pr-stage/`
- GitHub CLI: `gh` (authenticated as CrepuscularIRIS)
- Working directory: MUST `cd` into each repo before analysis

---

## Phase 1: DISCOVERY

Search for high-quality target repos:

```bash
gh search repos --stars=1000..10000 --sort=updated --limit=30 \
  --json fullName,stargazersCount,description,updatedAt,hasIssuesEnabled,language \
  -- "agent OR llm OR langchain OR autogen OR crewai OR swarm OR rag OR embedding OR inference OR serving"
```

Filter criteria:
- Has issues enabled, not archived, pushed in last 30 days
- Not already in `~/workspace/archive/`
- Must be related to: AI agents, LLM frameworks, inference engines, RAG pipelines, embedding systems
- Prefer: Python, TypeScript, Go, Rust repos with active communities
- Prefer repos with < 500 open issues (indicates responsive maintainers)
- Avoid: tutorial repos, awesome-lists, wrapper-only projects

Select TOP 2 repos (not 3 — depth over breadth). Clone:
```bash
gh repo clone <owner/repo> ~/workspace/archive/<repo-name> -- --depth=1
```

---

## Phase 2: DEEP SCAN (per repo, MUST cd into repo first)

For EACH cloned repo, execute ALL THREE analysis passes:

### Pass 1: Claude Direct Analysis (you do this yourself)

```bash
cd ~/workspace/archive/<repo-name>
```

Then use Read, Grep, Glob tools to deeply analyze the codebase:
- Read entry points (main.go, main.py, src/index.ts, etc.)
- Grep for dangerous patterns: `eval(`, `exec(`, `unsafe`, `panic(`, `os.Exit`, `TODO`, `FIXME`, `HACK`
- Find error handling gaps: bare `except:`, empty `catch {}`, unchecked error returns
- Look for race conditions: shared mutable state, missing locks, goroutine leaks
- Check for security issues: hardcoded secrets, SQL injection, path traversal, SSRF

Focus on **critical issues that break functionality or compromise security**. Ignore style issues, documentation gaps, or minor code quality problems.

### Pass 2: Codex Code Audit (MANDATORY — must actually call this)

Still in the repo directory, run:

```
/codex:review
```

This invokes the Codex CLI to perform an independent code review. Wait for its output and record the findings verbatim. Do NOT invent Codex findings.

### Pass 3: Gemini Architecture Analysis (MANDATORY — must actually call this)

Run:

```
/gemini:consult "Analyze the codebase at the current directory. Focus on: (1) critical bugs that would cause crashes or data loss in production, (2) security vulnerabilities exploitable by external users, (3) race conditions or concurrency bugs, (4) API contract violations that break client integrations. Ignore documentation, style, and minor issues. List only P0/P1 severity findings with exact file paths and line numbers."
```

Record Gemini's findings verbatim. Do NOT invent Gemini findings.

### Cross-reference with existing issues

```bash
gh issue list --repo <owner/repo> --state open --limit 200 --json title,body,labels | head -500
```

Remove any finding that matches an existing open issue.

---

## Phase 3: TRIPLE MERGE + QUALITY FILTER

For each finding from all 3 passes:

### Severity classification (ONLY keep P0 and P1)

- **P0 (Critical)**: Crashes, data loss, security vulnerabilities, authentication bypass, RCE, SQL injection
- **P1 (High)**: Race conditions causing incorrect results, API contract violations breaking clients, resource leaks causing OOM
- **P2+ (Skip)**: Style issues, documentation, performance suggestions, test coverage gaps → DO NOT INCLUDE

### Validation checklist (ALL must be true to keep a finding)

- [ ] Issue is reproducible (you can describe exact steps)
- [ ] Issue affects real users (not just theoretical)
- [ ] Issue is not already reported (checked existing issues)
- [ ] You verified the code path exists (read the actual file and line)
- [ ] At least 2 of 3 reviewers (Claude/Codex/Gemini) flagged it

### Write proposal for each validated finding

Save to `~/workspace/pr-stage/<date>-<repo>-finding-<N>.md`:

```markdown
---
repo: <owner/repo>
severity: P0|P1
found_by: [claude, codex, gemini]  # which reviewers found this
status: proposal
---

# Issue Proposal: <concise title>

## Problem
<exact file path, line number, code snippet>
<what happens and why it's critical>

## Reproduction
<concrete steps to trigger the bug>

## Impact
<who is affected, how severe, how common>

## Evidence

### Claude Analysis
<your findings>

### Codex Review Output
<verbatim codex output for this finding>

### Gemini Analysis Output
<verbatim gemini output for this finding>

## Suggested Fix
<code diff or approach — only if fix is clear>
```

---

## Phase 4: FINAL REVIEW GATE

After all proposals are written, do a final cross-check:

1. Re-read each proposal file
2. Verify the code references are correct (Read the actual files cited)
3. Run `/codex:review` one final time on the proposals themselves
4. Run `/gemini:consult "Review these issue proposals: [list files]. Are they technically accurate, non-duplicate, and severe enough (P0/P1 only) to submit to the maintainers?"` 

Record final verdicts. Mark each proposal as `PASS` or `REJECT` in the frontmatter.

---

## Phase 5: SUMMARY REPORT

Write to `~/workspace/pr-stage/hunt-summary-<date>.md`:

```markdown
# GitHub Hunt Report — <date>

## Repos Scanned
| Repo | Stars | Language |
|------|-------|----------|

## Findings (P0/P1 only)
| # | Repo | Title | Severity | Found By | Final Verdict |
|---|------|-------|----------|----------|---------------|

## Rejected Findings
| # | Title | Reason |

## Review Evidence
### Codex Review Calls
- Call 1: <timestamp>, repo: <name>, output summary
- Call 2: ...

### Gemini Consult Calls
- Call 1: <timestamp>, repo: <name>, output summary
- Call 2: ...

## Next Steps
- Proposals marked PASS are ready for manual review before submission
- User should verify reproduction steps before filing issues
```

---

## Rules

1. **DO NOT file issues or submit PRs** — only produce proposals
2. **MUST actually call `/codex:review` and `/gemini:consult`** — no faking
3. **MUST `cd` into repo directory** before any analysis
4. **ONLY P0/P1 findings** — skip everything else
5. **Verify before claiming** — read the actual code, don't guess
6. **At least 2/3 reviewers must agree** for a finding to pass
7. Report progress after each phase completes
