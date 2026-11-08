"""Native raincloud declaration over every selected paired difference."""


def add_panel(slot, bundle, support, *, title=None):
    counts = {len(bundle["groups"][name]) for name in bundle["names"]}
    sample_note = (f"{next(iter(counts))} pairs / dataset" if len(counts) == 1
                   else "all paired observations")
    slot.set("raincloud", x="dataset", y="difference_pp", group="dataset",
             order=list(bundle["names"]), title=title or "Raincloud: shape, points and spread",
             where={"record_type": "observation", "condition": bundle["condition"]},
             chart_opts={"xlabel": "Paired change: B - A (pp)", "ylabel": "",
                         "summary_format": "+.2f", "summary_text": "median (pp)",
                         "reference": 0,
                         "note": f"Condition {bundle['condition']}  |  {sample_note}",
                         "key": "Density + observations + median / IQR"})
