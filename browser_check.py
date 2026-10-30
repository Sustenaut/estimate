#!/usr/bin/env python3
"""Open each estimate page in headless Chromium and check two things:

1. the browser asks only the site's own origin for anything (every request,
   from the page and from marimo's worker, is logged; one elsewhere fails),
   and gets every file it asks for;
2. the result the page computes in Pyodide equals the native one, to the
   last digit.

    python browser_check.py build/estimate-site      # serves it
    python browser_check.py --url http://localhost:8080

Serving a folder, it sends the same headers as nginx (headers.conf),
Content-Security-Policy included. Needs `pip install playwright` and a
Chromium: Playwright's own, or the one in PLAYWRIGHT_CHROMIUM.
"""
from __future__ import annotations

import argparse
import ast
import functools
import http.server
import importlib
import json
import os
import re
import sys
import threading
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE
TIMEOUT_MS = 180_000


def nginx_headers() -> dict[str, str]:
    text = (HERE / "headers.conf").read_text()
    return {name: value.strip('"') for name, value in re.findall(r'^add_header (\S+) (".*?"|\S+) always;', text, re.M)}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".mjs": "text/javascript", ".wasm": "application/wasm"}

    def end_headers(self):
        for name, value in nginx_headers().items():
            self.send_header(name, value)
        super().end_headers()

    def log_message(self, *args):
        pass


def serve(folder: Path) -> str:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(folder)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}"


def native(model: str) -> list[float] | None:
    """The model's result computed here, as the page computes it."""
    sys.path.insert(0, str(ROOT))
    from estimate import site

    module = importlib.import_module(f"estimate.models.{model}")
    if not hasattr(module, "quantiles"):
        return None
    return module.quantiles(module.sample(site.generator(), module.PARAMETERS))


def check(base: str, models: list[str]) -> bool:
    from playwright.sync_api import sync_playwright

    origin = "{0.scheme}://{0.netloc}".format(urlsplit(base))
    ok = True
    with sync_playwright() as p:
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        for model in models:
            context = browser.new_context(service_workers="block")
            requests, elsewhere, violations, missing = Counter(), [], [], []

            def on_request(request):
                where = "{0.scheme}://{0.netloc}".format(urlsplit(request.url))
                if request.url.startswith(("data:", "blob:")):
                    return
                requests[where] += 1
                if where != origin:
                    elsewhere.append(request.url)

            # Requests are only watched: routing them through Playwright stalls
            # Pyodide's synchronous loads in marimo's worker.
            context.on("request", on_request)
            context.on("response", lambda r: missing.append(f"{r.status} {r.url}") if r.status >= 400 else None)
            page = context.new_page()
            page.on("console", lambda m: violations.append(m.text) if "Content Security Policy" in m.text else None)
            page.goto(f"{base}/{model}/")
            node = page.wait_for_selector("#estimate-result", state="attached", timeout=TIMEOUT_MS)
            in_browser = ast.literal_eval(node.text_content())
            here = native(model)
            same = here is None or in_browser == here
            print(json.dumps({
                "model": model,
                "requests": dict(requests),
                "elsewhere": elsewhere,
                "csp_violations": violations,
                "failed_responses": missing,
                "browser": in_browser,
                "native": here,
                "equal": same,
            }, indent=1))
            ok &= not elsewhere and not violations and not missing and same
            context.close()
        index = browser.new_page()
        index.goto(f"{base}/")
        ok &= all(index.locator(f'a[href="{m}/"]').count() == 1 for m in models)
        browser.close()
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", nargs="?", type=Path, default=ROOT / "build" / "estimate-site")
    parser.add_argument("--url", help="check a running site instead of serving the folder")
    parser.add_argument("--model", action="append", help="only these models (default: every page in the folder)")
    args = parser.parse_args()
    models = args.model or sorted(p.stem for p in (HERE / "notebooks").glob("*.py"))
    base = (args.url or serve(args.folder)).rstrip("/")
    ok = check(base, models)
    print("browser check passed" if ok else "browser check FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
