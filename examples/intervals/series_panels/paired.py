"""Native complete-pair trajectories; no inferred matching or units."""


def add_panel(slot, bundle, support, *, title=None):
    slot.set("paired", pair="paired_run", x="measurement", y="measurement_value", group="dataset",
             order=["A", "B"], title=title or f"Paired trajectories | condition {bundle['condition']}",
             where={"record_type": "paired_observation", "condition": bundle["condition"]},
             chart_opts={"xlabel": "", "ylabel": "Accuracy (%)", "difference_unit": "pp",
                         "summary_format": "+.2f", "key": "Thin: paired runs   |   thick: means"})
