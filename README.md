# FreeRumble

A local-first Rumble desktop client for Linux (also works anywhere Python 3.10+ is available).

This is **not** a code fork of [FreeTube](https://github.com/FreeTubeApp/FreeTube). FreeTube’s extractors, IDs, Invidious layer, and UI bindings are YouTube-specific. Replacing that stack with Rumble would mean rewriting most of the app anyway. FreeRumble keeps the *idea* — a dedicated desktop client, local subscriptions, no official platform account — and talks to Rumble directly.

License: **AGPL-3.0-or-later**, same family as FreeTube.

## Why this exists

There is no mature “FreeTube, but only for Rumble.” Grayjay can do Rumble as one plugin among many, and it is source-available rather than OSI-open. FreeRumble is meant to open a Rumble video, browse, search, and subscribe without a developer API key.

## Features (v0.1)

- Browse Rumble’s public video listing and live page
- Search videos and channels
- Open any `rumble.com` watch URL
- HTML5 playback from Rumble’s embedJS streams (HLS via hls.js)
- Optional **yt-dlp** fallback when a page is awkward or Cloudflare-grumpy
- Local subscriptions and watch history (`~/.local/share/freerumble`)
- No Rumble login, no telemetry from this app

## Install (Linux)

```bash
git clone https://github.com/JMHBM/FreeRumble.git
cd FreeRumble
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -U yt-dlp   # recommended
python3 -m freerumble
```

The UI opens at [http://127.0.0.1:4310/](http://127.0.0.1:4310/).

```
python3 -m freerumble --no-browser --port 4310
```

## How it talks to Rumble

Rumble does not ship a public consumer watch API. FreeRumble uses the same unofficial surfaces [yt-dlp](https://github.com/yt-dlp/yt-dlp) already documents:

1. Public HTML listings (`/videos`, `/search/video`, `/c/…`, `/browse/live`)
2. Watch-page embed id (`Rumble("play", { video: "…" })`)
3. `https://rumble.com/embedJS/u3/?request=video&ver=2&v=ID`

Site HTML changes will break parsers. That is the same deal every unofficial client lives with.

Cloudflare sometimes challenges datacenter IPs. A normal home Linux box usually works. If browse fails but yt-dlp works in a terminal, enable the yt-dlp fallback in Settings and paste a video URL.

## What v0.1 does not do yet

- Electron/Flatpak packaged binary
- Import/export subscription files
- Comments, playlists, or Rumble login
- Background download manager

Those are the next useful FreeTube-parity items if anyone wants to help.

## Legal / ToS

This client only reads public pages and the public embedJS endpoint. It does not use a partner API key. Using it may or may not align with Rumble’s terms; that is your call. Do not use it to scrape at abusive volume.

## Credits

- UX idea: [FreeTube](https://github.com/FreeTubeApp/FreeTube)
- Stream discovery pattern: [yt-dlp Rumble extractors](https://github.com/yt-dlp/yt-dlp)
