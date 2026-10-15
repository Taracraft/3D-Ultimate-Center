#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import select
import signal
import time


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def clamp_percent(value: object) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, parsed))


def eta_estimate(history: list[dict], started_epoch: float, now_epoch: float) -> tuple[float | None, str]:
    progress_events: list[tuple[float, int]] = []
    last_percent = -1
    for event in history:
        percent = clamp_percent(event.get("total_percent"))
        try:
            at = float(event.get("epoch"))
        except (TypeError, ValueError):
            continue
        if percent > last_percent:
            progress_events.append((at, percent))
            last_percent = percent
    if not progress_events:
        return None, "warming_up"
    current_at, current_percent = progress_events[-1]
    if current_percent >= 100:
        return 0.0, "complete"
    elapsed = max(0.001, now_epoch - started_epoch)
    if current_percent < 3 or len(progress_events) < 2:
        return None, "warming_up"
    overall_rate = current_percent / elapsed
    if overall_rate <= 0:
        return None, "warming_up"

    anchor = None
    for candidate in reversed(progress_events[:-1]):
        if current_percent - candidate[1] >= 5 or current_at - candidate[0] >= 45:
            anchor = candidate
            break
    rate = overall_rate
    confidence = "medium"
    if anchor is not None:
        delta_percent = current_percent - anchor[1]
        delta_time = max(0.001, now_epoch - anchor[0])
        recent_rate = delta_percent / delta_time
        if recent_rate > 0:
            recent_rate = max(overall_rate * 0.25, min(overall_rate * 4.0, recent_rate))
            rate = overall_rate * 0.35 + recent_rate * 0.65
            confidence = "high" if len(progress_events) >= 6 and current_percent >= 15 else "medium"
        elif now_epoch - current_at > 20:
            rate = overall_rate * 0.5
            confidence = "low"
    elif now_epoch - current_at > 20:
        rate = overall_rate * 0.65
        confidence = "low"

    if rate <= 0:
        return None, "low"
    remaining = (100 - current_percent) / rate
    if not math.isfinite(remaining) or remaining < 0 or remaining > 24 * 60 * 60:
        return None, "low"
    return remaining, confidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipe", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()

    pipe = Path(args.pipe)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pipe.parent.mkdir(parents=True, exist_ok=True)
    if pipe.exists():
        if pipe.is_fifo():
            pipe.unlink()
        else:
            raise RuntimeError(f"Refusing to replace non-FIFO path: {pipe}")
    os.mkfifo(pipe, 0o600)

    stopping = False
    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    started_epoch = time.time()
    started_at = utc_now()
    history: list[dict] = []
    state: dict = {
        "schema_version": 1,
        "source": "bambu_cli_pipe",
        "job_id": args.job_id,
        "active": True,
        "started_at": started_at,
        "updated_at": started_at,
        "last_event_at": None,
        "elapsed_seconds": 0.0,
        "plate_index": 0,
        "plate_count": 0,
        "plate_percent": 0,
        "total_percent": 0,
        "message": "Bambu Studio wird gestartet",
        "warning": None,
        "event_count": 0,
        "parse_error_count": 0,
        "eta_seconds": None,
        "eta_confidence": "warming_up",
        "history": history,
    }
    atomic_json(output, state)

    read_fd = os.open(pipe, os.O_RDONLY | os.O_NONBLOCK)
    keepalive_fd = os.open(pipe, os.O_WRONLY | os.O_NONBLOCK)
    poller = select.poll()
    poller.register(read_fd, select.POLLIN)
    buffer = b""
    last_write = 0.0
    try:
        while not stopping:
            for fd, mask in poller.poll(250):
                if fd != read_fd or not (mask & select.POLLIN):
                    continue
                try:
                    chunk = os.read(read_fd, 65536)
                except BlockingIOError:
                    chunk = b""
                if chunk:
                    buffer += chunk
                    while b"\n" in buffer:
                        raw, buffer = buffer.split(b"\n", 1)
                        raw = raw.strip()
                        if not raw:
                            continue
                        try:
                            event = json.loads(raw.decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            state["parse_error_count"] = int(state.get("parse_error_count", 0)) + 1
                            continue
                        if not isinstance(event, dict):
                            continue
                        now_epoch = time.time()
                        at = utc_now()
                        plate_percent = clamp_percent(event.get("plate_percent"))
                        total_percent = max(clamp_percent(state.get("total_percent")), clamp_percent(event.get("total_percent")))
                        message = str(event.get("message") or "").strip()[:420] or None
                        warning = str(event.get("warning") or "").strip()[:420] or None
                        entry = {
                            "at": at,
                            "epoch": now_epoch,
                            "plate_index": max(0, int(event.get("plate_index") or 0)),
                            "plate_count": max(0, int(event.get("plate_count") or 0)),
                            "plate_percent": plate_percent,
                            "total_percent": total_percent,
                            "message": message,
                            "warning": warning,
                        }
                        history.append(entry)
                        del history[:-160]
                        state.update({
                            "last_event_at": at,
                            "plate_index": entry["plate_index"],
                            "plate_count": entry["plate_count"],
                            "plate_percent": plate_percent,
                            "total_percent": total_percent,
                            "message": message or state.get("message"),
                            "warning": warning,
                            "event_count": int(state.get("event_count", 0)) + 1,
                        })
            now_epoch = time.time()
            if now_epoch - last_write >= 1.0:
                eta, confidence = eta_estimate(history, started_epoch, now_epoch)
                state.update({
                    "active": True,
                    "updated_at": utc_now(),
                    "elapsed_seconds": round(now_epoch - started_epoch, 3),
                    "eta_seconds": round(eta, 3) if eta is not None else None,
                    "eta_confidence": confidence,
                    "history": history,
                })
                atomic_json(output, state)
                last_write = now_epoch
    finally:
        now_epoch = time.time()
        eta, confidence = eta_estimate(history, started_epoch, now_epoch)
        state.update({
            "active": False,
            "updated_at": utc_now(),
            "elapsed_seconds": round(now_epoch - started_epoch, 3),
            "eta_seconds": 0.0 if clamp_percent(state.get("total_percent")) >= 100 else (round(eta, 3) if eta is not None else None),
            "eta_confidence": "complete" if clamp_percent(state.get("total_percent")) >= 100 else confidence,
            "history": history,
        })
        atomic_json(output, state)
        os.close(keepalive_fd)
        os.close(read_fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
