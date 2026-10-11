"""Publication figures from an assessment, in the style of the textbook (Latin Modern Sans, thin marks, panel
letters and axis labels only; captions belong to the document). Requires matplotlib.
"""
from __future__ import annotations

import io
from pathlib import Path

FONT_DIR = Path(__file__).parent / "data" / "fonts"
C = {"Steel": "#B5452E", "Aluminium": "#4F86C6", "Concrete": "#9AA0A8", "Glass": "#7FB7C9", "Timber": "#C8871E",
     "Plasterboard": "#D8C6A8", "Masonry and stone": "#7551A8", "Plastics and rubber": "#4E9A68", "Other": "#5A5F68",
     "ink": "#30343B", "ink2": "#5A5F68", "grid": "#E2E4E7"}
W = 6.3
FIGURES = {"modules": "Upfront carbon by module, A1-A3 to A5r",
           "elements": "A1-A3 by element category and material group",
           "materials": "A1-A3 and mass by material group",
           "storeys": "A1-A3, A4 and A5w against the number of storeys",
           "checks": "Equivalent solid thickness of sheet products against a plausible bound"}
_ready = False


def _plt():
    global _ready
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if not _ready:
        from matplotlib import font_manager
        for f in FONT_DIR.glob("*.ttf"):
            font_manager.fontManager.addfont(str(f))
        fam = "LMSans10TT" if any(FONT_DIR.glob("*.ttf")) else "DejaVu Sans"
        plt.rcParams.update({"font.family": fam, "font.size": 8.5, "axes.labelsize": 8.5, "xtick.labelsize": 8,
                             "ytick.labelsize": 8, "legend.fontsize": 8, "axes.edgecolor": C["ink2"], "axes.linewidth": 0.6,
                             "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
                             "pdf.fonttype": 42, "svg.fonttype": "path", "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
                             "axes.unicode_minus": False})
        _ready = True
    return plt


def _grid(ax, axis="y"):
    getattr(ax, f"{axis}axis").grid(True, color=C["grid"], lw=0.5); ax.set_axisbelow(True)


def make_modules(res, p=None, inv=None):
    plt = _plt(); fig, ax = plt.subplots(figsize=(W * 0.6, 2.4))
    ks = list(res.modules_t); vs = [res.modules_t[k] / 1e3 for k in ks]
    ax.bar(ks, vs, color=C["ink2"], width=0.6); _grid(ax)
    ax.set_ylabel("Upfront carbon, $E$ (ktCO$_2$e)")
    return fig


def make_elements(res, p=None, inv=None):
    plt = _plt(); cats = [c for c in res.a1a3_by_category][:12][::-1]; grps = list(res.a1a3_by_group)
    fig, ax = plt.subplots(figsize=(W, 0.28 * len(cats) + 1.0)); left = [0.0] * len(cats)
    for g in grps:
        v = [res.a1a3_by_category_group.get(f"{c}|{g}", 0.0) / 1e3 for c in cats]
        ax.barh(cats, v, left=left, color=C.get(g, C["Other"]), label=g, height=0.65)
        left = [a + b for a, b in zip(left, v)]
    _grid(ax, "x"); ax.set_xlabel("A1-A3 carbon, $E$ (ktCO$_2$e)")
    ax.legend(ncol=4, loc="lower right", bbox_to_anchor=(1, 1.0)); return fig


def make_materials(res, p=None, inv=None):
    plt = _plt(); fig, axs = plt.subplots(1, 2, figsize=(W, 2.6))
    g = list(res.a1a3_by_group)
    for ax, vals, lab, let in ((axs[0], [res.a1a3_by_group[k] / 1e3 for k in g], "A1-A3 carbon, $E$ (ktCO$_2$e)", "a"),
                               (axs[1], [res.mass_by_group_t.get(k, 0) / 1e3 for k in g], "Mass, $m$ (kt)", "b")):
        ax.barh(g[::-1], vals[::-1], color=[C.get(k, C["Other"]) for k in g[::-1]], height=0.65); _grid(ax, "x"); ax.set_xlabel(lab)
        ax.text(-0.02, 1.03, f"({let})", transform=ax.transAxes, ha="right", fontweight="bold")
    axs[1].set_yticklabels([]); fig.tight_layout(); return fig


def make_storeys(res, p=None, inv=None):
    if not res.storey_curve:
        raise ValueError("no storey roles in the project: set storeys.roles")
    plt = _plt(); fig, ax = plt.subplots(figsize=(W * 0.6, 2.6)); n = [r["storeys"] for r in res.storey_curve]
    ax.plot(n, [r["A1A3_t"] / 1e3 for r in res.storey_curve], color=C["Steel"], lw=1.2, label="A1-A3")
    ax.plot(n, [r["total_t"] / 1e3 for r in res.storey_curve], color=C["ink"], lw=1.2, ls="--", label="A1-A5w")
    _grid(ax); ax.set_xlabel("Number of storeys, $n$"); ax.set_ylabel("Upfront carbon, $E$ (ktCO$_2$e)"); ax.legend()
    return fig


def make_checks(res, p=None, inv=None):
    from collections import defaultdict
    from .checks import SHEET_CLASSES
    plt = _plt(); fig, ax = plt.subplots(figsize=(W, 2.6))
    if inv is None:
        raise ValueError("the checks figure needs the inventory")
    va = defaultdict(lambda: [0.0, 0.0])
    for r in inv.rows:
        if r.material_class in SHEET_CLASSES and r.area_m2 > 0:
            va[r.material_class][0] += r.volume_m3; va[r.material_class][1] += r.area_m2
    ks = [k for k in va if va[k][1] > 0]
    ax.bar(ks, [1e3 * va[k][0] / va[k][1] for k in ks], color=C["Aluminium"], width=0.55, label="Model")
    ax.scatter(ks, [SHEET_CLASSES[k] for k in ks], color=C["Steel"], marker="_", s=400, lw=2, label="Plausible bound", zorder=3)
    _grid(ax); ax.set_ylabel("Equivalent solid thickness, $V/A$ (mm)"); ax.legend(); plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    return fig


MAKERS = {"modules": make_modules, "elements": make_elements, "materials": make_materials, "storeys": make_storeys, "checks": make_checks}


def render(name, res, fmt="pdf", **kw) -> bytes:
    plt = _plt(); fig = MAKERS[name](res, inv=kw.get("inv"))
    buf = io.BytesIO(); fig.savefig(buf, format=fmt, dpi=1000 if fmt == "png" else None); plt.close(fig)
    return buf.getvalue()
