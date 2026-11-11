# Bundled Tinos fonts

These unmodified fonts provide an offline, Times-compatible fallback when the
requested system Times New Roman font is unavailable. Available explicit font
choices retain priority. Math expressions continue to use Matplotlib's STIX.

The four faces are Regular, Bold, Italic and Bold Italic, version 1.340. Their
source is [googlefonts/tinos](https://github.com/googlefonts/tinos/tree/3b4482a99b80ea5fc75f187b1be3120a3f5905b3),
commit `3b4482a99b80ea5fc75f187b1be3120a3f5905b3`, under `fonts/ttf/`.
`SOURCE.json` records the original paths, byte sizes, SHA-256 hashes and Git blob
hashes. The included `OFL.txt` is copied from the same source commit.

Copyright 2026 The Tinos Project Authors (https://github.com/googlefonts/tinos).
The fonts remain under the SIL Open Font License 1.1; FigCompose's Python source
remains under Apache License 2.0. Keep `OFL.txt` with redistributed font files.

Tinos is a separate typeface designed to be metrically compatible with Times New
Roman. Publications requiring Times New Roman by name still need that font.
Tinos does not supply Chinese glyphs; select a suitable installed font for Chinese
text. Fonts register only in the current Python process, with no system install
or runtime download.

PNG output contains rendered pixels and PDF embeds the font. Default SVG keeps
editable text and requires the viewing application to have the font available.
For SVG outlines, save the rendered Matplotlib Figure inside
`matplotlib.rc_context({"svg.fonttype": "path"})`.
