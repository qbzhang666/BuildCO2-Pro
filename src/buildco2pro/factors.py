"""Emission-factor library with provenance.

Every factor carries its basis (per kg, m3 or m2), unit, density, source and a data-quality tier (1 product EPD,
2 national database, 3 generic database, 4 placeholder), so that each line of a report can say where its number
came from. Two sets are bundled: ``epic2019``, the EPiC values used by the dashboard of Ma et al. (2025), and
``ice_uk``, the ICE V3.0 alternative of the same dashboard.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import resources

SETS = {"epic2019": "EPiC 2019 (Crawford, Stephan and Prideaux), values of Ma et al. (2025)",
        "ice_uk": "ICE V3.0 (Jones and Hammond 2019), as used in the dashboard of Ma et al. (2025)"}
GROUPS = ["Concrete", "Steel", "Aluminium", "Glass", "Timber", "Plasterboard", "Masonry and stone", "Plastics and rubber"]


@dataclass(frozen=True)
class Factor:
    key: str
    group: str
    name: str
    basis: str            # mass | volume | area
    value: float
    unit: str
    density: float        # kg/m3
    source: str
    tier: int
    notes: str = ""


@dataclass(frozen=True)
class SiteFactor:
    key: str
    name: str
    value: float
    unit: str
    source: str
    notes: str = ""


def _read(name):
    with resources.files("buildco2pro").joinpath("data", name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


class FactorLibrary:
    def __init__(self, set_name: str = "epic2019", overrides: dict | None = None):
        if set_name not in SETS:
            raise ValueError(f"unknown factor set {set_name!r}; choose one of {list(SETS)}")
        self.set = set_name
        self.version = SETS[set_name]
        self.materials: dict[str, Factor] = {}
        for r in _read("factors.csv"):
            if r["set"] == set_name:
                self.materials[r["key"]] = Factor(r["key"], r["group"], r["name"], r["basis"], float(r["value"]), r["unit"],
                                                  float(r["density_kg_m3"]), r["source"], int(r["tier"]), r["notes"])
        self.site = {r["key"]: SiteFactor(r["key"], r["name"], float(r["value"]), r["unit"], r["source"], r["notes"])
                     for r in _read("site_factors.csv")}
        self.waste = {r["group"]: float(r["factor"]) for r in _read("waste_factors.csv")}
        self.waste_rows = _read("waste_factors.csv")
        for k, v in (overrides or {}).items():
            self.override(k, **v) if isinstance(v, dict) else self.override(k, value=float(v))

    def override(self, key, **kw):
        """Project value (an EPD, say) in place of the library value; recorded as tier 1 unless stated."""
        base = self.materials.get(key)
        if base is None:
            raise KeyError(f"no material class {key!r}")
        kw.setdefault("tier", 1); kw.setdefault("source", "Project override")
        self.materials[key] = replace(base, **kw)

    def get(self, key) -> Factor:
        return self.materials[key]

    def rows(self):
        return [f.__dict__ for f in self.materials.values()]


@lru_cache(maxsize=4)
def load_library(set_name: str = "epic2019") -> FactorLibrary:
    return FactorLibrary(set_name)
