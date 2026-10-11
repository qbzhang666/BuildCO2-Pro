# Third-party components

BuildCO2 Pro is released under the MIT licence. Its run-time dependencies are under licences compatible with it.

| Component | Licence | Use | Notes |
| --- | --- | --- | --- |
| pydantic | MIT | input models | |
| openpyxl | MIT | Excel report | |
| FastAPI, Starlette, Uvicorn, python-multipart | MIT / BSD-3-Clause / Apache-2.0 | API server | |
| IfcOpenShell (optional) | LGPL-3.0 | IFC import and export | Used unmodified, dynamically linked (pip wheel) |
| pbixray (optional) | MIT | reading Power BI files | |
| matplotlib (optional) | PSF-based | figures | |
| Apache ECharts (bundled) | Apache-2.0 | charts | `web/vendor/LICENSE-echarts.txt` |

Not used: Power BI, Revit (except to export IFC from the design team's models).

## Latin Modern Sans (data/fonts)

Latin Modern Sans 10 (regular, bold, oblique) as TrueType, by B. Jackowski and J. M. Nowacki (GUST e-foundry),
under the GUST Font License (GFL), which permits redistribution and embedding.

## Data

`data/factors.csv` holds the factor values used by Ma et al. (2025) from EPiC 2019 (Crawford, Stephan and Prideaux,
The University of Melbourne) and the ICE V3.0 alternative of the same dashboard (Jones and Hammond, Circular
Ecology), with their sources. Check the terms of each database before redistributing an extended library.
