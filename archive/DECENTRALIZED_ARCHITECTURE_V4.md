# Beatless V4 — Decentralized Multi-Agent Architecture

> **Philosophy**: 5 independent MainAgents operating as co-workers in a company. No central orchestrator. Each agent has nearly equal capabilities with specialized skill/plugin preferences.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Beatless V4 — Distributed Company                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│   │   Lacia     │  │  Methode    │  │  Satonus    │  │  Snowdrop   │       │
│   │   (CEO)     │  │  (Engineer) │  │   (QA)      │  │ (Researcher)│       │
│   │             │  │             │  │             │  │             │       │
│   │  Tmux: S1   │  │  Tmux: S2   │  │  Tmux: S3   │  │  Tmux: S4   │       │
│   │  PID: P1    │  │  PID: P2    │  │  PID: P3    │  │  PID: P4    │       │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│          │                │                │                │              │
│          └────────────────┴────────────────┴────────────────┘              │
│                                   │                                        │
│                          ┌────────┴────────┐                               │
│                          │   Mailbox Bus    │                               │
│                          │  (Message Queue) │                               │
│                          └────────┬────────┘                               │
│                                   │                                        │
│                          ┌────────┴────────┐                               │
│                          │  Shared Memory   │                               │
│                          │  (Blackboard)    │                               │
│                          └─────────────────┘                               │
│                                   │                                        │
│                          ┌────────┴────────┐                               │
│                          │    Kouka         │                               │
│                          │  (Delivery)      │                               │
│                          │  Tmux: S5        │                               │
│                          │  PID: P5         │                               │
│                          └─────────────────┘                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Design Principles

### 2.1 Peer-to-Peer Equality

| Principle | Description |
|-----------|-------------|
| **No Master** | Lacia is "first among equals", not a boss. Any agent can initiate tasks. |
| **Equal Capability** | All 5 agents can call ClaudeCode, read/write memory, send mail. |
| **Preference-Based Specialization** | Skills/plugins differ by preference, not capability restriction. |
| **Autonomous Decision** | Each agent decides whether to accept, reject, or delegate a task. |

### 2.2 Communication: Mailbox + Event Bus

```
┌─────────────────────────────────────────────────────────────┐
│                     Mailbox System                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Message Format:                                             │
│  {                                                           │
│    "id": "msg-uuid",                                         │
│    "from": "methode",                                        │
│    "to": "satonus",        // null = broadcast               │
│    "type": "review_request",                                 │
│    "payload": { ... },                                       │
│    "timestamp": "2026-04-08T10:00:00Z",                      │
│    "priority": "normal",   // low/normal/high/urgent         │
│    "expires_at": "2026-04-08T12:00:00Z"                      │
│  }                                                           │
│                                                              │
│  Message Types:                                              │
│  - task_proposal      → "I think we should do X"            │
│  - task_accepted      → "I'll take this task"               │
│  - task_rejected      → "I can't do this, reason: ..."      │
│  - review_request     → "Please review my work"             │
│  - review_approved    → "LGTM"                              │
│  - review_rejected    → "Issues found: ..."                 │
│  - help_request       → "I need help with ..."              │
│  - escalation         → "This needs CEO attention"          │
│  - info_share         → "I found something interesting"     │
│  - consensus_query    → "Do we agree on ...?"               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Tmux Session Management

```bash
# Each agent runs in its own Tmux session
beatless-lacia      →  tmux session: beatless-s1
beatless-methode    →  tmux session: beatless-s2
beatless-satonus    →  tmux session: beatless-s3
beatless-snowdrop   →  tmux session: beatless-s4
beatless-kouka      →  tmux session: beatless-s5

# Inside each session:
# Pane 1: Agent main process (heartbeat + mailbox poll)
# Pane 2: ClaudeCode worker (when executing tasks)
# Pane 3: Logs tail
```

---

## 3. Five Agents — Equal but Different

### 3.1 Capability Matrix

| Capability | Lacia | Methode | Satonus | Snowdrop | Kouka |
|------------|:-----:|:-------:|:-------:|:--------:|:-----:|
| Call ClaudeCode GSD | ✅ | ✅ | ✅ | ✅ | ✅ |
| Read/Write Memory | ✅ | ✅ | ✅ | ✅ | ✅ |
| Send/Receive Mail | ✅ | ✅ | ✅ | ✅ | ✅ |
| Create Tasks | ✅ | ✅ | ✅ | ✅ | ✅ |
| Review Work | ✅ | ✅ | ✅ | ✅ | ✅ |
| Veto Decisions | ✅ | ✅ | ✅ | ✅ | ✅ |
| Escalate | ✅ | ✅ | ✅ | ✅ | ✅ |

### 3.2 Skill/Plugin Preferences

```yaml
# Each agent has preferred skills but CAN use others

