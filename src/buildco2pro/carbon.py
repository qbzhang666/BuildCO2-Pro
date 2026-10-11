"""Upfront carbon, EN 15978 modules A1-A5, of a building from its material inventory.

A1-A3  E = q x ECF, q = mass (volume x density), volume or area according to the basis of the factor
A4     E = m x d x TEF, road freight, every material group (the dashboard: not aluminium or rubber)
A5w    E = m x ECF_A5w, ECF_A5w = WF (ECF_A1-A3 + ECF_A4), WF = 1/(1 - WR) - 1 (Ma et al. 2025, Table 4)
A5a    site plant: E = P x fleet hours x EF_grid (tower cranes)
A5r    spoil: E = V x rho x d x TEF
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .factors import FactorLibrary, GROUPS
from .inventory import Inventory
from .models import ProjectInput

NO_A4_DASHBOARD = ("aluminium", "rubber")      # the dashboard's A4 table gives these no distance


@dataclass
class Line:
    material_class: str
    group: str
    name: str
    basis: str
    quantity: float
    unit: str
    factor: float
    factor_unit: str
    source: str
    tier: int
    mass_t: float
    tCO2e: float
    rows: int


@dataclass
class Result:
    modules_t: dict
    total_t: float
    per_m2_kg: float
    a1a3_by_category: dict
    a1a3_by_group: dict
    a1a3_by_category_group: dict
    a1a3_by_storey: dict
    mass_by_group_t: dict
    lines: list
    a4_by_group_t: dict
    a5w_by_group_t: dict
    a5a_by_crane_t: dict
    unclassified: dict
    storey_curve: list = field(default_factory=list)
    scenarios: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    factor_set: str = ""

    def to_dict(self):
        d = dict(self.__dict__); d["lines"] = [l.__dict__ for l in self.lines]
        return d


def _rows_carbon(inv: Inventory, lib: FactorLibrary, p: ProjectInput):
    """Per row: (row, factor, mass_kg, quantity, kgCO2e) for classified rows; unclassified tallied apart."""
    out, uncl = [], defaultdict(lambda: dict(rows=0, volume_m3=0.0, area_m2=0.0))
    for r in inv.rows:
        f = lib.materials.get(r.material_class) if r.material_class else None
        if f is None:
            key = "out of scope" if r.rule in ("rule 10", "rule 20", "rule 30") else "no class"
            u = uncl[(r.category, r.material or "(none)", key)]; u["rows"] += 1; u["volume_m3"] += r.volume_m3; u["area_m2"] += r.area_m2
            continue
        rho = r.density_kg_m3 if (p.density_from_source and r.density_kg_m3) else f.density
        V = r.volume_m3
        t = p.product_thickness_mm.get(f.key)
        if p.sheet_products == "product_thickness":
            if t and r.area_m2 > 0:
                V = min(V, r.area_m2 * t / 1e3)
            elif f.key in p.product_solid_fraction:
                V = V * p.product_solid_fraction[f.key]
        mass = V * rho
        if p.compat_dashboard and r.src_factor is not None:
            q = {"mass": r.volume_m3 * (r.density_kg_m3 or f.density), "volume": r.volume_m3, "area": r.area_m2}[r.src_basis]
            out.append((r, f, mass, q, q * r.src_factor)); continue
        q = {"mass": mass, "volume": V, "area": r.area_m2}[f.basis]
        if f.basis == "area" and q == 0 and r.volume_m3 > 0:
            q = r.volume_m3 / 0.013 if f.key == "plasterboard" else 0.0   # 13 mm board when only a volume is known
        out.append((r, f, mass, q, q * f.value))
    return out, uncl


def assess(p: ProjectInput, inv: Inventory, lib: FactorLibrary | None = None, with_curve: bool = True) -> Result:
    lib = lib or FactorLibrary(p.factor_set, p.factor_overrides)
    rows, uncl = _rows_carbon(inv, lib, p)
    warn = []
    by_cat, by_grp, by_cg, by_st = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
    mass_g = defaultdict(float); mass_a4 = defaultdict(float); lines = {}
    for r, f, mass, q, e in rows:
        by_cat[r.category] += e; by_grp[f.group] += e; by_cg[(r.category, f.group)] += e; by_st[r.storey or "(none)"] += e
        mass_g[f.group] += mass
        if not (p.compat_dashboard and f.key.startswith(NO_A4_DASHBOARD)):
            mass_a4[f.group] += mass
        L = lines.get(f.key)
        if L is None:
            L = lines[f.key] = Line(f.key, f.group, f.name, f.basis, 0.0, {"mass": "kg", "volume": "m3", "area": "m2"}[f.basis],
                                    f.value, f.unit, f.source, f.tier, 0.0, 0.0, 0)
        L.quantity += q; L.mass_t += mass / 1e3; L.tCO2e += e / 1e3; L.rows += 1
    for it in p.extra_items:
        t = float(it.get("tCO2e", 0.0)); g = it.get("group", "Other"); c = it.get("category", it.get("name", "Other"))
        if not t and it.get("material_class") in lib.materials:
            f = lib.get(it["material_class"]); t = float(it.get("quantity", 0)) * f.value / 1e3; g = f.group
        by_cat[c] += t * 1e3; by_grp[g] += t * 1e3; by_cg[(c, g)] += t * 1e3
        if it.get("mass_t"):
            mass_g[g] += float(it["mass_t"]) * 1e3; mass_a4[g] += float(it["mass_t"]) * 1e3
    a13 = sum(by_grp.values()) / 1e3
    # A4
    tr = p.transport; a4 = {}
    for g, m in mass_a4.items():
        d = tr.by_group_km.get(g, tr.distance_km)
        a4[g] = m / 1e3 * d * tr.tef / 1e3
    # A5
    wf = dict(lib.waste); wf.update(p.waste_overrides)
    a5w = {g: m * wf.get(g, 0.0) / 1e3 for g, m in mass_g.items()}
    missing = [g for g in mass_g if g not in wf]
    if missing:
        warn.append("No A5w waste factor for " + ", ".join(missing))
    a5a = {c.name: c.power_kw * c.fleet_hours * p.grid_ef / 1e3 for c in p.cranes}
    s = p.spoil; a5r = s.volume_m3 * s.density_t_m3 * s.distance_km * s.tef / 1e3
    mods = {"A1-A3": a13, "A4": sum(a4.values()), "A5w": sum(a5w.values()), "A5a": sum(a5a.values()), "A5r": a5r}
    total = sum(mods.values())
    nc = {k: u for k, u in uncl.items() if k[2] == "no class"}
    if nc:
        n = sum(u["rows"] for u in nc.values()); v = sum(u["volume_m3"] for u in nc.values())
        warn.append(f"{n} inventory rows ({v:,.1f} m3) have no material class and carry no carbon: see the checks")
    res = Result(modules_t=mods, total_t=total, per_m2_kg=total * 1e3 / p.gfa_m2,
                 a1a3_by_category={k: v / 1e3 for k, v in sorted(by_cat.items(), key=lambda x: -x[1])},
                 a1a3_by_group={k: v / 1e3 for k, v in sorted(by_grp.items(), key=lambda x: -x[1])},
                 a1a3_by_category_group={f"{c}|{g}": v / 1e3 for (c, g), v in by_cg.items()},
                 a1a3_by_storey={k: v / 1e3 for k, v in by_st.items()},
                 mass_by_group_t={k: v / 1e3 for k, v in sorted(mass_g.items(), key=lambda x: -x[1])},
                 lines=sorted(lines.values(), key=lambda l: -l.tCO2e), a4_by_group_t=a4, a5w_by_group_t=a5w,
                 a5a_by_crane_t=a5a,
                 unclassified={f"{c}|{m}|{k}": u for (c, m, k), u in sorted(uncl.items(), key=lambda x: -x[1]["volume_m3"])},
                 warnings=warn, factor_set=lib.set)
    res.scenarios = scenarios(p, res)
    if with_curve and p.storeys.roles:
        res.storey_curve = storey_curve(p, inv, lib, rows)
    return res


def scenarios(p: ProjectInput, res: Result) -> list:
    """Each lever as a fractional cut of A1-A3 by group (and optionally of A4 and A5)."""
    out = []
    for lv in p.levers:
        cut = sum(res.a1a3_by_group.get(g, 0.0) * fr for g, fr in lv.reduction.items() if g in GROUPS or g == "*")
        if "*" in lv.reduction:
            cut = res.modules_t["A1-A3"] * lv.reduction["*"]
        a45 = (res.modules_t["A4"] + res.modules_t["A5w"] + res.modules_t["A5a"] + res.modules_t["A5r"])
        cut45 = a45 * lv.reduction.get("*", 0.0) if lv.applies_to_a4_a5 else 0.0
        out.append(dict(name=lv.name, A1A3_t=res.modules_t["A1-A3"] - cut, total_t=res.total_t - cut - cut45,
                        saving_t=cut + cut45, saving_pct=100 * (cut + cut45) / res.total_t if res.total_t else 0.0))
    return out


def storey_curve(p: ProjectInput, inv, lib, rows=None) -> list:
    """A1-A3, A4 and A5w for 1 to range_max storeys: foundation + fixed + top + (n - fixed - top) typical storeys."""
    rows = rows if rows is not None else _rows_carbon(inv, lib, p)[0]
    roles = p.storeys.roles
    e = defaultdict(float); m = defaultdict(lambda: defaultdict(float))
    for r, f, mass, q, c in rows:
        role = roles.get(r.storey, "fixed")
        if role == "ignore":
            continue
        e[role] += c; m[role][f.group] += mass
    n_typ = max(p.storeys.typical_count, 1)
    present = {r.storey for r, *_ in rows}
    n_fixed = sum(1 for s, v in roles.items() if v == "fixed" and s in present)
    n_top = 1 if any(v == "top" and s in present for s, v in roles.items()) else 0     # roof and parapet: one storey
    wf = dict(lib.waste); wf.update(p.waste_overrides); tr = p.transport
    out = []
    for n in range(max(1, n_fixed + n_top), p.storeys.range_max + 1):
        k = max(n - n_fixed - n_top, 0)
        a13 = (e["foundation"] + e["fixed"] + e["top"] + k * e["typical"] / n_typ) / 1e3
        mass = defaultdict(float)
        for role, w in (("foundation", 1), ("fixed", 1), ("top", 1), ("typical", k / n_typ)):
            for g, v in m[role].items():
                mass[g] += v * w
        a4 = sum(v / 1e3 * tr.by_group_km.get(g, tr.distance_km) * tr.tef / 1e3 for g, v in mass.items()
                 if not p.compat_dashboard or g != "Aluminium")
        a5w = sum(v * wf.get(g, 0) / 1e3 for g, v in mass.items())
        out.append(dict(storeys=n, A1A3_t=a13, A4_t=a4, A5w_t=a5w, total_t=a13 + a4 + a5w))
    return out
