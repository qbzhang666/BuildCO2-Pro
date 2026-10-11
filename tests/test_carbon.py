"""Hand-checked cases for every module (EN 15978 A1-A5)."""
import pytest

from buildco2pro.carbon import assess
from buildco2pro.factors import FactorLibrary
from buildco2pro.inventory import Inventory, Row, classify
from buildco2pro.models import Crane, ProjectInput, Spoil


def inv(*rows):
    return Inventory([classify(Row(source="t", **r)) for r in rows])


def test_a1a3_by_basis():
    i = inv(dict(category="Structural framing", family_type="530UB82", material="Steel, structural", volume_m3=1.0),
            dict(category="Floors", family_type="Slab", material="Concrete, 32 MPa", volume_m3=10.0),
            dict(category="Walls", family_type="Partition", material="Plasterboard", volume_m3=0.13, area_m2=10.0))
    r = assess(ProjectInput(gfa_m2=100), i)
    assert r.a1a3_by_group["Steel"] == pytest.approx(7850 * 3.7 / 1e3)          # mass basis
    assert r.a1a3_by_group["Concrete"] == pytest.approx(10 * 416 / 1e3)         # volume basis
    assert r.a1a3_by_group["Plasterboard"] == pytest.approx(10 * 5.8 / 1e3)     # area basis


def test_a4_a5_modules():
    i = inv(dict(category="Floors", family_type="Slab", material="Concrete, 32 MPa", volume_m3=100.0))
    p = ProjectInput(gfa_m2=100, cranes=[Crane(power_kw=37.8, fleet_hours=1584)], spoil=Spoil(volume_m3=65520))
    r = assess(p, i)
    m = 100 * 2327                                                             # kg
    assert r.modules_t["A4"] == pytest.approx(m / 1e3 * 60 * 0.107 / 1e3)
    assert r.modules_t["A5w"] == pytest.approx(m * 0.00595 / 1e3)
    assert r.modules_t["A5a"] == pytest.approx(37.8 * 1584 * 0.86 / 1e3)      # 51.5 t, as the dashboard
    assert r.modules_t["A5r"] == pytest.approx(420.6384)                       # 65,520 m3 x 60 km x 0.107, Ma et al. (2025)


def test_dashboard_mode_no_a4_for_aluminium():
    i = inv(dict(category="Mullions", family_type="Mullion", material="Aluminium", volume_m3=1.0),
            dict(category="Floors", family_type="Slab", material="Concrete, 32 MPa", volume_m3=1.0))
    a = assess(ProjectInput(), i); b = assess(ProjectInput(compat_dashboard=True), i)
    assert "Aluminium" in a.a4_by_group_t and "Aluminium" not in b.a4_by_group_t and "Concrete" in b.a4_by_group_t


def test_ice_set_ratio():
    i = inv(dict(category="Framing", family_type="530UB82", material="Steel", volume_m3=1.0))
    e = assess(ProjectInput(), i).modules_t["A1-A3"]; c = assess(ProjectInput(factor_set="ice_uk"), i).modules_t["A1-A3"]
    assert c / e == pytest.approx(0.714, abs=0.002)


def test_override_is_tier_1():
    lib = FactorLibrary("epic2019", {"steel.section": 1.2})
    assert lib.get("steel.section").value == 1.2 and lib.get("steel.section").tier == 1


def test_product_thickness_caps_solid_panels():
    i = inv(dict(ifc_class="IfcPlate", category="Curtain panels", family_type="Cladding panel, solid 40",
                 material="Aluminium", volume_m3=4.0, area_m2=100.0))
    solid = assess(ProjectInput(), i).a1a3_by_group["Aluminium"]
    sheet = assess(ProjectInput(sheet_products="product_thickness"), i).a1a3_by_group["Aluminium"]
    assert solid / sheet == pytest.approx(40 / 3.0)


def test_unclassified_rows_carry_no_carbon_and_warn():
    i = inv(dict(category="Floors", family_type="Screed", material="SCREED", volume_m3=5.0))
    r = assess(ProjectInput(), i)
    assert r.modules_t["A1-A3"] == 0 and r.warnings


def test_storey_curve_reproduces_the_model():
    from buildco2pro.examples import example_inventory, example_project
    p = example_project(); r = assess(p, example_inventory())
    n_model = 4                                             # ground, two typical levels, roof
    row = next(x for x in r.storey_curve if x["storeys"] == n_model)
    assert row["A1A3_t"] == pytest.approx(r.modules_t["A1-A3"], rel=1e-9)
