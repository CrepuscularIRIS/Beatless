# Beatless Architecture v2.1: Two-Layer Dispatch (Hardened)

> Date: 2026-04-11 | Status: PROPOSAL-V2.1 | Base: architecture-v2-simplification.md

---

## 1. Intent

Keep the original v2 direction:

1. Aoi is the control plane.
2. MainAgents are thin dispatchers.
3. ClaudeCode (Sonnet) executes complex work.

This v2.1 only adds hardening rules required for real production autonomy.

---

## 2. Non-Negotiable Constraints

1. No `/ralph-loop` in any runtime path.
2. All external side effects require dual review gate **before** execution:
   - Stage 1 mandatory: `/codex:review`
   - Stage 2 mandatory unless unavailable: `/gemini:consult`
   - If Gemini fails: `stage2_unavailable=true` and continue with Codex-only merged verdict.
3. Every task is resumable and idempotent.
4. No success claim without runtime evidence (command, exit code, UTC timestamp, key lines, artifact path).

---

## 3. Runtime Layers

## Layer 0: User Interface

- StepFun APP -> `stepfun-bridge.mjs`
- Routing target: default `@aoi`

## Layer 1: Control Plane (Aoi)

Aoi responsibilities:

1. Parse intent
2. Create task envelopes
3. Dispatch to worker mailboxes
4. Track task state and SLA
5. Push status/results to StepFun

Aoi must not perform code/research/delivery itself.

## Layer 2: Worker Plane (5 MainAgents)

Workers are mailbox consumers + single ClaudeCode invokers.

Worker responsibilities:

1. Read `task_request`
2. Execute one controlled `claude --print` command
3. Emit `progress_update` (optional)
4. Emit terminal `task_result`

---

## 4. Scheduler Model (Revised)

Original v2 suggested killing all 5 worker cron jobs.

v2.1 changes this to avoid mailbox starvation:

1. Keep Aoi heartbeat schedule (`*/30`) as control cadence.
2. Add lightweight worker consumer loops (event-driven preferred, short tick fallback acceptable).
3. Do not rely on Aoi-only tick for worker mailbox consumption.

Minimum acceptable worker runtime:

- `consumer poll interval <= 60s` or equivalent event listener
- retry with backoff for transient failures

---

## 5. Mailbox Protocol v2.1 (Idempotent)

All messages must include:

- `task_id` (stable per task)
- `correlation_id` (stable across related events)
- `idempotency_key` (stable for side-effect step)
- `attempt` (1..N)
- `deadline_at` (UTC)
- `created_at` (UTC)
- `from`, `to`, `type`

## task_request

```json
{
  "type": "task_request",
  "task_id": "task_20260411_001",
  "correlation_id": "corr_20260411_001",
  "idempotency_key": "github-hunt:repoX:issueY:v1",
  "attempt": 1,
  "deadline_at": "2026-04-11T14:00:00Z",
  "from": "aoi",
  "to": "snowdrop",
  "body": {
    "pipeline": "github-hunt",
    "step": "DISCOVERY",
    "claude_command": "...",
    "timeout_minutes": 30
  }
}
```

## progress_update (optional)

```json
{
  "type": "progress_update",
  "task_id": "task_20260411_001",
  "correlation_id": "corr_20260411_001",
  "attempt": 1,
  "from": "snowdrop",
  "to": "aoi",
  "body": {
    "progress": "40%",
    "current_step": "SCAN repo 2/5",
    "eta_minutes": 12
  }
}
```

## task_result (terminal)

```json
{
  "type": "task_result",
  "task_id": "task_20260411_001",
  "correlation_id": "corr_20260411_001",
  "attempt": 1,
  "from": "snowdrop",
  "to": "aoi",
  "body": {
    "status": "SUCCESS",
    "stage2_unavailable": false,
    "codex_verdict": "PASS",
    "gemini_verdict": "PASS",
    "merged_verdict": "PASS",
    "artifacts": ["/abs/path/..."],
    "summary": "..."
  }
}
```

---

## 6. Pipeline Model (Segmented + Recoverable)

Do not run the whole business flow in one giant Claude session.

Use resumable segments:

1. `DISCOVERY`
2. `SCAN`
3. `REVIEW`
4. `ACT` (side effects)
5. `REPORT`

Each segment must:

1. Write artifact to disk
2. Write state checkpoint
3. Be replay-safe via `idempotency_key`

