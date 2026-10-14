import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
async def _():
    # In the browser, install the estimate wheel shipped next to the page;
    # natively, import it from the repository.
    import json
    import sys

    import marimo as mo

    here = mo.notebook_location()
    if sys.platform == "emscripten":
        import micropip
        import numpy  # noqa: F401  from Pyodide's lockfile, so micropip need not look it up
        from pyodide.http import open_url

        build = json.loads(open_url(f"{here}/public/build.json").read())
        await micropip.install(f"{here}/public/{build['wheel']}")
    else:
        _root = str(mo.notebook_dir().parent.parent)
        if _root not in sys.path:
            sys.path.insert(0, _root)
    installed = True
    return here, installed, mo


@app.cell
def _(installed):
    assert installed
    from estimate import site
    from estimate.models import example as model
    return model, site


@app.cell
def _(here, mo, model, site):
    bundle = site.load_bundle(here)
    parameters = site.with_bundle(model.PARAMETERS, bundle)
    mo.md("\n\n".join([
        f"# {model.MODEL['name']}",
        "The smallest model this site serves: one three-point input read as a"
        " triangular distribution, summarised by its quantiles. It tests the"
        " pipeline before the real models arrive.",
        "## Inputs",
        site.input_table(parameters),
    ]))
    return (parameters,)


@app.cell
def _(here, mo, model, parameters, site):
    rng = site.generator()
    draws = model.sample(rng, parameters)
    result = model.quantiles(draws)
    _table = "\n".join(
        [f"| {model.OUTPUTS[0]['name']} | `{model.OUTPUTS[0]['unit']}` |", "|---|--:|"]
        + [f"| {round(q * 100)}th percentile | {site.fmt(v)} |" for q, v in zip(model.QUANTILES, result)]
    )
    mo.md("\n\n".join([
        "## Result",
        _table,
        f"{len(draws):,} draws from a generator seeded with **{site.SEED}**. {site.rounding_note()}",
        site.citation_text(site.citation(here)),
    ]))
    return (result,)


@app.cell
def _(mo, result):
    # The unrounded result, for the browser test to compare with pytest.
    mo.Html(f'<pre id="estimate-result" hidden>{result!r}</pre>')
    return


if __name__ == "__main__":
    app.run()
