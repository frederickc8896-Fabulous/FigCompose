"""Native FigCompose boxes of the original paired differences."""


def add_panel(slot, bundle, support, *, title=None):
    names = bundle["names"]
    step = .6 / len(names)
    positions = [(index - (len(names) - 1) / 2) * step for index in range(len(names))]
    slot.box(x="condition", y="difference_pp", group="dataset", title=title,
             where={"record_type": "observation", "condition": bundle["condition"]},
             chart_opts={
                 "xlabel": "Dataset", "ylabel": "Paired change: B - A (pp)",
                 "xticks": positions, "xticklabels": list(names),
                 "xlim": (-.42, .42), "ylim": bundle["focus_limits"],
                 "guides": [{"axis": "y", "value": 0, "linestyle": "--",
                             "color": "#8993a1", "linewidth": .7}],
             })