lacia:
  preferred_skills:
    - orchestration      # Better at task decomposition
    - routing            # Better at choosing who does what
    - consensus_building # Better at resolving disagreements
  preferred_plugins:
    - thread-ownership   # Conversation continuity
  can_use_all: true

methode:
  preferred_skills:
    - coding             # Better code generation
    - gh-issues          # GitHub operations
    - build_tools        # Compilation, testing
  preferred_plugins:
    - openclaw-codex-app-server  # Direct Codex access
  can_use_all: true

satonus:
  preferred_skills:
    - audit              # Security/compliance review
    - review             # Code review
    - gate_keeping       # Quality gates
  preferred_plugins:
    - diagnostics-otel   # Observability
  can_use_all: true

snowdrop:
  preferred_skills:
    - research           # Information gathering
    - analysis           # Data analysis
    - alternatives       # Finding options
  preferred_plugins:
    - gemini-bridge      # Research delegation
  can_use_all: true

kouka:
  preferred_skills:
    - delivery           # Release management
    - notification       # User communication
    - emergency_response # Urgent handling
  preferred_plugins:
    - openclaw-openroom-bridge  # User notification
  can_use_all: true
```

### 3.3 Decision Autonomy

Each agent makes independent decisions based on:

```python
class AgentDecision:
    def should_accept_task(self, task, mailbox_state, memory):
        # 1. Check my current load
        if self.current_tasks >= self.max_parallel:
            return False, "OVERLOADED"
        
        # 2. Check if task matches my preference
        preference_score = self.soul.match_preference(task.type)
        
        # 3. Check if someone else is better suited
        peers = mailbox_state.get_active_peers()
        for peer in peers:
            if peer.preference_score(task.type) > preference_score + 0.3:
                return False, f"DELEGATE_TO_{peer.name}"
        
        # 4. Check my own judgment
        if self.soul.judge_capability(task) < 0.5:
            return False, "BEYOND_CAPABILITY"
        
        return True, "ACCEPT"
```

---

## 4. Deadlock Prevention

### 4.1 Design-Level Prevention

| Mechanism | Implementation |
|-----------|----------------|
| **Async Only** | No synchronous "call-and-wait". All communication is async via Mailbox. |
| **Timeout on All Waits** | Every pending task has `expires_at`. Expired = auto-escalate. |
| **No Circular Dependencies** | Tasks declare dependencies upfront. System validates no cycles. |
| **Resource Limits** | Each agent has `max_parallel_tasks`. Can't hoard work. |
| **Heartbeat Watchdog** | If agent hasn't heartbeat in 5 min, marked "stalled". |

### 4.2 Timeout Escalation Flow

```
Methode sends review request to Satonus
    │
    ├──→ Satonus doesn't respond in 30 min
    │
    ├──→ Auto-escalation to Lacia
    │    "Satonus hasn't reviewed. Escalating."
    │
    ├──→ Lacia decides:
    │     a) Wait longer (Satonus busy)
    │     b) Assign to another reviewer (e.g., Snowdrop)
    │     c) Review herself
    │     d) Force-approve (emergency)
    │
    └──→ Task continues, no deadlock
```

### 4.3 Conflict Resolution

```
Satonus rejects Methode's work
    │
    ├──→ Methode disagrees
    │
    ├──→ Both send "consensus_query" to all agents
    │
    ├──→ Agents vote:
    │     Lacia: "Methode is right"
    │     Snowdrop: "Satonus has a point"
    │     Kouka: "Neutral"
    │
    ├──→ No clear consensus
    │
    └──→ Lacia makes final call (tie-breaker role)
        
