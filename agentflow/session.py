from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentflow.agent.pipeline import RunResult


def save_session(workspace: Path, result: RunResult, task: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = workspace / ".agentflow" / "sessions"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stamp}.json"
    payload = {
        "task": task,
        "mode": result.pipeline.mode,
        "classification": result.pipeline.classification.model_dump(),
        "stages": [s.model_dump() for s in result.pipeline.stages],
        "artifacts": result.artifacts,
        "changed": result.changed,
        "cost_usd": result.ledger.total_usd,
        "cap_usd": result.ledger.cap_usd,
        "events": [e.model_dump() for e in result.ledger.events],
        "stopped": result.stopped,
        "skills_loaded": result.skills_loaded,
        "skills_saved": result.skills_saved,
        "code_review_rounds": result.code_review_rounds,
        "trial_rounds": result.trial_rounds,
        "trial_passed": result.trial_passed,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def latest_session_file(workspace: Path) -> Path | None:
    folder = workspace / ".agentflow" / "sessions"
    if not folder.is_dir():
        return None
    files = sorted(folder.glob("*.json"))
    return files[-1] if files else None


def load_session_ledger(path: Path):
    from agentflow.cost import CostEvent, Ledger

    payload = json.loads(path.read_text(encoding="utf-8"))
    events = [CostEvent.model_validate(item) for item in payload.get("events") or []]
    cap = float(payload.get("cap_usd") or 0) or max((e.usd for e in events), default=0.0) or 3.0
    return Ledger(events=events, cap_usd=cap), payload
