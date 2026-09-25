"""Rumble page + embedJS extractor."""

from __future__ import annotations

import html as html_lib
import json
import random
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
]
BASE = "https://rumble.com"
EMBED_JS = "https://rumble.com/embedJS/u3/"


class ExtractorError(RuntimeError):
    pass


def fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://rumble.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read()[:200].decode("utf-8", "replace")
        raise ExtractorError(f"HTTP {exc.code} fetching {url}: {body[:120]}") from exc
    except urllib.error.URLError as exc:
        raise ExtractorError(f"Network error fetching {url}: {exc.reason}") from exc
    text = raw.decode("utf-8", "replace")
    if "Just a moment" in text and ("challenge-platform" in text or "cf-mitigated" in text.lower()):
        raise ExtractorError(
            "Rumble served a Cloudflare challenge. This usually happens from "
            "datacenter IPs. Try again from your home network, or install yt-dlp."
        )
    return text


def _abs(href: str) -> str:
    if href.startswith("http"):
        return href.split("?")[0]
    return urllib.parse.urljoin(BASE + "/", href.lstrip("/"))


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return html_lib.unescape(re.sub(r"\s+", " ", text)).strip()


VIDEO_HREF_RE = re.compile(r'href="(/v(?!ideos)[\w.-]+\.html)"', re.I)
VIDEOSTREAM_RE = re.compile(r'<a[^>]+class="[^"]*videostream__link[^"]*"[^>]+href="([^"]+)"', re.I)
CARD_RE = re.compile(r'<a[^>]+href="(/v(?!ideos)[\w.-]+\.html)"[^>]*>(.*?)</a>', re.I | re.S)
TITLE_RE = re.compile(r'class="[^"]*(?:videostream__title|video-item--title|media-heading)[^"]*"[^>]*>(.*?)</', re.I | re.S)
IMG_RE = re.compile(r'<img[^>]+(?:src|data-src)="([^"]+)"', re.I)
CHANNEL_NAME_RE = re.compile(r'class="[^"]*(?:videostream__channel|channel-name|media-heading-name)[^"]*"[^>]*>(.*?)<', re.I | re.S)
DURATION_RE = re.compile(r'class="[^"]*(?:videostream__status--duration|video-item--duration)[^"]*"[^>]*>(.*?)<', re.I | re.S)
VIEWS_RE = re.compile(r'class="[^"]*(?:videostream__data--views|video-item--views)[^"]*"[^>]*>(.*?)<', re.I | re.S)
CHANNEL_HREF_RE = re.compile(r'href="(/(?:c|user)/[^"?#]+)"', re.I)
EMBED_ID_RE = re.compile(r"""Rumble\(\s*["']play["']\s*,\s*\{[^}]*["']?video["']?\s*:\s*["']([0-9a-z]+)["']""", re.I)
EMBED_URL_RE = re.compile(r"https?://(?:www\.)?rumble\.com/embed/(?:[0-9a-z]+\.)?([0-9a-z]+)", re.I)


def parse_listing(webpage: str, limit: int = 48) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in CARD_RE.finditer(webpage):
        href, inner = match.group(1), match.group(2)
        url = _abs(href)
        if url in seen:
            continue
        seen.add(url)
        title_m = TITLE_RE.search(inner) or TITLE_RE.search(webpage[match.start(): match.start() + 2500])
        img_m = IMG_RE.search(inner)
        dur_m = DURATION_RE.search(inner)
        views_m = VIEWS_RE.search(inner)
        chan_m = CHANNEL_NAME_RE.search(inner)
        title = _clean(re.sub("<[^>]+>", "", title_m.group(1))) if title_m else ""
        if not title:
            title = href.split("/")[-1].replace(".html", "").replace("-", " ")
        items.append({
            "id": href.strip("/").split(".")[0],
            "url": url,
            "title": title,
            "thumbnail": img_m.group(1) if img_m else "",
            "duration": _clean(dur_m.group(1)) if dur_m else "",
            "views": _clean(views_m.group(1)) if views_m else "",
            "channel": _clean(re.sub("<[^>]+>", "", chan_m.group(1))) if chan_m else "",
        })
        if len(items) >= limit:
            return items
    for href in VIDEOSTREAM_RE.findall(webpage) + VIDEO_HREF_RE.findall(webpage):
        url = _abs(href)
        if url in seen:
            continue
        seen.add(url)
        slug = href.strip("/").split(".")[0]
        items.append({"id": slug, "url": url, "title": slug.replace("-", " "), "thumbnail": "", "duration": "", "views": "", "channel": ""})
        if len(items) >= limit:
            break
    return items


def parse_channel_meta(webpage: str, url: str) -> dict[str, Any]:
    title = ""
    m = re.search(r"<title>(.*?)</title>", webpage, re.I | re.S)
    if m:
        title = _clean(m.group(1)).replace(" — Rumble", "").replace("- Rumble", "").strip()
    handle = url.rstrip("/").split("/")[-1]
    return {"name": title or handle, "handle": handle, "url": url.split("?")[0]}


