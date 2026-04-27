---
name: github-pr
description: "Convergence-driven GitHub PR pipeline. Picks targets from Tier 0 (curated repos.tier0.yaml) and Tier 1 (network-derived from followed-users events), filters via Tier 2 (BIG_ORGS exclusion) and Tier 3 (per-issue gates), then delegates the actual PR work to claude-code-router. Triple-pass review (codex correctness + gemini architecture + sonnet adversarial) before submit."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [github, pr, convergence, tier0, hermes-native]
    related_skills: [claude-code-router, codex-router, gemini-router]
    standards: /home/lingxufeng/claw/Beatless/standards/Repos.md
---

# github-pr — Hermes-native PR pipeline (with Tier 0/1 convergence)

Replaces `~/.hermes/scripts/github-pr.py`. The new flow obeys the convergence standard at `Beatless/standards/Repos.md` — small target set from Tier 0/1, no global `gh search issues` flood.

## Procedure

### Step 1 — load Tier 0 + Tier 1 candidates

```bash
TIER0=~/claw/Beatless/standards/repos.tier0.yaml
TIER1_STATE=~/.hermes/state/repos.tier1.json

TIER0_REPOS=$(yq -r '.active[].repo' "$TIER0" 2>/dev/null)
TIER1_REPOS=$(jq -r '.repos[].repo' "$TIER1_STATE" 2>/dev/null)

CANDIDATES="$TIER0_REPOS"$'\n'"$TIER1_REPOS"
[ -z "$(echo "$CANDIDATES" | tr -d '[:space:]')" ] && {
  echo "SILENT: no Tier 0 or Tier 1 repos available"; exit 0
}
```

### Step 2 — fetch issues per candidate repo

For each repo:
```bash
for label in "good first issue" "help wanted" "bug"; do
  gh issue list --repo "$repo" --label "$label" --state open --limit 5 --json number,title,labels,author,updatedAt
done
```

### Step 3 — Tier 2 (BIG_ORGS) + Tier 3 (per-issue) gates

Apply existing gates from `~/.hermes/scripts/github-pr.py`:
- BIG_ORGS exclusion (anthropic / google / openai / microsoft / meta / nvidia / ...)
- bot-author + bot-noise label filter
- repo stars ≥ MIN_REPO_STARS (env, default 20)
- AI policy scan of CONTRIBUTING.md (forbidden / restricted)
- CLA gate
- duplicate PR scan via `gh pr list --search "#<num>"`

### Step 4 — score + pick top-N

```bash
# tier_score weights per Repos.md §Discovery flow:
#   Tier 0 membership: +100
#   Tier 1 rank ≤ 3: +30
#   "good first issue" label: +20
#   "help wanted" label: +15
#   tests exist in repo: +10
#   stars ≥ 1000: +5
#   updated last 7d: +5
#   body 200-2000 chars: +5
```

Pick top 1-3 highest-scoring candidates per cron tick.

### Step 5 — delegate PR work to claude-code-router

For each chosen issue:
```
true  # AGENT-ACTION: delegate_task(skill="claude-code-router", args='task="Read issue $URL, design fix, implement, test, push, open PR" working_dir="$(temp clone)"')
```

### Step 6 — three-pass review (P2 hard rule)

After PR opened:
- Pass 1 (correctness): `# Agent: delegate to skill `codex-router`` via your `delegate_task` tool. Args: to score code correctness 0-10
- Pass 2 (architecture): `# Agent: delegate to skill `gemini-router`` via your `delegate_task` tool. Args: to score design 0-10
- Pass 3 (adversarial): a fresh sonnet session (not the one that wrote it) red-teams 0-10

Aggregate: mean. Threshold 6.0. Below → close PR with apology comment, mark `needs-human`.

### Step 7 — status + memory

```bash
cat > ~/.hermes/shared/.last-github-pr-status <<EOF
{
  "ts": "$(date -Iseconds)",
  "tier0_size": $T0_N,
  "tier1_size": $T1_N,
  "candidates_pre_filter": $PRE,
  "candidates_post_filter": $POST,
  "chosen_issue": "$ISSUE",
  "chosen_tier": $TIER,
  "result": "$RESULT",
  "pr_url": "$PR_URL",
  "quality_score": $SCORE
}
EOF

true  # AGENT-ACTION: record to memory tool: "github-pr ts:$(date -Iseconds) result:$RESULT score:$SCORE pr:$PR_URL tier:$TIER"
```

## Anti-patterns

- ❌ Do NOT fall back to `gh search issues --label='good first issue'` over the global graph — that's the divergence we're escaping (per Repos.md §Anti-patterns)
- ❌ Do NOT skip three-pass review even on Tier 0 repos — the gate protects us, not just the repo
- ❌ Do NOT push if any review pass < 6.0 — the missing-passes guard auto-closes such PRs
