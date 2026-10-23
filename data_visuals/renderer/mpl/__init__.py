"""
renderer/mpl/__init__.py
========================
Matplotlib backend for data_visuals — renders FigureSpec via absolute-canvas mode.

Architecture:
    canvas.py   — FigureSpec → matplotlib Figure  (top-level orchestrator)
    config.py   — theme JSON → matplotlib rcParams / style mapping
    legend.py   — fig.legend() wrapping + reference-line entries
    export.py   — SVG / PDF / PNG save
    charts/     — per-chart-type draw functions (bar, line, scatter, box, …)

Rules (NON-NEGOTIABLE):
    1. NEVER call tight_layout(), constrained_layout(), or bbox_inches="tight".
    2. Every axes uses explicit placement within FigureSpec grid geometry.
       Measured decoration extents are aligned by layout/placement.py.
    3. Font sizes come from SubplotSpec.font_sizes (layout/sizing.py is the single source).
    4. Colour palettes come from utils/colors.py + themes/general.json.
    5. Statistics are consumed from computed_data / derived_data (compute/ layer).
"""

from data_visuals.renderer.mpl.canvas import figure_to_matplotlib
from data_visuals.renderer.mpl.export import save, to_svg, to_png, to_pdf
