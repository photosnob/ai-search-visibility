"""Charts drawn with SVG and plain text. No JavaScript and no network."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from xml.sax.saxutils import escape


@dataclass(frozen=True)
class Point:
    label: str
    value: str


@dataclass(frozen=True)
class Series:
    name: str
    points: tuple[Point, ...]


_COLORS = ("#8f3d1b", "#1f4e79", "#1d6b45", "#6b3fa0", "#8a5a12", "#315c5a")
_WIDTH = 720
_HEIGHT = 248
_LEFT = 44
_RIGHT = 16
_TOP = 16
_BOTTOM = 36


def series_color(index: int) -> str:
    return _COLORS[index % len(_COLORS)]


def line_chart_svg(series: Sequence[Series]) -> str:
    labels = _labels(series)
    if not labels:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 80" '
            'role="img" aria-label="No visibility scores to chart">'
            '<text x="0" y="24" fill="#5c564c" font-family="Palatino, Georgia, serif" '
            'font-size="16">No successful answers to chart.</text></svg>'
        )
    width = _WIDTH - _LEFT - _RIGHT
    height = _HEIGHT - _TOP - _BOTTOM
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {_HEIGHT}" '
        'role="img" aria-label="Visibility score by run">',
        "<title>Visibility score by run</title>",
    ]
    for tick in (0, 25, 50, 75, 100):
        y = _y(tick, height)
        parts.append(
            f'<line x1="{_LEFT}" y1="{y:.1f}" x2="{_WIDTH - _RIGHT}" y2="{y:.1f}" '
            'stroke="#d9d2c5" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{_LEFT - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#5c564c" '
            'font-size="11" font-family="ui-monospace, Menlo, Consolas, monospace">'
            f"{tick}</text>"
        )
    for index, label in enumerate(labels):
        x = _x(index, len(labels), width)
        parts.append(
            f'<text x="{x:.1f}" y="{_HEIGHT - 12}" text-anchor="middle" fill="#5c564c" '
            'font-size="11" font-family="ui-monospace, Menlo, Consolas, monospace">'
            f"{escape(label)}</text>"
        )
    lookup = {
        (item.name, point.label): Decimal(point.value) for item in series for point in item.points
    }
    for series_index, item in enumerate(series):
        color = series_color(series_index)
        segment: list[str] = []
        for label_index, label in enumerate(labels):
            value = lookup.get((item.name, label))
            if value is None:
                _polyline(parts, color, segment)
                segment = []
                continue
            segment.append(f"{_x(label_index, len(labels), width):.1f},{_y(value, height):.1f}")
        _polyline(parts, color, segment)
        for label_index, label in enumerate(labels):
            value = lookup.get((item.name, label))
            if value is None:
                continue
            x = _x(label_index, len(labels), width)
            y = _y(value, height)
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}">'
                f"<title>{escape(item.name)} {escape(label)}: {escape(format(value, 'f'))}</title>"
                "</circle>"
            )
    parts.append("</svg>")
    return "".join(parts)


def text_chart(series: Sequence[Series]) -> str:
    if not any(item.points for item in series):
        return "No successful answers to chart."
    width = max((len(item.name) for item in series), default=8)
    lines: list[str] = []
    for item in series:
        for point in item.points:
            filled = int(
                (Decimal(point.value) / Decimal(10)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            filled = max(0, min(10, filled))
            bar = "█" * filled + "░" * (10 - filled)
            lines.append(f"{point.label:<16} {item.name:<{width}}  {bar}  {point.value:>5}")
    return "\n".join(lines)


def _polyline(parts: list[str], color: str, points: list[str]) -> None:
    if len(points) < 2:
        return
    parts.append(
        f'<polyline fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linejoin="round" points="{" ".join(points)}"/>'
    )


def _labels(series: Sequence[Series]) -> list[str]:
    labels: list[str] = []
    for item in series:
        for point in item.points:
            if point.label not in labels:
                labels.append(point.label)
    return labels


def _x(index: int, count: int, width: int) -> float:
    if count <= 1:
        return _LEFT + width / 2
    return _LEFT + width * index / (count - 1)


def _y(value: Decimal | int, height: int) -> float:
    ratio = Decimal(value) / Decimal(100)
    return float(Decimal(_TOP + height) - (ratio * Decimal(height)))
