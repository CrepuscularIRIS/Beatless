"""GitHub Response — wake-gate + ClaudeCode execution.

Wakes the PR-follow-up pipeline when ANY of:
  1. A maintainer posted a new non-author comment since the last visit.
  2. A maintainer's comment has no author reply after it (stale unreplied).
  3. A PR has a failing CI status rollup (FAILURE / ERROR).

All three conditions independently justify a wake. Skipping a PR just because
"no new comments this cron tick" is wrong — broken CI or unanswered feedback
must not be ignored.
Working directory: ~/workspace (where repos are cloned)
"""
import subprocess
import argparse
import json
import os
import re
from datetime import datetime, timezone

from beatless_config import CONFIG

AUTHOR = CONFIG.github_author
MARKER = str(CONFIG.shared_file(".last-github-response"))
STATUS_FILE = str(CONFIG.shared_file(".last-github-response-status"))
WORKSPACE = str(CONFIG.workspace)
PR_STAGE_ROOT = str(CONFIG.pr_stage_root)


def get_open_prs():
    result = subprocess.run(
        ["gh", "search", "prs",
         f"--author={AUTHOR}", "--state=open",
         "--sort=updated", "--limit=20",
         "--json=number,title,repository,updatedAt"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout) or []
    except json.JSONDecodeError:
        return []


def get_pr_comments(repo, number):
    """Fetch issue-comments in chronological order."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/issues/{number}/comments",
             "--jq", "[.[] | {login: .user.login, created_at: .created_at, body: .body, type: \"issue\"}]"],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def get_pr_review_comments(repo, number):
    """Fetch inline review comments (files/diff annotations)."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/pulls/{number}/comments",
             "--jq", "[.[] | {login: .user.login, created_at: .created_at, body: .body, type: \"review\"}]"],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def get_ci_status(repo, number):
    """Return one of: 'pass', 'fail', 'pending', 'none'."""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(number), "--repo", repo,
             "--json", "statusCheckRollup"],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0 or not result.stdout.strip():
            return "none"
        data = json.loads(result.stdout)
        checks = data.get("statusCheckRollup") or []
        if not checks:
            return "none"
        has_fail = False
        has_pending = False
        for c in checks:
            status = c.get("status") or ""
            conclusion = c.get("conclusion") or ""
            state = c.get("state") or ""  # commit-status API
            if conclusion in ("FAILURE", "TIMED_OUT", "CANCELLED") or state == "FAILURE":
                has_fail = True
            elif status in ("QUEUED", "IN_PROGRESS") or state == "PENDING":
                has_pending = True
        if has_fail:
            return "fail"
        if has_pending:
            return "pending"
        return "pass"
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return "none"


def bot_login(login):
    if not login:
        return True
    low = login.lower()
    return (
        low.endswith("[bot]")
        or low in {"codacy-production", "dependabot", "renovate", "codecov",
                   "github-actions", "mergify", "cla-assistant", "netlify"}
    )


def analyze_pr(repo, number):
    """Return (actionable, reason, last_check) triple."""
    issue_comments = get_pr_comments(repo, number)
    review_comments = get_pr_review_comments(repo, number)
    all_comments = sorted(
        issue_comments + review_comments,
        key=lambda c: c.get("created_at", "")
    )

    # Filter out bots and our own voice
    human_comments = [
        c for c in all_comments
        if not bot_login(c.get("login")) and c.get("login") != AUTHOR
    ]
    our_replies = [
        c for c in all_comments
        if c.get("login") == AUTHOR
    ]

    # Find unreplied maintainer comments — any maintainer comment
    # with no subsequent author reply
    unreplied = []
    for m in human_comments:
        m_time = m.get("created_at", "")
        later_reply = any(
            r.get("created_at", "") > m_time for r in our_replies
        )
        if not later_reply:
            unreplied.append(m)

    # New since last wake-gate visit
    new_since_marker = []
    if os.path.exists(MARKER):
        last_check = datetime.fromtimestamp(
            os.path.getmtime(MARKER), tz=timezone.utc
        )
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

    reasons = []
    if new_since_marker:
        reasons.append(f"new-comments={len(new_since_marker)}")
    if unreplied:
        reasons.append(f"unreplied={len(unreplied)}")
    if ci == "fail":
        reasons.append("ci-failing")

    actionable = bool(new_since_marker or unreplied or ci == "fail")
    return actionable, ", ".join(reasons) or "no-action", ci


def write_status(payload):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(payload, f, indent=2)


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="inspect open PRs and write status without invoking ClaudeCode",
    )
    return ap.parse_args()


