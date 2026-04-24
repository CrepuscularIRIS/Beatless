"""Unit tests for paper-harvest v2 pure-logic helpers.

Run:
    cd ~/.hermes/scripts && python3 -m pytest tests/test_paper_harvest.py -v

Covers:
    is_recent_enough  — date boundary logic
    detect_tier_lab   — Tier 1 / Tier 2 / Other / None classification
    classify_tier     — routing decision
    title_similarity  — Jaccard dedup fallback
    is_duplicate      — end-to-end dedup
"""
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location(
    "paper_harvest",
    str(pathlib.Path(__file__).parent.parent / "paper-harvest.py"),
)
ph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ph)


class TestIsRecentEnough:
    def test_2024_dec_rejected(self):
        assert ph.is_recent_enough(2024, 12) is False

    def test_2025_jan_accepted_for_processing(self):
        # 2025 papers are eligible for processing; classify_tier decides tier
        assert ph.is_recent_enough(2025, 1) is True

    def test_2025_aug_accepted(self):
        assert ph.is_recent_enough(2025, 8) is True

    def test_2025_sep_accepted(self):
        assert ph.is_recent_enough(2025, 9) is True

    def test_2025_dec_accepted(self):
        assert ph.is_recent_enough(2025, 12) is True

    def test_2026_any_accepted(self):
        assert ph.is_recent_enough(2026, 1) is True
        assert ph.is_recent_enough(2026, 6) is True
        assert ph.is_recent_enough(2026, 12) is True

    def test_none_year_rejected(self):
        assert ph.is_recent_enough(None, 1) is False

    def test_unknown_month_2025_still_processed(self):
        # 2025 with no month is processed (goes to Scouting via classify_tier)
        assert ph.is_recent_enough(2025, None) is True


class TestDetectTierLab:
    def test_tier1_anthropic(self):
        tier, lab = ph.detect_tier_lab("Authors from Anthropic")
        assert tier == "tier1"
        assert lab == "anthropic"

    def test_tier1_openai(self):
        tier, lab = ph.detect_tier_lab("OpenAI research team")
        assert tier == "tier1"
        assert lab == "openai"

    def test_tier1_deepmind(self):
        tier, lab = ph.detect_tier_lab("Google DeepMind, London")
        assert tier == "tier1"

    def test_tier2_moonshot(self):
        tier, lab = ph.detect_tier_lab("Moonshot AI - Kimi team")
        assert tier == "tier2"

    def test_tier2_deepseek(self):
        tier, lab = ph.detect_tier_lab("DeepSeek AI")
        assert tier == "tier2"

    def test_tier2_bytedance(self):
        tier, lab = ph.detect_tier_lab("ByteDance Seed Team")
        assert tier == "tier2"

    def test_tier2_qwen(self):
        tier, lab = ph.detect_tier_lab("Qwen Team, Alibaba Qwen")
        assert tier == "tier2"

    def test_other_meta(self):
        tier, lab = ph.detect_tier_lab("Meta AI FAIR labs")
        assert tier == "other"

    def test_none_on_university(self):
        tier, lab = ph.detect_tier_lab("Stanford University, MIT")
        # Universities are NOT in ALL_LAB_SIGNALS anymore
        assert tier is None

    def test_none_on_empty(self):
        tier, lab = ph.detect_tier_lab("")
        assert tier is None
        assert lab is None

    def test_tier1_beats_tier2_in_order(self):
        # If both appear, tier 1 wins (iteration order).
        tier, lab = ph.detect_tier_lab("A paper from Anthropic and ByteDance")
        assert tier == "tier1"


