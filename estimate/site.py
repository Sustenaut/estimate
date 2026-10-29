"""What every estimate notebook needs around its model: the inputs from the
publication bundle, the input table linking each input to its publet, a
seeded random generator, stated rounding, and a citation of the code.

The notebooks run natively (marimo edit, pytest) and in the browser (Pyodide,
estimate.sustenaut.eu). In the browser a notebook's files are URLs next to
the page: `public/bundle/` (publication 0's `pub bundle` output) and
`public/build.json` (the wheel's name, its sha256 and the git commit). Natively
they are usually absent, and the parameters stay as the model states them.

Standard library and numpy only.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import numpy as np

SEED = 42
SIGNIFICANT_FIGURES = 3
PUB_SITE = "https://pub.sustenaut.eu"
# The measure whose parameters are the three points a model input carries.
THREE_POINTS = ("low", "likely", "high")


def in_browser() -> bool:
    return sys.platform == "emscripten"


def _read_text(location) -> str | None:
    """The text at a local path or (in the browser) a URL; None if missing."""
    where = str(location)
    if "://" in where:
        from pyodide.http import open_url  # only there in the browser

        try:
            return open_url(where).read()
        except OSError:
            return None
    path = Path(where)
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _join(location, *parts: str):
    where = str(location).rstrip("/")
    if "://" in where:
        return "/".join([where, *(quote(p, safe="") for p in parts)])
    return Path(where, *parts)


# --- The publication bundle --------------------------------------------------


class Bundle:
    """Publication 0 as `pub bundle` writes it: index.json, def/<name>.json
    and o/<cid>.json under one folder (or URL). Files are read when asked for."""

    def __init__(self, location=None):
        self.location = location
        self._cache: dict[tuple[str, ...], dict | None] = {}
        self.index = self._json("index.json") if location is not None else None

    def __bool__(self) -> bool:
        return self.index is not None

    def _json(self, *parts: str) -> dict | None:
        if parts not in self._cache:
            text = _read_text(_join(self.location, *parts))
            self._cache[parts] = json.loads(text) if text is not None else None
        return self._cache[parts]

    def object(self, cid: str) -> dict | None:
        return self._json("o", f"{cid}.json") if self else None

    def definitions(self, name: str) -> list[str]:
        """The identifiers of the objects that define a name."""
        return list((self.index or {}).get("names", {}).get(name, []))

    def three_points(self, publet: str, row: str | None = None) -> tuple[dict | None, str]:
        """low, likely and high for a publet from the bundle, and why or why not.

        The publet is an empirical claim's identifier, or the name of the
        quantity kind it measures. The value is the one data cell whose
        measure has the parameters low, likely and high, in the row whose
        first column is `row` (needed when the claim has several rows)."""
        if not self:
            return None, "no publication bundle next to this page"
        claims = self._claims_for(publet)
        if not claims:
            return None, "publet not in the publication"
        found = []
        for claim in claims:
            body = claim["object"]["body"]
            parameters = claim.get("parameters", {})
            columns = (body.get("data") or {}).get("columns", [])
            for i, column in enumerate(columns):
                if tuple(parameters.get(column.get("measure"), ())) != THREE_POINTS:
                    continue
                for cells in body["data"].get("rows", []):
                    if row is not None and (not cells or cells[0] != row):
                        continue
                    value = _three(cells[i])
                    if value is not None:
                        found.append({**value, "unit": column.get("unit")})
        if not found:
            return None, "not measured yet"
        if len(found) > 1:
            return None, f"{len(found)} values in the publication; name the row"
        return found[0], "from the publication"

    def _claims_for(self, publet: str) -> list[dict]:
        if publet.startswith("pub:"):
            claim = self.object(publet)
            return [claim] if claim else []
        claims = []
        for kind in self.definitions(publet):
            definition = self.object(kind) or {}
            for use in definition.get("used_by", []):
                claim = self.object(use["cid"])
                if claim and claim["object"]["body"].get("class") == "empirical":
                    claims.append(claim)
        return claims


def _three(cell) -> dict | None:
    if isinstance(cell, dict) and all(isinstance(cell.get(k), (int, float)) for k in THREE_POINTS):
        return {k: float(cell[k]) for k in THREE_POINTS}
    if isinstance(cell, (list, tuple)) and len(cell) == 3 and all(isinstance(v, (int, float)) for v in cell):
        return dict(zip(THREE_POINTS, map(float, cell)))
    return None


def load_bundle(notebook_location) -> Bundle:
    """The bundle shipped next to the page, in public/bundle/."""
    if notebook_location is None:
        return Bundle(None)
    return Bundle(_join(notebook_location, "public", "bundle"))


def with_bundle(parameters: list[dict], bundle: Bundle) -> list[dict]:
    """A copy of a model's PARAMETERS with low, likely and high taken from the
    bundle wherever it has them in the same unit. Each parameter's status says
    which values were used: the bundle's ("from the publication") or the
    model's own, with the reason."""
    out = []
    for parameter in parameters:
        p = copy.deepcopy(parameter)
        value, why = bundle.three_points(p["publet"], p.get("row"))
        if value is not None and value["unit"] != p["unit"]:
            value, why = None, f"publication states {value['unit']}, model needs {p['unit']}"
        if value is not None:
            p.update({k: value[k] for k in THREE_POINTS}, status="from the publication", source=publet_url(p["publet"]))
        else:
            p["status"] = f"{p.get('status', 'model value')} ({why})"
        out.append(p)
    return out


