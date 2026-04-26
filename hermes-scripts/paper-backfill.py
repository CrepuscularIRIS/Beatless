"""Paper backfill — one-shot topical batch for 2026+ agents + training paradigms.

Different from paper-harvest.py (which is the steady-state cron):
  - Runs manually, not on cron.
  - Uses keyword queries rather than category listings.
  - No MAX_PER_TICK cap (pushes everything it finds).
  - Default year floor is 2026 (paper-harvest uses 2025).
  - Tags each paper with `topic:<slug>` so the Obsidian side can route.

Usage:
    set -a; source .env.local; set +a
    python3 paper-backfill.py

Tune TOPIC_QUEUES and YEAR_MIN below, then re-run. Safe to re-run — dedups
against whatever is already in the Zotero library.
"""
import os
import sys
import time
import json

# Pull in the harvester module
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)
import importlib.util
_spec = importlib.util.spec_from_file_location("ph", os.path.join(_dir, "paper-harvest.py"))
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)

YEAR_MIN = 2026
PER_QUERY_LIMIT = 25           # arXiv allows up to 2000; 25 per keyword is plenty
CATS = ["cs.LG", "cs.CL", "cs.CV", "cs.AI"]

# Two queue sets per user direction 2026-04-23:
#   1. Agents — agent frameworks, tool use, multi-agent, coding agents, etc.
#   2. AI training paradigms — RLHF, CAI, DPO, weak-to-strong, scalable oversight, etc.
# Keywords chosen from:
#   - User's AI alignment digest (arXiv search keywords §7)
#   - automated-w2s-research Idea.md (UE, data reweighting, noisy channel, distillation)
#   - Standard 2025-2026 agent & post-training vocabulary

TOPIC_QUEUES_AGENTS = [
    ("agent-framework",       'abs:"LLM agent" OR abs:"language model agent"'),
    ("multi-agent",           'abs:"multi-agent" AND (abs:"large language model" OR abs:"LLM")'),
    ("autonomous-research",   'abs:"autonomous research" OR abs:"automated alignment research" OR abs:"AI scientist"'),
    ("tool-use",              'abs:"tool use" OR abs:"tool-use" AND abs:"LLM"'),
    ("agent-planning",        'abs:"agent planning" OR abs:"LLM planning"'),
    ("agent-memory",          'abs:"agent memory" OR abs:"long-term memory" AND abs:"LLM"'),
    ("browser-web-agent",     'abs:"browser agent" OR abs:"web agent" OR abs:"web navigation agent"'),
    ("coding-agent",          'abs:"coding agent" OR abs:"code agent" OR abs:"software engineering agent"'),
    ("react-reasoning-act",   'abs:"ReAct" OR ti:"reasoning and acting"'),
    ("agent-benchmark",       'abs:"agent benchmark" OR abs:"agentic benchmark"'),
    ("agent-safety",          'abs:"agent safety" OR abs:"agent alignment"'),
    ("mcp-protocol",          'abs:"Model Context Protocol" OR abs:"MCP" AND abs:"agent"'),
    ("auditor-agent",         'abs:"auditor agent" OR abs:"semantic monitoring" AND abs:"agent"'),
    ("cross-pollination-agents", 'abs:"cross-pollination" AND abs:"agent"'),
    ("entropy-collapse-agents",  'abs:"entropy collapse" AND abs:"agent"'),
    ("leaderboard-driven",    'abs:"leaderboard" AND abs:"automated research"'),
]

