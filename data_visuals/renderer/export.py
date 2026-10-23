"""FigureSpec exports through the Matplotlib renderer."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Optional, Union


def _spec_to_dict(spec: Any) -> Dict[str, Any]:
    return spec.to_dict() if hasattr(spec, "to_dict") else spec


def _validate_backend(backend: str) -> None:
    if backend != "matplotlib":
        raise ValueError(f"Unknown backend {backend!r}. Only 'matplotlib' is supported.")


def _resolve_png_dpi(spec: Any, dpi: Optional[float], scale: Optional[float]) -> float:
    """Apply scale to the requested DPI, falling back to the figure setting."""
    resolved = dpi if dpi is not None else _spec_to_dict(spec).get("canvas", {}).get("dpi", 150)
    resolved = 150 if resolved is None else resolved
    multiplier = 1 if scale is None else scale
    for name, value in (("dpi", resolved), ("scale", multiplier)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive finite number")
    return resolved * multiplier


def to_svg(spec: Any, path: Union[str, Path], *, backend: str = "matplotlib", **kwargs: Any) -> None:
    """Save a vector SVG with fixed figure dimensions."""
    _validate_backend(backend)
    from data_visuals.renderer.mpl.export import to_svg as mpl_to_svg
    mpl_to_svg(spec, path, **kwargs)


def to_png(
    spec: Any, path: Union[str, Path], *, scale: Optional[float] = None,
    dpi: Optional[int] = None, backend: str = "matplotlib", **kwargs: Any,
) -> None:
    """Save PNG at (explicit DPI or FigureSpec DPI) multiplied by scale."""
    _validate_backend(backend)
    from data_visuals.renderer.mpl.export import to_png as mpl_to_png
    mpl_to_png(spec, path, scale=scale, dpi=dpi, **kwargs)


def to_pdf(spec: Any, path: Union[str, Path], *, backend: str = "matplotlib", **kwargs: Any) -> None:
    """Save vector PDF."""
    _validate_backend(backend)
    from data_visuals.renderer.mpl.export import to_pdf as mpl_to_pdf
    mpl_to_pdf(spec, path, **kwargs)


def save(
    spec: Any, path: Union[str, Path], *, scale: Optional[float] = None,
    dpi: Optional[int] = None, backend: str = "matplotlib", **kwargs: Any,
) -> None:
    """Choose SVG/PNG/PDF by suffix."""
    _validate_backend(backend)
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".svg":
        to_svg(spec, path, backend=backend, **kwargs)
    elif ext == ".png":
        to_png(spec, path, scale=scale, dpi=dpi, backend=backend, **kwargs)
    elif ext == ".pdf":
        to_pdf(spec, path, backend=backend, **kwargs)
    else:
        raise ValueError(f"Unsupported export format {ext!r}. Use .svg, .png or .pdf.")


def display(spec: Any, *, backend: str = "matplotlib", **kwargs: Any) -> None:
    """Display a Matplotlib figure inline and release it afterwards."""
    _validate_backend(backend)
    from IPython.display import display as display_inline
    import matplotlib.pyplot as plt
    from data_visuals.renderer.mpl.canvas import figure_to_matplotlib
    figure = figure_to_matplotlib(spec, **kwargs)
    try:
        display_inline(figure)
    finally:
        plt.close(figure)
