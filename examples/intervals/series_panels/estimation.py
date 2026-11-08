"""Native paired estimation with the original supplied confidence bounds."""


def add_panel(slot, bundle, support, *, title=None):
    name = bundle["ridge_dataset"]
    count = len(bundle["paired_values"][name][0])
    slot.set("estimation", pair="paired_run", x="measurement", y="measurement_value", group="dataset",
             lower="ci95_lower_pp", upper="ci95_upper_pp", confidence=.95, order=["A", "B"],
             density_range=tuple(bundle["focus_limits"]),
             title=title or "Paired estimation",
             where={"record_type": "paired_observation", "condition": bundle["condition"], "dataset": name},
             chart_opts={"xlabel": "", "ylabel": "Accuracy (%)", "summary_format": "+.2f",
                         "difference_label": "Paired change B - A (pp)", "difference_unit": "pp",
                         "xticks": [0, 1, 2.30], "xticklabels": ["Method A", "Method B", "Paired change"],
                         "note": f"{name}  |  condition {bundle['condition']}  |  {count} pairs"})
