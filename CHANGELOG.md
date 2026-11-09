# Changelog

## 0.3.0 — 2026-11-09

- Add native `participant_tracks`, `clustered_heatmap` and `alluvial` chart kinds,
  bringing the total to 22. All three use the chart/compute/renderer pipeline and
  support JSON-serializable Figure specifications.
- Preserve unique participant identities, explicit numeric ranges and complete
  observations across aligned tracks and descriptive cohort summaries. Check
  rotated ID-label space before creating data artists and keep angular gaps
  within each participant sector; reject numeric ranges whose float64 span is
  nonpositive or nonfinite.
- Compute circular heatmaps from the supplied matrix with Ward/Euclidean linkage,
  optimal leaf ordering and distance-preserving radial branches. Retain raw
  values and expose separate cluster and continuous color overrides.
- Conserve complete-path weights across 2–8 alluvial stages. Reject unrepresentable
  zero-height slots, crowded node labels and overlapping stage titles. Keep
  registered initial-category order and color identities.
- Migrate the three public examples to native declarations and remove their old
  custom-panel modules. Expand the alluvial example to 1,200 simulated people,
  five stages and 60 complete paths, with a deterministic data generator and the
  original three-stage CSV retained.
- Fix color-domain lookup for partial subplot descriptions and verify all 22
  native kinds in the installed-package release checks. The 13 curated palettes,
  three styles and default Times New Roman typography remain available.
- Prefer Matplotlib's bundled STIXGeneral before generic `serif` when Times New
  Roman is unavailable, preserving available explicit font choices and the default
  STIX math font.

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