Note: This is rare. Most disagreements resolved via discussion.
```

---

## 5. Task Lifecycle (Decentralized)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Task State Machine                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  proposed ──→ any agent can propose a task                       │
│     │                                                            │
│     ▼                                                            │
│  claimed ────→ agent A claims it (or auto-assigned)              │
│     │                                                            │
│     ▼                                                            │
│  in_progress ─→ agent A works on it (may call ClaudeCode)        │
│     │                                                            │
│     ├──→ help_request ──→ agent B assists                        │
│     │                                                            │
│     ▼                                                            │
│  review_pending ─→ agent A requests review from agent B          │
│     │                                                            │
│     ├──→ approved ──→ goto delivery                              │
│     │                                                            │
│     └──→ rejected ──→ goto in_progress (with feedback)           │
│                   or goto claimed (reassigned)                   │
│                                                                  │
│  delivery ────→ Kouka handles release/notification               │
│     │                                                            │
│     ▼                                                            │
│  completed ───→ archived to memory                               │
│                                                                  │
│  blocked ─────→ auto-escalate after timeout                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Example: Bug Fix Task

```yaml
# Step 1: Lacia proposes (or user asks Lacia)
from: "user"
to: "lacia"
message: "Fix the login bug"

# Step 2: Lacia creates task proposal
broadcast:
  type: "task_proposal"
  task:
    id: "task-123"
    title: "Fix login bug"
    description: "Users can't login with special characters"
    priority: "high"

# Step 3: Agents decide
methode: "I'll take this"        → claims task
satonus: "I'll review when done" → pre-commits to review
snowdrop: "I'll research similar issues" → parallel research

# Step 4: Methode works (calls ClaudeCode GSD)
methode -> claude_code_cli: "Fix login bug in auth.py"

# Step 5: Methode requests review
methode -> satonus:
  type: "review_request"
  artifact: "/tmp/fix-login.diff"

# Step 6: Satonus reviews
satonus -> methode:
  type: "review_approved"
  comment: "LGTM, but add one more test case"

# Step 7: Methode adds test, requests re-review
methode -> satonus:
  type: "review_request"
  
# Step 8: Satonus approves
satonus -> broadcast:
  type: "review_approved"
  task_id: "task-123"

# Step 9: Kouka delivers
kouka -> broadcast:
  type: "task_completed"
  notification: "Login bug fixed and deployed"

# Step 10: All agents update memory
Each agent writes to shared memory:
  - What they learned
  - What worked well
  - What to improve
```

---

## 6. Shared Memory (Blackboard)

```yaml
# Blackboard Structure
blackboard:
  tasks:
    task-123:
      status: "completed"
      owner: "methode"
      reviewers: ["satonus"]
      artifacts: ["/tmp/fix-login.diff"]
      
  agent_states:
    lacia:
      status: "active"
      current_tasks: ["task-456"]
      last_heartbeat: "2026-04-08T10:05:00Z"
    methode:
      status: "active"
      current_tasks: []
      last_heartbeat: "2026-04-08T10:04:30Z"
      
  consensus_log:
    - topic: "Use TypeScript or Python?"
      decision: "TypeScript"
      supporters: ["methode", "satonus"]
      dissenters: ["snowdrop"]
      timestamp: "2026-04-07T15:00:00Z"
      
  user_profile:
    preferences:
      response_time: "async"
      detail_level: "concise"
      preferred_channels: ["email", "openroom"]
    history_summary: "User focuses on security and performance"
    
  learnings:
    - "Satonus is strict about input validation"
    - "Methode prefers ClaudeCode for complex refactoring"
    - "Snowdrop's research often uncovers edge cases"
```

---

## 7. Tmux Implementation Details

```bash
#!/bin/bash
# scripts/start_beatless_v4.sh

# Create Tmux sessions for each agent
tmux new-session -d -s beatless-lacia -n main
 tmux send-keys -t beatless-lacia "python3 -m beatless.agent --name lacia --config agents/lacia/config.yaml" C-m

tmux new-session -d -s beatless-methode -n main
 tmux send-keys -t beatless-methode "python3 -m beatless.agent --name methode --config agents/methode/config.yaml" C-m

tmux new-session -d -s beatless-satonus -n main
 tmux send-keys -t beatless-satonus "python3 -m beatless.agent --name satonus --config agents/satonus/config.yaml" C-m

tmux new-session -d -s beatless-snowdrop -n main
 tmux send-keys -t beatless-snowdrop "python3 -m beatless.agent --name snowdrop --config agents/snowdrop/config.yaml" C-m

tmux new-session -d -s beatless-kouka -n main
 tmux send-keys -t beatless-kouka "python3 -m beatless.agent --name kouka --config agents/kouka/config.yaml" C-m

