"""Command line.

  buildco2pro serve                                   browser dashboard at http://127.0.0.1:8000
  buildco2pro inventory a.ifc b.ifc -o inventory.csv  inventory from IFC files (or a take-off CSV/XLSX, or a .pbix)
  buildco2pro assess inventory.csv [-p project.json] [-o report.xlsx] [--checks]
  buildco2pro tag model.ifc [-p project.json] -o model_carbon.ifc
  buildco2pro figures inventory.csv [-p project.json] -o figures
  buildco2pro example [-o DIR]                        the synthetic example: inventory, project, report
  buildco2pro defaults                                print the default project JSON
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _load_inventory(paths):
    from .inventory import Inventory, from_ifc, from_pbix, from_takeoff_csv
    inv = Inventory()
    for p in paths:
        low = p.lower()
        if low.endswith(".ifc"):
            inv.extend(from_ifc(p))
        elif low.endswith(".pbix"):
            inv.extend(from_pbix(p)[0])
        elif low.endswith((".xlsx", ".xlsm")):
            from .api import _from_xlsx
            inv.extend(_from_xlsx(p, Path(p).name))
        elif low.endswith(".csv"):
            head = Path(p).read_text(encoding="utf-8")[:400]
            inv.extend(Inventory.from_csv(p) if "material_class" in head and "rule" in head else from_takeoff_csv(p))
        else:
            raise SystemExit(f"{p}: use .ifc, .csv, .xlsx or .pbix")
    return inv


def _project(path):
    from .models import ProjectInput
    return ProjectInput.model_validate_json(Path(path).read_text()) if path else ProjectInput()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="buildco2pro", description="Upfront carbon (EN 15978 A1-A5) of buildings")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve"); s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-browser", action="store_true")
    i = sub.add_parser("inventory"); i.add_argument("inputs", nargs="+"); i.add_argument("-o", "--csv", required=True)
    a = sub.add_parser("assess"); a.add_argument("inputs", nargs="+"); a.add_argument("-p", "--project")
    a.add_argument("-o", "--xlsx"); a.add_argument("--checks", action="store_true")
    t = sub.add_parser("tag"); t.add_argument("ifc"); t.add_argument("-p", "--project"); t.add_argument("-o", "--out", required=True)
    f = sub.add_parser("figures"); f.add_argument("inputs", nargs="+"); f.add_argument("-p", "--project")
    f.add_argument("-o", "--dir", default="figures"); f.add_argument("-f", "--formats", nargs="*", default=["pdf", "png"])
    e = sub.add_parser("example"); e.add_argument("-o", "--dir", default="example_output")
    sub.add_parser("defaults")
    args = ap.parse_args(argv)

    if args.cmd == "serve":
        from .api import run
        run(args.host, args.port, not args.no_browser); return 0
    if args.cmd == "defaults":
        from .models import ProjectInput
        print(ProjectInput().model_dump_json(indent=2)); return 0
    from .carbon import assess
    from .checks import run as checks
    from .factors import FactorLibrary
    if args.cmd == "example":
        from .examples import example_inventory, example_project
        from .report import build_workbook
        out = Path(args.dir); out.mkdir(parents=True, exist_ok=True)
        inv, p = example_inventory(), example_project(); lib = FactorLibrary(p.factor_set, p.factor_overrides)
        inv.to_csv(out / "example_inventory.csv"); (out / "example_project.json").write_text(p.model_dump_json(indent=2))
        res = assess(p, inv, lib); (out / "example_report.xlsx").write_bytes(build_workbook(p, res, lib, checks(inv, lib)))
        _print(p, res); print("Written:", out); return 0
    if args.cmd == "inventory":
        inv = _load_inventory(args.inputs); inv.to_csv(args.csv)
        n = sum(bool(r.material_class) for r in inv.rows)
        print(f"{len(inv)} rows, {n} classified; written {args.csv}"); return 0
    p = _project(args.project); lib = FactorLibrary(p.factor_set, p.factor_overrides)
    if args.cmd == "tag":
        from .ifcexport import tag_ifc
        from .inventory import from_ifc
        n = tag_ifc(args.ifc, args.out, from_ifc(args.ifc), lib, p); print(f"{n} elements tagged; written {args.out}"); return 0
    inv = _load_inventory(args.inputs); res = assess(p, inv, lib)
    if args.cmd == "figures":
        from . import figures as F
        out = Path(args.dir); out.mkdir(parents=True, exist_ok=True)
        for name in F.FIGURES:
            try:
                for fmt in args.formats:
                    (out / f"{name}.{fmt}").write_bytes(F.render(name, res, fmt, inv=inv))
                print("wrote", out / name)
            except ValueError as err:
                print(f"skipped {name}: {err}")
        return 0
    _print(p, res)
    ck = checks(inv, lib)
    if args.checks:
        for c in ck:
            print(f"  [{c['check']}] {c['finding']}  {c['estimate']}")
    if args.xlsx:
        from .report import build_workbook
        Path(args.xlsx).write_bytes(build_workbook(p, res, lib, ck)); print("Report written:", args.xlsx)
    return 0


def _print(p, res):
    print(f"{p.name}: {res.total_t:,.0f} tCO2e A1-A5, {res.per_m2_kg:,.0f} kgCO2e/m2 GFA ({res.factor_set})")
    for m, v in res.modules_t.items():
        print(f"  {m:6s} {v:12,.1f} tCO2e")
    for w in res.warnings:
        print("  ! " + w)


if __name__ == "__main__":
    sys.exit(main())
