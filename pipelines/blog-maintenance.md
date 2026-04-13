---
name: blog-maintenance
description: "Autonomous blog maintenance pipeline for ~/blog/ (Astro site). Audits existing posts, researches trending AI/ML topics via Gemini (gemini:gemini-consult agent), writes new posts, verifies build, and reviews quality via Codex (codex:codex-rescue agent). Use this skill when the user mentions blog maintenance, writing blog posts, auditing blog content, researching topics for the blog, or wants to update their technical blog."
---

# Blog Maintenance Pipeline

Autonomous pipeline: audit existing posts -> research trending topics (Gemini agent) -> write new posts -> verify build -> quality review (Codex + Gemini agents).

## Why This Architecture

Previous versions put Codex/Gemini calls inside a `claude --print` prompt, where Claude could skip the Bash calls. This skill uses Claude Code's **Agent tool** to spawn `codex:codex-rescue` and `gemini:gemini-consult` as independent subagents that must execute.

## Execution Model

- **Claude**: Primary writer, auditor, and orchestrator via Read/Write/Grep/Glob tools
- **Gemini**: Research agent via `Agent` tool with `subagent_type: "gemini:gemini-consult"` (1M context window, good for broad research)
- **Codex**: Quality review agent via `Agent` tool with `subagent_type: "codex:codex-rescue"`
- **Build**: `pnpm build` via Bash

## Context

- Blog directory: `~/blog/` (Astro site, MDX format)
- Content path: `~/blog/src/content/blogs/<slug>/index.mdx`
- Build command: `cd ~/blog && pnpm build`
- Author: CS PhD, focus on AI/ML, EEG/BCI, agent systems
- GitHub: CrepuscularIRIS

---

## Phase 1: AUDIT (Claude direct)

Read all posts in `~/blog/src/content/blogs/*/index.mdx` using Read/Glob tools.

Classify each:
- **KEEP**: >800 words, code examples, well-structured, original content
- **REWRITE**: Good topic but poor execution — too short, missing depth, auto-generated feel
- **DRAFT**: Low-value filler, placeholder → set `isDraft: true`

Keep audit results in context for Phase 3.

---

## Phase 2: RESEARCH (Gemini Agent)

Spawn **gemini:gemini-consult** via Agent tool for each research category. These can run in parallel.

### Agent: Research AI Thought Leaders

```
Research the latest from these sources in the last 2 weeks:
1. Andrej Karpathy — blog posts, YouTube, X/Twitter
2. Anthropic — research papers, Claude updates
3. OpenAI — technical reports, system card updates
4. Google DeepMind — Gemini papers, research
5. Key industry interviews
For each: source, key insights, suggested blog angle.
```

### Agent: Research Agent Engineering

```
Most impactful developments in AI agent frameworks in the last 2 weeks?
Focus on: MCP protocol, Claude Code / Codex / Gemini CLI patterns, autonomous coding agents, multi-agent orchestration.
For each: title, key technical insight, practical code pattern.
```

### Agent: Research BCI/Neuroscience (optional)

```
Search for the most discussed papers in brain-computer interfaces, neural decoding, EEG/fMRI from the last 14 days.
List top 5 with title, key contribution, and blog post potential.
```

Select top 3 topics across all research results.

**Priority**: Adapt/summarize existing high-quality content (Karpathy blogs, Anthropic reports, technical papers) over writing from scratch.

---

## Phase 3: WRITE (Claude direct)

### New posts (write 2)

For each of the top 2 research topics:

1. Create directory: `~/blog/src/content/blogs/<slug>/`
2. Write `index.mdx` with frontmatter:
   ```yaml
   ---
   title: "<title>"
   description: "<one-line hook>"
   pubDate: "<today YYYY-MM-DD>"
   tags: [<relevant tags>]
   isDraft: false
   ---
   ```
3. Write 1500+ words:
   - Introduction with concrete hook (not "In this post we will...")
   - Technical depth with working code examples
   - Personal perspective or unique analysis angle
   - Practical takeaways
   - References with real URLs

4. Writing quality rules:
   - NO AI filler: avoid "Let's dive in", "In conclusion", "It's worth noting"
   - Use direct statements, specific numbers, concrete examples
   - Code blocks must be syntactically correct and runnable

### Rewrite (pick 1 from audit)

If any posts classified REWRITE, pick the best topic and rewrite with deeper analysis.

### Draft cleanup

For DRAFT posts: set `isDraft: true` in frontmatter. Never delete posts.

---

## Phase 4: VERIFY (Build + Parallel Agent Reviews)

### Build check (Bash)

```bash
cd ~/blog && pnpm build
```

Must exit 0. Fix if it fails.

### Parallel quality reviews — spawn BOTH agents in a single message:

#### Codex Review (codex:codex-rescue)

```
Review the recently changed blog posts in ~/blog/src/content/blogs/.
Check for:
1. Technical accuracy — are claims correct?
2. Grammar and clarity — any awkward phrasing?
3. Code example correctness — do they compile/run?
4. Broken links or references
Output a quality score 1-10 per post and specific issues found.
```

#### Gemini Review (gemini:gemini-consult)

```
Review the blog content quality in ~/blog/src/content/blogs/.
Check the most recent posts for:
1. Are the topics timely and relevant?
2. Is the technical depth sufficient for a PhD-level audience?
3. Are there any factual errors or misleading claims?
4. Quality score 1-10 per post.
```

Both agents must return results. If either finds critical issues (score < 6), address them before committing.

### Commit and Push (only if build passes and reviews acceptable)

```bash
cd ~/blog && git add src/content/blogs/ && git commit -m "content: blog maintenance — new posts and cleanup"
cd ~/blog && git push origin main
```

Auto-push is enabled because this pipeline runs autonomously via heartbeat.
The blog deploys via GitHub Pages on push, so pushing is the final delivery step.

---

## Phase 5: REPORT

Output:
- Posts audited (total, KEEP/REWRITE/DRAFT counts)
- New posts written (slugs + topics + word counts)
- Posts rewritten (slugs)
- Posts marked as draft (slugs)
- Build status (PASS/FAIL)
- Codex review scores
- Gemini review scores
- Paths to all modified files

---

## Rules

1. **Spawn Gemini and Codex as Agent subagents** — real subprocesses, not prompt suggestions
2. **Both must actually run** — verify you received results from both before proceeding
3. **Never delete a blog post** — mark as draft at most
4. **Auto-push after commit** — pipeline runs autonomously, push is the delivery step
5. **Never invent citations** — use Gemini research to verify URLs exist
6. **Build must pass** before committing
7. **All posts in MDX format** with valid frontmatter
8. **No AI filler language** — direct, specific, technical writing
