---
name: pr-direction-check
description: "Decides whether an issue is worth pursuing as a PR. Use AFTER the Python preflight has fetched the issue body, labels, comments, and CONTRIBUTING.md excerpt — this skill does the JUDGMENT (dispute detection, AI-policy interpretation, direction alignment) that regex cannot do reliably. Returns a structured verdict: proceed / block / yield / ambiguous. Invoke from /github-pr Phase 2.5 before cloning any repo."
---

# PR Direction Check

## Purpose

Every PR run in `~/claw/Beatless/pipelines/github-pr.md` hits a hard-fail
preflight (Phase 2). Some of those gates are deterministic (duplicate-PR
detection via `Fixes #N` grep, block-label matching) and live in Python.
**Others require judgment**:

- Is the CONTRIBUTING.md really forbidding AI, or is the reader being
  reminded to disclose?
- Did the maintainer *dispute* the issue, or just ask a clarifying question?
- Is the issue still open because it's accepted, or because nobody has
  closed it yet?

Regex-based encoding of these calls gets both false positives and false
negatives. This skill is the LLM-reasoning side of the preflight.

## When invoked

`/github-pr` Phase 2.5 — after the Python wake-gate has fetched:

- Issue title + body
- Issue labels (list)
- Last 20 comments, each with `author_association` (OWNER / MEMBER /
  COLLABORATOR / CONTRIBUTOR / NONE / FIRST_TIME_CONTRIBUTOR)
- CONTRIBUTING.md text (first 4000 chars) OR "NONE" if missing
- List of open PRs in the repo that mention this issue number

## Contract — input

You will receive a JSON blob with keys:

```json
{
  "repo": "owner/name",
  "issue_number": 12404,
  "issue_title": "...",
  "issue_body": "...",
  "labels": ["bug", "..."],
  "comments": [
    {"author": "Dreamsorcerer", "role": "MEMBER", "body": "...", "created_at": "2026-04-21T..."},
    ...
  ],
  "contributing_md": "...",
  "related_open_prs": [
    {"number": 12413, "author": "someoneelse", "title": "..."}
  ]
}
```

## Contract — output

Emit exactly one line at the end of your reasoning, in this format:

```
DIRECTION_VERDICT: <status> | <one-line reason>
```

Where `<status>` is one of:

- `proceed` — safe to clone and start work
- `block:ai-forbidden` — CONTRIBUTING.md prohibits AI-generated contributions
- `block:maintainer-disputed` — a maintainer (OWNER/MEMBER/COLLABORATOR) has argued against the premise of the issue
- `block:rejected-label` — issue carries wontfix / invalid / by-design etc. (should have been caught in Python; flag if it slipped through)
- `block:duplicate-pr` — an open PR already addresses this issue
- `yield:claimed` — another contributor has said they'll work on it
- `yield:stale-claim` — old claim (>14d) with no PR; prefer to comment asking if they still plan to work on it before taking over
- `ambiguous:<what-needs-clarification>` — the signals conflict; a human should decide

The `<one-line reason>` must cite evidence (quote or reference the commenter and role) so downstream logging can audit the decision.

## Reasoning rules

### AI-policy interpretation

- Treat "please disclose AI-assisted contributions" as REQUIRES-DISCLOSURE, **not** forbidden. Proceed, but ensure the PR body contains an AI disclosure paragraph (PullRequest.md §AI Disclosure).
- Treat "AI-generated code is forbidden / will be rejected / not accepted" as FORBIDDEN. Block.
- Treat silence (no mention of AI) as PROCEED — default to permitted if no policy stated.
- When ambiguous ("please review carefully if using AI" / "AI contributions are generally discouraged but case-by-case"): return `ambiguous:ai-policy-unclear`.

### Maintainer-dispute detection

A maintainer voice = `author_association` in `{OWNER, MEMBER, COLLABORATOR}`.

Dispute indicators:

- **Direct rejection**: "won't fix", "not going to merge", "closing this"
- **Premise skepticism**: "I don't see why", "not sure what you want", "this is already by design", "not a bug"
- **Redirection**: "out of scope", "that's intentional", "this was a deliberate choice"
- **Technical correction that invalidates the ask**: e.g. user says "bug X breaks Y", maintainer replies "X is the intended behavior and Y is unrelated"

Non-dispute:

- Questions asking for reproduction / details
- Acknowledgment ("thanks for the report, looking into it")
- Assignment / labeling comments

Edge case: if two maintainers disagree (one disputes, one accepts), treat as `ambiguous:maintainer-disagreement`.

### Claim interpretation

- `/assign` or "I'll work on this" within the last 14 days → `yield:claimed`
- Same phrase >14 days old with no PR opened → `yield:stale-claim` (we'll politely check in rather than steal)
- "Can I try?" without a yes from maintainer → proceed (it's a question, not a claim)
- Multiple claimers → `yield:claimed` on the most recent one

### Duplicate-PR interpretation

- An open PR with `Fixes #N` or `Closes #N` → `block:duplicate-pr`
- A closed-merged PR fixing the same issue → `block:duplicate-pr` (the issue should have auto-closed; something is odd, human review)
- An open PR titled similarly but not linking the issue → `ambiguous:possible-duplicate-pr` — a human should check

### Direction-alignment nuance

- Issue labelled `help wanted` + explicit maintainer engagement → strong proceed signal
- Issue body says "proposal" or "discussion" or "RFC" → `block:discussion-not-patch` (these aren't ready for code)
- Issue is 6+ months old with no recent activity → `ambiguous:stale-issue`

## Example — aiohttp#12404 (the real dispute case)

Input excerpt (simplified):
```json
{
  "repo": "aio-libs/aiohttp",
  "issue_number": 12404,
  "issue_title": "Bug: BodyPartReader.filename and read() leak bytearray...",
  "labels": ["bug"],
  "comments": [
    {"author": "Dreamsorcerer", "role": "MEMBER",
     "body": "bytes is not JSON serializable either, not sure what you want here...",
     "created_at": "2026-04-21T11:52:05Z"}
  ]
}
```

Correct output:
```
DIRECTION_VERDICT: block:maintainer-disputed | Dreamsorcerer (MEMBER) on 2026-04-21: "bytes is not JSON serializable either, not sure what you want here" — rejects the premise of the fix.
```

## Hard rule — output discipline

Your reasoning can be as long as necessary. The final line MUST be the
single `DIRECTION_VERDICT:` marker. Downstream Python parses this line
to decide whether to proceed. No quotes around the line, no other
markers, no explanation after it.
