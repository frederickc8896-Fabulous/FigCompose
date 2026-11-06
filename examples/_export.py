"""Shared export helper for the downloadable FigCompose examples."""
from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

from data_visuals import check_figure


def export_figure(paper, destination_dir, *, config=None, write_report=False):
    """Render once, check the actual layout, and save three full-canvas views.

    Uses the installed FigCompose package and Matplotlib's public Figure API.
    Full reports are optional so the examples stay small and easy to copy.
    """
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    rendered = paper.render()
    try:
        report = check_figure(rendered)
        report.raise_for_errors(include_warnings=True)
        if write_report:
            report.save(destination / "report.json")
        if config is not None:
            config.save(destination / "style.yaml")
        with matplotlib.rc_context({"savefig.bbox": None, "savefig.pad_inches": 0,
                                    "svg.fonttype": "path", "pdf.fonttype": 42,
                                    "text.usetex": False, "svg.hashsalt": "figcompose-examples"}):
            for filename, dpi in (("figure.png", 300), ("figure.svg", 72), ("preview.png", 120)):
                target = destination / filename
                rendered.savefig(target, dpi=dpi, bbox_inches=None,
                                 facecolor=rendered.get_facecolor(),
                                 metadata={"Date": None} if filename.endswith(".svg") else None)
                if filename.endswith(".svg"):
                    lines = target.read_text(encoding="utf-8").splitlines()
                    target.write_text("\n".join(line.rstrip() for line in lines) + "\n",
                                      encoding="utf-8", newline="\n")
        print(report.summary(), flush=True)
        return {"errors": len(report.errors), "warnings": len(report.warnings),
                "canvas_mm": [report.canvas["width_mm"], report.canvas["height_mm"]],
                "destination": str(destination.resolve())}
    finally:
        plt.close(rendered)
