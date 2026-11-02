#!/usr/bin/env python3
"""Open each estimate page in headless Chromium and check two things:

1. the browser asks only the site's own origin for anything (every request,
   from the page and from marimo's worker, is logged; one elsewhere fails),
   and gets every file it asks for;
2. the result the page computes in Pyodide equals the native one, to the
   last digit.

    python browser_check.py build/estimate-site      # serves it
    python browser_check.py --url http://localhost:8080

Serving a folder, it sends the same headers as the site (headers.json),
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
# What a first visit takes with the bundles: the loader, the service worker, two bundles, the page again, and an icon.
MOST_REQUESTS = 8


def site_headers() -> dict[str, str]:
    return json.loads((HERE / "headers.json").read_text())


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".mjs": "text/javascript", ".wasm": "application/wasm"}

    def end_headers(self):
        for name, value in site_headers().items():
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


def visit(browser, base: str, origin: str, model: str, workers: str) -> dict:
    """Opens a model's page once in a new browser profile, with the service worker or without it."""
    context = browser.new_context(service_workers=workers)
    requests, elsewhere, violations, missing, network = Counter(), [], [], [], []

    def on_request(request):
        where = "{0.scheme}://{0.netloc}".format(urlsplit(request.url))
        if request.url.startswith(("data:", "blob:")):
            return
        requests[where] += 1
        if where != origin:
            elsewhere.append(request.url)

    def on_response(response):
        if response.status >= 400:
            missing.append(f"{response.status} {response.url}")
        if not response.from_service_worker and not response.url.startswith(("data:", "blob:")):
            network.append(urlsplit(response.url).path)

    # Requests are only watched: routing them through Playwright stalls
    # Pyodide's synchronous loads in marimo's worker.
    context.on("request", on_request)
    context.on("response", on_response)
    page = context.new_page()
    page.on("console", lambda m: violations.append(m.text) if "Content Security Policy" in m.text else None)
    page.goto(f"{base}/{model}/")
    node = page.wait_for_selector("#estimate-result", state="attached", timeout=TIMEOUT_MS)
    in_browser = ast.literal_eval(node.text_content())
    here = native(model)
    context.close()
    return {
        "model": model,
        "service_worker": workers,
        "requests": dict(requests),
        "network_requests": len(network),
        "elsewhere": elsewhere,
        "csp_violations": violations,
        "failed_responses": missing,
        "browser": in_browser,
        "native": here,
        "equal": here is None or in_browser == here,
        "network": network,
    }


def write_lock(base: str, origin: str, models: list[str]) -> None:
    """Records what a model's page loads, without the bundles, as the runtime's bundle to be."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        seen = visit(browser, base, origin, models[0], "block")["network"]
        browser.close()
    prefix = f"/{models[0]}/assets/"
    names = sorted({path[1:] if path.startswith("/vendor/") else path[len(f"/{models[0]}/"):]
                    for path in seen if path.startswith(("/vendor/", prefix))})
    pins = json.loads((HERE / "vendor-lock.json").read_text())
    (HERE / "bundle" / "runtime-lock.json").write_text(json.dumps({"marimo": pins["marimo"], "pyodide": pins["pyodide"], "runtime": names}, indent=1) + "\n")
    print(f"bundle/runtime-lock.json: {len(names)} files. Build again.")


def check(base: str, models: list[str]) -> bool:
    from playwright.sync_api import sync_playwright

    origin = "{0.scheme}://{0.netloc}".format(urlsplit(base))
    ok = True
    with sync_playwright() as p:
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM")
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        for model in models:
            # With the bundles, and in a browser where a service worker can't run.
            for workers in ("allow", "block"):
                result = visit(browser, base, origin, model, workers)
                network = result.pop("network")
                print(json.dumps(result, indent=1))
                ok &= not result["elsewhere"] and not result["csp_violations"] and not result["failed_responses"] and result["equal"]
                if workers == "allow" and len(network) > MOST_REQUESTS:
                    print(f"{len(network)} requests, more than {MOST_REQUESTS}: not in a bundle? {network}")
                    ok = False
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
    parser.add_argument("--write-lock", action="store_true", help="record what a page loads in bundle/runtime-lock.json")
    args = parser.parse_args()
    models = args.model or sorted(p.stem for p in (HERE / "notebooks").glob("*.py"))
    base = (args.url or serve(args.folder)).rstrip("/")
    if args.write_lock:
        write_lock(base, "{0.scheme}://{0.netloc}".format(urlsplit(base)), models)
        return
    ok = check(base, models)
    print("browser check passed" if ok else "browser check FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