# Create control session
tmux new-session -d -s beatless-ctl -n monitor
 tmux send-keys -t beatless-ctl "python3 -m beatless.monitor" C-m

echo "Beatless V4 started. Attach with:"
echo "  tmux attach -t beatless-lacia"
echo "  tmux attach -t beatless-methode"
echo "  tmux attach -t beatless-satonus"
echo "  tmux attach -t beatless-snowdrop"
echo "  tmux attach -t beatless-kouka"
echo "Monitor: tmux attach -t beatless-ctl"
```

```bash
#!/bin/bash
# scripts/stop_beatless_v4.sh

tmux kill-session -t beatless-lacia
tmux kill-session -t beatless-methode
tmux kill-session -t beatless-satonus
tmux kill-session -t beatless-snowdrop
tmux kill-session -t beatless-kouka
tmux kill-session -t beatless-ctl

echo "Beatless V4 stopped"
```

---

## 8. Agent Configuration

```yaml
# agents/lacia/config.yaml
agent:
  name: "lacia"
  role: "coordinator"  # Not "boss", just "first among equals"
  
heartbeat:
  interval: 60  # seconds
  timeout: 300  # seconds before marked stalled

mailbox:
  poll_interval: 10  # seconds
  max_pending: 50    # max unread messages
  
skills:
  shared:  # All agents have these
    - heartbeat
    - memory_rw
    - mailbox
    - claude_code_cli
  preferred:  # This agent uses these more often
    - orchestration
    - routing
    - consensus_building
  
plugins:
  shared:
    - thread-ownership
  preferred:
    - openclaw-openroom-bridge

memory:
  type: "shared_blackboard"  # All agents read/write same blackboard
  path: "runtime/blackboard/"
  
limits:
  max_parallel_tasks: 3
  max_daily_tasks: 20
  
autonomy:
  can_initiate_tasks: true
  can_reject_tasks: true
  can_delegate_tasks: true
  can_request_help: true
```

```yaml
# agents/methode/config.yaml
agent:
  name: "methode"
  role: "engineer"
  
heartbeat:
  interval: 60
  timeout: 300

mailbox:
  poll_interval: 10
  max_pending: 50
  
skills:
  shared:
    - heartbeat
    - memory_rw
    - mailbox
    - claude_code_cli
  preferred:
    - coding
    - gh-issues
    - build_tools
  
plugins:
  shared:
    - thread-ownership
  preferred:
    - openclaw-codex-app-server

memory:
  type: "shared_blackboard"
  path: "runtime/blackboard/"
  
limits:
  max_parallel_tasks: 2  # Engineering tasks are heavy
  max_daily_tasks: 15
  
autonomy:
  can_initiate_tasks: true
  can_reject_tasks: true
  can_delegate_tasks: true
  can_request_help: true
```

---

## 9. Monitoring & Observability

```bash
# View all agent sessions
tmux ls | grep beatless

# View specific agent
tmux attach -t beatless-lacia
# Ctrl+b then " to see panes:
#   - Pane 1: Agent process logs
#   - Pane 2: Active ClaudeCode session (when working)
#   - Pane 3: Mailbox message stream

# Monitor from control session
tmux attach -t beatless-ctl
# Shows:
#   - Agent health status
#   - Task queue overview
#   - Recent messages
#   - Deadlock detection alerts
```

---

## 10. Migration from V3

| V3 (Current) | V4 (This Design) |
|--------------|------------------|
| Lacia orchestrates all | Lacia is peer coordinator |
| Agent A "calls" Agent B | Agent A sends mail to Agent B |
| Synchronous handoffs | Async mailbox-based workflow |
| Skills load flat | Skills load by preference + capability |
| Single execution lane | Multiple parallel lanes via Tmux |
| 5 fixed roles | 5 flexible peers with preferences |

---

## 11. Key Advantages of V4

1. **True Decentralization**: No single point of failure
2. **Natural Scaling**: Each agent runs independently
3. **Deadlock-Free**: Async communication + timeouts
4. **Flexible Specialization**: Preferences, not restrictions
5. **Observable**: Tmux provides real-time visibility
6. **Fault Tolerant**: Agent crash doesn't stop others
7. **Sociologically Interesting**: Emergent behaviors from peer interaction

---

*Document Version: V4-20260408*
*Status: Design Phase — Ready for Opus Implementation*
