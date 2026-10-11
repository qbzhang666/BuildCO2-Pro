"""Project inputs (pydantic): everything the dashboard's slicers and side tables held, in one JSON file."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Crane(BaseModel):
    name: str = "Tower crane"
    number: int = Field(1, ge=0, description="Number of cranes (for the record; hours are fleet hours)")
    power_kw: float = Field(37.8, ge=0, description="Average electrical power drawn, kW")
    fleet_hours: float = Field(1584, ge=0, description="Working hours of all cranes of this model together")


class Spoil(BaseModel):
    volume_m3: float = Field(0.0, ge=0, description="Bulked volume of excavated spoil, m3")
    distance_km: float = Field(60.0, ge=0, description="Haul distance, km (round trip, as for A4)")
    density_t_m3: float = Field(1.0, gt=0, description="Bulked density, t/m3. Ma et al. (2025) imply 1.0")
    tef: float = Field(0.107, ge=0, description="Transport emission factor, kgCO2e/(t km)")


class Transport(BaseModel):
    distance_km: float = Field(60.0, ge=0, description="Delivery distance, km (round trip)")
    tef: float = Field(0.107, ge=0, description="Road freight emission factor, kgCO2e/(t km)")
    by_group_km: dict[str, float] = Field(default_factory=dict, description="Distance by material group, overriding the default")


class Storeys(BaseModel):
    """Typical-storey model of the dashboard: the building as fixed parts plus n copies of a typical storey."""
    roles: dict[str, Literal["foundation", "fixed", "typical", "top", "ignore"]] = Field(
        default_factory=dict, description="Role of each storey name of the inventory")
    typical_count: int = Field(3, ge=0, description="Number of typical storeys in the building as modelled")
    range_max: int = Field(15, ge=1, le=60, description="Largest number of storeys in the curve")


class Lever(BaseModel):
    name: str = "Lever"
    reduction: dict[str, float] = Field(default_factory=dict, description="Fractional reduction of A1-A3 by material group or class key")
    applies_to_a4_a5: bool = False


class ProjectInput(BaseModel):
    name: str = "Building"
    gfa_m2: float = Field(10000.0, gt=0, description="Gross floor area, m2, for kgCO2e/m2")
    factor_set: Literal["epic2019", "ice_uk"] = "epic2019"
    factor_overrides: dict[str, float] = Field(default_factory=dict, description="Material class key -> factor value (e.g. from an EPD)")
    sheet_products: Literal["as_modelled", "product_thickness"] = Field(
        "as_modelled", description="Sheet products (panels, sheets, doors): the modelled solid, or area x product thickness")
    product_thickness_mm: dict[str, float] = Field(
        default_factory=lambda: {"aluminium.sheet": 3.0, "aluminium.composite_panel": 4.0, "steel.sheet_wall": 1.0, "steel.door": 3.0, "steel.cold_rolled": 0.5,
                                 "steel.clad_frame": 4.0},
        description="Equivalent metal thickness of sheet products, mm (indicative; replace with product data)")
    product_solid_fraction: dict[str, float] = Field(
        default_factory=lambda: {"aluminium.extrusion": 0.225},
        description="Hollow products modelled as solid outlines: metal fraction of the outline (indicative; a 150 x 50 mm "
                    "mullion is about 4.5 kg/m hollow against 20 kg/m solid)")
    density_from_source: bool = Field(True, description="Use the density of the take-off row when it has one")
    transport: Transport = Transport()
    waste_overrides: dict[str, float] = Field(default_factory=dict, description="Material group -> A5w factor, kgCO2e/kg")
    cranes: list[Crane] = Field(default_factory=list)
    grid_ef: float = Field(0.86, ge=0, description="Grid emission factor for site electricity, kgCO2e/kWh")
    spoil: Spoil = Spoil()
    storeys: Storeys = Storeys()
    levers: list[Lever] = Field(default_factory=list)
    extra_items: list[dict] = Field(default_factory=list, description="Items outside the model (e.g. lighting): "
                                    "{name, group, category, tCO2e} or {name, material_class, quantity}")
    compat_dashboard: bool = Field(False, description="Reproduce the Power BI arithmetic: the take-off's own factors, "
                                   "no A4 for aluminium and rubber")
