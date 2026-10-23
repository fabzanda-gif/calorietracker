from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any
from xml.etree import ElementTree


MAX_GPX_BYTES = 5 * 1024 * 1024
MAX_OUTPUT_POINTS = 1500


class GpxActivityError(ValueError):
    pass


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _child_text(
    element: ElementTree.Element,
    name: str,
) -> str | None:
    wanted = name.lower()

    for child in element:
        if _local_name(child.tag) == wanted:
            return child.text

    return None


def _extension_value(
    point: ElementTree.Element,
    names: set[str],
) -> float | None:
    for descendant in point.iter():
        if descendant is point:
            continue

        if _local_name(descendant.tag) in names:
            value = _safe_float(descendant.text)

            if value is not None:
                return value

    return None


def _distance_meters(
    first: dict[str, Any],
    second: dict[str, Any],
) -> float:
    radius = 6_371_000.0
    latitude_1 = radians(first["latitude"])
    latitude_2 = radians(second["latitude"])
    latitude_delta = latitude_2 - latitude_1
    longitude_delta = radians(
        second["longitude"] - first["longitude"]
    )

    value = (
        sin(latitude_delta / 2) ** 2
        + cos(latitude_1)
        * cos(latitude_2)
        * sin(longitude_delta / 2) ** 2
    )

    return 2 * radius * asin(min(1.0, sqrt(value)))


def _average(values: list[float]) -> float | None:
    if not values:
        return None

    return round(sum(values) / len(values), 1)


def _downsample(
    points: list[dict[str, Any]],
    maximum: int = MAX_OUTPUT_POINTS,
) -> list[dict[str, Any]]:
    if len(points) <= maximum:
        return points

    if maximum <= 2:
        return [points[0], points[-1]]

    indexes = {
        round(
            index
            * (len(points) - 1)
            / (maximum - 1)
        )
        for index in range(maximum)
    }

    return [
        point
        for index, point in enumerate(points)
        if index in indexes
    ]


def parse_gpx_activity(
    content: bytes,
    *,
    fallback_name: str = "Attività GPX",
) -> dict[str, Any]:
    if not content:
        raise GpxActivityError("Il file GPX è vuoto.")

    if len(content) > MAX_GPX_BYTES:
        raise GpxActivityError(
            "Il file GPX supera il limite di 5 MB."
        )

    lowered = content.lower()

    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise GpxActivityError(
            "Il file GPX contiene dichiarazioni XML "
            "non consentite."
        )

    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise GpxActivityError(
            "Il file non contiene un GPX valido."
        ) from exc

    if _local_name(root.tag) != "gpx":
        raise GpxActivityError(
            "Il documento caricato non è un file GPX."
        )

    activity_name = fallback_name

    for element in root.iter():
        if _local_name(element.tag) == "trk":
            track_name = _child_text(element, "name")

            if track_name and track_name.strip():
                activity_name = track_name.strip()

            break

    route_points: list[dict[str, Any]] = []
    series_points: list[dict[str, Any]] = []
    timestamps: list[datetime] = []
    cadence_values: list[float] = []
    heart_rate_values: list[float] = []

    for point in root.iter():
        if _local_name(point.tag) != "trkpt":
            continue

        latitude = _safe_float(point.attrib.get("lat"))
        longitude = _safe_float(point.attrib.get("lon"))

        if latitude is None or longitude is None:
            continue

        elevation = _safe_float(
            _child_text(point, "ele")
        )
        timestamp = _parse_time(
            _child_text(point, "time")
        )
        cadence = _extension_value(
            point,
            {"cad", "cadence"},
        )
        heart_rate = _extension_value(
            point,
            {"hr", "heartrate", "heart_rate"},
        )

        route_point: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
        }

        if elevation is not None:
            route_point["elevation"] = elevation

        if timestamp is not None:
            route_point["time"] = timestamp.isoformat()
            timestamps.append(timestamp)

        route_points.append(route_point)

        series_point: dict[str, Any] = {
            "index": len(route_points) - 1,
        }

        if timestamp is not None:
            series_point["time"] = timestamp.isoformat()

        if cadence is not None:
            series_point["cadence"] = cadence
            cadence_values.append(cadence)

        if heart_rate is not None:
            series_point["heart_rate"] = heart_rate
            heart_rate_values.append(heart_rate)

        if cadence is not None or heart_rate is not None:
            series_points.append(series_point)

    if not route_points:
        raise GpxActivityError(
            "Il GPX non contiene punti del percorso."
        )

    distance_meters = sum(
        _distance_meters(first, second)
        for first, second in zip(
            route_points,
            route_points[1:],
        )
    )

    duration_seconds: int | None = None

    if len(timestamps) >= 2:
        elapsed = (
            max(timestamps) - min(timestamps)
        ).total_seconds()

        if elapsed >= 0:
            duration_seconds = round(elapsed)

    started_at = (
        min(timestamps).isoformat()
        if timestamps
        else None
    )

    return {
        "activity_name": activity_name,
        "source": "gpx",
        "started_at": started_at,
        "date": (
            min(timestamps).date().isoformat()
            if timestamps
            else None
        ),
        "duration_seconds": duration_seconds,
        "distance_meters": round(distance_meters, 1),
        "average_cadence": _average(cadence_values),
        "average_heart_rate": _average(
            heart_rate_values
        ),
        "route_points": _downsample(route_points),
        "series_points": _downsample(series_points),
        "original_point_count": len(route_points),
    }
