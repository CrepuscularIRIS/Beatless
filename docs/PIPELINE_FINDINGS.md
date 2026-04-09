# Pipeline Findings — claude_code_cli, Heartbeat, Mailbox

**Date**: 2026-04-09  
**Scope**: Verify what the `claude_code_cli` router actually invokes, document the current Heartbeat architecture, flag the Mailbox robustness gap, and scope the "blog maintenance + good-first-issue feedback" workflow.

---

## 1. `claude_code_cli` routing — verified by source reading

**File**: `.openclaw/extensions/openclaw-rawcli-router/index.js` (single-mode, ~200 lines).

### What it actually does

```javascript
async function executeClaudeCodeCli(params, cfg, logger) {
  ...
  if (shouldDelegateToGemini(prompt)) {              // keyword-gated
    try {
      const delegated = await runGeminiBridge(...);
      return { backend: "gemini-bridge", ... };
    } catch (error) { /* fall through to claude */ }
  }

  const result = await runClaude(lanePrompt, model, ...);  // default path
  return { backend: "claude", model, result };
}
```

### Backend matrix

| Backend | Invoked when | How |
|---------|--------------|-----|
| **Claude Sonnet 4.6** (default) | Every call, unless Gemini trigger matches | `spawn("claude", ["--permission-mode", "bypassPermissions", "--model", "claude-sonnet-4-6", "--print", prompt])` |
| **Gemini (CLI bridge)** | Prompt contains `deep research`, `外部大脑`, `iterative search`, `递归检索`, `学术调研`, or `gemini ... research` | `adapters/gemini-bridge.js` → `spawn("gemini", ...)` |
| **Codex** | **NEVER directly from this router** | See note below |

### ⚠️ Important finding about Codex

The router's `lanePrompt` text **says** "delegate adversarial review to Codex (keyword: codex review / 审查)" — but that is just **advisory text injected into the Claude prompt**. There is **no code path in the router** that spawns a `codex` CLI.

Codex review happens **one level deeper**, inside ClaudeCode (Sonnet), which has access to the `codex:codex-rescue` / `codex:codex-consult` subagents via Claude's built-in plugin system. So the call chain is:

```
Agent (step-3.5-flash)
  → claude_code_cli tool
    → spawn("claude", "--print", ...)
      → Claude Sonnet 4.6 reads the lanePrompt, sees "codex review" keyword
        → Claude spawns codex-rescue agent as its own subtask
          → which eventually spawns `codex` CLI via its runtime bash tool
```

**This means:**
1. ✅ Sonnet 4.6 is always reached (default backend).
2. ✅ Gemini CLI is reached directly by the router for research keywords.
3. ⚠️ Codex CLI is **indirectly** reachable, only if Sonnet itself decides to delegate. It is not guaranteed.

**If you want explicit Codex routing** (parallel to `gemini-bridge.js`), the fix is a new `adapters/codex-bridge.js` with trigger keywords `codex review / 审查 / P0-P3 / adversarial`, following the same pattern as `gemini-bridge.js`.

### Recommendation

Create `.openclaw/extensions/openclaw-rawcli-router/adapters/codex-bridge.js` that:

1. Exports `shouldDelegateToCodex(prompt)` with triggers: `codex review`, `codex audit`, `审查`, `P0`, `P1`, `adversarial review`.
2. Exports `runCodexBridge({ prompt, cwd, timeoutMs, logger })` that spawns `codex exec --prompt "..."` or whatever the codex CLI entry point is on this box.
3. Wire it into `index.js` after the Gemini check:
   ```javascript
   if (shouldDelegateToCodex(prompt)) { ... return { backend: "codex-bridge", ... }; }
   ```

This should stay under the 200-line router budget (add ~50 lines).

---

## 2. Heartbeat — current architecture (does not touch Mailbox)

**Source of truth**: `.openclaw/openclaw.json`:

```json
"heartbeat": { "every": "30m" }      // per-agent, all 5 = 30m
```

### How it currently works

