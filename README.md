# BuildCO2 Pro

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23292247.svg)](https://doi.org/10.5281/zenodo.23292247)

Upfront embodied carbon (EN 15978 A1–A5) of buildings, from an IFC model or a Revit material take-off, with a
browser dashboard, an Excel report and the carbon written back into the IFC file. Open source under the MIT
licence (`LICENSE`). Copyright (c) 2026 Qianbing Zhang, Monash University; contact qianbing.zhang@monash.edu.
To cite the toolbox, see `CITATION.cff` (DOI [10.5281/zenodo.23292247](https://doi.org/10.5281/zenodo.23292247)) and the
references at the end of this file.

BuildCO2 Pro replaces the Power BI dashboard of the BIM-integrated life-cycle assessment of Ma et al. (2025),
*Building and Environment* 286, 113689, in the way that TunCO2 Pro replaced the Power BI dashboard of TunCO2 for
tunnels: the same calculation, in Python, readable and tested, with every factor carrying its source, and no
commercial software needed to run it. It is the worked toolbox of the building case of the
teaching textbook *Digital Twins for Underground Infrastructure* (in preparation).

## Download and install

The only prerequisite is Python 3.10 or later (https://www.python.org).

**Windows.** Double-click `Start-BuildCO2Pro.bat`. The first start creates a private Python environment in the
folder (`.venv`, a few minutes), installs the package and opens the dashboard in the browser; later starts take
seconds. `Run-Tests.bat` runs the test suite. The `.venv` folder is marked as ignored by Dropbox.

**Any platform:**

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[all]"                            # core + IFC + Power BI import + figures + tests
buildco2pro serve                                  # opens http://127.0.0.1:8000
python -m pytest
```

Optional extras: `ifc` (IfcOpenShell: IFC import and carbon export), `pbix` (pbixray: read a Power BI file),
`figures` (matplotlib), `dev` (tests). The core calculation needs none of them.

**Docker:** `docker build -t buildco2pro . && docker run -p 8000:8000 buildco2pro`.

## Command line

```bash
buildco2pro example -o out                               # the synthetic example: inventory, project, Excel report
buildco2pro inventory MAIN.ifc STEEL.ifc FACADE.ifc -o inventory.csv
buildco2pro inventory LCA.pbix -o inventory.csv          # the take-off tables of a Power BI dashboard
buildco2pro assess inventory.csv -p project.json -o report.xlsx --checks
buildco2pro tag MAIN.ifc -p project.json -o MAIN_carbon.ifc
buildco2pro figures inventory.csv -p project.json -o figures
buildco2pro defaults > project.json                      # every input, with its default
```

## What it does

| Step | Module |
| --- | --- |
| Inventory from IFC (quantities from `Qto_*` base quantities, material layer sets split by thickness, storeys), from Revit take-off tables (CSV or Excel), or from the tables of a Power BI file | `inventory.py` |
| Material class of every row by ordered, editable rules on the IFC class, the type and the Revit material name | `data/material_map.csv` |
| Factor library: EPiC 2019 and ICE V3.0 sets, each factor with basis (kg, m³, m²), density, source and data-quality tier; project overrides (EPDs) recorded as tier 1 | `factors.py`, `data/factors.csv` |
| A1–A3 by element, material and storey; A4 road freight by group; A5w construction waste (Ma et al. 2025, Table 4); A5a cranes; A5r spoil | `carbon.py` |
| Typical-storey model: carbon against the number of storeys (the dashboard's modular levels) | `carbon.storey_curve` |
| Scenarios: reduction levers by material group, including the dashboard's flat material replacement | `carbon.scenarios` |
| Checks: elements without a material, name–factor mismatches, equivalent solid thickness of sheet products, proxies, missing quantities | `checks.py` |
| Excel report, IFC with a `BuildCO2_Carbon` property set on every element, publication figures | `report.py`, `ifcexport.py`, `figures.py` |
| Browser dashboard and REST API (documented at `/docs` on the running server) | `api.py`, `web/` |

## Calculation modes

- **Default:** the factor library, A4 on every material group, one mass per group for A4 and A5.
- **Power BI arithmetic** (`compat_dashboard: true`, or the tick box in the dashboard): each take-off row keeps the
  factor and the quantity the dashboard multiplied it by, and A4 leaves out aluminium and rubber, to which the
  dashboard's A4 table gives no distance. On the
  tables of the case of Ma et al. (2025) this reproduces the dashboard's A1–A3 of 39,190 tCO2e to 0.001%; with the
  lighting added as an `extra_items` entry, 42,366 t against 42,372.7 t in the paper (`docs/CASE_STUDY.md`).

## Sheet products

A model built for drawings often shows a panel, a sheet or a door as a solid block of the right outline. With
`sheet_products: "as_modelled"` (default) BuildCO2 Pro costs the solid, as the take-off does, and check C3 reports
the equivalent solid thickness V/A. With `"product_thickness"` it costs area × an equivalent metal thickness per
material class (`product_thickness_mm`; indicative defaults, to be replaced by product data).

## References

- Ma X, Huang M, Chen X, Bai Y, Zhang Q-B (2025). BIM-integrated LCA framework for prefabricated buildings with
  automated benchmarking and visual decision support. *Building and Environment* 286, 113689.
  https://doi.org/10.1016/j.buildenv.2025.113689
- Crawford RH, Stephan A, Prideaux F (2019). Environmental Performance in Construction (EPiC) Database. The
  University of Melbourne.
- Jones C, Hammond G (2019). Inventory of Carbon and Energy (ICE) Database, Version 3.0. Circular Ecology.
- EN 15978:2011. Sustainability of construction works: assessment of environmental performance of buildings.
- TunCO2 Pro (tunnels): https://github.com/qbzhang666/TunCO2-Pro

The example building in `examples.py` is synthetic. No project data are bundled; `docs/CASE_STUDY.md` describes how
the case of Ma et al. (2025) is reproduced from its own files.

## Disclaimer

BuildCO2 Pro is research and teaching software. Its results are estimates that depend on the model or take-off,
the factor set and the assumptions of the project file; they are not a certified life-cycle assessment or an
environmental product declaration, and should be checked by a qualified practitioner before they are used in
design, procurement or reporting. The software is provided under the MIT licence, without warranty of any kind.
