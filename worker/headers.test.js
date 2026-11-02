import assert from "node:assert/strict";
import { test } from "node:test";
import { failuresNotKept, headersFor } from "./headers.js";

test("every file holds the browser to this origin", () => {
  for (const path of ["/", "/example/", "/vendor/pyodide/v314.0.0/pyodide.asm.wasm", "/example/assets/x.mjs"]) {
    const csp = headersFor(path)["Content-Security-Policy"];
    assert.match(csp, /connect-src 'self'/);
    assert.match(csp, /'wasm-unsafe-eval'/);
    assert.equal(headersFor(path)["X-Content-Type-Options"], "nosniff");
  }
});

test("Pyodide's loader is JavaScript and its core WebAssembly, and what's pinned is kept, by this browser only", () => {
  assert.equal(headersFor("/vendor/pyodide/v314.0.0/pyodide.asm.mjs")["Content-Type"], "text/javascript");
  assert.equal(headersFor("/vendor/pyodide/v314.0.0/pyodide.asm.wasm")["Content-Type"], "application/wasm");
  assert.match(headersFor("/vendor/pyodide/v314.0.0/numpy.whl")["Cache-Control"], /^private, .*immutable/);
  assert.equal(headersFor("/example/")["Cache-Control"], undefined);
  assert.equal(headersFor("/example/")["Content-Type"], undefined);
});

test("a failure at a pinned address isn't kept, and the rest stand as they are", () => {
  const marked = (status) => new Response("x", { status, headers: headersFor("/vendor/nothing.whl") });
  assert.equal(failuresNotKept(marked(404)).headers.get("Cache-Control"), "no-store");
  assert.match(failuresNotKept(marked(200)).headers.get("Cache-Control"), /immutable/);
  const refused = new Response("x", { status: 403, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
  assert.equal(failuresNotKept(refused).headers.get("Content-Type"), "text/html; charset=utf-8");
});
