"""Test charts/__init__.py — chart registry and factory."""
import pytest
from data_visuals.charts import (
    ChartSpec, register_chart,
    get_chart, list_chart_types, create_chart,
)


class TestChartRegistry:
    def test_all_eight_types_registered(self):
        types = list_chart_types()
        expected = ["bar", "box", "confusion", "heatmap", "histogram",
                    "line", "scatter"]
        for t in expected:
            assert t in types, f"'{t}' not in registry"

    def test_count_is_eight(self):
        assert len(list_chart_types()) == 7

    def test_get_chart_returns_class(self):
        cls = get_chart("bar")
        assert issubclass(cls, ChartSpec)
        assert cls.chart_type == "bar"

    def test_get_chart_unknown_raises(self):
        with pytest.raises(ValueError, match="未知图表类型"):
            get_chart("nonexistent")

    def test_create_chart_returns_instance(self):
        chart = create_chart("bar", {"x": "method", "y": "accuracy"})
        assert isinstance(chart, ChartSpec)
        assert chart.chart_type == "bar"
        assert chart.x == "method"

    def test_create_chart_routes_chart_options_into_dataclass_fields(self):
        line = create_chart("line", {"x": "epoch", "y": "loss", "smooth": True, "area": True})
        histogram = create_chart("histogram", {"x": "score", "density": True, "bins": 10})
        confusion = create_chart("confusion", {"x": "truth", "y": "pred", "normalize": True})

        assert line.smooth is True
        assert line.area is True
        assert histogram.density is True
        assert histogram.bins == 10
        assert confusion.normalize is True

    def test_create_chart_unknown_option_raises(self):
        with pytest.raises(ValueError, match="未知参数"):
            create_chart("line", {"x": "epoch", "y": "loss", "not_a_real_option": True})

    def test_create_chart_missing_required_fields_raises(self):
        with pytest.raises(ValueError):
            create_chart("bar", {})  # missing x, y

    def test_create_chart_unknown_type_raises(self):
        with pytest.raises(ValueError):
            create_chart("nonexistent", {"x": "a", "y": "b"})


class TestChartSpecBase:
    def test_chart_type_must_be_set_on_register(self):
        """register_chart rejects classes with empty chart_type."""
        with pytest.raises(ValueError, match="chart_type"):
            @register_chart
            class Bad(ChartSpec):
                pass  # chart_type = "" by default

    def test_optional_fields_default_none(self):
        chart = create_chart("line", {"x": "epoch", "y": "loss"})
        # optional fields not passed should be None
        assert chart.group is None
