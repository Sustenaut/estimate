#!/usr/bin/env python3
"""Build estimate.sustenaut.eu: every notebook in notebooks/ as
a marimo WebAssembly page that runs in the visitor's browser, with every file
it loads served from the same origin.

    python build.py site --out build/estimate-site --pub pub
    python build.py lock     # re-pin vendor-lock.json (network)

`site` does, in order:

1. builds estimate/ into a wheel, byte for byte the same for the same source;
2. writes publication 0's reading data with `pub bundle` (or takes --bundle);
3. downloads Pyodide, the Python wheels the pages load (marimo's runtime,
   micropip, msgspec, numpy, ...) and the two files marimo fetches from npm
   (MathJax and the lucide icons), checking each against vendor-lock.json,
   into <out>/vendor/;
4. exports each notebook with `marimo export html-wasm --mode run` into
   <out>/<name>/, puts the wheel, the bundle and build.json in its public/,
   points the page at <out>/vendor/ and rewrites marimo's CDN addresses;
5. writes <out>/index.html listing the models.

The pins (Pyodide and marimo versions, every file's sha256) are in
vendor-lock.json; `lock` regenerates it from marimo's lockfile for the pinned
versions. Standard library only, apart from marimo for the export.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE
LOCK = HERE / "vendor-lock.json"
NOTEBOOKS = HERE / "notebooks"

ESTIMATE_VERSION = "0.1.0"
MARIMO_VERSION = "0.25.0"
PYODIDE_VERSION = "314.0.0"
PYODIDE_CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
PYODIDE_CORE = ["pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip"]
# What marimo's worker loads at start (worker.js, loadPyodideAndPackages), what
# its runtime loads next (docutils, jedi, pygments, pyodide-http), and what the
# models import. A package missing here shows up in browser_check.py.
PACKAGES = [
    "micropip", "msgspec", "marimo-base", "markdown", "pymdown-extensions", "narwhals", "packaging",
    "docutils", "jedi", "pygments", "pyodide-http",
    "numpy",
]
# The two npm files marimo fetches from jsDelivr or unpkg in a read-only page.
NPM = {
    "mathjax-full@3.2.2": {"files": ["es5/tex-mml-svg.min.js"]},
    "lucide-static@0.452.0": {"files": ["tags.json"], "dirs": ["icons/"]},
}
PUB_BASE = "https://pub.sustenaut.eu"
PUB_TITLE = "Publication 0: growing herbs at home in Estonia, or buying them"


# --- Fetching, with every byte checked -----------------------------------------


def fetch(url: str, cache: Path, sha256: str | None = None) -> bytes:
    """url's bytes, from the cache when there; refuses bytes whose sha256
    differs from the pin."""
    name = hashlib.sha256(url.encode()).hexdigest()[:16] + "-" + url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
    path = cache / name
    if path.is_file():
        data = path.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "estimate-site-build/1"})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if sha256 is not None and digest != sha256:
        raise SystemExit(f"{url}: sha256 {digest}, pinned {sha256}")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def npm_tarball(spec: str) -> str:
    name, version = spec.rsplit("@", 1)
    return f"https://registry.npmjs.org/{name}/-/{name.rsplit('/', 1)[-1]}-{version}.tgz"


def lock(cache: Path) -> None:
    """Pin vendor-lock.json: marimo's Pyodide lockfile, cut to the packages the
    pages load and their dependencies, and the sha256 of every other file."""
    marimo_lock = json.loads(
        fetch(f"https://wasm.marimo.app/pyodide-lock.json?v={MARIMO_VERSION}&pyodide=v{PYODIDE_VERSION}", cache)
    )
    packages, todo = {}, list(PACKAGES)
    while todo:
        name = todo.pop()
        if name not in packages:
            packages[name] = marimo_lock["packages"][name]
            todo += packages[name]["depends"]
    core = {f: hashlib.sha256(fetch(PYODIDE_CDN + f, cache)).hexdigest() for f in PYODIDE_CORE}
    npm = {spec: hashlib.sha256(fetch(npm_tarball(spec), cache)).hexdigest() for spec in NPM}
    LOCK.write_text(
        json.dumps(
            {
                "marimo": MARIMO_VERSION,
                "pyodide": PYODIDE_VERSION,
                "pyodide_core": core,
                "npm": npm,
                "info": marimo_lock["info"],
                "packages": dict(sorted(packages.items())),
            },
            indent=1,
        )
        + "\n"
    )
    print(f"pinned {len(packages)} packages, {len(core)} Pyodide files and {len(npm)} npm packages in {LOCK}")


def vendor(out: Path, cache: Path) -> dict:
    """Pyodide, its lockfile and wheels, MathJax and lucide in out/, checked
    against the pins. Returns the pins."""
    pins = json.loads(LOCK.read_text())
    pyodide = out / "pyodide" / f"v{pins['pyodide']}"
    pyodide.mkdir(parents=True, exist_ok=True)
    for name, sha in pins["pyodide_core"].items():
        (pyodide / name).write_bytes(fetch(PYODIDE_CDN + name, cache, sha))
    served = {}
    for name, entry in pins["packages"].items():
        source = entry["file_name"]
        url = source if "://" in source else PYODIDE_CDN + source
        local = source.rsplit("/", 1)[-1]
        (pyodide / local).write_bytes(fetch(url, cache, entry["sha256"]))
        served[name] = {**entry, "file_name": local}
    (pyodide / "pyodide-lock.json").write_text(json.dumps({"info": pins["info"], "packages": served}))
    for spec, sha in pins["npm"].items():
        want = NPM[spec]
        with tarfile.open(fileobj=io.BytesIO(fetch(npm_tarball(spec), cache, sha))) as tar:
            for member in tar.getmembers():
                inner = member.name.split("/", 1)[1]  # tarballs hold package/<path>
                if member.isfile() and (inner in want.get("files", []) or any(inner.startswith(d) for d in want.get("dirs", []))):
                    target = out / "npm" / spec / inner
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tar.extractfile(member).read())
    return pins


# --- The estimate wheel ------------------------------------------------------------


def wheel(out: Path) -> Path:
    """estimate/ as a pure-Python wheel. Entries are sorted and dated
    1980-01-01, so the same source always gives the same bytes and sha256."""
    dist = f"estimate-{ESTIMATE_VERSION}"
    files = {
        str(p.relative_to(ROOT)): p.read_bytes()
        for p in sorted((ROOT / "estimate").rglob("*.py"))
    }
    files[f"{dist}.dist-info/METADATA"] = (
        f"Metadata-Version: 2.1\nName: estimate\nVersion: {ESTIMATE_VERSION}\n"
        "Summary: Sustenaut's estimate models and the helpers their pages use\n"
        "Requires-Python: >=3.10\nRequires-Dist: numpy\n"
    ).encode()
    files[f"{dist}.dist-info/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: build.py\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    record = "".join(
        f"{name},sha256={base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()},{len(data)}\n"
        for name, data in files.items()
    ) + f"{dist}.dist-info/RECORD,,\n"
    files[f"{dist}.dist-info/RECORD"] = record.encode()
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{dist}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as whl:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            whl.writestr(info, data)
    return path


# --- Pages -------------------------------------------------------------------


# marimo's addresses for things the page may load, and where our copies are,
# relative to a model's page (<out>/<model>/index.html).
REWRITES = [
    ("https://cdn.jsdelivr.net/pyodide/", "../vendor/pyodide/"),
    ("https://cdn.jsdelivr.net/npm/", "../vendor/npm/"),
    ("https://unpkg.com/", "../vendor/npm/"),
]
THIRD_PARTY = re.compile(r"https://(cdn\.jsdelivr\.net|unpkg\.com|wasm\.marimo\.app)/")


def export(notebook: Path, out: Path, pins: dict) -> None:
    # marimo looks for notebook-local imports with ruff, run through uv: the
    # one installed next to this Python (requirements.lock) unless UV says.
    uv = shutil.which("uv", path=str(Path(sys.executable).parent)) or shutil.which("uv")
    subprocess.run(
        [sys.executable, "-m", "marimo", "export", "html-wasm", str(notebook), "-o", str(out), "--mode", "run", "--no-show-code"],
        check=True,
        stdout=subprocess.DEVNULL,
        env={**({"UV": uv} if uv else {}), **os.environ},
    )
    (out / "CLAUDE.md").unlink(missing_ok=True)  # an editing aid marimo adds, not part of the page
    page = out / "index.html"
    text = page.read_text()
    pyodide = f"../vendor/pyodide/v{pins['pyodide']}/"
    tag = (
        f'<marimo-wasm hidden="" data-pyodide-index-url="{pyodide}" '
        f'data-pyodide-lockfile-url="{pyodide}pyodide-lock.json" '
        f'data-pypi-index-url="../vendor/pypi/{{package_name}}/json"></marimo-wasm>'
    )
    if text.count('<marimo-wasm hidden=""></marimo-wasm>') != 1:
        raise SystemExit(f"{page}: no <marimo-wasm> element to point at our Pyodide; has marimo's export changed?")
    page.write_text(text.replace('<marimo-wasm hidden=""></marimo-wasm>', tag))
    for asset in (out / "assets").glob("*.js"):
        js = asset.read_text()
        patched = re.sub(
            r"https://wasm\.marimo\.app/pyodide-lock\.json\?v=\$\{e\.version\}&pyodide=\$\{e\.pyodideVersion\}",
            f"{pyodide}pyodide-lock.json",
            js,
        )
        for old, new in REWRITES:
            patched = patched.replace(old, new)
        if THIRD_PARTY.search(patched):
            raise SystemExit(f"{asset}: still loads {THIRD_PARTY.search(patched).group(0)}")
        if patched != js:
            asset.write_text(patched)


def model_info(stem: str) -> dict:
    sys.path.insert(0, str(ROOT))
    try:
        module = importlib.import_module(f"estimate.models.{stem}")
    except ModuleNotFoundError:
        return {"name": stem, "version": "", "summary": ""}
    summary = (module.__doc__ or "").strip().split("\n\n")[0].replace("\n", " ")
    return {**module.MODEL, "summary": summary}


INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sustenaut estimates</title>
<style>
:root {{ color-scheme: light dark; --ink: #1d2a24; --muted: #5d6b64; --rule: #d6ddd9; --bg: #fbfcfb; --link: #23704f; }}
@media (prefers-color-scheme: dark) {{ :root {{ --ink: #e6ece9; --muted: #a3b1aa; --rule: #34413b; --bg: #141a17; --link: #7fd1a7; }} }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 system-ui, sans-serif; }}
main {{ max-width: 46rem; margin: 0 auto; padding: 2rem 1rem; }}
a {{ color: var(--link); }}
li {{ border-bottom: 1px solid var(--rule); padding: .75rem 0; list-style: none; }}
ul {{ padding: 0; }}
small, footer {{ color: var(--muted); }}
</style>
</head>
<body>
<main>
<h1>Sustenaut estimates</h1>
<p>Models behind the publications on <a href="{pub}">{pub_host}</a>. Each page runs its model in your browser with
Python (Pyodide), from inputs taken from the publication where it has them; every file it loads comes from this site.</p>
<ul>
{items}
</ul>
<footer><p>Built from commit <code>{commit}</code> with marimo {marimo} and Pyodide {pyodide}.</p></footer>
</main>
</body>
</html>
"""


