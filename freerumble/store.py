"""Local JSON storage for subscriptions, history, and settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = root / "freerumble"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(name: str) -> Path:
    return data_dir() / name


def _load(name: str, default: Any) -> Any:
    path = _path(name)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save(name: str, payload: Any) -> None:
    path = _path(name)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_state() -> dict[str, Any]:
    return {
        "subscriptions": _load("subscriptions.json", []),
        "history": _load("history.json", []),
        "settings": _load(
            "settings.json",
            {
                "use_ytdlp": True,
                "default_quality": "best",
                "open_browser": True,
            },
        ),
    }


def save_subscriptions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    for item in items:
        url = (item.get("url") or "").rstrip("/")
        if not url or url in seen:
            continue
        seen.add(url)
        clean.append(item)
    _save("subscriptions.json", clean)
    return clean


def add_history(entry: dict[str, Any]) -> list[dict[str, Any]]:
    history = _load("history.json", [])
    vid = entry.get("id") or entry.get("url")
    history = [h for h in history if (h.get("id") or h.get("url")) != vid]
    history.insert(0, entry)
    history = history[:200]
    _save("history.json", history)
    return history


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    current = _load("settings.json", {})
    current.update(settings)
    _save("settings.json", current)
    return current
