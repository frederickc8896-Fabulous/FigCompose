"""Fixed-size SVG/PDF/PNG exports for the Matplotlib renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

import matplotlib
import matplotlib.pyplot as plt

from data_visuals.renderer.export import _resolve_png_dpi
from data_visuals.renderer.mpl.canvas import figure_to_matplotlib, DPI


def _render_fig(spec: Any, **kwargs: Any) -> Any:
    return figure_to_matplotlib(spec, **kwargs)


def _save(spec: Any, path: Union[str, Path], format: str, dpi: float, **kwargs: Any) -> None:
    """Preserve the complete design canvas, even with user savefig defaults."""
    figure = _render_fig(spec, **kwargs)
    try:
        # bbox_inches=None alone still inherits rcParams['savefig.bbox'].
        rcparams = dict(getattr(figure, "_data_visuals_rcparams", {}))
        rcparams.update({"savefig.bbox": None, "savefig.pad_inches": 0})
        metadata = {"Date": None} if format == "svg" else (
            {"CreationDate": None, "ModDate": None} if format == "pdf" else None)
        with matplotlib.rc_context(rcparams):
            figure.savefig(
                str(path), format=format, dpi=dpi,
                facecolor=figure.get_facecolor(), bbox_inches=None,
                metadata=metadata,
            )
    finally:
        plt.close(figure)


def to_svg(spec: Any, path: Union[str, Path], **kwargs: Any) -> None:
    """Save a vector SVG with fixed figure dimensions."""
    _save(spec, path, "svg", DPI, **kwargs)


def to_png(
    spec: Any, path: Union[str, Path], *,
    scale: Optional[float] = None, dpi: Optional[int] = None, **kwargs: Any,
) -> None:
    """Save PNG at (explicit DPI or FigureSpec DPI) multiplied by scale.

    Output DPI increases pixel density without changing physical dimensions.
    The renderer uses a 72-DPI design coordinate system.
    """
    _save(spec, path, "png", _resolve_png_dpi(spec, dpi, scale), **kwargs)


def to_pdf(spec: Any, path: Union[str, Path], **kwargs: Any) -> None:
    """Save a vector PDF with fixed figure dimensions."""
    _save(spec, path, "pdf", DPI, **kwargs)


def save(
    spec: Any, path: Union[str, Path], *, scale: Optional[float] = None,
    dpi: Optional[int] = None, **kwargs: Any,
) -> None:
    """Choose the static output format from the filename suffix."""
    ext = Path(path).suffix.lower()
    if ext == ".svg":
        to_svg(spec, path, **kwargs)
    elif ext == ".png":
        to_png(spec, path, dpi=dpi, scale=scale, **kwargs)
    elif ext == ".pdf":
        to_pdf(spec, path, **kwargs)
    else:
        raise ValueError(f"Matplotlib backend does not support {ext!r}. Use .svg, .png or .pdf.")