TOPIC_QUEUES_TRAINING = [
    ("rlhf",                  'abs:"RLHF" OR abs:"reinforcement learning from human feedback"'),
    ("rlaif",                 'abs:"RLAIF" OR abs:"reinforcement learning from AI feedback"'),
    ("constitutional-ai",     'abs:"Constitutional AI"'),
    ("dpo",                   'abs:"direct preference optimization" OR ti:"DPO"'),
    ("preference-learning",   'abs:"preference learning" AND abs:"LLM"'),
    ("w2s-generalization",    'abs:"weak-to-strong" OR abs:"weak to strong generalization"'),
    ("scalable-oversight",    'abs:"scalable oversight"'),
    ("superalignment",        'abs:"superalignment"'),
    ("reward-hacking",        'abs:"reward hacking" OR abs:"specification gaming"'),
    ("pgr-w2s",               'abs:"Performance Gap Recovery" OR abs:"PGR" AND abs:"weak"'),
    ("unsup-elicitation",     'abs:"unsupervised elicitation" OR abs:"elicit strong model prior"'),
    ("em-weak-supervision",   'abs:"EM" AND abs:"weak supervision"'),
    ("noisy-channel-w2s",     'abs:"noisy channel" AND (abs:"weak supervision" OR abs:"label noise")'),
    ("self-training",         'abs:"self-training" AND abs:"LLM"'),
    ("synthetic-data-train",  'abs:"synthetic data" AND abs:"training" AND abs:"LLM"'),
    ("data-reweighting",      'abs:"data reweighting" OR abs:"example reweighting" AND abs:"training"'),
    ("distillation-lm",       'abs:"distillation" AND abs:"language model"'),
    ("reasoning-rl",          'abs:"reasoning" AND (abs:"reinforcement learning" OR abs:"process reward model")'),
    ("instruction-tuning",    'abs:"instruction tuning" OR abs:"SFT" AND abs:"LLM"'),
    ("ood-generalization",    'abs:"out-of-distribution" AND abs:"generalization" AND abs:"alignment"'),
    ("dp-eval",               'abs:"differential privacy" AND abs:"evaluation"'),
    ("label-exfiltration",    'abs:"label exfiltration" OR abs:"label leakage" AND abs:"evaluation"'),
]

ALL_QUEUES = TOPIC_QUEUES_AGENTS + TOPIC_QUEUES_TRAINING


def main():
    if not ph.ZOT_KEY or not ph.ZOT_USER:
        print("ERROR: ZOTERO_API_KEY / ZOTERO_USER_ID must be exported first.")
        return 1

    print(f"== Backfill start: {len(ALL_QUEUES)} topic queries, year>={YEAR_MIN}, {PER_QUERY_LIMIT} per query ==")
    print("== step 1: fetch existing identifiers (dedup index) ==")
    existing = ph.fetch_existing_identifiers()
    print(f"   {len(existing)} existing identifiers")

    print("\n== step 2: topical arXiv queries ==")
    entries = ph.fetch_arxiv_queries(
        ALL_QUEUES, year_min=YEAR_MIN, per_query_limit=PER_QUERY_LIMIT, cats=CATS,
    )
    print(f"   {len(entries)} unique entries after in-run dedup")

    print("\n== step 3: dedup against existing library ==")
    fresh = []
    for p in entries:
        it = ph.arxiv_to_zotero_item(p)
        if ph.is_duplicate(it, existing):
            continue
        fresh.append(it)
        if it.get("archiveID"):
            existing.add(it["archiveID"].strip().lower())
        if it.get("url"):
            existing.add(it["url"].strip().lower())
        if it.get("title"):
            existing.add(("title", it["title"].strip().lower()[:80]))
    print(f"   {len(fresh)} fresh (not in library yet)")

    if not fresh:
        print("\nNo new items — library already up to date for these topics.")
        return 0

    print(f"\n== step 4: push {len(fresh)} items to Zotero ==")
    created, failed = ph.zot_post_items(fresh)
    print(f"   created={len(created)}  failed={len(failed)}")

    summary = {
        "mode": "backfill",
        "year_min": YEAR_MIN,
        "queries_run": len(ALL_QUEUES),
        "existing_at_start": len(existing),
        "entries_fetched": len(entries),
        "fresh_pushed": len(fresh),
        "created_count": len(created),
        "failed_count": len(failed),
        "failures": failed[:10],
        "created_sample": created[:15],
    }
    out = str(ph.CONFIG.shared_file(".last-paper-backfill-status"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nSummary → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
