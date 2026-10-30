# estimate

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
uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python -r requirements.lock
./fetch-publication.sh                                       # without a token, gh downloads the release: it must be able to read business-plan
.venv/bin/python build.py site --out build/estimate-site --pub path/to/pub
.venv/bin/pip install playwright==1.64.0 && .venv/bin/python browser_check.py build/estimate-site   # headless Chromium: same origin only, same numbers as pytest
python3 -m http.server -d build/estimate-site 8000
```

`pub` must be one with `bundle` (publet at the `PUBLET_REV` in the
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

The export needs `uv` (in `requirements.lock`): marimo runs ruff through it
to look for notebook-local imports, fetching ruff the first time.

## Changing marimo or Pyodide

The versions are pinned together: `MARIMO_VERSION` and `PYODIDE_VERSION` in
`build.py`, marimo in `requirements.lock`, and every file in
`vendor-lock.json`. After changing them, run
`.venv/bin/python build.py lock`, which takes marimo's own
Pyodide lockfile for that pair, keeps the packages the pages load and their
dependencies (`PACKAGES`), and records each file's sha256. If a page then
loads something not pinned, `browser_check.py` shows the 404.

## Updating the objects

The objects change in business-plan. Its `publication` workflow releases them as
`publication-0/YYYY-MM-DD.N`; put that tag and the sha256 its release notes give in
`publication.json`, in a pull request here.

## Deploying

`.github/workflows/deploy.yml` fetches the pinned publication, builds the image,
asks it for the index, a page, Pyodide and the inputs, runs `browser_check.py`
against it, and deploys on each merge to main. It needs no secret:
storage.sustenaut.eu takes the job's OpenID Connect token, as its `publications`
tenant names `github:Sustenaut/estimate` as a reader, and Google credentials come
from Workload Identity Federation (this repository is in business-plan's
`var.github_repositories`). The Cloud Run service, its image repository and the
domain mapping are in business-plan's `infra/estimate-site.tf`, and the `estimate`
DNS record is in its `pubkit.json` hosting block.
