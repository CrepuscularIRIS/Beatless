"""GitHub Response — wake-gate + ClaudeCode execution with CI-debug pipeline.

Wakes ClaudeCode when ANY of:
  1. A maintainer posted a new non-author comment since the last visit.
  2. A maintainer's comment has no author reply after it (stale unreplied).
  3. A PR has a failing CI status rollup (FAILURE / ERROR).

When CI is failing, this script does NOT just hand Claude a "go fix it" string —
it pulls the actual failing-workflow log tails, classifies the failure
(build/test/lint/type/dep/flake/unknown), tracks per-PR retry counts, and
escalates the prompt accordingly:

  Retry 1: ClaudeCode (Sonnet) — local repro → fix → push → reply
  Retry 2: ClaudeCode + delegate to codex:codex-rescue for second opinion
  Retry 3: ClaudeCode + delegate to gemini:gemini-consult for alternative root cause
  Retry 4+: pause auto-fix on this PR, post a comment requesting maintainer guidance

State files:
  ~/.hermes/shared/.last-github-response          (timestamp marker)
  ~/.hermes/shared/.last-github-response-status   (JSON: which PRs were actionable)
  ~/.hermes/shared/.github-response-retries.json  (per-PR retry tracker)

Working directory: ~/workspace (where repos are cloned)
"""
import json
import os
import re
import subprocess
from datetime import datetime, timezone

AUTHOR = "CrepuscularIRIS"
MARKER = os.path.expanduser("~/.hermes/shared/.last-github-response")
STATUS_FILE = os.path.expanduser("~/.hermes/shared/.last-github-response-status")
RETRIES_FILE = os.path.expanduser("~/.hermes/shared/.github-response-retries.json")
WORKSPACE = os.path.expanduser("~/workspace")
PR_STAGE_ROOT = os.path.join(WORKSPACE, "pr-stage")

MAX_AUTOFIX_RETRIES = 3       # retry 4 = pause + ask maintainer
LOG_TAIL_LINES = 40           # how much failing-workflow log to feed Claude
MAX_FAILING_WORKFLOWS = 3     # cap to avoid prompt bloat


# ---------- generic helpers ----------

