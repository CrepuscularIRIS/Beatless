#!/usr/bin/env python3
import argparse
import contextlib
import errno
import fcntl
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


TERMINAL = {"done", "blocked", "escalated", "rolled_back"}
DIRECT_PASS_STAGES = ["planned", "implementing", "verifying", "reviewing", "done"]
HARNESS_STAGE_CHAIN = [
    ("queued", "plan", "planned"),
    ("planned", "implement", "implementing"),
    ("implementing", "verify", "verifying"),
    ("verifying", "review", "reviewing"),
    ("reviewing", "publish", "done"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise ValueError(f"empty json file: {path}")
    return json.loads(raw)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


@dataclass
class JobContext:
    root: Path
    job_id: str
    job_dir: Path
    contract_path: Path
    state_path: Path
    failures_path: Path
    handoff_path: Path


def build_context(jobs_root: Path, job_dir: Path) -> JobContext:
    return JobContext(
        root=jobs_root,
        job_id=job_dir.name,
        job_dir=job_dir,
        contract_path=job_dir / "contract.json",
        state_path=job_dir / "state.json",
        failures_path=job_dir / "failures.log",
        handoff_path=job_dir / "handoff.md",
    )


def default_state(job_id: str) -> Dict[str, Any]:
    now = now_iso()
    return {
        "job_id": job_id,
        "status": "queued",
        "current_stage": "queue",
        "current_iteration": 0,
        "created_at": now,
        "updated_at": now,
        "wall_clock_elapsed_min": 0,
        "retry_count": 0,
        "circuit_breaker": {
            "consecutive_no_diff": 0,
            "consecutive_same_error": 0,
            "state": "closed",
        },
        "stage_history": [],
        "last_checkpoint": {
            "verify_fail_count": 0,
            "last_error_fp": "",
            "last_error_msg": "",
        },
        "failure_log": [],
    }


def ensure_job_files(ctx: JobContext, contract: Dict[str, Any]) -> Dict[str, Any]:
    if ctx.state_path.exists():
        try:
            return read_json(ctx.state_path)
        except Exception:  # noqa: BLE001
            corrupt = ctx.state_path.with_suffix(f".corrupt.{int(time.time())}.json")
            with contextlib.suppress(Exception):
                ctx.state_path.replace(corrupt)
    state = default_state(contract.get("id", ctx.job_id))
    write_json(ctx.state_path, state)
    return state


def append_history(state: Dict[str, Any], stage: str, status: str, note: str = "") -> None:
    item = {"stage": stage, "status": status, "at": now_iso()}
    if note:
        item["note"] = note
    state["stage_history"].append(item)
    state["updated_at"] = now_iso()


def dict_get(d: Dict[str, Any], key: str, default: Any) -> Any:
    v = d.get(key)
    return default if v is None else v


def compute_dirs(paths: List[str]) -> int:
    roots = set()
    for p in paths:
        n = p.strip("/")
        roots.add(n.split("/")[0] if n else "")
    return len([x for x in roots if x])


def stage_chain_for_status(status: str) -> Optional[Tuple[str, str, str]]:
    for item in HARNESS_STAGE_CHAIN:
        if item[0] == status:
            return item
    return None


def safe_load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml
    except Exception:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_trigger_event(root: Path, ctx: JobContext, contract: Dict[str, Any], stage_status: str) -> Dict[str, Any]:
    resolver = root / "scripts" / "resolve_trigger.py"
    if not resolver.exists():
        return {"stage": stage_status, "error": "resolver_missing"}

    stage_map = {
        "queued": "plan",
        "planned": "implement",
        "implementing": "verify",
        "verifying": "review",
        "reviewing": "publish",
        "done": "publish",
    }
    normalized_stage = stage_map.get(stage_status, "implement")
    prompt = str(contract.get("goal", "")).strip()

    cmd = [
        "python3",
        str(resolver),
        "--prompt",
        prompt,
        "--contract",
        str(ctx.contract_path),
        "--stage",
        normalized_stage,
        "--json",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        return {
            "stage": stage_status,
            "normalized_stage": normalized_stage,
            "prompt": prompt,
            "resolution": data,
        }
    except subprocess.CalledProcessError as exc:
        return {
            "stage": stage_status,
            "normalized_stage": normalized_stage,
            "prompt": prompt,
            "error": "resolver_failed",
            "stderr": (exc.stderr or "").strip(),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "stage": stage_status,
            "normalized_stage": normalized_stage,
            "prompt": prompt,
            "error": "resolver_bad_json",
            "detail": str(exc),
        }


def run_cmd(
    cmd: List[str],
    *,
    cwd: Optional[Path] = None,
    stdin: Optional[str] = None,
    timeout: int = 120,
) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        input=stdin,
        timeout=timeout,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def render_verify_script(contract: Dict[str, Any]) -> str:
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    lines.append("# Auto-generated from contract.acceptance.must_pass")
    lines.append("")
    must_pass = ((contract.get("acceptance") or {}).get("must_pass") or [])
    for cmd in must_pass:
        lines.append(cmd)
    lines.append('echo "ALL_CHECKS_PASS"')
    lines.append("")
    return "\n".join(lines)


def run_build_mode_selector(
    root: Path,
    contract: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    selector = root / "scripts" / "build_mode_selector.py"
    editable = contract.get("editable_paths", []) or []
    file_count = len(editable)
    dir_count = compute_dirs(editable)
    has_test = bool(((contract.get("acceptance") or {}).get("must_pass") or []))
    goal = str(contract.get("goal", ""))
    has_iter = any(k in goal for k in ["迭代", "直到通过", "循环", "多轮"])

    verify_fail_count = int(dict_get(state.get("last_checkpoint", {}), "verify_fail_count", 0))
    no_diff = int(dict_get(state.get("circuit_breaker", {}), "consecutive_no_diff", 0))

    cmd = [
        "python3",
        str(selector),
        "--file-count",
        str(file_count),
        "--dir-count",
        str(dir_count),
        "--has-test",
        "true" if has_test else "false",
        "--has-iter",
        "true" if has_iter else "false",
        "--consecutive-verify-fail",
        str(verify_fail_count),
        "--consecutive-no-diff",
        str(no_diff),
        "--json",
    ]
    code, out, err = run_cmd(cmd, timeout=30)
    if code != 0:
        return {
            "mode": "single_lane",
            "error": "build_mode_selector_failed",
            "stderr": err.strip(),
        }
    try:
        return json.loads(out)
    except Exception:  # noqa: BLE001
        return {
            "mode": "single_lane",
            "error": "build_mode_selector_bad_json",
            "stdout": out.strip(),
        }


def run_gate_plan(root: Path, ctx: JobContext, plan_json: Path) -> Tuple[bool, str]:
    cmd = [
        "bash",
        str(root / "scripts" / "verify_gates.sh"),
        "--stage",
        "plan",
        "--contract",
        str(ctx.contract_path),
        "--plan-json",
        str(plan_json),
    ]
    code, out, err = run_cmd(cmd, timeout=60)
    if code == 0:
        return True, out.strip() or "gate:plan PASS"
    msg = (err or out).strip() or "plan gate failed"
    return False, msg


def run_gate_review(root: Path, ctx: JobContext, codex_result: Path) -> Tuple[bool, str]:
    cmd = [
        "bash",
        str(root / "scripts" / "verify_gates.sh"),
        "--stage",
        "review",
        "--contract",
        str(ctx.contract_path),
        "--codex-result",
        str(codex_result),
    ]
    code, out, err = run_cmd(cmd, timeout=60)
    if code == 0:
        return True, out.strip() or "gate:review PASS"
    msg = (err or out).strip() or "review gate failed"
    return False, msg


def run_gate_publish(root: Path, ctx: JobContext) -> Tuple[bool, str]:
    cmd = [
        "bash",
        str(root / "scripts" / "verify_gates.sh"),
        "--stage",
        "publish",
        "--contract",
        str(ctx.contract_path),
        "--job-dir",
        str(ctx.job_dir),
    ]
    code, out, err = run_cmd(cmd, timeout=30)
    if code == 0:
        return True, out.strip() or "gate:publish PASS"
    msg = (err or out).strip() or "publish gate failed"
    return False, msg


def run_stage_plan(root: Path, ctx: JobContext, contract: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    artifacts = ctx.job_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    plan_json = artifacts / "plan.json"
    if not plan_json.exists():
        editable = contract.get("editable_paths", []) or []
        route = contract.get("routing", {}) or {}
        plan = {
            "stages": [
                {
                    "stage": "implement",
                    "lane": route.get("builder", "claude_build_cli"),
                    "sub_tasks": [f"Implement: {contract.get('goal', '')}"],
                    "editable_paths": editable,
                },
                {
                    "stage": "verify",
                    "lane": route.get("reviewer", "codex_review_cli"),
                    "sub_tasks": ["Run must_pass and review gates"],
                    "editable_paths": editable,
                },
            ]
        }
        write_json(plan_json, plan)

    verify_script = ctx.job_dir / "verify.sh"
    verify_script.write_text(render_verify_script(contract), encoding="utf-8")
    verify_script.chmod(0o755)

    ok, msg = run_gate_plan(root, ctx, plan_json)
    meta = {
        "plan_json": str(plan_json.relative_to(ctx.job_dir)),
        "verify_script": str(verify_script.relative_to(ctx.job_dir)),
    }
    return ok, msg, meta


def _all_within_paths(changed_files: List[str], editable_paths: List[str]) -> List[str]:
    normalized_allowed = [p.rstrip("/") for p in editable_paths]
    violations: List[str] = []
    for f in changed_files:
        ff = f.strip()
        if not ff:
            continue
        ok = any(ff == p or ff.startswith(p + "/") for p in normalized_allowed)
        if not ok:
            violations.append(ff)
    return violations


def run_stage_implement(
    root: Path,
    ctx: JobContext,
    contract: Dict[str, Any],
    state: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    artifacts = ctx.job_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    mode_info = run_build_mode_selector(root, contract, state)

    changed_manifest = artifacts / "changed_files.txt"
    if not changed_manifest.exists() and os.environ.get("MOCK_WORKER", "0") == "1":
        editable = (contract.get("editable_paths") or ["Beatless/docs"])[0].rstrip("/")
        auto_file = f"{editable}/AUTO_IMPL.txt"
        changed_manifest.write_text(auto_file + "\n", encoding="utf-8")

    if not changed_manifest.exists():
        return False, "implement artifact missing: artifacts/changed_files.txt", {"mode": mode_info.get("mode")}

    changed_files = [ln.strip() for ln in changed_manifest.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not changed_files:
        cb = state.get("circuit_breaker", {})
        cb["consecutive_no_diff"] = int(cb.get("consecutive_no_diff", 0)) + 1
        return False, "no changed files produced", {"mode": mode_info.get("mode")}

    violations = _all_within_paths(changed_files, contract.get("editable_paths", []) or [])
    if violations:
        return False, f"path compliance failed: {', '.join(violations)}", {
            "mode": mode_info.get("mode"),
            "violations": violations,
        }

    cb = state.get("circuit_breaker", {})
    cb["consecutive_no_diff"] = 0
    return True, "implement gate passed", {
        "mode_info": mode_info,
        "changed_files": changed_files,
    }


def run_stage_verify(root: Path, contract: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    acceptance = (contract.get("acceptance") or {})
    must_pass = acceptance.get("must_pass") or []
    if not must_pass:
        return False, "acceptance.must_pass is empty", {}

    run_cwd = Path(os.environ.get("TASK_OS_COMMAND_CWD", str(root.parent))).resolve()
    cmd_timeout = int(os.environ.get("TASK_OS_CMD_TIMEOUT_SECONDS", "180"))

    logs: List[Dict[str, Any]] = []
    for cmd in must_pass:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(run_cwd),
            timeout=cmd_timeout,
            capture_output=True,
            text=True,
        )
        logs.append(
            {
                "cmd": cmd,
                "code": proc.returncode,
                "stdout_tail": (proc.stdout or "").strip()[-800:],
                "stderr_tail": (proc.stderr or "").strip()[-800:],
            }
        )
        if proc.returncode != 0:
            return False, f"must_pass failed: {cmd} (exit={proc.returncode})", {
                "cwd": str(run_cwd),
                "logs": logs,
            }

    return True, "verify gate passed", {"cwd": str(run_cwd), "logs": logs}


def run_stage_review(root: Path, ctx: JobContext) -> Tuple[bool, str, Dict[str, Any]]:
    artifacts = ctx.job_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    codex_result = artifacts / "codex_result.md"

    if not codex_result.exists() and os.environ.get("MOCK_WORKER", "0") == "1":
        codex_result.write_text(
            "## Review complete\nNo blocking issues found. Minor style suggestions only.\n",
            encoding="utf-8",
        )

    if not codex_result.exists():
        return False, "review artifact missing: artifacts/codex_result.md", {}

    ok, msg = run_gate_review(root, ctx, codex_result)
    return ok, msg, {"codex_result": str(codex_result.relative_to(ctx.job_dir))}


def run_stage_publish(root: Path, ctx: JobContext) -> Tuple[bool, str, Dict[str, Any]]:
    handoff = ctx.job_dir / "handoff"
    required = [
        handoff / "CHANGELOG.md",
        handoff / "PR_DESCRIPTION.md",
        handoff / "ROLLBACK.md",
    ]

    if os.environ.get("MOCK_WORKER", "0") == "1":
        handoff.mkdir(parents=True, exist_ok=True)
        for p in required:
            if not p.exists():
                p.write_text(f"# {p.stem}\n\nAuto-generated mock handoff.\n", encoding="utf-8")

    ok, msg = run_gate_publish(root, ctx)
    return ok, msg, {
        "handoff_files": [str(p.relative_to(ctx.job_dir)) for p in required if p.exists()],
    }


def run_stage(
    root: Path,
    ctx: JobContext,
    contract: Dict[str, Any],
    state: Dict[str, Any],
    stage_name: str,
) -> Tuple[bool, str, Dict[str, Any]]:
    if stage_name == "plan":
        return run_stage_plan(root, ctx, contract)
    if stage_name == "implement":
        return run_stage_implement(root, ctx, contract, state)
    if stage_name == "verify":
        return run_stage_verify(root, contract)
    if stage_name == "review":
        return run_stage_review(root, ctx)
    if stage_name == "publish":
        return run_stage_publish(root, ctx)
    return False, f"unsupported stage: {stage_name}", {}


def error_fingerprint(stage_name: str, message: str) -> str:
    base = f"{stage_name}:{message}".encode("utf-8")
    return hashlib.sha1(base).hexdigest()


def update_error_counters(state: Dict[str, Any], fp: str, msg: str) -> None:
    cp = state.setdefault("last_checkpoint", {})
    cb = state.setdefault("circuit_breaker", {})
    prev_fp = str(cp.get("last_error_fp", ""))
    if prev_fp == fp:
        cb["consecutive_same_error"] = int(cb.get("consecutive_same_error", 0)) + 1
    else:
        cb["consecutive_same_error"] = 1
    cp["last_error_fp"] = fp
    cp["last_error_msg"] = msg
    state["updated_at"] = now_iso()


def reset_error_counters_after_success(state: Dict[str, Any], stage_name: str) -> None:
    cp = state.setdefault("last_checkpoint", {})
    cb = state.setdefault("circuit_breaker", {})
    cb["consecutive_same_error"] = 0
    cb["state"] = "closed"
    cp["last_error_fp"] = ""
    cp["last_error_msg"] = ""
    if stage_name == "verify":
        cp["verify_fail_count"] = 0


def write_iteration_record(
    root: Path,
    ctx: JobContext,
    state: Dict[str, Any],
    stage_status: str,
    stage_name: str,
    result_status: str,
    message: str,
    details: Dict[str, Any],
) -> None:
    state["current_iteration"] += 1
    iteration_dir = ctx.job_dir / "iteration" / str(state["current_iteration"])
    iteration_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    trigger_event = resolve_trigger_event(root, ctx, read_json(ctx.contract_path), stage_status)
    write_json(iteration_dir / "trigger_event.json", trigger_event)

    summary = {
        "iteration": state["current_iteration"],
        "job_id": state["job_id"],
        "stage_status": stage_status,
        "stage": stage_name,
        "result": result_status,
        "at": now_iso(),
        "message": message,
        "details": details,
        "trigger_event_ref": f"iteration/{state['current_iteration']}/trigger_event.json",
    }
    write_json(iteration_dir / "summary.json", summary)
    state["last_checkpoint"] = {
        **state.get("last_checkpoint", {}),
        "iteration": state["current_iteration"],
        "stage": stage_name,
        "summary_ref": f"iteration/{state['current_iteration']}/summary.json",
    }


def maybe_apply_mode_hints(state: Dict[str, Any], contract: Dict[str, Any]) -> List[str]:
    notes: List[str] = []
    cp = state.setdefault("last_checkpoint", {})
    cb = state.setdefault("circuit_breaker", {})

    verify_fail = int(cp.get("verify_fail_count", 0))
    no_diff = int(cb.get("consecutive_no_diff", 0))
    same_error = int(cb.get("consecutive_same_error", 0))
    has_testable = bool(((contract.get("acceptance") or {}).get("must_pass") or []))

    if verify_fail >= 2 and has_testable:
        notes.append("hint: single_to_ralph (consecutive_verify_fail >= 2)")
    if no_diff >= 3:
        cb["state"] = "open"
        notes.append("hint: ralph_to_teams_debug (consecutive_no_progress >= 3)")
    if same_error >= 2:
        notes.append("hint: ralph_to_codex_rescue (consecutive_same_error >= 2)")

    cp["mode_hints"] = notes
    return notes


def handle_stage_failure(
    ctx: JobContext,
    contract: Dict[str, Any],
    state: Dict[str, Any],
    stage_status: str,
    stage_name: str,
    message: str,
    details: Dict[str, Any],
) -> None:
    max_retry = int(((contract.get("budget") or {}).get("max_retry", 0)) or 0)

    fp = error_fingerprint(stage_name, message)
    update_error_counters(state, fp, message)

    if stage_name == "verify":
        cp = state.setdefault("last_checkpoint", {})
        cp["verify_fail_count"] = int(cp.get("verify_fail_count", 0)) + 1

    append_history(state, stage_name, "failed", message)
    append_line(ctx.failures_path, f"[{now_iso()}] stage={stage_name} error={message}")
    state["failure_log"].append(f"{stage_name}:{message}")

    hints = maybe_apply_mode_hints(state, contract)
    if hints:
        details = {**details, "mode_hints": hints}

    # retry budget still available
    if state.get("retry_count", 0) < max_retry:
        state["retry_count"] = int(state.get("retry_count", 0)) + 1
        state["status"] = stage_status
        state["current_stage"] = stage_name
        append_history(state, stage_name, "retrying", f"retry {state['retry_count']}/{max_retry}")
        return

    cb = state.get("circuit_breaker", {})
    severe = int(cb.get("consecutive_same_error", 0)) >= 2 or int(cb.get("consecutive_no_diff", 0)) >= 3
    state["status"] = "escalated" if severe else "blocked"
    state["current_stage"] = stage_name


def run_direct_pass(root: Path, ctx: JobContext, contract: Dict[str, Any], state: Dict[str, Any]) -> bool:
    if state["status"] in TERMINAL:
        return False

    changed = False
    for stage in DIRECT_PASS_STAGES:
        state["status"] = stage
        state["current_stage"] = stage
        append_history(state, stage, "completed")
        write_iteration_record(
            root,
            ctx,
            state,
            stage_status=stage,
            stage_name=stage,
            result_status="completed",
            message="direct-pass stage result",
            details={"mode": "direct-pass"},
        )
        changed = True

    state["status"] = "done"
    state["current_stage"] = "done"
    state["updated_at"] = now_iso()
    ctx.handoff_path.write_text(
        "# Task Handoff\n\n"
        f"- job_id: `{state['job_id']}`\n"
        "- mode: direct-pass\n"
        f"- completed_at: `{state['updated_at']}`\n",
        encoding="utf-8",
    )
    return changed


def run_harness_stage(root: Path, ctx: JobContext, contract: Dict[str, Any], state: Dict[str, Any]) -> bool:
    status = str(state.get("status", "queued"))
    if status in TERMINAL:
        return False

    chain = stage_chain_for_status(status)
    if chain is None:
        state["status"] = "blocked"
        state["current_stage"] = "unknown"
        state["failure_log"].append(f"unknown status: {status}")
        state["updated_at"] = now_iso()
        return True

    stage_status, stage_name, next_status = chain

    ok, msg, details = run_stage(root, ctx, contract, state, stage_name)

    write_iteration_record(
        root,
        ctx,
        state,
        stage_status=stage_status,
        stage_name=stage_name,
        result_status="completed" if ok else "failed",
        message=msg,
        details=details,
    )

    if ok:
        append_history(state, stage_name, "completed", msg)
        reset_error_counters_after_success(state, stage_name)
        state["retry_count"] = 0
        state["status"] = next_status
        state["current_stage"] = next_status
        state["updated_at"] = now_iso()

        if next_status == "done":
            ctx.handoff_path.write_text(
                "# Task Handoff\n\n"
                f"- job_id: `{state['job_id']}`\n"
                "- mode: harness\n"
                f"- completed_at: `{state['updated_at']}`\n"
                f"- final_stage: `{stage_name}`\n",
                encoding="utf-8",
            )
        return True

    handle_stage_failure(ctx, contract, state, stage_status, stage_name, msg, details)
    state["updated_at"] = now_iso()
    return True


def read_scheduler_config(root: Path) -> Dict[str, Any]:
    path = root / "runtime" / "scheduler" / "config.json"
    if not path.exists():
        return {}
    try:
        return read_json(path)
    except Exception:  # noqa: BLE001
        return {}


def effective_mode(root: Path) -> str:
    env_mode = os.environ.get("ORCHESTRATION_MODE", "").strip().lower()
    if env_mode in {"legacy", "direct-pass", "harness"}:
        return env_mode

    cfg = read_scheduler_config(root)
    cfg_mode = str(cfg.get("mode", "direct-pass")).strip().lower()
    if cfg_mode in {"harness", "direct-pass"}:
        return cfg_mode
    return "direct-pass"


def refresh_metrics(state_path: Path, jobs_root: Path) -> None:
    metrics = {
        "jobs_total": 0,
        "jobs_done": 0,
        "jobs_blocked": 0,
        "jobs_escalated": 0,
        "updated_at": now_iso(),
    }
    for job_dir in sorted(p for p in jobs_root.iterdir() if p.is_dir()):
        metrics["jobs_total"] += 1
        sp = job_dir / "state.json"
        if not sp.exists():
            continue
        try:
            status = read_json(sp).get("status")
        except Exception:  # noqa: BLE001
            metrics["jobs_blocked"] += 1
            continue
        if status == "done":
            metrics["jobs_done"] += 1
        if status == "blocked":
            metrics["jobs_blocked"] += 1
        if status == "escalated":
            metrics["jobs_escalated"] += 1
    write_json(state_path, metrics)


def acquire_scheduler_lock(root: Path) -> Optional[int]:
    lock_path = root / "runtime" / "scheduler" / ".scheduler.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            os.close(fd)
            return None
        os.close(fd)
        raise
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode("utf-8"))
    return fd


def release_scheduler_lock(fd: Optional[int]) -> None:
    if fd is None:
        return
    with contextlib.suppress(Exception):
        fcntl.flock(fd, fcntl.LOCK_UN)
    with contextlib.suppress(Exception):
        os.close(fd)


def process_jobs(root: Path) -> int:
    jobs_root = root / "runtime" / "jobs"
    scheduler_root = root / "runtime" / "scheduler"
    state_root = root / "runtime" / "state"
    scheduler_root.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)
    jobs_root.mkdir(parents=True, exist_ok=True)

    changed_count = 0
    mode = effective_mode(root)
    execution_mode = "direct-pass" if mode in {"legacy", "direct-pass"} else "harness"

    for job_dir in sorted(p for p in jobs_root.iterdir() if p.is_dir()):
        ctx = build_context(jobs_root, job_dir)
        if not ctx.contract_path.exists():
            continue

        contract = read_json(ctx.contract_path)
        state = ensure_job_files(ctx, contract)

        changed = run_direct_pass(root, ctx, contract, state) if execution_mode == "direct-pass" else run_harness_stage(root, ctx, contract, state)

        if changed:
            write_json(ctx.state_path, state)
            changed_count += 1

    refresh_metrics(state_root / "metrics.json", jobs_root)
    return changed_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Beatless Task OS Scheduler")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Beatless repo root")
    parser.add_argument("--once", action="store_true", help="Run a single pass")
    parser.add_argument("--drain", action="store_true", help="Run until no new changes")
    parser.add_argument("--dry-run", action="store_true", help="Print mode and paths without processing jobs")
    parser.add_argument("--sleep", type=int, default=30, help="Loop sleep seconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    mode = effective_mode(root)

    if args.dry_run:
        print(f"dry-run orchestration_mode={mode} jobs_root={root / 'runtime' / 'jobs'}")
        return

    lock_fd = acquire_scheduler_lock(root)
    if lock_fd is None:
        print("scheduler lock busy: another scheduler instance is running; skip this run")
        return

    try:

        if args.once:
            changed = process_jobs(root)
            print(f"scheduler pass complete: changed_jobs={changed} orchestration_mode={mode}")
            return

        if args.drain:
            total = 0
            while True:
                changed = process_jobs(root)
                total += changed
                if changed == 0:
                    break
            print(f"scheduler drain complete: total_changed_jobs={total} orchestration_mode={mode}")
            return

        while True:
            changed = process_jobs(root)
            print(f"[{now_iso()}] scheduler loop changed_jobs={changed} orchestration_mode={mode}")
            time.sleep(max(1, args.sleep))
    finally:
        release_scheduler_lock(lock_fd)


if __name__ == "__main__":
    main()
