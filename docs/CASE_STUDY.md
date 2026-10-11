# The case building: a prefabricated steel-framed teaching building

The case of Ma et al. (2025) is a prefabricated steel-framed teaching building of about 19,000 m2 gross floor area.
Its files (the Revit models and the take-off workbooks) belong to the design team and the authors and are not part of
this repository. With them on disk:

```bash
# 1. The take-off route, from the tables of the Power BI file (needs the pbix extra)
buildco2pro inventory LCA.pbix -o case_pbix.csv
buildco2pro assess case_pbix.csv -p examples/case_building.json

# 2. The design-model route, from the IFC 4.3 exports of the Revit models (main, structural steel, facade)
buildco2pro inventory MAIN.ifc STEEL.ifc FACADE.ifc -o case_ifc.csv
buildco2pro assess case_ifc.csv -p examples/case_building.json --checks -o case_ifc.xlsx
buildco2pro tag STEEL.ifc -p examples/case_building.json -o STEEL_carbon.ifc
```

With `"compat_dashboard": true` the take-off route reproduces the A1-A3 of the dashboard, 39,190 tCO2e; with the
lighting added as an `extra_items` entry, 42,366 t against 42,372.7 t in the paper. `tests/test_case_building.py`
checks this when `BUILDCO2_CASE_TAKEOFF` points to the take-off CSV.

The design-model route costs the model element by element. Its checks (C1 to C5) report what has to be resolved
before the two routes can be compared: elements without a material, names that do not match their factor, and sheet
products (panels, sheets, doors) modelled as solids, which can be costed by an equivalent product thickness
(`"sheet_products": "product_thickness"`). The final verification of the building inventory by scan-to-BIM and site
inspection is reported separately.
