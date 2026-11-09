"""Validated weighted complete paths and stage marginals for alluvial plots."""
from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np
import pandas as pd

from data_visuals.compute.chord import _finite, _node, _plain, node_order


def _sum(values):
    try:
        total = math.fsum(float(value) for value in values)
    except (OverflowError, ValueError) as exc:
        raise ValueError("[alluvial] Weight totals must remain finite; rescale the weight unit explicitly.") from exc
    if not math.isfinite(total):
        raise ValueError("[alluvial] Weight totals must remain finite; rescale the weight unit explicitly.")
    return total


def validate_alluvial_input(df, mapping, *, stage_titles=None, note=None, order=None):
    errors = []
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        return ["[alluvial] Data must have unique column names."]
    if not isinstance(mapping, Mapping):
        return ["[alluvial] Map stages and value to existing columns."]
    stages, value = mapping.get("stages"), mapping.get("value")
    if (not isinstance(stages, (list, tuple)) or not 2 <= len(stages) <= 8
            or not all(isinstance(stage, str) and stage in df for stage in stages)
            or len(set(stages)) != len(stages)):
        return ["[alluvial] stages must name 2–8 distinct existing columns in stage order."]
    if not isinstance(value, str) or value not in df or value in stages:
        errors.append("[alluvial] value must name a separate numeric weight column.")
    if stage_titles is not None and (
            not isinstance(stage_titles, (list, tuple)) or len(stage_titles) != len(stages)
            or not all(isinstance(title, str) and title.strip() for title in stage_titles)):
        errors.append("[alluvial] stage_titles must contain one nonempty title per stage.")
    if note is not None and not isinstance(note, str):
        errors.append("[alluvial] note must be a string or None.")
    if df.empty:
        errors.append("[alluvial] Supply at least one complete path.")
    if not all(_node(item) for stage in stages for item in df[stage].tolist()):
        errors.append("[alluvial] Each stage requires nonempty string or finite numeric category IDs.")
    elif order is not None and (
            not isinstance(order, (list, tuple)) or not all(_node(item) for item in order)
            or len(set(order)) != len(order) or set(order) != set(df[stages[0]])):
        errors.append("[alluvial] order must contain every observed initial category exactly once.")
    if isinstance(value, str) and value in df and not all(_finite(item) and float(item) > 0 for item in df[value].tolist()):
        errors.append("[alluvial] Path weights must be finite positive real numbers.")
    return errors


def compute_alluvial(df, mapping, *, stage_titles=None, note=None, order=None):
    errors = validate_alluvial_input(df, mapping, stage_titles=stage_titles, note=note, order=order)
    if errors:
        raise ValueError("\n".join(errors))
    stages, value = list(mapping["stages"]), mapping["value"]
    categories = {stage: node_order(df[stage].tolist()) for stage in stages}
    if order is not None:
        categories[stages[0]] = [_plain(item) for item in order]
    ranks = {stage: {label: index for index, label in enumerate(categories[stage])} for stage in stages}
    weights = {}
    for row in df[[*stages, value]].itertuples(index=False, name=None):
        path = tuple(_plain(item) for item in row[:-1])
        weights.setdefault(path, []).append(float(row[-1]))
    rows = [(*path, _sum(amounts)) for path, amounts in sorted(
        weights.items(), key=lambda item: tuple(ranks[stage][label] for stage, label in zip(stages, item[0])))]
    result = pd.DataFrame(rows, columns=[*stages, value])
    total = _sum(result[value].tolist())
    marginals = []
    for stage in stages:
        nodes = [{"id": label, "weight": _sum(result.loc[result[stage] == label, value].tolist())}
                 for label in categories[stage]]
        marginals.append({"stage": stage, "nodes": nodes})
        if not math.isclose(math.fsum(node["weight"] / total for node in nodes), 1, abs_tol=1e-12):
            raise ArithmeticError("[alluvial] Every stage must conserve the complete path weight.")
    return result, {"alluvial": {"stages": stages, "marginals": marginals,
                                "total_weight": total, "path_count": len(result),
                                "segment_count": len(result) * (len(stages) - 1)}}


def alluvial_geometry(paths, mapping, payload):
    """Allocate one shared path slot per node, preserving adjacent flow widths."""
    stages, value = mapping["stages"], mapping["value"]
    totals = {item["stage"]: {node["id"]: node["weight"] for node in item["nodes"]}
              for item in payload["marginals"]}
    categories = {stage: tuple(totals[stage]) for stage in stages}
    count = max(map(len, categories.values()))
    extent, top = .79, .885
    gap = min(.030, extent / (2 * max(1, count - 1)))
    available = extent - gap * (count - 1)
    total = payload["total_weight"]
    ranks = {stage: {label: index for index, label in enumerate(categories[stage])} for stage in stages}
    nodes, slots = {}, {}
    for position, stage in enumerate(stages):
        neighbors = list(stages[position + 1:position + 2]) + list(stages[max(0, position - 1):position])
        sort_keys = list(dict.fromkeys((stages[0], *neighbors, *stages)))
        indices = sorted(paths.index, key=lambda index: tuple(ranks[key][paths.at[index, key]] for key in sort_keys))
        height = available + gap * (len(categories[stage]) - 1)
        cursor = top - (extent - height) / 2
        for label in categories[stage]:
            stop = cursor - totals[stage][label] / total * available
            nodes[stage, label] = (stop, cursor)
            inner = cursor
            for index in indices:
                if paths.at[index, stage] == label:
                    low = inner - float(paths.at[index, value]) / total * available
                    if low >= inner:
                        raise ValueError("[alluvial] The weight dynamic range produces a zero-height path slot; rescale or combine weights explicitly.")
                    slots[stage, index] = (low, inner)
                    inner = low
            if not np.isclose(inner, stop, atol=1e-12):
                raise ArithmeticError("[alluvial] Path slots must fill their node.")
            cursor = stop - gap
    return categories, totals, nodes, slots
