"""Checks of an inventory before its carbon is used (Chapter 7 of the Intelligent Tunnel Lifecycle textbook).

C1  elements without a material, or with a placeholder (render material, "Default"): absent from any take-off
    joined to factors by material name
C2  material name and material class disagree (a material named as steel costed as aluminium, and so on)
C3  equivalent solid thickness V/A of sheet products: a panel, sheet or door modelled as a solid block
C4  share of proxies (IfcBuildingElementProxy): elements the export could not classify
C5  elements with no quantity (no base quantities exported)
Each check returns rows with what was found, how much and what to do about it; none changes the inventory.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .factors import FactorLibrary
from .inventory import Inventory

SHEET_CLASSES = {"steel.sheet_wall": 2.0, "steel.door": 3.0, "aluminium.sheet": 3.0, "aluminium.composite_panel": 6.0,
                 "steel.decking": 1.2, "steel.cold_rolled": 1.5}      # plausible upper bound of V/A, mm
STRUCTURAL = ("IfcBeam", "IfcColumn", "IfcMember", "IfcFooting", "IfcPile", "IfcSlab", "IfcWall")
PLACEHOLDER = re.compile(r"(?i)render material|^default|^<unnamed>$|^$|^none$")
STEEL_SECTION = re.compile(r"(?i)\d{2,4}\s?(ub|uc|wb|wc|pfc|shs|rhs|chs)|(ub|uc|wb|wc|pfc|shs|rhs|chs)\s?\d|purlin")


def run(inv: Inventory, lib: FactorLibrary | None = None) -> list[dict]:
    lib = lib or FactorLibrary()
    out = []
    # C1
    g = defaultdict(lambda: dict(n=0, V=0.0, types=defaultdict(int)))
    for r in inv.rows:
        if r.ifc_class and r.ifc_class not in STRUCTURAL and r.ifc_class not in ("IfcPlate", "IfcCurtainWall", "IfcDoor", "IfcWindow", "IfcCovering", "IfcStairFlight", "IfcRailing"):
            continue
        if PLACEHOLDER.search(r.material or "") and r.volume_m3 > 0:
            kind = "steel section" if STEEL_SECTION.search(r.family_type) else (r.ifc_class or r.category)
            d = g[kind]; d["n"] += 1; d["V"] += r.volume_m3; d["types"][r.family_type] += 1
    for kind, d in sorted(g.items(), key=lambda x: -x[1]["V"]):
        est = ""
        if kind == "steel section":
            f = lib.materials["steel.section"]
            est = f"{d['V'] * f.density / 1e3:,.0f} t of steel, {d['V'] * f.density * f.value / 1e3:,.0f} tCO2e at {f.value} {f.unit}"
        top = ", ".join(f"{t} ({n})" for t, n in sorted(d["types"].items(), key=lambda x: -x[1])[:3])
        out.append(dict(check="C1", severity="high" if d["V"] > 1 else "medium",
                        finding=f"{d['n']} {kind} elements without a material ({d['V']:,.1f} m3)", estimate=est,
                        examples=top, action="Assign the material in the model, or add the elements to the take-off by type"))
    # C2
    mm = defaultdict(lambda: dict(n=0, V=0.0))
    for r in inv.rows:
        f = lib.materials.get(r.material_class)
        if not f:
            continue
        m = (r.material or "").lower()
        named = "steel" if "steel" in m else "aluminium" if ("alumin" in m or "alum" in m) else "timber" if ("wood" in m or "timber" in m) else ""
        if named and named != f.group.lower() and not (named == "steel" and f.group == "Steel"):
            d = mm[(r.material, f.key)]; d["n"] += 1; d["V"] += r.volume_m3
    for (mat, key), d in sorted(mm.items(), key=lambda x: -x[1]["V"])[:10]:
        out.append(dict(check="C2", severity="high", finding=f"{d['n']} rows with material '{mat}' costed as {key}",
                        estimate=f"{d['V']:,.1f} m3", examples="",
                        action="Confirm the product from the drawings or the supplier; correct the material or the mapping"))
    # C3
    va = defaultdict(lambda: dict(V=0.0, A=0.0, n=0))
    for r in inv.rows:
        if r.material_class in SHEET_CLASSES and r.area_m2 > 0:
            d = va[(r.material_class, r.family_type)]; d["V"] += r.volume_m3; d["A"] += r.area_m2; d["n"] += 1
    for (key, typ), d in sorted(va.items(), key=lambda x: -x[1]["V"]):
        t = 1e3 * d["V"] / d["A"] if d["A"] else 0
        if t > SHEET_CLASSES[key]:
            f = lib.materials[key]
            out.append(dict(check="C3", severity="high" if d["V"] > 5 else "medium",
                            finding=f"{typ}: equivalent solid thickness {t:.1f} mm of {f.name.lower()} over {d['A']:,.0f} m2",
                            estimate=f"{d['V']:,.1f} m3 modelled as solid", examples=f"{d['n']} rows",
                            action=f"Use the product mass per m2 (EPD or datasheet); above {SHEET_CLASSES[key]} mm the model is a solid block"))
    # C4, C5
    n = len(inv.rows) or 1
    px = sum(1 for r in inv.rows if r.ifc_class == "IfcBuildingElementProxy")
    if px / n > 0.05:
        out.append(dict(check="C4", severity="medium", finding=f"{px} proxies ({100 * px / n:.0f}% of rows)", estimate="",
                        examples="", action="Map the Revit categories to IFC classes (IfcExportAs) before export"))
    zq = sum(1 for r in inv.rows if r.material_class and r.volume_m3 == 0 and r.area_m2 == 0)
    if zq:
        out.append(dict(check="C5", severity="medium", finding=f"{zq} classified rows with no volume or area", estimate="",
                        examples="", action="Export base quantities, or compute them from the geometry"))
    return out
