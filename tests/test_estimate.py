"""The estimate models, the helpers their pages use, and the site build
(): the notebooks run natively, inputs come from a publication
bundle when it has them, links match pub.sustenaut.eu, the wheel is the same
bytes every time, and an exported page loads nothing from another origin."""
import importlib
import importlib.util
import json
import pkgutil
import sys
from pathlib import Path

import numpy as np
import pytest

from estimate import models, site
from estimate.models import example

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS = sorted((ROOT / "notebooks").glob("*.py"))
MODELS = [importlib.import_module(f"estimate.models.{m.name}") for m in pkgutil.iter_modules(models.__path__)]

spec = importlib.util.spec_from_file_location("estimate_build", ROOT / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

CLAIM = "pub:sha2-256:claim"
KIND = "pub:sha2-256:kind"
THREE = "pub:sha2-256:three"


@pytest.mark.parametrize("module", MODELS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_models_follow_the_contract(module):
    assert {"name", "version"} <= module.MODEL.keys()
    assert module.OUTPUTS and all({"name", "unit", "description"} <= o.keys() for o in module.OUTPUTS)
    for p in module.PARAMETERS:
        assert {"name", "unit", "low", "likely", "high", "publet"} <= p.keys()
        assert p["low"] <= p["likely"] <= p["high"]
        assert isinstance(p["publet"], str) and p["publet"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_runs(path):
    spec = importlib.util.spec_from_file_location(f"estimate_nb_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.run()  # raises if any cell fails


def test_example_result_is_fixed_by_the_seed():
    """The number the browser check compares the page against."""
    result = example.quantiles(example.sample(site.generator(), example.PARAMETERS))
    assert result == example.quantiles(example.sample(np.random.default_rng(42), example.PARAMETERS))
    low, mid, high = result
    assert 40 < low < mid < high < 90


def write_bundle(folder: Path, cell) -> Path:
    """A bundle like `pub bundle` writes: an empirical claim measuring a kind
    with a three-point estimate, rows by crop."""
    (folder / "o").mkdir(parents=True)
    (folder / "def").mkdir()
    (folder / "index.json").write_text(json.dumps({"bundle": 1, "names": {"harvest per tray": [KIND]}}))
    claim = {
        "cid": CLAIM,
        "parameters": {THREE: ["low", "likely", "high"]},
        "object": {"body": {"class": "empirical", "data": {
            "columns": [{"name": "crop"}, {"kind": KIND, "measure": THREE, "unit": "g/{tray}"}],
            "rows": [["basil", cell], ["radish", None]],
        }}},
    }
    kind = {"cid": KIND, "object": {"body": {"class": "definitional"}}, "used_by": [{"cid": CLAIM, "how": "kind of"}]}
    (folder / "o" / f"{CLAIM}.json").write_text(json.dumps(claim))
    (folder / "o" / f"{KIND}.json").write_text(json.dumps(kind))
    return folder


def parameter(**kw):
    return {"name": "basil", "unit": "g/{tray}", "low": 1.0, "likely": 2.0, "high": 3.0, "publet": CLAIM, "row": "basil", "status": "placeholder", **kw}


@pytest.mark.parametrize("cell", [[50, 70, 100], {"low": 50, "likely": 70, "high": 100}])
def test_bundle_values_replace_the_models(tmp_path, cell):
    bundle = site.Bundle(write_bundle(tmp_path / "bundle", cell))
    for publet in (CLAIM, "harvest per tray"):
        [p] = site.with_bundle([parameter(publet=publet)], bundle)
        assert (p["low"], p["likely"], p["high"]) == (50, 70, 100)
        assert p["status"] == "from the publication"


def test_model_values_stay_when_the_bundle_has_none(tmp_path):
    bundle = site.Bundle(write_bundle(tmp_path / "bundle", None))
    [p] = site.with_bundle([parameter()], bundle)
    assert (p["low"], p["likely"], p["high"]) == (1.0, 2.0, 3.0)
    assert p["status"] == "placeholder (not measured yet)"
    [p] = site.with_bundle([parameter()], site.Bundle(None))
    assert p["status"] == "placeholder (no publication bundle next to this page)"
    [p] = site.with_bundle([parameter(publet="pub:sha2-256:elsewhere")], bundle)
    assert p["status"] == "placeholder (publet not in the publication)"


def test_bundle_values_in_another_unit_are_not_used(tmp_path):
    bundle = site.Bundle(write_bundle(tmp_path / "bundle", [50, 70, 100]))
    [p] = site.with_bundle([parameter(unit="kg/{tray}")], bundle)
    assert p["low"] == 1.0 and "g/{tray}" in p["status"]


def test_several_rows_need_a_row(tmp_path):
    folder = write_bundle(tmp_path / "bundle", [50, 70, 100])
    claim = json.loads((folder / "o" / f"{CLAIM}.json").read_text())
    claim["object"]["body"]["data"]["rows"][1][1] = [1, 2, 3]
    (folder / "o" / f"{CLAIM}.json").write_text(json.dumps(claim))
    [p] = site.with_bundle([parameter(row=None)], site.Bundle(folder))
    assert p["low"] == 1.0 and "name the row" in p["status"]


def test_the_real_bundle_is_read_when_built(tmp_path):
    """Publication 0 as pub bundle writes it, when a pub with `bundle` is around."""
    import shutil
    import subprocess

    pub = shutil.which("pub")
    if not pub or subprocess.run([pub, "bundle"], capture_output=True, text=True).stderr.startswith("unknown command"):
        pytest.skip("no pub with `bundle` on PATH")
    if not (ROOT / "objects").is_dir():
        pytest.skip("no objects/: ./fetch-publication.sh puts the pinned publication there")
    subprocess.run([pub, "bundle", f"--dir={ROOT / 'objects'}", f"--out={tmp_path}"], check=True, capture_output=True)
    [p] = site.with_bundle(example.PARAMETERS, site.Bundle(tmp_path))
    assert p["status"] == "placeholder (not measured yet)"


def test_links_match_what_pub_site_serves():
    assert site.publet_url("pub:sha2-256:abc") == "https://pub.sustenaut.eu/o/pub:sha2-256:abc/"
    assert site.publet_url("{tray}") == "https://pub.sustenaut.eu/def/%7Btray%7D/"
    assert site.publet_url("harvest per tray") == "https://pub.sustenaut.eu/def/harvest%20per%20tray/"
    table = site.input_table(example.PARAMETERS)
    assert f"(https://pub.sustenaut.eu/o/{example.PARAMETERS[0]['publet']}/)" in table
    assert "| placeholder |" in table


def test_rounding():
    assert site.rounded(62.681313) == 62.7
    assert site.rounded(0.0123456) == 0.0123
    assert site.rounded(123456) == 123000
    assert site.fmt(62.681313) == "62.7"
    assert site.fmt(40.0) == "40.0"
    assert site.fmt(123456) == "123,000"
    assert "3 significant figures" in site.rounding_note()


def test_citation(tmp_path):
    native = site.citation(None)
    assert native["wheel"] is None
    assert native["commit"] == "unknown" or len(native["commit"]) == 40
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "build.json").write_text(json.dumps({"wheel": "estimate-0.1.0-py3-none-any.whl", "sha256": "ab" * 32, "commit": "c" * 40}))
    cite = site.citation(tmp_path)
    assert cite["sha256"] == "ab" * 32
    assert "sha256 `" + "ab" * 32 in site.citation_text(cite)


def test_wheel_is_reproducible_and_installable(tmp_path):
    import zipfile

    one, two = build.wheel(tmp_path / "1"), build.wheel(tmp_path / "2")
    assert one.read_bytes() == two.read_bytes()
    names = zipfile.ZipFile(one).namelist()
    assert "estimate/site.py" in names and "estimate/models/example.py" in names
    assert any(n.endswith(".dist-info/RECORD") for n in names)


def test_vendor_lock_pins_everything():
    pins = json.loads(build.LOCK.read_text())
    assert (pins["marimo"], pins["pyodide"]) == (build.MARIMO_VERSION, build.PYODIDE_VERSION)
    assert set(build.PACKAGES) <= set(pins["packages"])
    for entry in pins["packages"].values():
        assert len(entry["sha256"]) == 64
        assert set(entry["depends"]) <= set(pins["packages"])
    assert set(pins["pyodide_core"]) == set(build.PYODIDE_CORE)
    assert set(pins["npm"]) == set(build.NPM)


def test_marimo_matches_the_pins():
    import marimo

    assert marimo.__version__ == build.MARIMO_VERSION
    lock = (ROOT / "requirements.lock").read_text()
    assert f"marimo=={build.MARIMO_VERSION}" in lock


def test_exported_page_loads_only_from_this_site(tmp_path):
    """The export is pointed at /vendor/ and no CDN address is left in it."""
    pins = json.loads(build.LOCK.read_text())
    build.export(NOTEBOOKS[0], tmp_path / "page", pins)
    page = (tmp_path / "page" / "index.html").read_text()
    assert f'data-pyodide-index-url="../vendor/pyodide/v{build.PYODIDE_VERSION}/"' in page
    assert 'data-pyodide-lockfile-url="../vendor/pyodide/' in page
    for asset in (tmp_path / "page" / "assets").glob("*.js"):
        assert not build.THIRD_PARTY.search(asset.read_text()), asset.name
    assert not (tmp_path / "page" / "CLAUDE.md").exists()