---

## 7. Dual Review Gate Placement

Dual review gate is mandatory at two points:

1. Pre-Act Gate (required)
   - before `gh issue create`, `gh pr create`, `git push`, blog publish commit
2. Post-Act Gate (advisory)
   - verify final change quality and capture risk notes

Merged verdict policy:

- `REJECT`: block side effect
- `HOLD`: require explicit override marker
- `PASS`: continue
- `UNAVAILABLE`: allowed only when `codex_verdict=PASS` and `stage2_unavailable=true`

---

## 8. Entry Policy (Unified)

Default production entry: `@aoi` only.

Direct worker entry (`@lacia`, `@methode`, etc.) is debug-only and requires explicit flag:

- `mode=debug_direct`
- must still report back through Aoi record channel

This avoids governance drift and hidden task trees.

---

## 9. StepFun E2E Gate (Live Only)

Synthetic self-tests are not enough for production pass.

Required live evidence for PASS:

1. `stepfun.msg.received`
2. `stepfun.ack.sent`
3. `stepfun.final.sent`
4. same `correlation_id`
5. non-synthetic sender/session markers

If any missing: mark `ENV_BLOCKED` or `NOT_READY`.

---

## 10. Worker Profiles (Thin + Strict)

## Lacia (strategy)

Allowed:

- `/gsd-discuss-phase`
- `/gsd-plan-phase`

Not allowed:

- direct side effects without gate artifact

## Methode (execute)

Allowed:

- `/gsd-execute-phase`
- `/agent-teams:team-feature --plan-first`

Not allowed:

- bypass quality gate on external actions

## Satonus (review)

Mandatory outputs:

- `/codex:review`
- `/gemini:consult`
- merged verdict artifact

## Snowdrop (research/discovery)

Allowed:

- `/agent-teams:team-spawn research ...`
- `/gemini:consult` / `/gemini:analyze`

## Kouka (delivery)

Allowed:

- blog/package/release execution

Not allowed:

- publishing when pre-act gate is missing

---

## 11. State and Audit Files

Minimum state schema:

```json
{
  "status": "IDLE|RUNNING|DONE|FAILED|STALE",
  "last_run": "UTC",
  "next_run": "UTC",
  "last_task_id": "...",
  "last_correlation_id": "...",
  "last_verdict": "PASS|HOLD|REJECT|UNAVAILABLE"
}
```

Required artifacts per task:

1. command transcript summary
2. dual review artifact
3. output artifact list
4. StepFun notification evidence (if user-facing)

---

## 12. Acceptance Gates

All must pass for production readiness:

1. `G1 Scheduler`: >=2 consecutive automatic cycles
2. `G2 Consumers`: all 5 workers consume mailbox tasks within SLA
3. `G3 Dispatch`: Aoi -> 5 workers -> Aoi replies complete
4. `G4 DualReview`: codex + gemini(or stage2_unavailable) + merged verdict
5. `G5 StepFunLive`: real inbound/ack/final with same correlation_id
6. `G6 Workspace`: fresh `~/workspace/pr-stage` artifact in-session
7. `G7 Blog`: fresh blog artifact + `pnpm build` exit 0
8. `G8 Stability`: no silent failure across >=2 cycles

---

## 13. Migration Plan (v2 -> v2.1)

Phase A (same day):

1. Keep current Aoi heartbeat.
2. Add/verify worker consumers before removing worker cron fallback.
3. Introduce idempotent message fields.

Phase B (day 1-2):

1. Split GitHub/Blog pipelines into segmented steps.
2. Enforce pre-act dual-review gate.
3. Add checkpoint and replay logic.

Phase C (day 2-3):

1. Run live StepFun E2E verification (not self-test).
2. Run 8-hour burn-in with gate table capture.
3. Promote to production only if G1-G8 all pass.

---

## 14. Success Metrics (1 week)

1. GitHub issues/day >= 3
2. PRs/day >= 1
3. Blog posts/day >= 1
4. Pipeline success rate >= 80%
5. StepFun notification latency < 5 min
6. Idle spam = 0
7. Stale detection < 2h
8. Zero duplicate side effects (idempotency violations = 0)

---

## 15. Decision

Adopt v2 direction with v2.1 hardening.

Do not deploy pure Aoi-only heartbeat + no worker consumers.
Do not allow side effects before dual review gate evidence.
