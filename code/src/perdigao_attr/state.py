"""Run state: run_id, checkpointing, fail-closed validation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def protocol_hash(protocol_text: str) -> str:
    return hashlib.sha256(protocol_text.encode("utf-8")).hexdigest()


def make_run_id(protocol_text: str, now_iso: str | None = None) -> str:
    now_iso = now_iso or utc_now_iso()
    h = protocol_hash(protocol_text)[:8]
    safe = now_iso.replace(":", "").replace("+", "p")
    return f"{safe}_{h}"


def write_checkpoint(run_dir: Path, payload: dict) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at_utc": utc_now_iso(), **payload}
    path = run_dir / "checkpoint.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def append_event(repo_root: Path, event: dict) -> Path:
    """Append to audit/events.jsonl with required keys; no silent fallback."""
    required = {"phase", "severity", "code", "message", "action"}
    missing = required - set(event.keys())
    if missing:
        raise ValueError(f"event missing keys: {missing}")
    audit_dir = repo_root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    record = {"at_utc": utc_now_iso(), **event}
    path = audit_dir / "events.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return path
