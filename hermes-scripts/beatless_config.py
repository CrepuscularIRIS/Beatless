"""Shared runtime configuration for Beatless wake-gate scripts.

This module is intentionally dependency-free. It loads optional env files, then
exposes all machine-specific paths/accounts through one object so each pipeline
can be adapted independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        os.environ.setdefault(key, _strip_quotes(value))


def load_env_files() -> None:
    explicit = os.environ.get("BEATLESS_ENV_FILE")
    if explicit:
        _load_env_file(Path(explicit).expanduser())

    root = _repo_root()
    # Local repo env wins over the shared Hermes env because it is machine- and
    # project-specific. Existing process env always wins over all files.
    for path in (
        root / ".env.local",
        root / ".env",
        Path("~/.hermes/.env").expanduser(),
    ):
        _load_env_file(path)


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return value
    return default


def _path(*names: str, default: str) -> Path:
    return Path(_env(*names, default=default)).expanduser()


def _int(*names: str, default: int) -> int:
    raw = _env(*names, default=str(default))
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class BeatlessConfig:
    repo_root: Path
    home: Path

    github_author: str
    workspace: Path
    contrib_root: Path
    pr_stage_root: Path
    research_dir: Path
    blog_dir: Path
    blog_posts_subdir: str
    obsidian_vault: Path
    obsidian_literature_subdir: str
    hermes_shared_dir: Path

    zotero_api_key: str
    zotero_user_id: str
    zotero_web_username: str
    zotero_auto_harvest_collection: str
    zotero_a_tier_collection: str
    zotero_scouting_collection: str
    zotero_default_collection: str

    claude_bin: str
    claude_model: str
    claude_max_budget_usd: str
    github_pr_quality_threshold: float
    stale_blog_days: int
    user_agent_contact: str

    @property
    def shared_dir(self) -> Path:
        return self.hermes_shared_dir

    @property
    def blog_posts_dir(self) -> Path:
        return self.blog_dir / self.blog_posts_subdir

    @property
    def literature_dir(self) -> Path:
        return self.obsidian_vault / self.obsidian_literature_subdir

    def shared_file(self, name: str) -> Path:
        return self.shared_dir / name

    def zotero_item_url(self, zotero_key: str) -> str:
        if not zotero_key:
            return ""
        if self.zotero_web_username:
            return f"https://www.zotero.org/{self.zotero_web_username}/items/{zotero_key}"
        if self.zotero_user_id:
            return f"https://www.zotero.org/users/{self.zotero_user_id}/items/{zotero_key}"
        return ""


def _build_config() -> BeatlessConfig:
    load_env_files()

    home = Path.home()
    repo = _repo_root()
    workspace = _path("BEATLESS_WORKSPACE", default="~/workspace")
    github_author = _env(
        "BEATLESS_GITHUB_AUTHOR",
        "GITHUB_AUTHOR",
        "GITHUB_USER",
        default="",
    )
    contact = _env(
        "BEATLESS_USER_AGENT_CONTACT",
        default=(f"https://github.com/{github_author}; +research" if github_author else "beatless-local; +research"),
    )

    quality_raw = _env("BEATLESS_GITHUB_PR_QUALITY_THRESHOLD", default="7.0")
    try:
        quality_threshold = float(quality_raw)
    except ValueError:
        quality_threshold = 7.0

    return BeatlessConfig(
        repo_root=repo,
        home=home,
        github_author=github_author,
        workspace=workspace,
        contrib_root=_path("BEATLESS_CONTRIB_ROOT", default=str(workspace / "contrib")),
        pr_stage_root=_path("BEATLESS_PR_STAGE_ROOT", default=str(workspace / "pr-stage")),
        research_dir=_path("BEATLESS_RESEARCH_DIR", default="~/research"),
        blog_dir=_path("BEATLESS_BLOG_DIR", default="~/claw/blog"),
        blog_posts_subdir=_env("BEATLESS_BLOG_POSTS_SUBDIR", default="src/content/blogs"),
        obsidian_vault=_path("BEATLESS_OBSIDIAN_VAULT", "OBSIDIAN_VAULT", default="~/obsidian-vault"),
        obsidian_literature_subdir=_env(
            "BEATLESS_OBSIDIAN_LITERATURE_SUBDIR",
            default="papers/literature",
        ),
        hermes_shared_dir=_path("BEATLESS_HERMES_SHARED", default="~/.hermes/shared"),
        zotero_api_key=_env("ZOTERO_API_KEY"),
        zotero_user_id=_env("ZOTERO_USER_ID"),
        zotero_web_username=_env("ZOTERO_WEB_USERNAME", "ZOTERO_USERNAME"),
        zotero_auto_harvest_collection=_env(
            "ZOTERO_AUTO_HARVEST_COLLECTION",
            default="",
        ),
        zotero_a_tier_collection=_env("ZOTERO_A_TIER_COLLECTION"),
        zotero_scouting_collection=_env("ZOTERO_SCOUTING_COLLECTION"),
        zotero_default_collection=_env("ZOTERO_DEFAULT_COLLECTION"),
        claude_bin=_env("CLAUDE_BIN", default="claude"),
        claude_model=_env("BEATLESS_CLAUDE_MODEL", default="sonnet"),
        claude_max_budget_usd=_env("BEATLESS_CLAUDE_MAX_BUDGET_USD", default="5.00"),
        github_pr_quality_threshold=quality_threshold,
        stale_blog_days=_int("BEATLESS_STALE_BLOG_DAYS", default=60),
        user_agent_contact=contact,
    )


CONFIG = _build_config()


def ensure_parent(path: Path | str) -> None:
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
