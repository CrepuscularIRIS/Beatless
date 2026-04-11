# ClaudeCode Harness V2 (Beatless)

Date: 2026-04-04
Status: active design baseline (superseded operationally by V2.1 in `docs/CLAUDECODE_HARNESS_V2_1.md`)

## 1. Why V2

OpenClaw is kept as Control Plane (agent identity, routing policy, mailbox, cron, memory).
ClaudeCode is used as Worker Plane harness (plugin-driven execution with stronger loop controls).

Core decision:
- Do not let OpenClaw emulate ClaudeCode internals.
- Let OpenClaw decide "what to do", and let ClaudeCode plugins decide "how to execute".

## 2. Three Plugins: Real Capability Boundaries

### 2.1 Codex plugin (`/codex:*`)
Use for gate and challenge.

Primary commands:
- `/codex:review`
- `/codex:adversarial-review`
- `/codex:rescue`
- `/codex:status` `/codex:result` `/codex:cancel`

Hard behavior from plugin command specs:
- review/adversarial-review are review-only (no patching in same step).
- rescue supports `--resume` / `--fresh` continuation mode.
- long runs should prefer `--background`; short bounded checks can `--wait`.

### 2.2 AgentTeams plugin (`/agent-teams:*`)
Use for decomposition and parallel execution.

Primary commands:
- `/agent-teams:team-feature`
- `/agent-teams:team-debug`
- `/agent-teams:team-review`
- `/agent-teams:team-spawn`
- `/agent-teams:team-delegate` `/agent-teams:team-status` `/agent-teams:team-shutdown`

Hard behavior:
- requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.
- best with `teammateMode=tmux`.
- teammates use `model: inherit` and must inherit parent route `kimi k2.5`.
- must define file ownership/dependency before parallel spawn.

### 2.3 RalphLoop plugin (`/ralph-loop:*`)
Use for bounded iterative build loops.

Primary commands:
- `/ralph-loop "..." --max-iterations N --completion-promise "..."`
- `/cancel-ralph`

Hard behavior:
- stop hook blocks session exit and re-injects same prompt.
- if no max-iterations/promise guard, loop risk increases.
- best for clear done-criteria tasks, not fuzzy exploration.

## 3. Trigger Strategy (Prompt -> Plugin)

Machine-readable policy source:
- `config/claudecode_plugin_trigger_matrix.v2.yaml`

Human summary:
- Architecture / harness / prompt engineering:
  - route: `claude_architect_cli`
  - optional check: `/codex:adversarial-review`
- Simple implementation:
  - route: `claude_build_cli`
  - before merge: `/codex:review`
- Complex decomposable build:
  - route: `claude_build_cli` + `/agent-teams:team-feature --plan-first`
- Iterative polish / repeated fix-until-pass:
  - route: `claude_build_cli` + `/ralph-loop ... --max-iterations ...`
- Unknown root-cause debugging:
  - `/agent-teams:team-debug ...`
  - fallback: `/codex:rescue --wait`
- Release gate:
  - `/codex:review` then `/codex:adversarial-review`

## 4. Direct Answer: AgentTeams vs RalphLoop for Build

Not either-or. Use tiered build strategy:

1. Default: single-lane `claude_build_cli` for simple tasks.
2. Upgrade to RalphLoop when task is one objective with measurable completion.
3. Upgrade to AgentTeams when task is large and can be split into non-overlapping streams.
4. Always pass Codex review gate before production merge.

This avoids two common failures:
- overusing AgentTeams for tiny tasks (coordination overhead)
- overusing RalphLoop for ambiguous goals (loop drift)

## 5. 5 MainAgent plugin posture

- Lacia: orchestration first, AgentTeams for complex decomposition, Codex for gate.
- Methode: build first, RalphLoop for iterative quality, AgentTeams for large refactor.
- Satonus: Codex-first reviewer/guard, strong adversarial gate.
- Snowdrop: research first, AgentTeams for parallel discovery, Codex for synthesis challenge.
- Kouka: integration/publishing, team-review + final Codex gate.

## 6. Minimal command templates

- Complex feature:
  - `/agent-teams:team-feature "<feature>" --team-size 3 --plan-first`
- Iterative fix loop:
  - `/ralph-loop "<task with objective checks>" --max-iterations 8 --completion-promise "DONE"`
- Merge gate:
  - `/codex:review --background --scope working-tree`
- Adversarial gate:
  - `/codex:adversarial-review --background --scope working-tree <focus>`
- Rescue continuation:
  - `/codex:rescue --resume <delta instruction>`

## 7. Operational guardrails

- Every plugin execution must be mapped to a TaskContract stage.
- If AgentTeams status is unstable, fallback to single-lane build immediately.
- RalphLoop must always set max iterations.
- Codex review outputs are evidence artifacts, not direct merge approval by themselves.

## 8. Next implementation step

W2 should connect scheduler stage adapters to this matrix:
- `plan` -> architect lane
- `implement` -> build lane (+ optional agent-teams/ralph)
- `verify/review` -> codex gates
- `publish` -> kouka summary + satonus gate

## 8.1 V2.1 Rule Source Alignment

V2.1 executes from one machine-readable source:
- `config/claudecode_plugin_trigger_matrix.v2.yaml`
- `trigger_rules_v21` is the canonical trigger source.
- `trigger_keywords` dual-source matching is removed in runtime decisions.

## 9. Acceptance Gates (Machine-Checkable)

- `plan_completeness`: JSON parse success and every stage contains `stage/lane/sub_tasks/editable_paths`.
- `diff_exists`: implement stage must produce non-empty `changed_files`.
- `path_compliance`: all changed files must remain inside `editable_paths`.
- `must_pass_all`: all `contract.acceptance.must_pass` commands exit `0`.
- `codex_verdict`: parsed codex output must satisfy `blocking_count == 0`.
- `handoff_exists`: publish stage requires `CHANGELOG/PR_DESCRIPTION/ROLLBACK`.

## 10. Codex Gate Protocol

Required order:
1. `/codex:review --background --scope working-tree`
2. `/codex:adversarial-review --background --scope working-tree`
3. Parse result and block if any blocking findings exist.

Pass condition:
- `blocking_count = 0` for both review passes.

Fail condition:
- any blocking finding triggers retry (within budget) or escalation.

## 11. Failure Mode Catalog (Top 10)

1. AgentTeams teammate crash/disconnect.
2. RalphLoop no-progress drift.
3. Codex review timeout on large diff.
4. Hook timeout (>5s) causing toolchain interruption.
5. Provider rate-limit/402 in build lane.
6. Research lane API timeout.
7. Dirty worktree leakage between tasks.
8. Completion promise false-positive.
9. Context compaction drops hard rules.
10. Plugin command order inversion (review fired during implement).

## 12. Emergency Procedures

- AgentTeams unstable: `team-shutdown` then fall back to single-lane.
- RalphLoop no-progress >= 3: `cancel-ralph` then `team-debug`.
- Same error >= 2: prefer `codex:rescue`, otherwise escalate.
- Hook failures: security-critical hook failure blocks execution; non-critical hook failure degrades with warning.
