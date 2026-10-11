# Changelog

## 0.2.0 (October 2026)

First public release. Open-source successor to the Power BI dashboard of Ma et al. (2025).

- Inventory from IFC (base quantities, layer sets split by thickness, storeys), Revit take-off tables (CSV,
  Excel) and Power BI files; ordered, editable classification rules, including rules for facade products that
  carry a generic metal material in the model (`type_metal`, rules 391 to 394).
- EPiC 2019 and ICE V3.0 factor sets with basis, density, source and tier; project overrides.
- A1-A3, A4, A5w, A5a, A5r; typical-storey curve; reduction levers.
- Checks C1 to C5: elements without a material, name-factor mismatch, equivalent solid thickness, proxies,
  missing quantities.
- Excel report, IFC with a `BuildCO2_Carbon` property set, publication figures, browser dashboard, REST API.
- Power BI mode reproduces the dashboard's A1-A3 of 39,190 tCO2e; the case is described in `docs/CASE_STUDY.md`.