class TestClassifyTier:
    def test_ccf_a_venue_always_a_tier(self):
        assert ph.classify_tier(venue_label="NeurIPS", year=2024) == "A-Tier"
        assert ph.classify_tier(venue_label="ICML", year=2020) == "A-Tier"

    def test_ccf_a_optional_acl_is_a_tier(self):
        assert ph.classify_tier(venue_label="ACL", year=2025, month=7) == "A-Tier"

    def test_tier1_lab_2026_is_a_tier(self):
        assert ph.classify_tier(
            venue_label=None, authors_text="Anthropic team", year=2026, month=1
        ) == "A-Tier"

    def test_tier2_lab_2025_sep_is_a_tier(self):
        assert ph.classify_tier(
            venue_label=None, authors_text="DeepSeek AI", year=2025, month=9
        ) == "A-Tier"

    def test_tier1_lab_but_2025_aug_is_scouting(self):
        assert ph.classify_tier(
            venue_label=None, authors_text="OpenAI", year=2025, month=8
        ) == "Scouting"

    def test_tier2_lab_but_2024_is_scouting(self):
        assert ph.classify_tier(
            venue_label=None, authors_text="ByteDance Seed", year=2024, month=12
        ) == "Scouting"

    def test_no_lab_no_venue_2026_is_scouting(self):
        assert ph.classify_tier(
            venue_label=None, authors_text="Some random university", year=2026, month=5
        ) == "Scouting"

    def test_no_lab_no_venue_no_year_is_scouting(self):
        assert ph.classify_tier() == "Scouting"

    def test_other_lab_not_promoted_even_in_window(self):
        # Meta AI is "other" tier — NOT auto-promoted to A-Tier by lab alone.
        assert ph.classify_tier(
            venue_label=None, authors_text="Meta AI FAIR", year=2026, month=1
        ) == "Scouting"


class TestTitleSimilarity:
    def test_identical(self):
        a = "Weak-to-Strong Generalization via Bootstrapped Agents"
        assert ph.title_similarity(a, a) == 1.0

    def test_case_insensitive(self):
        a = "Attention Is All You Need"
        b = "ATTENTION IS ALL YOU NEED"
        assert ph.title_similarity(a, b) == 1.0

    def test_one_word_diff_high_sim(self):
        a = "Weak-to-Strong Generalization via Bootstrapped Agents"
        b = "Weak-to-Strong Generalization via Bootstrapped Tools"
        # Stop-words <= 2 chars dropped. "via" is 3 chars, kept.
        # Shared: weak, strong, generalization, via, bootstrapped. Diff: agents/tools
        # Jaccard = 5 / 7 ≈ 0.71
        sim = ph.title_similarity(a, b)
        assert sim > 0.6
        assert sim < 0.95  # not identical

    def test_totally_different(self):
        a = "Attention Is All You Need"
        b = "Residual Learning for Deep Networks"
        sim = ph.title_similarity(a, b)
        assert sim < 0.1

    def test_empty_inputs(self):
        assert ph.title_similarity("", "") == 0.0
        assert ph.title_similarity("foo bar baz", "") == 0.0


class TestIsDuplicate:
    def _index(self, ids=None, titles=None):
        return {"ids": set(ids or []), "titles": list(titles or [])}

    def test_archive_id_match(self):
        idx = self._index(ids={"arxiv:2510.12345"})
        item = {"archiveID": "arXiv:2510.12345", "title": "New Paper", "url": ""}
        assert ph.is_duplicate(item, idx) is True

    def test_url_match(self):
        idx = self._index(ids={"https://arxiv.org/abs/2601.01"})
        item = {"archiveID": "", "title": "X", "url": "https://arxiv.org/abs/2601.01"}
        assert ph.is_duplicate(item, idx) is True

    def test_title_exact_match(self):
        idx = self._index(ids={("title", "some paper about agents")})
        item = {"archiveID": "", "title": "Some Paper About Agents", "url": ""}
        assert ph.is_duplicate(item, idx) is True

    def test_title_similarity_match(self):
        idx = self._index(titles=["weak-to-strong generalization via bootstrapping"])
        item = {"archiveID": "", "title": "Weak-to-Strong Generalization via Bootstrapping", "url": ""}
        assert ph.is_duplicate(item, idx) is True

    def test_no_match(self):
        idx = self._index(ids={"arxiv:9999.99"}, titles=["totally unrelated work"])
        item = {"archiveID": "arXiv:0001.01", "title": "Brand New Paper", "url": ""}
        assert ph.is_duplicate(item, idx) is False
