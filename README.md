# estimate-site

The models in `estimate/` as pages at
[estimate.sustenaut.eu](https://estimate.sustenaut.eu), behind the same
Google login (IAP) as pub.sustenaut.eu. Team only until the shared wallet
sign-in exists; later, expert panels keyed to PDC concept codes get in.

Each page is a marimo notebook from `notebooks/`, exported to WebAssembly.
It runs its model in the reader's browser with Pyodide, so the server only
serves files. Every file a page loads comes from this site: Pyodide, the
Python wheels (marimo's runtime, micropip, numpy, ...), MathJax and the
icons are in `/vendor/`, and the Content-Security-Policy (`headers.conf`)
stops the browser from fetching anything elsewhere.

## A model and its page

A model is a module in `estimate/models/` (standard library and numpy only)
with:

- `PARAMETERS`: a dict per input: `name`, `unit` (UCUM), `low`, `likely`,
  `high`, `publet` (an object identifier as `pub bundle` prints it, or a
  definition name such as `{tray}`), and optionally `row` (which data row of
  the publet, when it has several), `source` and `status`;
- `OUTPUTS`: a dict per result: `name`, `unit`, `description`;
- `MODEL`: `name` and `version`;
- samplers that take a `numpy.random.Generator`.

Its page is `notebooks/<model>.py`, named like the module. `estimate/site.py`
does the rest: it reads publication 0's bundle next to the page and takes
low, likely and high from it wherever the publication has them in the same
unit (`with_bundle`); shows the inputs with their status, each linked to its
page on pub.sustenaut.eu (`/o/<CID>/` or `/def/<name>/`); gives the seeded
generator (seed 42, shown on the page); rounds results to 3 significant
figures and says so; and cites the code: the wheel's sha256 and the git
commit. `notebooks/example.py` is the smallest such page.

## Building it

```sh
make estimate PUB=path/to/pub    # into build/estimate-site/
make estimate-check              # headless Chromium: same origin only, same numbers as pytest
python3 -m http.server -d build/estimate-site 8000
```

`PUB` must be a `pub` with `bundle` (publet at the `PUBLET_REV` in the
Dockerfile). `build.py site`:

1. builds `estimate/` into a wheel, the same bytes for the same source;
2. writes publication 0's reading data with `pub bundle`;
3. fetches Pyodide, the wheels, MathJax and lucide into `/vendor/`, each
   checked against its sha256 in `vendor-lock.json` (cached in `.cache/`);
4. exports each notebook with `marimo export html-wasm --mode run`, copies
   the wheel, the bundle and `build.json` into its `public/`, points the
   page's `<marimo-wasm>` element at our Pyodide and lockfile, and rewrites
   the jsDelivr and unpkg addresses in marimo's scripts to `/vendor/npm/`;
5. writes the index page listing the models.

The export needs `uv` (in requirements.lock): marimo runs ruff through it
to look for notebook-local imports, fetching ruff the first time.

## Changing marimo or Pyodide

The versions are pinned together: `MARIMO_VERSION` and `PYODIDE_VERSION` in
`build.py`, marimo in `requirements.lock`, and every file in
`vendor-lock.json`. After changing them, run
`.venv/bin/python estimate-site/build.py lock`, which takes marimo's own
Pyodide lockfile for that pair, keeps the packages the pages load and their
dependencies (`PACKAGES`), and records each file's sha256. If a page then
loads something not pinned, `make estimate-check` shows the 404.

## Deploying

`.github/workflows/estimate-site.yml` builds the image
(`podman build -f estimate-site/Dockerfile --build-arg GIT_COMMIT=$(git rev-parse HEAD) -t estimate-site .`),
asks it for the index, a page, Pyodide and the inputs, runs
`browser_check.py` against it, and deploys on each merge to main that
touches `estimate/`, `estimate-site/`, publication 0's objects or
`requirements.lock`. The Cloud Run service, its image repository and the
domain mapping are in `infra/estimate-site.tf`; the `estimate` DNS record
is in schryer/schryer-eu-infra (`sustenaut.tf`). First-time setup is in
`help/notebooks.md`.
