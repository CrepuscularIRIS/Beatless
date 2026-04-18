# Beatless Pipeline Architecture

Three layers of scheduled work, each with a distinct role.

## Layer 1 — System cron (30-min heartbeat)

Driven by the user's crontab at `*/30 * * * *` which invokes
`~/.hermes/shared/scripts/cron-driver.sh` → `heartbeat-driver.sh`.

### Pipelines

| Pipeline | Interval | Role |
|----------|----------|------|
| **pr-followup** | 1h | GitHub inbox triage: read notifications, address maintainer asks, yield to competing claimers. Never opens new PRs. |
| **blog-maintenance** | 1h | Daily AI/ML writing on `~/blog/`. Pre-step runs `fetch-github-activity.mjs` for the `/activity` page. |
| **github-pr** | PAUSED | New-PR discovery. Paused while finishing existing PRs. Re-enable via `state.json.interval_hours=2.5`. |

Each pipeline is a `test-run.sh` in `.openclaw/hermes/pipelines/<name>/` that:
1. Locks via `/tmp/<name>.lock` to prevent concurrent runs
2. Spawns a tmux session named after the pipeline
3. Runs `timeout <seconds> claude --dangerously-skip-permissions -p '<prompt>'`
4. Writes result JSON to `.openclaw/hermes/logs/<name>-<ts>.result`

## Layer 2 — OpenClaw gateway + 5-agent cron (30-min heartbeat)

The OpenClaw gateway on `127.0.0.1:18789` hosts 5 long-running agent workspaces with their own cron scheduler.

### 5 agents

| Agent | Primary model | Role |
|-------|---------------|------|
| **Lacia** | stepfun/step-3.5-flash | Orchestration / dispatch. Cron: Maintenance-Daily-Lacia. |
| **Methode** | stepfun/step-3.5-flash | Build / execution. Cron: PR-Cycle-Methode. |
| **Satonus** | stepfun/step-3.5-flash | Review / gate. Cron: CI-Guard-Satonus. |
| **Snowdrop** | stepfun/step-3.5-flash | Research / evidence. Cron: Github-Explore-Snowdrop. |
| **Kouka** | **minimax/MiniMax-M2.7** | Delivery / close-out. Cron: Blog-Maintenance-Kouka. MiniMax multimodal skills (minimax-docx/pdf/xlsx + pptx-generator). |

StepFun uses the coding-plan URL `https://api.stepfun.com/step_plan/v1`. MiniMax uses Anthropic-compat `https://api.minimaxi.com/anthropic`.

### Gateway lifecycle

- `scripts/openclaw/gateway-manual.sh {start|stop|status|logs}` — single-shot start
- `scripts/openclaw/gateway-supervisor.sh` — watchdog, relaunches on crash, **uses port-listener check** (not `pgrep`) because the process renames itself to `openclaw-gateway` after bootstrap
- Run the supervisor in tmux: `tmux new-session -d -s openclaw-supervisor "bash scripts/openclaw/gateway-supervisor.sh"`

### Agent invocation

- Local (embedded, no gateway): `./openclaw-local agent --agent <id> --local -m "<msg>" --json`
- Gateway (uses running service): `./openclaw-local agent --agent <id> -m "<msg>" --json`
- Cron: `./openclaw-local cron list` / `cron run <id>` / `cron runs --id <id>`

## Layer 3 — Slash commands (manual trigger)

| Command | Skill | When |
|---------|-------|------|
| `/pr-followup` | `pr-followup` | Manual GitHub inbox triage |
| `/blog-maintenance` | `blog-maintenance` | Manual blog content tick |
| `/github-pr` | `github-pr` | Open a new contribution PR |

## Verification

```bash
# Layer 1 pipelines — read state
cat .openclaw/hermes/pipelines/*/state.json

# Layer 2 — gateway + cron
ss -tlnp | grep 18789
./openclaw-local cron list

# Layer 3 — smoke-test any agent
./openclaw-local agent --agent lacia --local -m "reply PONG" --json
```

