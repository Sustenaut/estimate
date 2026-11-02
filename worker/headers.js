// The headers every page carries: headers.json, which browser_check.py sends too. What's in /vendor/ is pinned by
// version in its path, so it is kept for good; Pyodide's loader must be JavaScript and its core WebAssembly.
import policy from "../headers.json" with { type: "json" };

const KEEP = "private, max-age=31536000, immutable";

/** The headers of a served file. */
export function headersFor(pathname) {
  if (pathname.endsWith(".mjs")) return { ...policy, "Content-Type": "text/javascript", "Cache-Control": KEEP };
  if (pathname.startsWith("/vendor/")) {
    return { ...policy, "Cache-Control": KEEP, ...(pathname.endsWith(".wasm") ? { "Content-Type": "application/wasm" } : {}) };
  }
  return policy;
}

/** The gate marks everything at an address, and only a file is for good: a browser must ask again after a failure. */
export function failuresNotKept(response) {
  if (response.status >= 400 && /immutable/.test(response.headers.get("Cache-Control") || "")) {
    response.headers.set("Cache-Control", "no-store");
    response.headers.set("Content-Type", "text/plain; charset=utf-8");
  }
  return response;
}