1. Gateway wakes each agent every 30 minutes on its own cadence (independent per agent).
2. The agent receives an internal "heartbeat" turn with a synthetic prompt derived from `HEARTBEAT.md` in its workspace.
3. The agent reads shared state (`.openclaw/agents/*/memory/`, `Queue.md`, cron outputs), produces a `DONE / BLOCKED / NEXT` report, and writes it back to memory.
4. **There is no automatic delivery to any external channel** from the heartbeat tick. The report stays inside the agent's session/memory.

### What your prompt asks for (gap)

You want:
- Idle agents → send a "nothing to do" message to **Lacia**.
- Lacia → push to **you** via **StepFun app** with a "what do you need me to work on?" message.

**Currently this does not happen.** The heartbeat is a self-monologue. Two pieces are missing:

| Missing piece | Where it should go |
|---------------|-------------------|
| Agent → Lacia idle-ping | Mailbox write from non-Lacia agents. HEARTBEAT.md step: `if status=idle → mail.send(to=lacia, type=idle_report)` |
| Lacia → user (StepFun) | `channels.stepfun` is enabled (`appId: 346623`). Lacia needs to call the `message` tool (or `openclaw message broadcast`) with `--channel stepfun` to push to your account. This is a delivery step in Lacia's heartbeat. |

### Minimal wiring to make this work

1. **Each non-Lacia agent** — add to HEARTBEAT.md:
   ```
   If DONE list is empty AND no cron fired this tick:
     write mailbox letter { to: lacia, type: idle_report,
                            body: "<agent> idle — no delivery this cycle" }
   ```

2. **Lacia** — add to HEARTBEAT.md:
   ```
   Read mailbox for unread idle_report letters.
   If ≥3 agents reporting idle: call message tool with
     channel=stepfun, target=<user>, text="<n> agents idle — what next?"
   Mark letters read.
   ```

3. **StepFun channel** is already enabled in `openclaw.json` — no config change needed. Lacia just needs to know the user's StepFun target ID. Confirm that target with `./openclaw-local channels list` or check `.openclaw/channels/stepfun/` for your pairing.

### Whether to implement this now

Not done in this turn (context budget). This is a clean 2-file edit in each workspace's HEARTBEAT.md plus a small mailbox helper script. I can scope this as a next phase if you confirm the StepFun target.

---

## 3. Mailbox robustness issue — scoping, not fixing

Your observation: *"only Methode's subagent actually completed the `cat file EOF` write operation. Others either didn't execute the write command or failed."*

### Root-cause hypotheses (ordered by likelihood)

1. **Here-doc handling in small models.** step-3.5-flash and MiniMax-M2.7 don't reliably emit multi-line shell strings via the `exec` tool. The `<<EOF` syntax is fragile — newlines inside tool-call JSON get escaped incorrectly. **Fix**: switch mailbox write to the `write` tool (direct file path + content string) instead of `exec cat <<EOF`.

2. **Write-permission deny**. Lacia's `openclaw.json` has `"tools": { "deny": ["edit", "web_fetch", "browser"] }` — but NOT `write`, so that's not it. Need to verify for each agent.

3. **Path resolution**. Agents sometimes write to `~/.openclaw/workspace/mailbox/` but that directory doesn't exist on this box:
   ```
   $ ls ~/.openclaw/workspace/mailbox/
   No such file or directory
   ```
   The `agent-mailbox` skill is installed only in `workspace-snowdrop/skills/agent-mailbox/` — it's not a gateway-level service. Each agent that uses the mailbox must have the skill installed, AND the target dir must exist.

4. **Mailbox ACID**. File-based mailboxes need lock files or atomic-rename (`write → .tmp → rename`) to avoid torn writes when two agents append simultaneously. Not sure if the current skill does this.

### Recommended fix (not executed — confirm before coding)

**Replace the skill-based mailbox with a small wrapper in the `openclaw-local` CLI**:

```bash
./openclaw-local mail send --to lacia --from methode --type idle_report --body "..."
./openclaw-local mail read --agent lacia [--unread]
./openclaw-local mail mark-read <id>
```

Storage: one JSONL file per recipient under `.openclaw/mailbox/<recipient>.jsonl`. Append-only with file locking (`flock`). Agents call this via their `exec` tool — which is known to work reliably (we verified in the rc-probe test).

This is a ~100-line Node script. I'll write it in the next turn if you approve.