def listing(kind: str, query: str = "", page: int = 1) -> dict[str, Any]:
    if kind == "search":
        if not query.strip():
            return {"items": [], "title": "Search"}
        url = f"{BASE}/search/video?q={urllib.parse.quote(query)}&page={page}"
        title = f"Search: {query}"
    elif kind == "live":
        url = f"{BASE}/browse/live?page={page}"
        title = "Live"
    elif kind == "channel":
        raw = query.strip()
        if raw.startswith("http"):
            channel_url = raw.split("?")[0]
        elif raw.startswith("/"):
            channel_url = _abs(raw)
        elif raw.startswith("user/"):
            channel_url = f"{BASE}/{raw}"
        else:
            handle = raw.lstrip("@").removeprefix("c/")
            channel_url = f"{BASE}/c/{handle}"
        url = f"{channel_url}?page={page}"
        title = channel_url
    else:
        url = f"{BASE}/videos?page={page}"
        title = "Browse"
    webpage = fetch(url)
    items = parse_listing(webpage)
    meta = parse_channel_meta(webpage, url) if kind == "channel" else {"name": title, "url": url}
    return {"title": meta.get("name") or title, "url": url.split("?")[0], "items": items, "channel": meta}


def _embed_id_from_page(webpage: str) -> str | None:
    m = EMBED_ID_RE.search(webpage)
    if m:
        return m.group(1)
    m = EMBED_URL_RE.search(webpage)
    if m:
        return m.group(1)
    return None


def embed_info(embed_id: str) -> dict[str, Any]:
    qs = urllib.parse.urlencode({"request": "video", "ver": 2, "v": embed_id})
    raw = fetch(f"{EMBED_JS}?{qs}")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ExtractorError("Unexpected embedJS payload")
    return data


def _formats_from_embed(data: dict[str, Any]) -> list[dict[str, Any]]:
    formats: list[dict[str, Any]] = []
    ua = data.get("ua") or {}
    for fmt_type, info in ua.items():
        if fmt_type == "tar":
            continue
        values = info.values() if isinstance(info, dict) else info if isinstance(info, list) else []
        for video_info in values:
            if not isinstance(video_info, dict) or not video_info.get("url"):
                continue
            meta = video_info.get("meta") or {}
            formats.append({"url": video_info["url"], "type": fmt_type, "height": meta.get("h"), "width": meta.get("w"), "bitrate": meta.get("bitrate")})
    formats.sort(key=lambda f: int(f.get("height") or 0), reverse=True)
    return formats


def _ytdlp_resolve(url: str) -> dict[str, Any] | None:
    try:
        import yt_dlp  # type: ignore
    except ImportError:
        return None
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None
    if not info:
        return None
    formats = []
    for fmt in info.get("formats") or []:
        if not fmt.get("url"):
            continue
        formats.append({"url": fmt["url"], "type": fmt.get("ext") or fmt.get("protocol") or "http", "height": fmt.get("height"), "width": fmt.get("width"), "bitrate": fmt.get("tbr")})
    formats.sort(key=lambda f: int(f.get("height") or 0), reverse=True)
    thumbs = info.get("thumbnails") or []
    thumb = (thumbs[-1].get("url") if thumbs else "") or info.get("thumbnail") or ""
    return {
        "id": info.get("id"),
        "watch_url": url,
        "embed_id": info.get("id"),
        "title": info.get("title") or "Untitled",
        "description": info.get("description") or "",
        "thumbnail": thumb,
        "duration": info.get("duration"),
        "channel": info.get("channel") or info.get("uploader") or "",
        "channel_url": info.get("channel_url") or "",
        "formats": formats,
        "best_url": formats[0]["url"] if formats else info.get("url"),
        "live": info.get("live_status") == "is_live",
        "resolver": "yt-dlp",
    }


def resolve_video(url: str, use_ytdlp: bool = True) -> dict[str, Any]:
    url = url.strip()
    if url.startswith("/"):
        url = _abs(url)
    if not url.startswith("http"):
        raise ExtractorError("Need a Rumble URL or /v… path")
    last_error: Exception | None = None
    webpage = ""
    embed_id = None
    try:
        webpage = fetch(url)
        embed_id = _embed_id_from_page(webpage)
    except ExtractorError as exc:
        last_error = exc
    data = None
    if embed_id:
        try:
            data = embed_info(embed_id)
        except ExtractorError as exc:
            last_error = exc
    if data:
        formats = _formats_from_embed(data)
        author = data.get("author") or {}
        desc = ""
        if webpage:
            dm = re.search(r'class="[^"]*media-description[^"]*"[^>]*>(.*?)</div>', webpage, re.I | re.S)
            if dm:
                desc = _clean(re.sub("<[^>]+>", " ", dm.group(1)))
        return {
            "id": embed_id,
            "watch_url": url,
            "embed_id": embed_id,
            "title": _clean(data.get("title")) or "Untitled",
            "description": desc,
            "thumbnail": data.get("i") or "",
            "duration": data.get("duration"),
            "channel": author.get("name") or "",
            "channel_url": author.get("url") or "",
            "formats": formats,
            "best_url": formats[0]["url"] if formats else None,
            "live": data.get("live") == 2,
            "resolver": "embedJS",
        }
    if use_ytdlp:
        fallback = _ytdlp_resolve(url)
        if fallback and fallback.get("best_url"):
            return fallback
    if last_error:
        raise ExtractorError(str(last_error))
    raise ExtractorError("Could not resolve this Rumble video")


def search_channels(query: str) -> list[dict[str, Any]]:
    url = f"{BASE}/search/channel?q={urllib.parse.quote(query)}"
    webpage = fetch(url)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for href in CHANNEL_HREF_RE.findall(webpage):
        full = _abs(href)
        if full in seen:
            continue
        seen.add(full)
        results.append({"name": href.rstrip("/").split("/")[-1], "url": full, "handle": href})
        if len(results) >= 20:
            break
    return results
