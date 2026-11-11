"""Register the bundled Times-compatible font only when it is requested."""

from pathlib import Path
from threading import Lock

from matplotlib import font_manager


_FONT_DIRECTORY = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "tinos"
_FONT_FILES = (
    "Tinos-Regular.ttf", "Tinos-Bold.ttf",
    "Tinos-Italic.ttf", "Tinos-BoldItalic.ttf",
)
_REGISTRATION_LOCK = Lock()


def register_tinos() -> str:
    """Make all four packaged faces available to the current FontManager.

    Registration stays in this process and does not install system fonts. Check
    the current manager each time so replacing Matplotlib's cache/manager works
    as well as repeated renders. Prefer these files over a system Tinos version.
    """
    with _REGISTRATION_LOCK:
        manager = font_manager.fontManager
        by_path = {str(font.fname): font for font in manager.ttflist}
        entries = []
        for filename in _FONT_FILES:
            path = str(_FONT_DIRECTORY / filename)
            entry = by_path.get(path)
            if entry is None:
                manager.addfont(path)
                entry = manager.ttflist[-1]
            entries.append(entry)
        if manager.ttflist[:len(entries)] != entries:
            identities = {id(entry) for entry in entries}
            manager.ttflist[:] = entries + [
                entry for entry in manager.ttflist if id(entry) not in identities
            ]
            # addfont clears this cache before we reorder; clear it again so an
            # earlier same-name system-font lookup cannot retain precedence.
            manager._findfont_cached.cache_clear()
    return "Tinos"