---

## 4. Blog maintenance + GitHub issue discovery — workflow design

Your requirements:

- **Blog**: clean up posts under `~/blog/`, reorganize / delete / expand existing content. Not writing new posts.
- **Must run through the OpenClaw pipeline** → GSD commands → Codex/Gemini CLIs → not ClaudeCode-only.
- **GitHub**: discover good first issues on **non-mainstream repos, 5k–30k stars**, and leave meaningful feedback.

### Pipeline design (draft — needs your sign-off)

**Daily cron** (Lacia, 10:00 Asia/Shanghai):

```
Lacia HEARTBEAT-CRON:
  1. Dispatch to Snowdrop via mailbox: "Research good-first-issue candidates
     on GitHub repos with 5k–30k stars, non-mainstream only"
     → Snowdrop calls claude_code_cli with keyword "deep research"
       → hits Gemini bridge → Gemini CLI returns ranked candidates
     → Snowdrop writes findings to mailbox

  2. Dispatch to Methode: "For each candidate, gh issue view,
     filter by reproducibility + clear scope + language fit"
     → Methode calls claude_code_cli → Sonnet → gh CLI
     → writes shortlist to mailbox

  3. Dispatch to Satonus: "Review shortlist against
     our engagement guidelines (no drive-by PRs, real value)"
     → Satonus calls claude_code_cli with keyword "审查"
     → Sonnet delegates to Codex subagent → verdict
     → writes PASS/HOLD/REJECT to mailbox

  4. Dispatch to Kouka: "Post feedback to PASS issues,
     log to Queue.md, commit to ~/blog/Research/github-feedback.md"
     → Kouka calls claude_code_cli → Sonnet → gh issue comment + git commit
```

**Weekly cron** (Kouka, Sat 10:00 Asia/Shanghai):

```
Kouka HEARTBEAT-CRON (Blog-Maintenance):
  1. ls ~/blog/posts/ → find stale posts (>90 days, no updates)
  2. Call claude_code_cli: "review ~/blog/posts/<slug>.md for
     outdated content, broken links, missing sections"
     → Sonnet reads the file, returns recommendations
  3. For each post flagged expand: dispatch to Snowdrop
     "deep research update for <topic>"
     → Gemini bridge
  4. Kouka stitches the update into the post, commits to
     ~/blog/posts/ and pushes to GitHub

  Deletion: Kouka proposes delete list in Queue.md.
  Satonus reviews before any delete (Codex keyword). No unilateral deletes.
```

### Verification that this hits Codex AND Gemini (not just Sonnet)

- **Gemini**: triggered by step 1 (research "deep research" keyword) → verified code path.
- **Codex**: triggered by step 3 (review "审查" keyword) → currently indirect via Sonnet's built-in delegation. Will become direct if you approve the `codex-bridge.js` proposal in §1.
- **Sonnet**: triggered by every non-keyword call (steps 2, 4, 1-blog, 2-blog).

---

## Summary & decision points

| Item | Status | Action needed |
|------|--------|---------------|
| claude_code_cli → Sonnet | ✅ verified (default path) | none |
| claude_code_cli → Gemini | ✅ verified (keyword-gated) | none |
| claude_code_cli → Codex | ⚠️ only indirect via Sonnet | **Decision**: write `codex-bridge.js`? (~50 lines) |
| Heartbeat → StepFun push | ❌ not wired | **Decision**: add Lacia stepfun push on ≥3 idle reports? Need your StepFun target ID. |
| Mailbox robustness | ⚠️ here-doc fragile, no locking | **Decision**: replace skill-based mailbox with `openclaw-local mail` CLI wrapper? (~100 lines) |
| Blog maintenance workflow | 📋 designed, not implemented | **Decision**: approve pipeline above before I wire the crons? |
| GitHub issue feedback workflow | 📋 designed, not implemented | **Decision**: same. Also, need engagement guidelines (PR vs comment, max/day). |

### Nothing destructive has been done in this turn.

I only read source, verified config, and wrote this doc. No workspace files changed; no commits; no pushes; no cron edits.

**Please pick which of the 5 decision points you want me to proceed with, in what order.**
