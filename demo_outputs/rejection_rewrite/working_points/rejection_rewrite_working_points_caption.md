# Fixed-reference-threshold operating-point shifts

**Figure caption.** Actual operating points under rejection-description rewrites at a fixed reference threshold. Columns show xsmall, small, and RoBERTa; rows show Single-phrase and Multi-phrase training. Each description marker is the mean over five seeds (0, 7, 42, 99, 127). The eight rewrites share these same trained models. Each rewrite uses the threshold calibrated under the reference description for the same checkpoint; thresholds are not recalibrated for the rewrites. The blue star denotes the reference description, orange circles the eight individual rewrites, and the open orange diamond their overall mean. The mean is calculated by averaging the eight rewrites within each seed, then averaging over the five seeds. Arrows point from the reference point to this mean. All panels share the same axis limits. The dashed line marks the 5% reference ID calibration budget; it does not imply that the actual ID false-rejection rate is 5% in every condition. The AUROC annotations report the reference mean and the equally weighted rewrite mean to three decimal places. The main figure omits rewrite numbers to reduce annotation clutter; an optional numbered companion identifies the same rewrite in all six panels. Only labels are displaced; marker coordinates are never jittered. Seed uncertainty is reported by paired confidence intervals in the main text and supplementary appendix, rather than error bars here. This figure supports inspection of operating-point shifts, description heterogeneity, and residual changes after training. Actual false-rejection rates can differ between rows; equal-false-rejection comparisons are supported by the independent diagnostic in §4.2.

## Rewrite numbering

Reference: `REF_none` — The text is about none of these topics.

| Number | Description ID | Original wording |
|---|---|---|
| 1 | `OUT_nomatch` | The text does not match any supported request. |
| 2 | `OUT_outside` | This text falls outside the supported topics. |
| 3 | `OUT_unrelated` | The text is unrelated to any supported topic. |
| 4 | `OUT_notinlist` | The text is about a topic that is not in the list above. |
| 5 | `OUT_notabout` | The text is not about any supported topic. |
| 6 | `OUT_notamong` | This request is not among the supported ones. |
| 7 | `OUT_concerns` | The text concerns a topic outside the supported set. |
| 8 | `OUT_otherthan` | The text is about something other than the supported topics. |

## Data and reproduction

- Source: `rejection_rewrite_plot_data.csv`; the manifest records its full path and SHA-256.
- Filter: `score=p_none`, `policy=fixed`, `reference_budget=0.05`, `pool in {REF, OUT}`.
- All 270 selected rows participate: 6 conditions × 5 seeds × (1 reference + 8 rewrites).
- There are 60 plotted markers: 6 × (1 reference + 8 rewrites + 1 derived mean).
- Axes display the supplied percentage columns directly; no additional multiplication by 100.
- The selected CSV values are checked for a common `tau_reference` within each model/seed condition.
- Figure: 7 × 4.5 inches; Times New Roman; all visible text at least 8 pt; editable vector PDF/SVG and 300 DPI PNG.
- Run: `python demo/demo_rejection_rewrite.py`.
- Add `--numbered` to also export the numbered PDF/SVG/PNG companion.
- Uses `Figure → compute → physical layout → Matplotlib renderer → export`. Per-panel `where`, grouped marker styles, guides, arrows, optional point labels, and shared facet decorations are reusable library features; this script declares no axes coordinates or margins.
