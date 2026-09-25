"""Tiny local HTTP API + static UI. No third-party web framework required."""

from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import extractor, store

STATIC_DIR = Path(__file__).parent / "static"


def _json_ok(payload: Any) -> tuple[int, bytes, str]:
    return 200, json.dumps(payload).encode("utf-8"), "application/json"


def _json_err(message: str, status: int = 400) -> tuple[int, bytes, str]:
    return status, json.dumps({"error": message}).encode("utf-8"), "application/json"


def handle_api(method: str, path: str, query: dict[str, list[str]], body: dict[str, Any]) -> tuple[int, bytes, str]:
    q = lambda key, default="": (query.get(key) or [default])[0]

    if path == "/api/health" and method == "GET":
        return _json_ok({"ok": True, "name": "FreeRumble"})

    if path == "/api/state" and method == "GET":
        return _json_ok(store.load_state())

    if path == "/api/settings" and method == "POST":
        return _json_ok(store.save_settings(body))

    if path == "/api/feed" and method == "GET":
        kind = q("kind", "browse")
        page = int(q("page", "1") or 1)
        query_text = q("q")
        try:
            return _json_ok(extractor.listing(kind, query_text, page))
        except extractor.ExtractorError as exc:
            return _json_err(str(exc), 502)

    if path == "/api/search" and method == "GET":
        query_text = q("q")
        if not query_text:
            return _json_err("Missing q")
        try:
            videos = extractor.listing("search", query_text, 1)
            channels = extractor.search_channels(query_text)
            return _json_ok({"videos": videos.get("items", []), "channels": channels})
        except extractor.ExtractorError as exc:
            return _json_err(str(exc), 502)

    if path == "/api/video" and method == "GET":
        url = q("url")
        if not url:
            return _json_err("Missing url")
        settings = store.load_state()["settings"]
        try:
            info = extractor.resolve_video(url, use_ytdlp=bool(settings.get("use_ytdlp", True)))
        except extractor.ExtractorError as exc:
            return _json_err(str(exc), 502)
        store.add_history(
            {
                "id": info.get("id"),
                "url": info.get("watch_url"),
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "channel": info.get("channel"),
                "channel_url": info.get("channel_url"),
            }
        )
        return _json_ok(info)

    if path == "/api/subscriptions" and method == "POST":
        items = body.get("subscriptions")
        if not isinstance(items, list):
            return _json_err("subscriptions must be a list")
        return _json_ok(store.save_subscriptions(items))

    if path == "/api/subscriptions/add" and method == "POST":
        state = store.load_state()
        items = state["subscriptions"]
        items.insert(0, body)
        return _json_ok(store.save_subscriptions(items))

    if path == "/api/subscriptions/remove" and method == "POST":
        url = (body.get("url") or "").rstrip("/")
        items = [s for s in store.load_state()["subscriptions"] if s.get("url", "").rstrip("/") != url]
        return _json_ok(store.save_subscriptions(items))

    return _json_err("Not found", 404)


class Handler(BaseHTTPRequestHandler):
    server_version = "FreeRumble/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        if args and str(args[0]).startswith("GET /api"):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            status, body, ctype = handle_api("GET", parsed.path, parse_qs(parsed.query), {})
            self._send(status, body, ctype)
            return
        self._static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        status, body, ctype = handle_api("POST", parsed.path, parse_qs(parsed.query), self._body())
        self._send(status, body, ctype)

    def _static(self, path: str) -> None:
        if path in ("", "/"):
            path = "/index.html"
        rel = path.lstrip("/")
        target = (STATIC_DIR / rel).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self._send(403, b"forbidden", "text/plain")
            return
        if not target.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), ctype)


def serve(host: str = "127.0.0.1", port: int = 4310) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd
