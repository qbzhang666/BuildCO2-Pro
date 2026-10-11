from buildco2pro.checks import run
from buildco2pro.examples import example_inventory
from buildco2pro.inventory import Inventory, Row, classify


def cls(**kw):
    return classify(Row(source="t", **kw)).material_class


def test_rules():
    assert cls(material="CON-101") == "concrete.c40"
    assert cls(material="Concrete, 32 MPa") == "concrete.c32"
    assert cls(material="MTL-104 Metal - Steel MON-RED GUM", family_type="STB_UB_gm: 610UB 125") == "steel.section"
    assert cls(material="Render Material 255-255-0", family_type="STB_UB_gm: 360UB 44") == "steel.section"   # by type
    assert cls(material="Render Material 255-255-0", family_type="Generic") == ""
    assert cls(material="BLK-201 - SPEEDPANEL - 78mm") == "steel.sheet_wall"
    assert cls(material="GLS-100 Glass - Clear") == "glass.flat"
    assert cls(material="IL-107 - IMPACT RESISTANT PLASTERBOARD - 13mm") == "plasterboard"
    assert cls(ifc_class="IfcLightFixture", material="Aluminium") == ""
    assert cls(material="", family_type="A08 - ZONE 8") == ""


def test_generic_metal_products():
    """Facade products that carry a generic metal material in the model (rules 391 to 394)."""
    m = "MTL-100 Metal - Steel"
    assert cls(ifc_class="IfcPlate", material=m, family_type="Facade panel: ALUM PLAIN 3MM") == "aluminium.sheet"
    assert cls(ifc_class="IfcWall", material=m, family_type="Basic Wall: 150mm SANDWICH PANEL") == "steel.sheet_wall"
    assert cls(ifc_class="IfcWall", material=m, family_type="Basic Wall: PARAPET 200") == "steel.clad_frame"
    assert cls(ifc_class="IfcPlate", material=m, family_type="Louvre panel: LVR 100") == "aluminium.extrusion"
    # framing members and non-metal materials keep their class
    assert cls(ifc_class="IfcColumn", material=m, family_type="SHS stud column") == "steel.section"
    assert cls(ifc_class="IfcBuildingElementProxy", material="Render Material 255-255-0", family_type="Generic Models 10") == ""


def test_checks_find_what_the_example_hides():
    found = {c["check"] for c in run(example_inventory())}
    assert {"C1", "C2", "C3"} <= found


def test_csv_round_trip(tmp_path):
    inv = example_inventory(); p = tmp_path / "inv.csv"; inv.to_csv(p)
    back = Inventory.from_csv(p)
    assert len(back) == len(inv) and back.rows[5].volume_m3 == inv.rows[5].volume_m3
    assert back.rows[5].material_class == inv.rows[5].material_class
