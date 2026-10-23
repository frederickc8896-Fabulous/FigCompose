# Matched-ID training differences

**Figure caption.** Leakage differences between Multi-phrase and Single-phrase training at matched actual ID false-rejection rates, for (a) near-OOD and (b) far-OOD. Negative values favor Multi-phrase. Each panel shows three backbones at four matched nodes (0.875%, 1.875%, 4.875%, and 9.875%), for 12 estimates and intervals per panel. Colors and marker shapes identify the same backbone in both panels. Intervals are the supplied 95% paired-seed bootstrap CIs, based on five paired seeds and 5,000 replicates, for the eight OUT descriptions with score=p_none and policy=test_id_oracle. All 24 source rows and their asymmetric interval endpoints are retained without recalculation. The Test-ID oracle diagnostic is separate from the fixed-reference-threshold rewrite experiment. All point estimates are negative, but two near-OOD intervals and one far-OOD interval contain zero; the figure therefore does not establish a nonzero effect in every condition.

## Axis and rendering choices

- The two panels share actual numeric X positions and identical Y limits, with a zero guide.
- The four nodes are not equally spaced. Groups are offset by −4, 0, and +4 physical points only for legibility; markers and intervals use the same transform, and numeric source X values are unchanged.
- Tick text is rounded to two decimals to keep the nearby first two nodes legible; tick coordinates and the exact three-decimal node values stated above remain unchanged.
- Only the lower panel shows the shared X-axis labels; a single legend appears below them.
- The canvas matches the supplied reference: 3.4 × 4.45 inches (86.36 × 113.03 mm), 1020 × 1335 pixels at 300 DPI. Text uses Times New Roman at 8 pt or larger.
- Uses the existing Figure/scatter/facets/style/guide/export pipeline, with reusable asymmetric scatter intervals and a measured bottom shared legend. No axes positions are set in this demo.

## Reproduction and provenance

`python demo/demo_matched_training.py`

Input CSV SHA-256: `6d7b3d48eccedbe9362ae007311d9dc0ff613970cd2a7a936835e99b96e16362`.

The original JSON path and checksum are provenance declarations in the CSV. The original JSON and paired seed observations were not supplied, so the bootstrap procedure is not independently reconstructed here.
