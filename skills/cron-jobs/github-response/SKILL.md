---
name: github-response
description: "Triage open PRs we own and claimed issues. Read reviewer comments, fix CI breakage, address review points, and reply humbly. Never opens new PRs (that's github-pr's job), never claims new issues. Heavy lifting delegated to claude-code-router with a tightly-scoped permission boundary."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [github, pr-followup, triage, hermes-native]
    related_skills: [claude-code-router]
---

# github-response — Hermes-native PR follow-up

Replaces `~/.hermes/scripts/github-response.py`. Runs every 60m. Walks our open PRs, sees what changed since last tick, and either fixes things or marks human-needed.

## Procedure

### Step 1 — list our open PRs

```bash
ME=$(gh api user --jq .login)
gh pr list --author "$ME" --state open --json number,url,title,headRepository,reviewDecision,statusCheckRollup,comments --limit 20
```

### Step 2 — for each PR, classify state

| State | Action |
|---|---|
| CI failing | Delegate to claude-code-router: "fix CI failures on this PR" |
| Reviewer requested changes | Delegate: "address reviewer comments at <PR URL>" |
| Reviewer approved + waiting on CLA | Comment: "Thanks for the review. CLA signed." (only if true) |
| Reviewer commented (no change requested) | Reply with humble acknowledgment, no code change |
| No new activity | Skip |

### Step 3 — permission boundary for claude-code-router

When delegating, use:
```yaml
working_dir: <freshly-cloned PR fork>
permission_mode: bypassPermissions
extra_constraints:
  - "Never push to upstream directly. Only push to fork."
  - "Never close the PR. If you can't fix it, comment and stop."
  - "Never claim new issues. This skill only follows up."
```

### Step 4 — write status + memory

```bash
cat > ~/.hermes/shared/.last-github-response-status <<EOF
{
  "ts": "$(date -Iseconds)",
  "prs_checked": $N,
  "prs_fixed": $FIXED,
  "prs_replied": $REPLIED,
  "prs_skipped": $SKIPPED,
  "prs_blocked": $BLOCKED
}
EOF

hermes memory write "github-response ts:$(date -Iseconds) checked:$N fixed:$FIXED"
```

## Anti-patterns

- ❌ Do NOT open new PRs — that violates the github-pr / github-response separation
- ❌ Do NOT claim new issues — this skill only follows up on already-claimed work
- ❌ Do NOT escalate to upstream-direct push even with bypassPermissions — fork-only
- ❌ Do NOT fight reviewers; if a comment is unclear, reply asking for clarification, don't push back
