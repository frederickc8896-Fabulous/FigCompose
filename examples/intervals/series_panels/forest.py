"""Native estimates and supplied paired-t confidence intervals."""


def add_panel(slot, bundle, support, *, title=None):
    names = bundle["names"]
    slot.scatter(x="condition", y="difference_pp", group="dataset", title=title,
                 where={"record_type": "estimate"}, chart_opts={
                     "xlabel": "Evaluation condition", "ylabel": "Mean change: B - A (pp)",
                     "opacity": 1, "x_offsets": {
                         name: (index - (len(names) - 1) / 2) * 6
                         for index, name in enumerate(names)},
                     "series_styles": {name: {"marker": "o", "size": 27,
                                              "edgecolor": "white", "linewidth": .6}
                                       for name in names},
                     "errorbar": {"lower": "ci95_lower_pp", "upper": "ci95_upper_pp",
                                  "capsize": 2.2, "linewidth": 1.1, "alpha": .9},
                     "xticks": list(bundle["conditions"]),
                     "guides": [{"axis": "y", "value": 0, "linestyle": "--",
                                 "color": "#8993a1", "linewidth": .7}],
                 })
