# Reading view: rejection-description changes at a fixed reference threshold

**Figure caption.** Columns separate the two consequences of changing rejection wording: in-domain false rejections (left) and near-OOD leakage, i.e. inputs accepted (right). Both horizontal axes show actual percentages, with lower values preferred; their ranges differ between metrics but are fixed across backbones. Rows are backbones; within each panel the upper track is Single-phrase training and the lower track is Multi-phrase training. Blue stars are reference descriptions; open orange diamonds are means over eight rewrites. Arrows and printed values read reference → rewrite mean. Signed changes are in percentage points (pp), not relative percent changes. Small open orange circles just below each track show all eight individual rewrite means; coinciding rates may overlap. Their vertical offset distinguishes marker roles and does not encode another metric or uncertainty. Each description mean uses five shared seeds; rewrite means first average eight rewrites within each seed and then average the five seeds. All 270 selected source rows participate. For each checkpoint, rewrites use its reference-calibrated threshold without recalibration. The 5% dashed guide appears only in the ID column and denotes the reference calibration budget. Uncertainty is addressed by paired intervals in the main text and appendix, not by these eight points. This figure describes operating-point shifts; it does not establish benefits at equal ID false rejection. Those comparisons remain the separate diagnostic in §4.2.

## Observed mean changes

Across these backbones, rewrites reduce ID false rejection while increasing near-OOD leakage. The leakage increases are +34.0–36.4 pp for Single-phrase and +4.2–9.2 pp for Multi-phrase. Multi-phrase has smaller mean shifts in these data, with residual variation; this statement does not compare the methods at matched actual false-rejection rates.

## Numeric audit and ranking quality

AUROC is retained here and in the original joint operating-point figure so it does not compete with the main reading of decision consequences.

| Backbone | Training | ID reference → mean (%) | Δ ID (pp) | Near-OOD reference → mean (%) | Δ Near-OOD (pp) | AUROC reference → mean |
|---|---|---|---|---|---|---|
| xsmall | Single-phrase | 5.35 → 1.22 | −4.13 | 27.3 → 63.7 | +36.4 | 0.937 → 0.931 |
| xsmall | Multi-phrase | 4.48 → 3.02 | −1.46 | 27.5 → 36.7 | +9.2 | 0.933 → 0.933 |
| small | Single-phrase | 3.75 → 0.83 | −2.92 | 37.0 → 71.7 | +34.7 | 0.925 → 0.916 |
| small | Multi-phrase | 5.18 → 3.53 | −1.65 | 29.2 → 38.2 | +9.0 | 0.931 → 0.931 |
| RoBERTa | Single-phrase | 5.55 → 1.46 | −4.09 | 23.4 → 57.4 | +34.0 | 0.918 → 0.914 |
| RoBERTa | Multi-phrase | 4.55 → 3.36 | −1.19 | 25.2 → 29.4 | +4.2 | 0.919 → 0.930 |

## Reproduction

- `python demo/demo_rejection_rewrite_comparison.py`.
- Full `Figure → compute → physical layout → renderer → export` pipeline; 7 × 4.5 in; Times New Roman; minimum visible type 8 pt; vector PDF/SVG and 300 DPI PNG.
- 120 displayed markers are two projections of the same 60 scientific points, not additional samples.
- Original joint view: [PDF](../working_points/rejection_rewrite_working_points.pdf); original wording map: [CSV](../working_points/rejection_rewrite_working_points_rewrite_mapping.csv).
- Source SHA-256: `a45c7659d7af358a3530208f777457c1675a97ac89cb825be9bbe18056159863`.
