"""The estimate models, the helpers their pages use, and the site build: the
suite's own Whens call them through `attempt`, and pubtest's steps
(GRAMMAR.md) check what came back."""
import gzip
import importlib
import importlib.util
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pytest
from pubtest.core import value
from pytest_bdd import given, parsers, scenarios, then, when

from estimate import site
from estimate.models import example

scenarios("../features/estimate.feature")

ROOT = Path(__file__).resolve().parents[2]

spec = importlib.util.spec_from_file_location("estimate_build", ROOT / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

CLAIM = "pub:sha2-256:claim"
KIND = "pub:sha2-256:kind"
THREE = "pub:sha2-256:three"


# --- the models ------------------------------------------------------------------


def _model(name):
    return importlib.import_module(f"estimate.models.{name}")


@when(parsers.parse('I read the description of the model "{name}"'))
def model_description(ctx, name):
    ctx.attempt(lambda: _model(name).MODEL)


@when(parsers.parse('I read the outputs of the model "{name}"'))
def model_outputs(ctx, name):
    ctx.attempt(lambda: _model(name).OUTPUTS)


@when(parsers.parse('I read the parameters of the model "{name}"'))
def model_parameters(ctx, name):
    ctx.attempt(lambda: _model(name).PARAMETERS)


@then(parsers.parse('each item of the result has "{key}"'))
def each_has(ctx, key):
    assert all(key in item for item in ctx.result), ctx.result


@then(parsers.parse('each item of the result has "{low}", "{likely}" and "{high}" in that order'))
def each_in_order(ctx, low, likely, high):
    assert all(item[low] <= item[likely] <= item[high] for item in ctx.result), ctx.result


@then(parsers.parse('each item of the result has "{key}" as text that is not empty'))
def each_text(ctx, key):
    assert all(isinstance(item[key], str) and item[key] for item in ctx.result), ctx.result


@when(parsers.parse('I run the notebook "{path}"'))
def notebook_runs(ctx, path):
    def run():
        notebook = ROOT / path
        loaded = importlib.util.spec_from_file_location(f"estimate_nb_{notebook.stem}", notebook)
        module = importlib.util.module_from_spec(loaded)
        loaded.loader.exec_module(module)
        module.app.run()  # raises if any cell fails

    ctx.attempt(run)


@when("I sample the example model with the site's generator")
def sample_site(ctx):
    ctx.attempt(lambda: example.quantiles(example.sample(site.generator(), example.PARAMETERS)))


@then(parsers.parse("the result is what the example model gives with the seed {seed:d}"))
def seeded(ctx, seed):
    assert ctx.result == example.quantiles(example.sample(np.random.default_rng(seed), example.PARAMETERS))


@then(parsers.parse("the result rises from above {low:d} to below {high:d}"))
def rises(ctx, low, high):
    first, mid, last = ctx.result
    assert low < first < mid < last < high, ctx.result


# --- inputs from a publication bundle ------------------------------------------


def _write_bundle(folder: Path, cell) -> Path:
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


def _parameter(**kw):
    return {"name": "basil", "unit": "g/{tray}", "low": 1.0, "likely": 2.0, "high": 3.0, "publet": CLAIM,
            "row": "basil", "status": "placeholder", **kw}


@given(parsers.parse('a bundle "{path}" whose basil row holds "{cell}"'))
def a_bundle(ctx, path, cell):
    _write_bundle(ctx.directory / path, value(cell))


@given(parsers.parse('the bundle "{path}"\'s radish row holds "{cell}"'))
def radish_row(ctx, path, cell):
    claim_path = ctx.directory / path / "o" / f"{CLAIM}.json"
    claim = json.loads(claim_path.read_text())
    claim["object"]["body"]["data"]["rows"][1][1] = value(cell)
    claim_path.write_text(json.dumps(claim))


@when(parsers.parse('I read the parameter with "{key}" set to "{wanted}" against the bundle "{path}"'))
def parameter_with(ctx, key, wanted, path):
    ctx.attempt(lambda: site.with_bundle([_parameter(**{key: value(wanted)})], site.Bundle(ctx.directory / path))[0])


@when(parsers.parse('I read the parameter against the bundle "{path}"'))
def parameter_plain(ctx, path):
    ctx.attempt(lambda: site.with_bundle([_parameter()], site.Bundle(ctx.directory / path))[0])


@when("I read the parameter against no bundle")
def parameter_no_bundle(ctx):
    ctx.attempt(lambda: site.with_bundle([_parameter()], site.Bundle(None))[0])


@given(parsers.parse('the pinned publication bundled into "{path}" by a pub with `bundle`'))
def real_bundle(ctx, path):
    """Publication 0 as pub bundle writes it, when a pub with `bundle` is around."""
    pub = shutil.which("pub")
    if not pub or subprocess.run([pub, "bundle"], capture_output=True, text=True).stderr.startswith("unknown command"):
        pytest.skip("no pub with `bundle` on PATH")
    if not (ROOT / "objects").is_dir():
        pytest.skip("no objects/: ./fetch-publication.sh puts the pinned publication there")
    subprocess.run([pub, "bundle", f"--dir={ROOT / 'objects'}", f"--out={ctx.directory / path}"], check=True,
                   capture_output=True)


@when(parsers.parse('I read the example model\'s parameters against the bundle "{path}"'))
def example_with_bundle(ctx, path):
    ctx.attempt(lambda: site.with_bundle(example.PARAMETERS, site.Bundle(ctx.directory / path)))


# --- what a page shows -------------------------------------------------------------


@when(parsers.parse('I ask for the link to "{publet}"'))
def link_to(ctx, publet):
    ctx.attempt(lambda: site.publet_url(publet))


@when("I make the input table of the example model")
def input_table(ctx):
    ctx.attempt(lambda: site.input_table(example.PARAMETERS))


@when(parsers.parse("I round {number}"))
def round_number(ctx, number):
    ctx.attempt(lambda: site.rounded(value(number)))


@when(parsers.parse("I format {number}"))
def format_number(ctx, number):
    ctx.attempt(lambda: site.fmt(value(number)))


@when("I ask for the rounding note")
def rounding_note(ctx):
    ctx.attempt(site.rounding_note)


@when("I cite a native run")
def cite_native(ctx):
    ctx.attempt(lambda: site.citation(None))


@then(parsers.parse('the result\'s "{key}" is "unknown" or a 40-character hash'))
def commit_or_unknown(ctx, key):
    got = ctx.result[key]
    assert got == "unknown" or len(got) == 40, got


@when(parsers.parse('I cite the build in "{path}"'))
def cite_build(ctx, path):
    ctx.attempt(lambda: site.citation(ctx.directory / path))


@when(parsers.parse('I write the citation of the build in "{path}"'))
def citation_text(ctx, path):
    ctx.attempt(lambda: site.citation_text(site.citation(ctx.directory / path)))


# --- the build ------------------------------------------------------------------


@when(parsers.parse('I build the wheel into "{path}"'))
def build_wheel(ctx, path):
    ctx.attempt(lambda: build.wheel(ctx.directory / path))


@then(parsers.parse('the files "{one}" and "{two}" are the same bytes'))
def same_bytes(ctx, one, two):
    assert (ctx.directory / one).read_bytes() == (ctx.directory / two).read_bytes()


@when(parsers.parse('I list what the wheel built into "{path}" holds'))
def wheel_names(ctx, path):
    ctx.attempt(lambda: zipfile.ZipFile(build.wheel(ctx.directory / path)).namelist())


@when("I read the vendor lock")
def vendor_lock(ctx):
    ctx.attempt(lambda: json.loads(build.LOCK.read_text()))


@then("it pins the marimo and Pyodide versions build.py names")
def pins_versions(ctx):
    assert (ctx.result["marimo"], ctx.result["pyodide"]) == (build.MARIMO_VERSION, build.PYODIDE_VERSION)


@then("it pins every package build.py names, each by sha256, with what it depends on")
def pins_packages(ctx):
    pins = ctx.result
    assert set(build.PACKAGES) <= set(pins["packages"])
    for entry in pins["packages"].values():
        assert len(entry["sha256"]) == 64
        assert set(entry["depends"]) <= set(pins["packages"])


@then("it pins Pyodide's core files and the npm packages build.py names")
def pins_core(ctx):
    assert set(ctx.result["pyodide_core"]) == set(build.PYODIDE_CORE)
    assert set(ctx.result["npm"]) == set(build.NPM)


@when("I ask marimo for its version")
def marimo_version(ctx):
    import marimo

    ctx.attempt(lambda: marimo.__version__)


@then("the result is the marimo version build.py names")
def marimo_pinned(ctx):
    assert ctx.result == build.MARIMO_VERSION, ctx.result


@then("requirements.lock pins marimo at the version build.py names")
def marimo_locked():
    assert f"marimo=={build.MARIMO_VERSION}" in (ROOT / "requirements.lock").read_text()


@when(parsers.parse('I pack "{one}" as "{one_at}" and "{two}" as "{two_at}"'))
def pack(ctx, one, one_at, two, two_at):
    ctx.packed = {one_at: ctx.directory / one, two_at: ctx.directory / two}
    ctx.attempt(lambda: build.pack(ctx.packed))


@then("the packed bundle holds each file where its index says")
def packed_where_indexed(ctx):
    packed = gzip.decompress(ctx.result)
    length = int.from_bytes(packed[:4], "little")
    index = json.loads(packed[4:4 + length])
    start = 4 + length
    for path, source in ctx.packed.items():
        offset, size = index[path]
        assert packed[start + offset:start + offset + size] == source.read_bytes()


@then("packing them again gives the same bytes")
def packed_again(ctx):
    assert build.pack(ctx.packed) == ctx.result  # the same bytes, so the same hash in its name


@when(parsers.parse('I export "{notebook}" into "{path}"'))
def export(ctx, notebook, path):
    pins = json.loads(build.LOCK.read_text())
    ctx.attempt(lambda: build.export(ROOT / notebook, ctx.directory / path, pins))


@then(parsers.parse('"{path}" points Pyodide at the version build.py vendors'))
def points_at_pyodide(ctx, path):
    page = (ctx.directory / path).read_text()
    assert f'data-pyodide-index-url="../vendor/pyodide/v{build.PYODIDE_VERSION}/"' in page


@then(parsers.parse('no script in "{path}" loads from a third party'))
def no_third_party(ctx, path):
    for asset in (ctx.directory / path).glob("*.js"):
        assert not build.THIRD_PARTY.search(asset.read_text()), asset.name
