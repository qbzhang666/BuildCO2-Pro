"""A synthetic example building: four storeys of steel frame on pad footings, composite floors, a glazed and
clad facade and plasterboard partitions, 60 m by 24 m on a 7.5 m grid. Invented quantities, no project data.
It includes, on purpose, what the checks are for: floor beams without a material, a facade panel modelled as a
solid block, and mullions whose material is named as steel.
"""
from __future__ import annotations

from .inventory import Inventory, Row, classify
from .models import Crane, Lever, ProjectInput, Spoil, Storeys

STOREYS = ["00 Foundation", "01 Ground", "02 Level 1", "03 Level 2", "04 Roof"]


def example_inventory() -> Inventory:
    rows = []
    nx, ny, h = 9, 4, 4.0                     # 8 by 3 bays of 7.5 m
    plate = 60.0 * 24.0

    def add(**kw):
        rows.append(classify(Row(source="example", **kw)))
    for i in range(nx * ny):
        add(element_id=f"F{i}", ifc_class="IfcFooting", category="Foundations", family_type="Pad footing 2.4 x 2.4 x 0.8",
            material="Concrete, 40 MPa", storey=STOREYS[0], volume_m3=2.4 * 2.4 * 0.8)
    for s, st in enumerate(STOREYS[1:4]):
        for i in range(nx * ny):
            add(element_id=f"C{s}{i}", ifc_class="IfcColumn", category="Structural columns", family_type="310UC118",
                material="Steel, structural", storey=st, volume_m3=0.0150 * h, length_m=h, kg_per_m=118)
        for j in range(ny):
            add(element_id=f"B{s}x{j}", ifc_class="IfcBeam", category="Structural framing", family_type="530UB82",
                material="Steel, structural", storey=st, volume_m3=0.0105 * 60, length_m=60, kg_per_m=82)
        for i in range(nx):
            mat = "Render Material 255-255-0" if (s == 2 and i % 2) else "Steel, structural"   # beams without a material
            add(element_id=f"B{s}y{i}", ifc_class="IfcBeam", category="Structural framing", family_type="460UB67",
                material=mat, storey=st, volume_m3=0.0086 * 24, length_m=24, kg_per_m=67)
        add(element_id=f"S{s}", ifc_class="IfcSlab", category="Floors and slabs", family_type="Composite slab 150",
            material="Concrete, 32 MPa", storey=st, volume_m3=plate * 0.13, area_m2=plate)
        add(element_id=f"D{s}", ifc_class="IfcSlab", category="Floors and slabs", family_type="Profiled decking 1.0 BMT",
            material="Steel decking", storey=st, volume_m3=plate * 0.0012, area_m2=plate)
        per = 2 * (60 + 24) * h
        add(element_id=f"G{s}", ifc_class="IfcPlate", category="Curtain panels", family_type="Double glazed unit",
            material="Glass, clear", storey=st, volume_m3=0.55 * per * 0.012, area_m2=0.55 * per)
        add(element_id=f"M{s}", ifc_class="IfcMember", category="Mullions and members", family_type="Mullion 50 x 150",
            material="Metal - Steel, black", storey=st, volume_m3=0.55 * per / 1.5 * 0.0075 / 4, length_m=0.55 * per / 1.5)
        add(element_id=f"P{s}", ifc_class="IfcPlate", category="Curtain panels", family_type="Cladding panel, solid 40",
            material="Aluminium, powder coated", storey=st, volume_m3=0.45 * per * 0.040, area_m2=0.45 * per)
        add(element_id=f"W{s}", ifc_class="IfcWall", category="Walls", family_type="Partition, 2 x 13 plasterboard",
            material="Plasterboard", storey=st, volume_m3=600 * 0.026, area_m2=1200)
        add(element_id=f"T{s}", ifc_class="IfcWall", category="Walls", family_type="Partition studs 92",
            material="Steel stud 92", storey=st, volume_m3=600 * 0.0005, area_m2=600)
    add(element_id="R", ifc_class="IfcRoof", category="Roofs", family_type="Metal deck roof", material="Steel decking",
        storey=STOREYS[4], volume_m3=plate * 0.0006, area_m2=plate)
    add(element_id="ST", ifc_class="IfcStairFlight", category="Stairs", family_type="Glulam stair", material="Glulam",
        storey=STOREYS[1], volume_m3=6.0)
    add(element_id="Z", ifc_class="IfcBuildingElementProxy", category="Other elements", family_type="Zone mass", material="",
        storey=STOREYS[1], volume_m3=plate * 12)
    return Inventory(rows)


def example_project() -> ProjectInput:
    return ProjectInput(
        name="Example building (synthetic)", gfa_m2=60 * 24 * 3,
        cranes=[Crane(name="Tower crane", number=1, power_kw=40, fleet_hours=1500)],
        spoil=Spoil(volume_m3=2500),
        storeys=Storeys(roles={"00 Foundation": "foundation", "01 Ground": "fixed", "02 Level 1": "typical",
                               "03 Level 2": "typical", "04 Roof": "top"}, typical_count=2, range_max=12),
        levers=[Lever(name="Material replacement, flat 31% (as the dashboard)", reduction={"*": 0.31}, applies_to_a4_a5=True),
                Lever(name="Lower-carbon concrete (indicative 30%)", reduction={"Concrete": 0.30}),
                Lever(name="Recycled-content steel (indicative 40%)", reduction={"Steel": 0.40})])
