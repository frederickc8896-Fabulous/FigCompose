"""Native ridgeline declaration; one real distribution per condition."""


def add_panel(slot, bundle, support, *, title=None):
    selected = bundle["ridge_dataset"]
    counts = {len(bundle["ridge"][condition]) for condition in bundle["conditions"]}
    sample_note = (f"{next(iter(counts))} pairs per condition" if len(counts) == 1
                   else "sample sizes shown per condition")
    slot.set("ridgeline", x="condition", y="difference_pp", group="dataset",
             order=list(bundle["conditions"]), title=title or "Ridgeline: changing distributions",
             where={"record_type": "observation", "dataset": selected},
             chart_opts={"xlabel": "Paired change: B - A (pp)", "ylabel": "Condition",
                         "reference": 0, "note": f"{selected}  |  {sample_note}",
                         "key": "KDE ridges scaled to equal height"})
