// Answers a model's many files from a few bundles, so a first visit is a handful of requests and not hundreds. It holds
// nothing it can't get again: anything not bundled goes to the network. Each visit to a page still asks the site, so the
// sign-in decides who gets a page, as it does without this. build.py writes the manifest below.
const MANIFEST = __MANIFEST__;
const CACHE = `estimate-${MANIFEST.version}`;
const TYPES = {
  css: "text/css", html: "text/html; charset=utf-8", ico: "image/x-icon", js: "text/javascript", json: "application/json",
  mjs: "text/javascript", png: "image/png", svg: "image/svg+xml", ttf: "font/ttf", wasm: "application/wasm",
  webmanifest: "application/manifest+json", woff: "font/woff", woff2: "font/woff2",
};

function headersOf(path) {
  const type = TYPES[path.split(".").pop()] || "application/octet-stream";
  return { ...MANIFEST.headers, "Content-Type": type };
}

/** One spelling for a path, as a page may ask for pub:sha2-256:... with its colons encoded. */
const normal = (path) => path.split("/").map((part) => encodeURIComponent(decodeURIComponent(part))).join("/");

/** A bundle: gzip of a 4-byte length, a JSON index of {path: [offset, size]}, and the files. */
async function unpack(url) {
  const cache = await caches.open(CACHE);
  if (await cache.match(url)) return;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  const bytes = await new Response(response.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
  const length = new DataView(bytes).getUint32(0, true);
  const index = JSON.parse(new TextDecoder().decode(new Uint8Array(bytes, 4, length)));
  const start = 4 + length;
  await Promise.all(Object.entries(index).map(([path, [offset, size]]) =>
    cache.put(normal(path), new Response(bytes.slice(start + offset, start + offset + size), { headers: headersOf(path) }))));
  await cache.put(url, new Response("ok")); // only once every file is in
}

/** Every model's page loads the same runtime files: they are kept once, under /assets/ and /vendor/. */
function stored(pathname) {
  const assets = /^\/[^/]+(\/assets\/.+)$/.exec(pathname);
  return normal(assets ? assets[1] : pathname);
}

/** Asks the site first: signed out, it redirects, and without the role it refuses. Only then the page from the bundle. */
async function page(request, model) {
  const answer = await fetch(request);
  if (answer.status === 403) await caches.delete(CACHE);
  if (answer.type === "opaqueredirect" || !answer.ok) return answer;
  try {
    await unpack(MANIFEST.runtime);
    await unpack(MANIFEST.models[model]);
    const cache = await caches.open(CACHE);
    const body = await (await cache.match(`/${model}/app.html`)).arrayBuffer();
    return new Response(body, { headers: headersOf("app.html") });
  } catch {
    return Response.redirect(`/${model}/app.html`, 302);
  }
}

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(unpack(MANIFEST.runtime));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    await Promise.all((await caches.keys()).filter((name) => name !== CACHE).map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  const model = /^\/([^/]+)\/(index\.html)?$/.exec(url.pathname);
  if (event.request.mode === "navigate") {
    if (model && MANIFEST.models[model[1]]) event.respondWith(page(event.request, model[1]));
    return;
  }
  event.respondWith((async () => (await (await caches.open(CACHE)).match(stored(url.pathname))) || fetch(event.request))());
});
