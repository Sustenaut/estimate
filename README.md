# estimate

The models in `estimate/` as pages at
[estimate.sustenaut.eu](https://estimate.sustenaut.eu), behind the same
team sign-in as pub.sustenaut.eu. Team only until the shared wallet
sign-in exists; later, expert panels keyed to PDC concept codes get in.

Each page is a marimo notebook from `notebooks/`, exported to WebAssembly.
It runs its model in the reader's browser with Pyodide, so the server only
serves files. Every file a page loads comes from this site: Pyodide, the
Python wheels (marimo's runtime, micropip, numpy, ...), MathJax and the
icons are in `/vendor/`, and the Content-Security-Policy (`headers.json`)
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

`.github/workflows/deploy.yml` fetches the pinned publication, builds, asks the pages for the index, a page, Pyodide and
the inputs under wrangler, runs `browser_check.py` against them, and deploys on each merge to main, to Cloudflare Pages
like pub, with the team sign-in in front as the project's `_worker.js`: every request passes through it. `worker/gate.js`
is a copy of Sustenaut/auth's `edge-gate/gate.js` (its README, "A Worker gate for static sites"): the code flow with the
team realm, an encrypted session cookie, and on each request the access check, so someone who loses the role `estimate`
is refused at their next request. `worker/index.js` says which role, and `worker/headers.js` the headers every file carries.

Fetching the publication needs no secret: storage.sustenaut.eu takes the job's OpenID Connect token, as its `publications`
tenant names `github:Sustenaut/estimate` as a reader.

### Moving estimate.sustenaut.eu here

Merging moves no traffic: the deploy is skipped until the variable is set, and estimate.sustenaut.eu stays on Cloud Run behind IAP,
on its last image, until step 1. It is down between steps 1 and 4, which is fine while nobody else uses it.

Set up, once, a clone of this repository beside `auth`, with the Bitwarden token (`.env` is ignored here):

```sh
gh repo clone Sustenaut/estimate ~/git/estimate
cp ~/git/auth/.env ~/git/estimate/.env
git -C ~/git/auth pull --ff-only origin main
```

1. **The project and the address**, in `~/git/shared-infra`. In its `pubkit.json`, change the `estimate` line under `sites` to
   `"estimate": { "provider": "cloudflare", "kind": "pages", "project": "sustenaut-estimate", "ttl": 300 },`, merge that, pull it, and apply:

   ```sh
   cd ~/git/shared-infra
   ./with-secrets terraform -chdir=infra apply
   ```

   That makes the Pages project, its custom domain and the plain CNAME to `sustenaut-estimate.pages.dev` in both signers, as for pub.
2. **The token**, in `~/git/estimate`: the Pages: Edit token maps uses (`CLOUDFLARE_GITHUB_API_TOKEN`, and `CLOUDFLARE_ACCOUNT_ID`, in Bitwarden). Each answers "for Sustenaut/estimate":

   ```sh
   cd ~/git/estimate
   ./with-secrets bash -c 'printf %s "$CLOUDFLARE_GITHUB_API_TOKEN" | gh secret set CLOUDFLARE_GITHUB_API_TOKEN --repo Sustenaut/estimate'
   ./with-secrets bash -c 'gh variable set CLOUDFLARE_ACCOUNT_ID --repo Sustenaut/estimate --body "$CLOUDFLARE_ACCOUNT_ID"'
   ```
3. **Sign-in and secrets**, in `~/git/estimate`, signed in to Sustenaut's tailnet (`tailscale switch sustenaut-admin.github`). No new DNS approval: sustenaut.eu's client is already approved.

   ```sh
   cd ~/git/estimate
   npm ci --ignore-scripts
   ./with-secrets ./register-client.sh
   ```

   Tick `estimate` for whoever should read it, at <https://auth.sustenaut.eu/realms/team/access>.
4. **The deploy**, from any folder. Then sign in at estimate.sustenaut.eu.

   ```sh
   gh workflow run deploy --repo Sustenaut/estimate
   ```
5. Remove who may open the site through IAP and the domain mapping from Sustenaut/shared-infra's `infra/estimate-site.tf`, and the Cloud Run service, its accounts and its image repository from this repository's `infra/`.

Until then `infra/` still holds that Cloud Run service, and with no more deploys it stays on its last image. Its state is
`gs://sustenaut-tfstate/estimate`: `terraform -chdir=infra init`, then `./with-secrets terraform -chdir=infra plan` and `apply`,
with a `.env` holding `BWS_ACCESS_TOKEN`.

