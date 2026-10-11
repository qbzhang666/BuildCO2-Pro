"""Write the carbon back into the IFC file: a property set ``BuildCO2_Carbon`` on every assessed element.

The model then carries its own inventory: any IFC viewer (BlenderBIM/Bonsai, BIMvision, xeokit) can colour or
filter elements by their A1-A3 carbon, and the numbers stay attached to the GlobalIds when the model is
federated or handed over.
"""
from __future__ import annotations

from collections import defaultdict


def tag_ifc(src, dst, inv, lib, p):
    import ifcopenshell
    import ifcopenshell.api
    from .carbon import _rows_carbon
    f = ifcopenshell.open(str(src))
    rows, _ = _rows_carbon(inv, lib, p)
    per = defaultdict(lambda: dict(e=0.0, m=0.0, cls=[], fac=[], src=set()))
    for r, fa, mass, q, e in rows:
        d = per[r.element_id]; d["e"] += e; d["m"] += mass; d["cls"].append(fa.key); d["fac"].append(f"{fa.value} {fa.unit}"); d["src"].add(fa.source)
    n = 0
    for gid, d in per.items():
        try:
            el = f.by_guid(gid)
        except RuntimeError:
            continue
        ps = ifcopenshell.api.run("pset.add_pset", f, product=el, name="BuildCO2_Carbon")
        ifcopenshell.api.run("pset.edit_pset", f, pset=ps, properties={
            "A1A3_kgCO2e": round(d["e"], 3), "Mass_kg": round(d["m"], 3), "MaterialClass": ";".join(sorted(set(d["cls"]))),
            "Factor": ";".join(sorted(set(d["fac"]))), "FactorSet": lib.set, "Source": "; ".join(sorted(d["src"]))[:250],
            "Tool": "BuildCO2 Pro"})
        n += 1
    f.write(str(dst))
    return n
