"""The smallest model the estimate site serves: one three-point input read as a
triangular distribution, summarised by its quantiles. It exists to test the
pipeline (wheel, export, Pyodide, input table) before the real models land.

Every model module in estimate.models has the same shape:

- PARAMETERS: one dict per input, with name, unit (UCUM), low, likely and
  high, publet (an object identifier as `pub bundle` prints it, or a
  definition name such as "{tray}"), and optionally row (the first-column
  value of the publet's data row, when it has several), source and status;
- OUTPUTS: one dict per result, with name, unit and description;
- MODEL: the model's name and version;
- samplers that take a numpy Generator, so a seed fixes every draw.

Model modules use only the standard library and numpy.
"""
import numpy as np

MODEL = {"name": "Example: basil harvest per tray", "version": "0.1.0"}

PARAMETERS = [
    {
        "name": "basil harvest per tray",
        "unit": "g/{tray}",
        "low": 40.0,
        "likely": 60.0,
        "high": 90.0,
        "publet": "pub:sha2-256:xgkogmxvbj72gf7k2pqqfpis6xq7b6ozlcsyquqchvrluidhybpa",
        "row": "basil",
        "source": "placeholder until trays are weighed",
        "status": "placeholder",
    },
]

OUTPUTS = [
    {"name": "basil harvest per tray", "unit": "g/{tray}", "description": "5th, 50th and 95th percentiles of the harvest"},
]

QUANTILES = (0.05, 0.5, 0.95)


def sample(rng: np.random.Generator, parameters=PARAMETERS, n: int = 100_000) -> np.ndarray:
    """Draw n harvests from the triangular distribution of the one input."""
    p = parameters[0]
    return rng.triangular(p["low"], p["likely"], p["high"], n)


def quantiles(draws: np.ndarray, qs=QUANTILES) -> list[float]:
    return [float(q) for q in np.quantile(draws, qs)]
