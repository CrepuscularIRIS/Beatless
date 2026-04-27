#!/usr/bin/env python3
"""Hermes Monitor — single-file dashboard for cron jobs + chat activity.

Usage:
    python3 ~/.hermes/scripts/monitor-server.py [--port 8765] [--host 127.0.0.1]

Then open http://127.0.0.1:8765/ in a browser. The page auto-refreshes
every 30s via meta refresh, and the JSON endpoint at /api/state powers
any external dashboard.

No external dependencies — only stdlib. Reads:
  ~/.hermes/cron/jobs.json                     — job definitions
  ~/.hermes/cron/output/<jid>/<ts>.md          — last cron outputs
  ~/.hermes/logs/agent.log                     — chat / gateway activity
  ~/.hermes/shared/.last-github-pr-status      — github-pr converge stats
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
HERMES = HOME / ".hermes"
CRON_JOBS = HERMES / "cron" / "jobs.json"
CRON_OUT = HERMES / "cron" / "output"
AGENT_LOG = HERMES / "logs" / "agent.log"
ERRORS_LOG = HERMES / "logs" / "errors.log"
GITHUB_PR_STATUS = HERMES / "shared" / ".last-github-pr-status"

REFRESH_SECONDS = 30


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def _tail_file(path: Path, n: int = 50) -> list[str]:
    if not path.exists():
        return []
    try:
        with path.open("r", errors="replace") as f:
            return list(deque(f, maxlen=n))
    except OSError:
        return []


def _latest_output(job_id: str) -> tuple[str | None, str | None]:
    """Return (timestamp_str, body_excerpt) of the most recent cron output."""
    d = CRON_OUT / job_id
    if not d.is_dir():
        return None, None
    try:
        files = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None, None
    if not files:
        return None, None
    f = files[0]
    try:
        text = f.read_text(errors="replace")
    except OSError:
        return None, None
    excerpt = ""
    m = re.search(r"## Response\s*(.+?)(?:$|\n##\s)", text, re.DOTALL)
    if m:
        excerpt = m.group(1).strip()[:1200]
    else:
        m_err = re.search(r"## Script Error.+?```(.+?)```", text, re.DOTALL)
        excerpt = (m_err.group(1).strip() if m_err else text[-800:]).strip()[:1200]
    return f.stem, excerpt


def collect_state() -> dict:
    raw = _read_json(CRON_JOBS) or {}
    jobs = raw.get("jobs", []) if isinstance(raw, dict) else []
    enriched = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        ts, excerpt = _latest_output(j.get("id", ""))
        last_run = j.get("last_run_at")
        next_run = j.get("next_run_at")
        last_status = j.get("last_status")
        last_error = j.get("last_error")
        # health rule: ok if last_status == 'ok' and excerpt is non-empty
        if last_status == "ok" and excerpt and "Script Error" not in excerpt:
            health = "healthy"
        elif last_status == "ok" and (not excerpt or "wakeAgent=false" in excerpt):
            health = "noop"
        elif last_error or (excerpt and "Script Error" in excerpt):
            health = "broken"
        else:
            health = "unknown"
        enriched.append({
            "id": j.get("id"),
            "name": j.get("name"),
            "script": j.get("script"),
            "schedule": j.get("schedule_display") or j.get("schedule", {}).get("display"),
            "completed": j.get("repeat", {}).get("completed"),
            "enabled": j.get("enabled"),
            "state": j.get("state"),
            "last_run_at": last_run,
            "next_run_at": next_run,
            "last_status": last_status,
            "last_error": last_error,
            "last_output_ts": ts,
            "last_output_excerpt": excerpt,
            "health": health,
        })

    chat_lines = [ln.rstrip("\n") for ln in _tail_file(AGENT_LOG, 80)]
    error_lines = [ln.rstrip("\n") for ln in _tail_file(ERRORS_LOG, 30)]
    pr_status = _read_json(GITHUB_PR_STATUS)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs": enriched,
        "chat_tail": chat_lines,
        "error_tail": error_lines,
        "github_pr": pr_status,
    }


HEALTH_BADGE = {
    "healthy": ("Healthy", "#16a34a"),
    "noop": ("No-op",   "#a3a3a3"),
    "broken": ("Broken", "#dc2626"),
    "unknown": ("?",     "#6b7280"),
}


def render_html(state: dict) -> str:
    rows = []
    for j in state["jobs"]:
        label, color = HEALTH_BADGE.get(j["health"], HEALTH_BADGE["unknown"])
        excerpt = html.escape(j["last_output_excerpt"] or "(no output)")
        rows.append(f"""
        <tr>
          <td><span class="dot" style="background:{color}"></span> {html.escape(label)}</td>
          <td><b>{html.escape(j['name'] or '')}</b><br><code>{html.escape(j['script'] or '')}</code></td>
          <td>{html.escape(j['schedule'] or '')}<br><small>runs: {j['completed'] or 0}</small></td>
          <td><small>last: {html.escape(str(j['last_run_at'] or '—'))}</small><br>
              <small>next: {html.escape(str(j['next_run_at'] or '—'))}</small></td>
          <td><pre>{excerpt}</pre></td>
        </tr>
        """)

    chat_html = html.escape("\n".join(state["chat_tail"][-40:]))
    err_html = html.escape("\n".join(state["error_tail"][-20:])) or "(no recent errors)"
    pr = state.get("github_pr") or {}
    pr_html = ""
    if pr:
        pr_html = "<dl class='kv'>"
        for k, v in pr.items():
            pr_html += f"<dt>{html.escape(str(k))}</dt><dd>{html.escape(str(v))}</dd>"
        pr_html += "</dl>"
    else:
        pr_html = "<p><i>No github-pr status yet.</i></p>"

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="{REFRESH_SECONDS}">
<title>Hermes Monitor — Cron + Chat</title>
<style>
  :root {{
    color-scheme: dark light;
    --bg: #0b0d10;
    --fg: #e6e6e6;
    --panel: #15191e;
    --border: #2a3037;
    --accent: #4f8cff;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 24px; background: var(--bg); color: var(--fg);
         font: 14px/1.5 ui-monospace, Menlo, Consolas, monospace; }}
  header {{ display:flex; justify-content:space-between; align-items:baseline;
            margin-bottom: 16px; }}
  h1 {{ margin:0; font-size: 20px; }}
  small.muted {{ color: #8b95a3; }}
  section {{ background: var(--panel); border: 1px solid var(--border);
             border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ vertical-align: top; padding: 8px 10px; border-bottom: 1px solid var(--border); text-align: left; }}
  th {{ font-weight: 600; color: #8b95a3; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
  pre {{ margin: 0; white-space: pre-wrap; word-break: break-word;
         background:#0d1015; padding: 8px; border-radius: 4px; max-height: 220px; overflow:auto; }}
  code {{ color: #9bb3d8; }}
  .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:4px; }}
  .grid2 {{ display:grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 1100px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  dl.kv {{ display:grid; grid-template-columns: max-content 1fr; gap: 4px 12px; }}
  dl.kv dt {{ color:#8b95a3; }}
</style></head><body>
<header>
  <h1>⚕ Hermes Monitor</h1>
  <small class="muted">refreshed {html.escape(state['generated_at'])} · auto-refresh {REFRESH_SECONDS}s</small>
</header>

<section>
  <h2 style="margin:0 0 12px">Cron Jobs ({len(state['jobs'])})</h2>
  <table>
    <thead>
      <tr><th>Health</th><th>Job</th><th>Schedule</th><th>Times</th><th>Last Output</th></tr>
    </thead>
    <tbody>
      {''.join(rows) or '<tr><td colspan="5"><i>no jobs</i></td></tr>'}
    </tbody>
  </table>
</section>

<div class="grid2">
  <section>
    <h2 style="margin:0 0 12px">GitHub PR Pipeline (last)</h2>
    {pr_html}
  </section>
  <section>
    <h2 style="margin:0 0 12px">Recent Errors (errors.log tail)</h2>
    <pre>{err_html}</pre>
  </section>
</div>

<section>
  <h2 style="margin:0 0 12px">Hermes Activity (agent.log tail)</h2>
  <pre>{chat_html}</pre>
</section>

<footer><small class="muted">Source: {html.escape(str(CRON_OUT))} · {html.escape(str(AGENT_LOG))}</small></footer>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet stderr spam
        pass

    def _send(self, status, body, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                state = collect_state()
                self._send(200, render_html(state))
            except Exception as e:
                self._send(500, f"<pre>monitor error: {html.escape(str(e))}</pre>")
        elif self.path == "/api/state":
            try:
                state = collect_state()
                self._send(200, json.dumps(state, default=str, indent=2),
                           content_type="application/json")
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}),
                           content_type="application/json")
        else:
            self._send(404, "not found", content_type="text/plain")


def main():
    p = argparse.ArgumentParser(description="Hermes Monitor dashboard")
    p.add_argument("--host", default=os.environ.get("HERMES_MONITOR_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("HERMES_MONITOR_PORT", "8765")))
    args = p.parse_args()

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Hermes Monitor serving {url}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        srv.server_close()


if __name__ == "__main__":
    main()
