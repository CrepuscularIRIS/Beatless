---
name: daily-evolution
description: Daily strict-regulation audit of Hermes Agent + Beatless. Three-model parallel audit (Opus 4.7 + Codex gpt-5.3-codex + Gemini 3.1-pro) all run the SAME audit task simultaneously; final synthesis pass collapses three independent reports into one expert report. Output is committed as a blog post mdx and recorded into Hermes memory so the next cron tick is aware of prior findings.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [audit, evolution, regulations, heterogeneous-review, hermes-native]
    related_skills: [claude-code-router, codex-router, gemini-router]
---

# daily-evolution — Hermes-native audit loop

Replaces `~/.hermes/scripts/daily-evolution.py`. The driver becomes a thin shim that hands off to this skill. The skill orchestrates three independent audits + synthesis, writes the result to the blog, and stores findings in Hermes memory.

## Procedure

### Step 1 — gather state (Hermes-native, no external CLI yet)

```bash
STATE=/tmp/daily-evolution-state-$(date +%Y%m%d-%H%M%S).json
{
  echo "{"
  echo "  \"ts\": \"$(date -Iseconds)\","
  echo "  \"cron_jobs\": $(hermes cron list --json 2>/dev/null || echo '[]'),"
  echo "  \"errors_24h\": $(grep -c ERROR ~/.hermes/logs/errors.log 2>/dev/null || echo 0),"
  echo "  \"agent_log_tail\": $(tail -100 ~/.hermes/logs/agent.log | jq -Rs . 2>/dev/null || echo '\"\"')"
  echo "}"
} > "$STATE"
```

### Step 2 — three parallel audits (异源审查 hard rule)

Invoke all three in parallel via background jobs:

```bash
# Pass A: Opus (this Hermes session itself, no router needed — the host does it)
# Pass B: Codex via codex-router skill
# Pass C: Gemini via gemini-router skill

call_skill codex-router "Audit the Hermes system. State at $STATE. Read ~/claw/Beatless/standards/Regulations.md for rules. Output findings + verdict per rule. RESULT: <pass|fail|flag> SCORE: <0-10>" &
PID_CODEX=$!

call_skill gemini-router "Same audit task. Same state file. Independent verdict required. VERDICT: <pass|fail|flag>" &
PID_GEMINI=$!

# Pass A runs in this Hermes session: read state, read regulations, write findings.
# Wait for all three to complete.
wait $PID_CODEX $PID_GEMINI
```

### Step 3 — synthesis (Opus only — single voice, but reads all three reports)

```
Read three audit reports:
  /tmp/daily-evolution-opus-<ts>.md
  /tmp/daily-evolution-codex-<ts>.md
  /tmp/daily-evolution-gemini-<ts>.md

Produce a single synthesis with:
  - Findings consolidated by rule
  - Disagreements explicitly called out (this is where signal lives)
  - Three highest-priority actions
  - Open questions for human judgment
  - New regulation candidates (R9+)
```

### Step 4 — write to blog + Hermes memory

```bash
SLUG="daily-evolution-$(date +%Y-%m-%d)"
OUT=~/claw/blog/src/content/blogs/$SLUG/index.mdx

mkdir -p "$(dirname "$OUT")"
cat > "$OUT" <<EOF
---
title: "Daily Evolution — $(date +%Y-%m-%d)"
description: "Three-model strict-regulation audit synthesis."
publishDate: "$(date +%Y-%m-%d)"
language: en
draft: false
hIE: saturnus
category: audit
tags: [audit, evolution, hermes, beatless]
---

<synthesis content>
EOF

cd ~/claw/blog && git add "$OUT" && git commit -m "audit(evolution): daily $(date +%Y-%m-%d)"

# Memory: future cron ticks see this
hermes memory write "daily-evolution $(date +%Y-%m-%d) committed:$SLUG findings_count:$N priority_actions:$ACTIONS"
```

## Constitutional anchor

Reads `~/claw/Beatless/standards/Regulations.md` § Three Core Principles every run:

- **P1 Parallel-Orthogonal** — three audits run in parallel, independent contexts
- **P2 Triple-Heterogeneous Review** — Opus (Anthropic) + Codex (OpenAI) + Gemini (Google), no model family judges itself
- **P3 Surface Implicit Knowledge** — every audit must surface silent_priors, unspoken_alternatives, failure_dna, hidden_dependencies

## NEVER

- Never run only one audit — that violates P2
- Never use the same model family for both audit and synthesis (Opus does synthesis only because it didn't audit alone)
- Never skip writing to Hermes memory — that's how subsequent ticks see findings (was the F1 bug fix lever)
