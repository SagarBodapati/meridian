"""Chart generation — produces JSON-serialisable Plotly specs and SVG."""
import json
from dataclasses import dataclass
from typing import Any


@dataclass
class ChartSpec:
    """A portable chart description that the frontend can render via Plotly.js."""
    chart_type: str  # "bar", "line", "waterfall", "scatter"
    title: str
    plotly_json: str  # JSON string of a full Plotly figure dict


def time_series_chart(
    periods: list[str],
    values: list[float],
    title: str,
    y_label: str = "Value",
    color: str = "#2563EB",
) -> ChartSpec:
    fig = {
        "data": [{
            "type": "scatter",
            "mode": "lines+markers",
            "x": periods,
            "y": values,
            "line": {"color": color, "width": 2},
            "marker": {"size": 6},
        }],
        "layout": {
            "title": {"text": title, "font": {"size": 16}},
            "xaxis": {"title": "Period"},
            "yaxis": {"title": y_label},
            "plot_bgcolor": "#F9FAFB",
            "paper_bgcolor": "#FFFFFF",
            "margin": {"t": 50, "b": 40, "l": 60, "r": 20},
        },
    }
    return ChartSpec(chart_type="line", title=title, plotly_json=json.dumps(fig))


def bar_chart(
    categories: list[str],
    values: list[float],
    title: str,
    y_label: str = "Value",
    color: str = "#2563EB",
) -> ChartSpec:
    fig = {
        "data": [{
            "type": "bar",
            "x": categories,
            "y": values,
            "marker": {"color": color},
        }],
        "layout": {
            "title": {"text": title, "font": {"size": 16}},
            "xaxis": {"title": "Category"},
            "yaxis": {"title": y_label},
            "plot_bgcolor": "#F9FAFB",
            "paper_bgcolor": "#FFFFFF",
            "margin": {"t": 50, "b": 40, "l": 60, "r": 20},
        },
    }
    return ChartSpec(chart_type="bar", title=title, plotly_json=json.dumps(fig))


def multi_series_chart(
    periods: list[str],
    series: dict[str, list[float]],  # {label: values}
    title: str,
    y_label: str = "Value",
) -> ChartSpec:
    """Overlay multiple companies / metrics on one chart."""
    colors = ["#2563EB", "#DC2626", "#16A34A", "#9333EA", "#EA580C"]
    traces = []
    for i, (name, values) in enumerate(series.items()):
        traces.append({
            "type": "scatter",
            "mode": "lines+markers",
            "name": name,
            "x": periods,
            "y": values,
            "line": {"color": colors[i % len(colors)], "width": 2},
        })
    fig = {
        "data": traces,
        "layout": {
            "title": {"text": title, "font": {"size": 16}},
            "xaxis": {"title": "Period"},
            "yaxis": {"title": y_label},
            "legend": {"orientation": "h", "y": -0.2},
            "plot_bgcolor": "#F9FAFB",
            "paper_bgcolor": "#FFFFFF",
        },
    }
    return ChartSpec(chart_type="line", title=title, plotly_json=json.dumps(fig))


def waterfall_chart(
    labels: list[str],
    values: list[float],
    title: str,
) -> ChartSpec:
    fig = {
        "data": [{
            "type": "waterfall",
            "x": labels,
            "y": values,
            "connector": {"line": {"color": "#CBD5E1"}},
            "increasing": {"marker": {"color": "#16A34A"}},
            "decreasing": {"marker": {"color": "#DC2626"}},
        }],
        "layout": {
            "title": {"text": title, "font": {"size": 16}},
            "plot_bgcolor": "#F9FAFB",
            "paper_bgcolor": "#FFFFFF",
        },
    }
    return ChartSpec(chart_type="waterfall", title=title, plotly_json=json.dumps(fig))