# --- Links to pub.sustenaut.eu ------------------------------------------------


def publet_url(publet: str) -> str:
    """The page pub.sustenaut.eu serves for an object identifier or a name:
    /o/<cid>/ or /def/<name>/ (the name percent-encoded as pubtheme does)."""
    if publet.startswith("pub:"):
        return f"{PUB_SITE}/o/{publet}/"
    return f"{PUB_SITE}/def/{quote(publet, safe='')}/"


def input_table(parameters: list[dict]) -> str:
    """The inputs as a Markdown table, each linked to its publet."""
    lines = [
        "| Input | Unit | Low | Likely | High | Publet | Status |",
        "|---|---|--:|--:|--:|---|---|",
    ]
    for p in parameters:
        label = _short(p["publet"]) + (f", row {p['row']}" if p.get("row") else "")
        link = f"[{label}]({publet_url(p['publet'])})"
        lines.append(
            f"| {p['name']} | `{p['unit']}` | {fmt(p['low'])} | {fmt(p['likely'])} | {fmt(p['high'])} | {link} | {p.get('status', '')} |"
        )
    return "\n".join(lines)


def _short(publet: str) -> str:
    return publet if not publet.startswith("pub:") else publet.split(":")[-1][:10] + "…"


# --- Randomness and rounding -------------------------------------------------


def generator(seed: int = SEED) -> np.random.Generator:
    """The page's random generator; the seed is shown on the page, so anyone
    can draw the same numbers again."""
    return np.random.default_rng(seed)


def rounded(x: float, figures: int = SIGNIFICANT_FIGURES) -> float:
    """x to a number of significant figures (3 unless a page says otherwise)."""
    if x == 0 or not math.isfinite(x):
        return x
    return round(x, figures - 1 - math.floor(math.log10(abs(x))))


def fmt(x: float, figures: int = SIGNIFICANT_FIGURES) -> str:
    """x rounded as `rounded` does, written without spurious digits."""
    if x == 0 or not math.isfinite(x):
        return str(x)
    decimals = max(figures - 1 - math.floor(math.log10(abs(x))), 0)
    return f"{rounded(x, figures):,.{decimals}f}"


def rounding_note(figures: int = SIGNIFICANT_FIGURES) -> str:
    return f"Results are rounded to {figures} significant figures; the draws themselves are not."


# --- Citing the code ----------------------------------------------------------


def citation(notebook_location) -> dict:
    """What produced the numbers: the estimate wheel (name and sha256) and the
    git commit it was built from. In the browser this is public/build.json,
    written by the build; natively it is the working tree's commit."""
    if notebook_location is not None:
        text = _read_text(_join(notebook_location, "public", "build.json"))
        if text is not None:
            return json.loads(text)
    root = Path(__file__).resolve().parent.parent
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    return {"wheel": None, "sha256": None, "commit": commit}


def citation_text(cite: dict) -> str:
    commit = cite.get("commit") or "unknown"
    code = f"commit [`{commit[:12]}`](https://github.com/Sustenaut/business-plan/commit/{commit})" if commit != "unknown" else "an unknown commit"
    if cite.get("wheel"):
        return f"Computed by `{cite['wheel']}` (sha256 `{cite['sha256']}`), built from {code}."
    return f"Computed by the `estimate` package in the working tree at {code} (not a built wheel)."


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