def main():
    args = parse_args()
    os.makedirs(os.path.dirname(MARKER), exist_ok=True)
    os.makedirs(WORKSPACE, exist_ok=True)
    os.makedirs(PR_STAGE_ROOT, exist_ok=True)

    prs = get_open_prs()
    if not prs:
        write_status({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": args.dry_run,
            "total_open_prs": 0,
            "actionable_count": 0,
            "overview": [],
        })
        print(json.dumps({"wakeAgent": False}))
        return

    actionable = []
    overview = []
    for pr in prs:
        repo = pr["repository"]["nameWithOwner"]
        number = pr["number"]
        try:
            should_act, reason, ci = analyze_pr(repo, number)
        except Exception as e:
            print(f"warn: analyze failed for {repo}#{number}: {e}")
            continue
        overview.append({
            "repo": repo, "number": number, "title": pr["title"],
            "reason": reason, "ci": ci,
        })
        if should_act:
            actionable.append((pr, reason, ci))

    write_status({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "total_open_prs": len(prs),
        "actionable_count": len(actionable),
        "overview": overview,
    })

    if not actionable:
        print(json.dumps({"wakeAgent": False}))
        return

    pr_list = "\n".join(
        f"- {p['repository']['nameWithOwner']}#{p['number']}: {p['title']}"
        f"  [{reason}; ci={ci}]"
        for p, reason, ci in actionable
    )

    if args.dry_run:
        print(json.dumps({
            "wakeAgent": False,
            "dryRun": True,
            "actionableCount": len(actionable),
            "actionable": [
                {
                    "repo": p["repository"]["nameWithOwner"],
                    "number": p["number"],
                    "title": p["title"],
                    "reason": reason,
                    "ci": ci,
                }
                for p, reason, ci in actionable
            ],
        }, indent=2))
        return

    prompt = (
        f"/pr-followup\n\n"
        f"Actionable PRs (include reason + CI state):\n\n"
        f"{pr_list}\n\n"
        f"Routing anchors (must follow exactly):\n"
        f"- Workspace root: {WORKSPACE}\n"
        f"- Follow-up summary path: {PR_STAGE_ROOT}/_followup/<timestamp>.md\n"
        f"- If code edits are needed, use Planning-with-Files in {PR_STAGE_ROOT}/<repo-name>/\n"
        f"- Required files for edited repos: task_plan.md, findings.md, progress.md\n"
        f"- Superpowers plans (repo-local): <repo-root>/docs/superpowers/plans/\n\n"
        f"PRIORITY ORDER (handle in this order, highest first):\n"
        f"1. ci-failing  -> reproduce the failure locally, fix it, push, then reply\n"
        f"2. unreplied   -> address EVERY maintainer comment with no subsequent reply\n"
        f"3. new-comments -> acknowledge/answer/act on new feedback\n"
        f"Do not skip to a later tier while earlier tier items remain.\n\n"
        f"REPLY TONE (non-negotiable; reject your own draft if it violates):\n"
        f"- Humility over cleverness. Open with a plain acknowledgement, not a status table.\n"
        f"- Preferred phrases: 'I might be wrong, but...', 'If this direction doesn't fit, no problem.',\n"
        f"  'Happy to adjust.'\n"
        f"- Never use: 'My analysis shows...', 'The optimal approach is...', bolded '@username',\n"
        f"  emoji-headed sections, multi-row status tables.\n"
        f"- Never mention internal tooling: no agent names, no multi-model pipelines, no orchestration systems.\n"
        f"- Match the project's language and commit format exactly.\n"
        f"- Short is better: 2-4 sentences beats 20 lines of Markdown.\n\n"
        f"For each PR:\n"
        f"1. gh pr view <owner/repo> <number> --comments\n"
        f"2. If CI failing: fix first, push, THEN reply with 'pushed a fix, thanks for flagging'.\n"
        f"3. If actionable feedback: implement, push, reply plainly.\n"
        f"4. Use codex:codex-rescue for requested-change implementation.\n"
        f"5. Use gemini:gemini-consult for larger architecture checks; if startup is slow, retry once.\n"
        f"6. If question: answer with evidence from code.\n"
        f"7. If approved: thank and confirm merge readiness.\n"
        f"8. If CLA required: sign if possible, else note it plainly and stop on that PR.\n"
    )

    result = subprocess.run(
        [CONFIG.claude_bin, "-p", "--model", CONFIG.claude_model,
         "--dangerously-skip-permissions",
         prompt],
        capture_output=True, text=True,
        timeout=3600,
        cwd=WORKSPACE
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
