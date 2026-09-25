from __future__ import annotations

import argparse
import sys
import time
import webbrowser

from . import __version__
from .server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FreeRumble — local Rumble desktop client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4310)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    httpd = serve(args.host, args.port)
    url = f"http://{args.host}:{args.port}/"
    print(f"FreeRumble {__version__}  →  {url}")
    print("Subscriptions and history stay on this machine.")
    print("Ctrl+C to quit.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\nStopping…")
        httpd.shutdown()
        return 0


if __name__ == "__main__":
    sys.exit(main())
