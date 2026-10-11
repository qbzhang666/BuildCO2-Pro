import pytest

from buildco2pro.carbon import assess
from buildco2pro.models import ProjectInput

ifcopenshell = pytest.importorskip("ifcopenshell")


def small_ifc(path):
    """One layered wall (13 mm plasterboard + 92 mm stud + 13 mm plasterboard) and one beam without a material."""
    import ifcopenshell.api as api
    f = ifcopenshell.file(schema="IFC4")
    proj = api.run("root.create_entity", f, ifc_class="IfcProject", name="P")
    api.run("unit.assign_unit", f)
    site = api.run("root.create_entity", f, ifc_class="IfcSite"); bld = api.run("root.create_entity", f, ifc_class="IfcBuilding")
    st = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="01 Ground")
    api.run("aggregate.assign_object", f, relating_object=proj, products=[site]); api.run("aggregate.assign_object", f, relating_object=site, products=[bld])
    api.run("aggregate.assign_object", f, relating_object=bld, products=[st])
    w = api.run("root.create_entity", f, ifc_class="IfcWall", name="Partition")
    ls = api.run("material.add_material_set", f, name="Partition", set_type="IfcMaterialLayerSet")
    for n, t in (("IL-107 Plasterboard", 13.0), ("MTL-204 - STUD - 92mm", 92.0), ("IL-107 Plasterboard", 13.0)):
        m = api.run("material.add_material", f, name=n); l = api.run("material.add_layer", f, layer_set=ls, material=m)
        api.run("material.edit_layer", f, layer=l, attributes={"LayerThickness": t})
    api.run("material.assign_material", f, products=[w], type="IfcMaterialLayerSet", material=ls)
    q = api.run("pset.add_qto", f, product=w, name="Qto_WallBaseQuantities")
    api.run("pset.edit_qto", f, qto=q, properties={"NetVolume": 1.18, "NetSideArea": 10.0})
    b = api.run("root.create_entity", f, ifc_class="IfcBeam", name="B1")
    b.ObjectType = "460UB67"
    q = api.run("pset.add_qto", f, product=b, name="Qto_BeamBaseQuantities")
    api.run("pset.edit_qto", f, qto=q, properties={"NetVolume": 0.086, "Length": 10.0})
    api.run("spatial.assign_container", f, relating_structure=st, products=[w, b])
    f.write(str(path)); return path


def test_ifc_layers_split_by_thickness(tmp_path):
    from buildco2pro.inventory import from_ifc
    inv = from_ifc(small_ifc(tmp_path / "m.ifc"))
    wall = [r for r in inv.rows if r.ifc_class == "IfcWall"]
    assert len(wall) == 3 and sum(r.volume_m3 for r in wall) == pytest.approx(1.18)
    assert {r.material_class for r in wall} == {"plasterboard", "steel.cold_rolled"}
    beam = next(r for r in inv.rows if r.ifc_class == "IfcBeam")
    assert beam.material_class == "steel.section" and beam.storey == "01 Ground"
    r = assess(ProjectInput(), inv)
    assert r.a1a3_by_group["Plasterboard"] == pytest.approx(2 * 10 * 5.8 / 1e3)


def test_tag_ifc(tmp_path):
    from buildco2pro.factors import FactorLibrary
    from buildco2pro.ifcexport import tag_ifc
    from buildco2pro.inventory import from_ifc
    import ifcopenshell.util.element as ue
    src = small_ifc(tmp_path / "m.ifc"); inv = from_ifc(src)
    n = tag_ifc(src, tmp_path / "t.ifc", inv, FactorLibrary(), ProjectInput())
    f = ifcopenshell.open(str(tmp_path / "t.ifc"))
    ps = ue.get_psets(f.by_type("IfcBeam")[0])["BuildCO2_Carbon"]
    assert n == 2 and ps["A1A3_kgCO2e"] == pytest.approx(0.086 * 7850 * 3.7, rel=1e-3)


def test_api_example_and_upload(tmp_path):
    from fastapi.testclient import TestClient
    from buildco2pro.api import app
    c = TestClient(app)
    assert c.get("/api/health").json()["status"] == "ok"
    ex = c.get("/api/defaults").json()["example"]
    r = c.post("/api/assess", json={"project": ex, "token": "example"}).json()
    assert r["result"]["total_t"] > 0 and r["checks"]
    up = c.post("/api/upload", files={"files": ("m.ifc", small_ifc(tmp_path / "m.ifc").read_bytes())}).json()
    r2 = c.post("/api/assess", json={"project": ex, "token": up["token"]}).json()
    assert r2["summary"]["rows"] == 4
    x = c.post("/api/report.xlsx", json={"project": ex, "token": up["token"]})
    assert x.status_code == 200 and x.content[:2] == b"PK"