def _gh_json(args, timeout=20):
    """Run gh and parse JSON, returning empty list/dict on failure."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return json.loads(r.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def get_open_prs():
    """Search returns no headRefName; we fetch that per-PR in analyze_pr."""
    data = _gh_json([
        "gh", "search", "prs",
        f"--author={AUTHOR}", "--state=open",
        "--sort=updated", "--limit=20",
        "--json=number,title,repository,updatedAt",
    ], timeout=30)
    return data or []


def get_pr_comments(repo, number):
    """Issue-comments in chronological order."""
    data = _gh_json([
        "gh", "api", f"repos/{repo}/issues/{number}/comments",
        "--jq", "[.[] | {login: .user.login, created_at: .created_at, body: .body, type: \"issue\"}]",
    ])
    return data or []


def get_pr_review_comments(repo, number):
    """Inline review (file/diff) comments."""
    data = _gh_json([
        "gh", "api", f"repos/{repo}/pulls/{number}/comments",
        "--jq", "[.[] | {login: .user.login, created_at: .created_at, body: .body, type: \"review\"}]",
    ])
    return data or []


def bot_login(login):
    if not login:
        return True
    low = login.lower()
    return (
        low.endswith("[bot]")
        or low in {"codacy-production", "dependabot", "renovate", "codecov",
                   "github-actions", "mergify", "cla-assistant", "netlify"}
    )


# ---------- CI failure deep-dive ----------

def get_ci_status(repo, number):
    """Return one of: 'pass', 'fail', 'pending', 'none'."""
    data = _gh_json([
        "gh", "pr", "view", str(number), "--repo", repo,
        "--json", "statusCheckRollup",
    ])
    if not data:
        return "none"
    checks = data.get("statusCheckRollup") or []
    if not checks:
        return "none"
    has_fail = False
    has_pending = False
    for c in checks:
        status = c.get("status") or ""
        conclusion = c.get("conclusion") or ""
        state = c.get("state") or ""
        if conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED") or state == "FAILURE":
            has_fail = True
        elif status in ("QUEUED", "IN_PROGRESS") or state == "PENDING":
            has_pending = True
    if has_fail:
        return "fail"
    if has_pending:
        return "pending"
    return "pass"


def get_failing_workflows(repo, number, limit=MAX_FAILING_WORKFLOWS):
    """Return list of {workflow, run_id, log_tail, classification} for failures.

    Combines two sources:
      1. GitHub Actions failed runs on the PR head SHA — log tail fetchable.
      2. External commit-status failures (Vercel, CircleCI, etc.) seen in
         statusCheckRollup — no log, just a name + detailsUrl.
    """
    pr = _gh_json([
        "gh", "pr", "view", str(number), "--repo", repo,
        "--json", "headRefOid,statusCheckRollup",
    ])
    if not pr:
        return []
    sha = pr.get("headRefOid", "")
    if not sha:
        return []

    enriched = []

    # Source 1: GitHub Actions failed runs
    runs = _gh_json([
        "gh", "api",
        f"repos/{repo}/actions/runs?head_sha={sha}&status=failure&per_page=10",
        "--jq", "[.workflow_runs[] | {workflow: .name, run_id: .id, html_url: .html_url, conclusion: .conclusion}]",
    ], timeout=30) or []

    seen_names = set()
    for r in runs[:limit]:
        name = r.get("workflow", "?")
        if name in seen_names:
            continue
        seen_names.add(name)
        run_id = r["run_id"]
        log = ""
        try:
            log_proc = subprocess.run(
                ["gh", "run", "view", str(run_id),
                 "--repo", repo, "--log-failed"],
                capture_output=True, text=True, timeout=60,
            )
            if log_proc.returncode == 0:
                lines = (log_proc.stdout or "").strip().splitlines()
                log = "\n".join(lines[-LOG_TAIL_LINES:])
        except subprocess.TimeoutExpired:
            log = "(log fetch timed out)"
        enriched.append({
            "workflow": name,
            "source": "actions",
            "run_id": run_id,
            "url": r.get("html_url", ""),
            "log_tail": log,
            "classification": classify_failure(log),
        })

    # Source 2: external commit-status failures from statusCheckRollup
    for c in (pr.get("statusCheckRollup") or []):
        if len(enriched) >= limit:
            break
        # External statuses have state=FAILURE, no conclusion; Actions checks
        # have conclusion=FAILURE, no state. Avoid duplicates.
        is_external_fail = c.get("state") == "FAILURE" and not c.get("conclusion")
        if not is_external_fail:
            continue
        name = c.get("name") or c.get("context") or "external-check"
        if name in seen_names:
            continue
        seen_names.add(name)
        enriched.append({
            "workflow": name,
            "source": "external",
            "run_id": None,
            "url": c.get("targetUrl") or c.get("detailsUrl") or "",
            "log_tail": "(external CI — no log via gh; check the URL)",
            "classification": "external",
        })

    return enriched


def classify_failure(log_tail):
    """Cheap regex-based classification — gives Claude a hint, not a verdict."""
    if not log_tail:
        return "unknown"
    low = log_tail.lower()
    rules = [
        ("test_failure",  r"\b(failed|failure)\b.*\b(test|spec|assert)\b|assertionerror|test\s+failed|FAIL\s+\["),
        ("type_error",    r"type\s*error|mypy|tsc|pyright|cannot find type|incompatible types"),
        ("lint",          r"\b(eslint|ruff|flake8|pylint|gofmt|clippy)\b|lint(ing)? (failed|error)"),
        ("build_error",   r"build (failed|error)|compilation (failed|error)|cannot find module|import error|modulenotfounderror|syntaxerror|elifecycle"),
        ("dependency",    r"could not resolve dependency|version mismatch|peer dep|sha.*mismatch|integrity check"),
        ("flake",         r"timed?\s*out|connection reset|ssl.*handshake|hash mismatch|503\s|server error.*retr"),
        ("permission",    r"permission denied|forbidden|unauthorized|token expired"),
        ("oom",           r"out of memory|killed.*signal 9|OOM"),
    ]
    for label, pattern in rules:
        if re.search(pattern, low, re.IGNORECASE):
            return label
    return "unknown"


# ---------- retry tracker ----------

def load_retries():
    if not os.path.exists(RETRIES_FILE):
        return {}
    try:
        with open(RETRIES_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_retries(data):
    os.makedirs(os.path.dirname(RETRIES_FILE), exist_ok=True)
    with open(RETRIES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_pr_retry_count(retries, repo, number, head_sha):
    """Return retry count for current head SHA. Resets on new SHA."""
    key = f"{repo}#{number}"
    entry = retries.get(key, {})
    if entry.get("head_sha") != head_sha:
        return 0
    return entry.get("count", 0)


def bump_pr_retry(retries, repo, number, head_sha):
    key = f"{repo}#{number}"
    entry = retries.get(key, {})
    if entry.get("head_sha") != head_sha:
        entry = {"head_sha": head_sha, "count": 0, "first_seen": datetime.now(timezone.utc).isoformat()}
    entry["count"] = entry.get("count", 0) + 1
    entry["last_attempt"] = datetime.now(timezone.utc).isoformat()
    retries[key] = entry
    return entry["count"]


# ---------- per-PR analysis ----------

def analyze_pr(repo, number, retries):
    """Return dict with actionable flag + reason + ci + ci_detail + retry_count."""
    issue_comments = get_pr_comments(repo, number)
    review_comments = get_pr_review_comments(repo, number)
    all_comments = sorted(
        issue_comments + review_comments,
        key=lambda c: c.get("created_at", "")
    )

    human_comments = [
        c for c in all_comments
        if not bot_login(c.get("login")) and c.get("login") != AUTHOR
    ]
    our_replies = [c for c in all_comments if c.get("login") == AUTHOR]

    unreplied = []
    for m in human_comments:
        m_time = m.get("created_at", "")
        later_reply = any(r.get("created_at", "") > m_time for r in our_replies)
        if not later_reply:
            unreplied.append(m)

    new_since_marker = []
    if os.path.exists(MARKER):
        last_check = datetime.fromtimestamp(os.path.getmtime(MARKER), tz=timezone.utc)
        for c in human_comments:
            try:
                ct = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                if ct > last_check:
                    new_since_marker.append(c)
            except (ValueError, KeyError):
                continue
    else:
        new_since_marker = list(human_comments)

    ci = get_ci_status(repo, number)
    ci_detail = []
    retry_count = 0
    head_sha = ""
    head_branch = ""

    # Always fetch head branch (needed in prompt block); SHA only when CI fails
    pr_meta = _gh_json(["gh", "pr", "view", str(number), "--repo", repo,
                        "--json", "headRefOid,headRefName"])
    if pr_meta:
        head_sha = pr_meta.get("headRefOid", "")
        head_branch = pr_meta.get("headRefName", "")

    if ci == "fail":
        ci_detail = get_failing_workflows(repo, number)
        retry_count = get_pr_retry_count(retries, repo, number, head_sha)

    reasons = []
    if new_since_marker:
        reasons.append(f"new-comments={len(new_since_marker)}")
    if unreplied:
        reasons.append(f"unreplied={len(unreplied)}")
    if ci == "fail":
        reasons.append(f"ci-failing(retry={retry_count})")

    actionable = bool(new_since_marker or unreplied or ci == "fail")
    return {
        "actionable": actionable,
        "reason": ", ".join(reasons) or "no-action",
        "ci": ci,
        "ci_detail": ci_detail,
        "retry_count": retry_count,
        "head_sha": head_sha,
        "head_branch": head_branch,
        "unreplied_count": len(unreplied),
        "new_comments_count": len(new_since_marker),
    }


# ---------- prompt builder ----------

def build_pr_block(pr, info):
    """Compose the per-PR prompt block, adding rich CI context when present."""
    repo = pr["repository"]["nameWithOwner"]
    number = pr["number"]
    head_branch = info.get("head_branch") or "(unknown)"
    title = pr["title"]

    lines = [
        f"### {repo}#{number}: {title}",
        f"- branch: `{head_branch}`",
        f"- reason: {info['reason']}",
        f"- ci: {info['ci']}",
    ]

    if info["ci"] == "fail" and info["ci_detail"]:
        retry = info["retry_count"]
        lines.append(f"- retry-tier: {retry} of {MAX_AUTOFIX_RETRIES} (after which: pause + ask maintainer)")
        lines.append("")
        lines.append("**Failing workflows (with last %d log lines):**" % LOG_TAIL_LINES)
        for f in info["ci_detail"]:
            lines.append(f"")
            lines.append(f"#### `{f['workflow']}`  [classification: {f['classification']}]")
            lines.append(f"  log url: {f['url']}")
            lines.append("  ```")
            for line in (f["log_tail"] or "(no log captured)").splitlines():
                lines.append(f"  {line}")
            lines.append("  ```")
    return "\n".join(lines)


def escalation_directive(max_retry_seen):
    """Choose the tool ladder based on the highest retry count among CI-failing PRs."""
    if max_retry_seen <= 0:
        return (
            "Tool ladder for CI-failing PRs (FIRST attempt — Tier 1):\n"
            "  - You (Sonnet) handle the fix directly.\n"
            "  - Local repro: clone/cd into the PR branch under ~/workspace, "
            "    reproduce the failure, fix, validate with the same command CI ran, push.\n"
        )
    if max_retry_seen == 1:
        return (
            "Tool ladder for CI-failing PRs (SECOND attempt — Tier 2 escalation):\n"
            "  - Tier-1 fix already failed (CI still red on same head SHA).\n"
            "  - SPAWN: subagent_type='codex:codex-rescue' for a second opinion. "
            "    Pass the failing log tail + the diff of your previous fix attempt.\n"
            "  - Take Codex's analysis, apply, validate locally, push.\n"
        )
    if max_retry_seen == 2:
        return (
            "Tool ladder for CI-failing PRs (THIRD attempt — Tier 3 escalation):\n"
            "  - Tier-1 and Tier-2 both failed. The fix direction is probably wrong.\n"
            "  - SPAWN: subagent_type='gemini:gemini-consult' to challenge your assumptions and "
            "    surface alternative root causes.\n"
            "  - If Gemini disagrees with the prior diagnosis, follow its lead. "
            "    Validate locally, push.\n"
        )
    return (
        "Tool ladder for CI-failing PRs (Tier 4 — PAUSE):\n"
        "  - Three auto-fix attempts have already failed on the current head SHA.\n"
        "  - DO NOT push another fix.\n"
        "  - Post a single short comment on the PR: explain the failure briefly, "
        "    list the 3 directions tried (one line each), and ask the maintainer for guidance.\n"
        "  - Then move on to other PRs.\n"
    )


def write_status(payload):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(payload, f, indent=2)


# ---------- main ----------

def main():
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    os.makedirs(WORKSPACE, exist_ok=True)
    os.makedirs(PR_STAGE_ROOT, exist_ok=True)

    prs = get_open_prs()
    if not prs:
        print(json.dumps({"wakeAgent": False, "reason": "no open PRs"}))
        return

    retries = load_retries()
    actionable = []
    overview = []
    paused_prs = []   # tier-4 PRs we will not auto-touch
    max_ci_retry = -1

    for pr in prs:
        repo = pr["repository"]["nameWithOwner"]
        number = pr["number"]
        try:
            info = analyze_pr(repo, number, retries)
        except Exception as e:
            print(f"warn: analyze failed for {repo}#{number}: {e}")
            continue

        overview.append({
            "repo": repo, "number": number, "title": pr["title"],
            "reason": info["reason"], "ci": info["ci"],
            "retry_count": info["retry_count"],
            "failing_workflows": [f["workflow"] for f in info["ci_detail"]],
        })

        if not info["actionable"]:
            continue

        if info["ci"] == "fail" and info["retry_count"] >= MAX_AUTOFIX_RETRIES:
            paused_prs.append((pr, info))
            continue

        actionable.append((pr, info))
        if info["ci"] == "fail":
            max_ci_retry = max(max_ci_retry, info["retry_count"])
            # Optimistically bump retry — Claude is about to attempt a fix
            bump_pr_retry(retries, repo, number, info["head_sha"])

    save_retries(retries)

    write_status({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_open_prs": len(prs),
        "actionable_count": len(actionable),
        "paused_count": len(paused_prs),
        "max_ci_retry": max_ci_retry,
        "overview": overview,
    })

    if not actionable and not paused_prs:
        print(json.dumps({"wakeAgent": False, "reason": "no actionable PRs"}))
        return

    pr_blocks = "\n\n---\n\n".join(build_pr_block(pr, info) for pr, info in actionable)
    paused_section = ""
    if paused_prs:
        paused_section = "\n\nPaused PRs (tier-4 — DO NOT auto-fix; post maintainer-help comment ONLY if not already posted on this SHA):\n"
        for pr, info in paused_prs:
            repo = pr["repository"]["nameWithOwner"]
            paused_section += f"- {repo}#{pr['number']}  (retries={info['retry_count']}, ci={info['ci']})\n"

    escalation = escalation_directive(max_ci_retry)

    prompt = (
        "You are running as the GitHub PR follow-up + CI debug pipeline.\n\n"
        f"Workspace root: {WORKSPACE}\n"
        f"Per-PR staging:  {PR_STAGE_ROOT}/<repo-name>/\n"
        f"Follow-up summary: {PR_STAGE_ROOT}/_followup/<timestamp>.md\n\n"
        "Actionable PRs (CI-failing entries include the failing-workflow log tail "
        "and a heuristic classification; trust the log over the classification):\n\n"
        f"{pr_blocks}"
        f"{paused_section}\n\n"
        "PRIORITY ORDER (handle highest first; do not skip tiers):\n"
        "  1. ci-failing  -> reproduce locally, fix, push, then reply\n"
        "  2. unreplied   -> address EVERY maintainer comment without a later author reply\n"
        "  3. new-comments -> acknowledge / answer / act on the new feedback\n\n"
        f"{escalation}\n"
        "WORKFLOW per CI-failing PR:\n"
        "  1. cd ~/workspace; if no clone of the repo, `gh repo clone <owner/repo>` then "
        "     `cd <repo>` and `gh pr checkout <number>`. Otherwise `git fetch origin` "
        "     and check out the PR head branch.\n"
        "  2. Reproduce the EXACT failing command from the log tail locally. "
        "     If you cannot infer the command, read .github/workflows/<file>.yml for that workflow.\n"
        "  3. Form a hypothesis. Apply the smallest fix that addresses the root cause "
        "     (not the symptom).\n"
        "  4. Re-run the same command locally. It must pass before you push.\n"
        "  5. Commit with a message that names the fix + log-line evidence. "
        "     Push to the same branch (do NOT open a new PR for the fix).\n"
        "  6. Reply on the PR thread: one or two sentences acknowledging the failure + "
        "     'pushed a fix' + commit SHA. No status tables, no bolded @mention, "
        "     no AI-tooling references.\n\n"
        "WORKFLOW per non-CI actionable item:\n"
        "  - `gh pr view <repo> <number> --comments` to read context.\n"
        "  - If maintainer requested a change: implement it on the existing branch, "
        "    push, reply plainly.\n"
        "  - If maintainer asked a question: answer with concrete code/log evidence.\n"
        "  - If approved: thank + confirm merge readiness.\n"
        "  - If CLA required: sign if you can, else note plainly and stop.\n\n"
        "REPLY TONE (non-negotiable):\n"
        "  - Humility over cleverness. Open with a plain acknowledgement.\n"
        "  - Preferred phrasing: 'I might be wrong, but...', 'Happy to adjust.', "
        "    'If this direction doesn't fit, no problem.'\n"
        "  - Never use: 'My analysis shows...', 'The optimal approach is...', "
        "    bolded '@username', emoji-headed sections, multi-row status tables.\n"
        "  - Never mention internal tooling (no agent names, no multi-model pipeline, "
        "    no orchestration system).\n"
        "  - Match the project's language and commit format exactly.\n"
        "  - Short > long: 2-4 sentences beats 20 lines of Markdown.\n\n"
        "When done with all PRs, write a one-paragraph follow-up summary to "
        f"{PR_STAGE_ROOT}/_followup/<UTC-timestamp>.md and report what you did.\n"
    )

    result = subprocess.run(
        ["claude", "-p", "--model", "sonnet",
         "--dangerously-skip-permissions",
         prompt],
        capture_output=True, text=True,
        timeout=3600,
        cwd=WORKSPACE,
    )

    if result.returncode == 0:
        open(MARKER, "w").close()

    output = result.stdout.strip()
    if output:
        print(output[-4000:] if len(output) > 4000 else output)
    else:
        print(f"ClaudeCode exited {result.returncode}: {result.stderr[:500]}")


if __name__ == "__main__":
    main()
