"""Reproduction of the dashboard of Ma et al. (2025) from its own take-off tables. The data are not bundled:
set BUILDCO2_CASE_TAKEOFF to the take-off CSV exported from the .pbix (``buildco2pro inventory LCA2.pbix``,
or the Power BI take-off CSV of the textbook's case folder)."""
import os

import pytest

from buildco2pro.carbon import assess
from buildco2pro.inventory import from_takeoff_csv
from buildco2pro.models import ProjectInput

P = os.environ.get("BUILDCO2_CASE_TAKEOFF")


@pytest.mark.skipif(not P or not os.path.exists(P or ""), reason="case take-off not available")
def test_power_bi_a1a3():
    r = assess(ProjectInput(gfa_m2=19000, compat_dashboard=True), from_takeoff_csv(P))
    # 39,190 tCO2e in the Power BI tables; with the lighting of the workbook, 42,366 t (paper 42,372.7 t)
    assert r.modules_t["A1-A3"] == pytest.approx(39190.4, rel=1e-4)
    # with the factor library instead of the take-off's own factors the result moves by about 1%
    lib = assess(ProjectInput(gfa_m2=19000), from_takeoff_csv(P)).modules_t["A1-A3"]
    assert lib == pytest.approx(39190, rel=0.02)