def site(out: Path, cache: Path, pub: str | None, bundle: Path | None, commit: str) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    import marimo

    if marimo.__version__ != MARIMO_VERSION:
        raise SystemExit(f"marimo {marimo.__version__} is installed; the pins are for {MARIMO_VERSION}")
    pins = json.loads(LOCK.read_text())
    if (pins["marimo"], pins["pyodide"]) != (MARIMO_VERSION, PYODIDE_VERSION):
        raise SystemExit("vendor-lock.json is for other versions: run `build.py lock`")
    work = out.parent / f".{out.name}-work"
    shutil.rmtree(work, ignore_errors=True)
    whl = wheel(work)
    if bundle is None:
        bundle = work / "bundle"
        subprocess.run(
            [pub or "pub", "bundle", f"--dir={ROOT / 'objects'}", f"--out={bundle}", f"--base={PUB_BASE}", f"--title={PUB_TITLE}"],
            check=True,
        )
    vendor(out / "vendor", cache)
    build = {
        "wheel": whl.name,
        "sha256": hashlib.sha256(whl.read_bytes()).hexdigest(),
        "commit": commit,
        "marimo": MARIMO_VERSION,
        "pyodide": PYODIDE_VERSION,
    }
    items = []
    for notebook in sorted(NOTEBOOKS.glob("*.py")):
        page = out / notebook.stem
        export(notebook, page, pins)
        public = page / "public"
        public.mkdir(exist_ok=True)
        shutil.copy2(whl, public / whl.name)
        shutil.copytree(bundle, public / "bundle")
        (public / "build.json").write_text(json.dumps(build, indent=1) + "\n")
        info = model_info(notebook.stem)
        items.append(
            f'<li><a href="{notebook.stem}/"><strong>{html.escape(info["name"])}</strong></a>'
            f' <small>{html.escape(info["version"])}</small><br>{html.escape(info["summary"])}</li>'
        )
    (out / "index.html").write_text(
        INDEX.format(
            pub=PUB_BASE, pub_host=PUB_BASE.split("//")[1], items="\n".join(items),
            commit=html.escape(commit[:12]), marimo=MARIMO_VERSION, pyodide=PYODIDE_VERSION,
        )
    )
    (out / "build.json").write_text(json.dumps(build, indent=1) + "\n")
    shutil.rmtree(work)
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"{out}: {len(items)} model page(s), {size / 1e6:.1f} MB; wheel {whl.name} sha256 {build['sha256']}")


def git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("site", help="build the site")
    s.add_argument("--out", type=Path, default=ROOT / "build" / "estimate-site")
    s.add_argument("--pub", help="the pub binary that writes the bundle (default: pub on PATH)")
    s.add_argument("--bundle", type=Path, help="an existing `pub bundle` output, instead of running pub")
    s.add_argument("--commit", default=None, help="the git commit to cite (default: HEAD)")
    l = sub.add_parser("lock", help="re-pin vendor-lock.json")
    w = sub.add_parser("wheel", help="build only the wheel")
    w.add_argument("--out", type=Path, default=ROOT / "build")
    for p in (s, l):
        p.add_argument("--cache", type=Path, default=ROOT / ".cache" / "estimate-site")
    args = parser.parse_args()
    if args.command == "lock":
        lock(args.cache)
    elif args.command == "wheel":
        print(wheel(args.out))
    else:
        site(args.out.resolve(), args.cache, args.pub, args.bundle, args.commit or git_commit())


if __name__ == "__main__":
    main()
