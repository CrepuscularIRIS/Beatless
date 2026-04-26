"""Beatless Dashboard API — FastAPI + SSE."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from collectors import collect_all, collect_agents, collect_pipelines, collect_experiments, collect_system_stats, collect_recent_activity

app = FastAPI(title="Beatless Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3720",
        "http://127.0.0.1:3720",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
def get_status():
    return collect_all()


@app.get("/api/agents")
def get_agents():
    return collect_agents()


@app.get("/api/pipelines")
def get_pipelines():
    return collect_pipelines()


@app.get("/api/experiments")
def get_experiments():
    return collect_experiments()


@app.get("/api/system")
def get_system():
    return collect_system_stats()


@app.get("/api/activity")
def get_activity(limit: int = 20):
    return collect_recent_activity(limit=limit)


@app.get("/api/events")
async def sse_events():
    """SSE stream — pushes full state every 10 seconds."""
    async def generate():
        while True:
            data = collect_all()
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(10)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=3721, reload=True)
