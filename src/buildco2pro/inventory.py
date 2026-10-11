"""The material inventory: one row per element and material, from IFC, a Revit take-off or a Power BI file.

A row keeps what the model says (IFC class or Revit category, family and type, material name, storey, volume,
area, length, count) and what BuildCO2 Pro makes of it (material class, by the rules of
``data/material_map.csv`` or the class of the take-off table). Nothing is dropped silently: rows without a
material class stay in the inventory, are left out of the carbon and are reported by ``checks.run``.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass, field, fields
from importlib import resources
from pathlib import Path

CATEGORY_OF_CLASS = {
    "IfcWall": "Walls", "IfcWallStandardCase": "Walls", "IfcCurtainWall": "Curtain walls", "IfcPlate": "Curtain panels",
    "IfcMember": "Mullions and members", "IfcSlab": "Floors and slabs", "IfcRoof": "Roofs", "IfcCovering": "Ceilings and coverings",
    "IfcBeam": "Structural framing", "IfcColumn": "Structural columns", "IfcFooting": "Foundations", "IfcPile": "Foundations",
    "IfcDoor": "Doors", "IfcWindow": "Windows", "IfcStair": "Stairs", "IfcStairFlight": "Stairs", "IfcRamp": "Stairs",
    "IfcRampFlight": "Stairs", "IfcRailing": "Railings", "IfcBuildingElementProxy": "Other elements",
    "IfcFurnishingElement": "Furniture", "IfcFurniture": "Furniture"}
CATEGORY_OF_TAKEOFF = {"Wall": "Walls", "CurtainPanel": "Curtain panels", "Mullion": "Mullions and members",
                       "StructuralFraming": "Structural framing", "StructuralColumn": "Structural columns", "Door": "Doors",
                       "Floor": "Floors and slabs", "Ceiling": "Ceilings and coverings", "Foundation": "Foundations",
                       "Stair": "Stairs", "Stairs": "Stairs", "Lighting": "Lighting"}


@dataclass
class Row:
    source: str                      # file the row came from
    element_id: str = ""             # IFC GlobalId or take-off row number
    ifc_class: str = ""
    category: str = ""
    family_type: str = ""
    material: str = ""
    storey: str = ""
    volume_m3: float = 0.0
    area_m2: float = 0.0
    length_m: float = 0.0
    count: int = 1
    density_kg_m3: float | None = None      # from the source when it has one
    material_class: str = ""                 # key in the factor library, "" = not classified
    rule: str = ""                           # the rule that gave the class
    kg_per_m: float | None = None            # section mass from the model (steel), if exported
    src_factor: float | None = None          # factor of the source take-off (dashboard reproduction)
    src_basis: str = ""                      # mass | volume | area, as the source multiplied it


@dataclass
class Inventory:
    rows: list[Row] = field(default_factory=list)

    def __len__(self):
        return len(self.rows)

    def extend(self, other: "Inventory"):
        self.rows.extend(other.rows); return self

    # ---------------------------------------------------------------- csv
    COLS = [f.name for f in fields(Row)]

    def to_csv(self, path=None) -> str:
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=self.COLS); w.writeheader()
        for r in self.rows:
            w.writerow(asdict(r))
        if path:
            Path(path).write_text(buf.getvalue(), encoding="utf-8")
        return buf.getvalue()

    @classmethod
    def from_csv(cls, path_or_text) -> "Inventory":
        text = Path(path_or_text).read_text(encoding="utf-8") if _is_path(path_or_text) else path_or_text
        rows = []
        for d in csv.DictReader(io.StringIO(text)):
            kw = {}
            for f in fields(Row):
                v = d.get(f.name, "")
                if f.name in ("volume_m3", "area_m2", "length_m"):
                    kw[f.name] = float(v or 0)
                elif f.name == "count":
                    kw[f.name] = int(float(v or 1))
                elif f.name in ("density_kg_m3", "kg_per_m", "src_factor"):
                    kw[f.name] = float(v) if v not in ("", None, "None") else None
                else:
                    kw[f.name] = v or ""
            rows.append(Row(**kw))
        return cls(rows)


def _is_path(x):
    return isinstance(x, Path) or (isinstance(x, str) and "\n" not in x and len(x) < 1000 and Path(x).exists())


# ---------------------------------------------------------------- classification
def _rules():
    with resources.files("buildco2pro").joinpath("data", "material_map.csv").open(encoding="utf-8") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: int(r["order"]))
    return [(r["match_on"], re.compile(r["pattern"]), r["material_class"], r["order"]) for r in rows]


def _takeoff_classes():
    with resources.files("buildco2pro").joinpath("data", "takeoff_classes.csv").open(encoding="utf-8") as f:
        return {r["takeoff_class"]: r["material_class"] for r in csv.DictReader(f)}


FRAMING = ("IfcBeam", "IfcColumn", "IfcMember")
METAL = re.compile(r"(?i)^mtl-|steel|metal")       # the generic metal materials that rule 400 would class as steel.section


def classify(row: Row, rules=None) -> Row:
    """Material class by the first matching rule (on the IFC class, the type or the material name)."""
    rules = rules or _rules()
    for on, rx, mc, order in rules:
        text = {"class": row.ifc_class, "type": row.family_type, "material": row.material, "type_metal": row.family_type}[on]
        if on == "type_metal" and (row.ifc_class in FRAMING or not METAL.search(row.material or "")):
            continue                                    # non-structural metal products only (see material_map.csv, 391-394)
        if rx.search(text or ""):
            if on == "type" and mc == "steel.door" and not re.search(r"(?i)steel|metal|mtl", row.material):
                continue
            if on == "type" and mc == "aluminium.extrusion" and re.search(r"(?i)glass|gl-|timber|wood", row.material):
                continue
            row.material_class = mc; row.rule = f"rule {order}"
            return row
    row.material_class = ""; row.rule = "no rule"
    return row


# ---------------------------------------------------------------- IFC
def from_ifc(path, rules=None) -> Inventory:
    """Rows from an IFC file: one per element and material layer or constituent, quantities from the base
    quantities (Qto_*), converted to metres. Layer volumes are split by layer thickness."""
    import ifcopenshell
    import ifcopenshell.util.element as ue
    import ifcopenshell.util.unit as uu
    f = ifcopenshell.open(str(path)); src = Path(path).name; rules = rules or _rules()
    LS = uu.calculate_unit_scale(f, "LENGTHUNIT"); AS = uu.calculate_unit_scale(f, "AREAUNIT"); VS = uu.calculate_unit_scale(f, "VOLUMEUNIT")
    rows = []
    for e in f.by_type("IfcElement"):
        if e.is_a("IfcOpeningElement") or e.is_a("IfcVirtualElement") or e.is_a("IfcFeatureElement"):
            continue
        ps = ue.get_psets(e)
        q = {}
        for k, v in ps.items():
            if k.startswith("Qto_") and "Validation" not in k:
                q.update(v)
        typ = ps.get("Other", {}).get("Family and Type") or ""
        if not typ:
            t = ue.get_type(e)
            typ = (t.Name if t else None) or e.ObjectType or e.Name or ""
        V = (q.get("NetVolume") or q.get("GrossVolume") or 0.0) * VS
        A = (q.get("NetSideArea") or q.get("NetArea") or q.get("NetSurfaceArea") or q.get("GrossArea")
             or q.get("NetFootprintArea") or 0.0) * AS
        L = (q.get("Length") or q.get("Height") or 0.0) * LS
        c = ue.get_container(e)
        base = dict(source=src, element_id=e.GlobalId, ifc_class=e.is_a(), category=CATEGORY_OF_CLASS.get(e.is_a(), "Other elements"),
                    family_type=typ, storey=(c.Name if c else "") or "", length_m=L,
                    kg_per_m=ps.get("Structural", {}).get("M"))
        for mat, share in _materials(e, ue):
            r = Row(**base, material=mat or "", volume_m3=V * share, area_m2=A if share == 1 else A)
            rows.append(classify(r, rules))
    return Inventory(rows)


def _materials(e, ue):
    """[(material name, share of the volume)], by layer thickness for layer sets."""
    m = ue.get_material(e, should_skip_usage=True)
    if m is None:
        return [("", 1.0)]
    if m.is_a("IfcMaterial"):
        return [(m.Name, 1.0)]
    if m.is_a("IfcMaterialLayerSet"):
        ls = [(l.Material.Name if l.Material else "", l.LayerThickness or 0.0) for l in m.MaterialLayers]
        t = sum(x for _, x in ls)
        return [(n, x / t) for n, x in ls if x > 0] if t > 0 else [(ls[0][0], 1.0)]
    if m.is_a("IfcMaterialProfileSet"):
        return [(m.MaterialProfiles[0].Material.Name if m.MaterialProfiles[0].Material else "", 1.0)]
    if m.is_a("IfcMaterialConstituentSet"):
        cs = m.MaterialConstituents or []
        fr = [c.Fraction for c in cs]
        if cs and all(x for x in fr):
            return [(c.Material.Name if c.Material else "", c.Fraction / sum(fr)) for c in cs]
        return [(cs[0].Material.Name if cs and cs[0].Material else "", 1.0)]
    if m.is_a("IfcMaterialList"):
        return [(m.Materials[0].Name, 1.0)]
    return [("", 1.0)]


# ---------------------------------------------------------------- Revit take-off tables
def from_takeoff_rows(records, source="take-off", category="", takeoff_class="") -> Inventory:
    """Rows from a Revit material take-off (``Family and Type``, ``Material: Name``, ``Material: Area``,
    ``Material: Volume``, ``Count``, ``Density``), as exported to Excel for the dashboard."""
    tc = _takeoff_classes(); rules = _rules(); rows = []

    def num(x):
        try:
            return float(str(x).replace(",", "").split()[0])
        except (ValueError, IndexError):
            return 0.0
    for i, d in enumerate(records):
        d = {str(k).strip(): v for k, v in d.items()}
        mat = str(d.get("Material: Name") or d.get("material") or "")
        r = Row(source=source, element_id=str(i), category=CATEGORY_OF_TAKEOFF.get(category, category),
                family_type=str(d.get("Family and Type") or ""), material=mat,
                volume_m3=num(d.get("Material: Volume", 0)), area_m2=num(d.get("Material: Area", 0)),
                count=int(num(d.get("Count", 1)) or 1), density_kg_m3=num(d.get("Density")) or None)
        fk = next((k for k in d if k.startswith("Emissions Factor")), None)
        if fk and num(d.get(fk)) and "Emission" in d and d.get("Emission") not in (None, ""):
            r.src_factor, r.src_basis = _source_basis(r, num(d[fk]), num(d["Emission"]))
        if takeoff_class and tc.get(takeoff_class):
            r.material_class = tc[takeoff_class]; r.rule = f"take-off table {takeoff_class}"
        else:
            classify(r, rules)
        rows.append(r)
    return Inventory(rows)


def from_takeoff_csv(path) -> Inventory:
    """A flat take-off CSV with the columns component, material_class, family_type, revit_material, area_m2,
    volume_m3, count, density (the export of ``from_pbix`` or of the dashboard tables)."""
    tc = _takeoff_classes(); rows = []
    with open(path, encoding="utf-8") as f:
        for i, d in enumerate(csv.DictReader(f)):
            r = Row(source=Path(path).name, element_id=str(i), category=CATEGORY_OF_TAKEOFF.get(d.get("component", ""), d.get("component", "")),
                    family_type=d.get("family_type", ""), material=d.get("revit_material", ""),
                    volume_m3=float(d.get("volume_m3") or 0), area_m2=float(d.get("area_m2") or 0),
                    count=int(float(d.get("count") or 1)), density_kg_m3=float(d["density"]) if d.get("density") else None)
            if d.get("factor") and d.get("emission_kg"):
                r.src_factor, r.src_basis = _source_basis(r, float(d["factor"]), float(d["emission_kg"]))
            mc = tc.get(d.get("material_class", ""), "")
            if mc:
                r.material_class = mc; r.rule = f"take-off class {d['material_class']}"
            else:
                classify(r)
            rows.append(r)
    return Inventory(rows)


def _source_basis(r: Row, f: float, e: float):
    """Which quantity the source multiplied by its factor: the one that reproduces its emission."""
    cand = {"mass": r.volume_m3 * (r.density_kg_m3 or 0) * f, "volume": r.volume_m3 * f, "area": r.area_m2 * f}
    b = min(cand, key=lambda k: abs(cand[k] - e))
    return f, b


def from_pbix(path) -> tuple[Inventory, dict]:
    """Inventory and the A4/A5 tables from a Power BI file built on per-component, per-material tables
    (``Wall_Steel``, ``Floor_Concrete32``, ...). Needs the optional ``pbixray`` package."""
    from pbixray import PBIXRay
    m = PBIXRay(str(path)); inv = Inventory(); extra = {}
    for t in m.tables:
        if "_" not in t or t.startswith(("Modular", "A5", "A4")):
            try:
                extra[t] = m.get_table(t).to_dict("records")
            except Exception:
                pass
            continue
        comp, cls_ = t.split("_", 1)
        try:
            recs = m.get_table(t).to_dict("records")
        except Exception:
            continue
        cls_ = {"Cold rolled Steel": "Cold rolled Steel", "Concrete": "Concrete"}.get(cls_, cls_)
        inv.extend(from_takeoff_rows(recs, source=f"{Path(path).name}:{t}", category=comp, takeoff_class=cls_))
    return inv, extra
