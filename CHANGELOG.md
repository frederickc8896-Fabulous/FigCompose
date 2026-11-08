# Changelog

## 0.2.0 — 2026-11-08

- Add eight native chart kinds: `chord`, `raincloud`, `ridgeline`, `paired`,
  `estimation`, `scatter3d`, `waterfall3d` and `bar3d`, bringing the total to 19.
- Add the `showcase` presentation style and native top/inline circular-bar mean
  summaries. Existing paper font defaults and curated palette order are preserved.
- Keep statistics in the compute layer, require explicit pair identity and CI
  choices, and support JSON-serializable specifications for all native kinds.
- Preserve series colors and order across filtered data, display-name aliases,
  target-only chord nodes and mixed 2D/3D figures.
- Measure projected 3D axis titles, exclude inactive cached ticks from reports,
  and sort stacked cuboid faces and scatter marker identities together.
- Migrate the circular-score, chord, paired-data series and 2D/3D examples to
  native declarations; include enlarged comparison panels and updated exports.
- Shorten the usage reference and document configurable colors, fonts, canvas,
  legends and chart options. Add installed-package checks for the new native kinds.

## 0.1.2

- Publish native circular bars, 13 curated palettes and eight reproducible examples.

## 0.1.1

- Initial published release.
