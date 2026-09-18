from __future__ import annotations

from datetime import datetime
from io import BytesIO
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from backend.services.activity_movement import (
    normalize_activity_type,
)
from backend.services.gpx_activity import (
    GpxActivityError,
    parse_gpx_activity,
)


MAX_ACTIVITY_FILE_BYTES = 10 * 1024 * 1024
MAX_OUTPUT_POINTS = 1500

SUPPORTED_ACTIVITY_EXTENSIONS = {
    ".gpx",
    ".tcx",
    ".fit",
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value

    if not value:
        return None

    text = str(value).strip()

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _descendant_text(
    element: ElementTree.Element,
    name: str,
) -> str | None:
    wanted = name.lower()

    for child in element.iter():
        if (
            child is not element
            and _local_name(child.tag) == wanted
        ):
            return child.text

    return None


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


def _distance_meters(
    first: dict[str, Any],
    second: dict[str, Any],
) -> float:
    radius = 6_371_000.0

    lat1 = radians(first["latitude"])
    lat2 = radians(second["latitude"])
    dlat = lat2 - lat1
    dlon = radians(
        second["longitude"]
        - first["longitude"]
    )

    value = (
        sin(dlat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(dlon / 2) ** 2
    )

    return (
        2
        * radius
        * asin(min(1.0, sqrt(value)))
    )


def _fit_position(value: Any) -> float | None:
    parsed = _safe_float(value)

    if parsed is None:
        return None

    # FIT normally stores coordinates in semicircles.
    if abs(parsed) > 180:
        return parsed * (180.0 / (2 ** 31))

    return parsed


def _activity_type_from_sport(
    sport: Any,
    sub_sport: Any = None,
) -> str:
    value = " ".join(
        part
        for part in (
            str(sub_sport or ""),
            str(sport or ""),
        )
        if part
    ).lower()

    extra_aliases = {
        "strength_training": "Palestra",
        "strength training": "Palestra",
        "fitness_equipment": "Palestra",
        "fitness equipment": "Palestra",
        "indoor_cycling": "Bicicletta",
        "road_biking": "Bicicletta",
        "mountain_biking": "Bicicletta",
        "lap_swimming": "Nuoto",
        "open_water": "Nuoto",
        "soccer": "Calcio",
        "racket": "Tennis",
    }

    for fragment, activity_type in (
        extra_aliases.items()
    ):
        if fragment in value:
            return activity_type

    return normalize_activity_type(value)


def parse_tcx_activity(
    content: bytes,
    *,
    fallback_name: str,
) -> dict[str, Any]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise GpxActivityError(
            "Il file non contiene un TCX valido."
        ) from exc

    if _local_name(root.tag) != (
        "trainingcenterdatabase"
    ):
        raise GpxActivityError(
            "Il documento caricato non è un file TCX."
        )

    activity = next(
        (
            item
            for item in root.iter()
            if _local_name(item.tag) == "activity"
        ),
        None,
    )

    sport = (
        activity.attrib.get("Sport")
        if activity is not None
        else None
    )

    activity_type = _activity_type_from_sport(
        sport
    )

    route_points: list[dict[str, Any]] = []
    series_points: list[dict[str, Any]] = []
    timestamps: list[datetime] = []
    cadence_values: list[float] = []
    heart_rate_values: list[float] = []
    distance_values: list[float] = []

    for point in root.iter():
        if _local_name(point.tag) != "trackpoint":
            continue

        timestamp = _parse_time(
            _descendant_text(point, "time")
        )

        latitude = _safe_float(
            _descendant_text(
                point,
                "latitudedegrees",
            )
        )
        longitude = _safe_float(
            _descendant_text(
                point,
                "longitudedegrees",
            )
        )
        elevation = _safe_float(
            _descendant_text(
                point,
                "altitudemeters",
            )
        )
        cadence = _safe_float(
            _descendant_text(point, "cadence")
        )
        heart_rate = _safe_float(
            _descendant_text(point, "value")
        )
        distance = _safe_float(
            _descendant_text(
                point,
                "distancemeters",
            )
        )

        if timestamp is not None:
            timestamps.append(timestamp)

        if distance is not None:
            distance_values.append(distance)

        if cadence is not None:
            cadence_values.append(cadence)

        if heart_rate is not None:
            heart_rate_values.append(
                heart_rate
            )

        if (
            latitude is not None
            and longitude is not None
        ):
            route_point: dict[str, Any] = {
                "latitude": latitude,
                "longitude": longitude,
            }

            if elevation is not None:
                route_point["elevation"] = (
                    elevation
                )

            if timestamp is not None:
                route_point["time"] = (
                    timestamp.isoformat()
                )

            route_points.append(route_point)

        series_point: dict[str, Any] = {
            "index": len(series_points),
        }

        if timestamp is not None:
            series_point["time"] = (
                timestamp.isoformat()
            )

        if cadence is not None:
            series_point["cadence"] = cadence

        if heart_rate is not None:
            series_point["heart_rate"] = (
                heart_rate
            )

        if (
            cadence is not None
            or heart_rate is not None
        ):
            series_points.append(series_point)

    lap_durations = [
        value
        for value in (
            _safe_float(
                _descendant_text(
                    lap,
                    "totaltimeseconds",
                )
            )
            for lap in root.iter()
            if _local_name(lap.tag) == "lap"
        )
        if value is not None
    ]

    calories = [
        value
        for value in (
            _safe_float(
                _descendant_text(
                    lap,
                    "calories",
                )
            )
            for lap in root.iter()
            if _local_name(lap.tag) == "lap"
        )
        if value is not None
    ]

    duration_seconds: int | None = None

    if lap_durations:
        duration_seconds = round(
            sum(lap_durations)
        )
    elif len(timestamps) >= 2:
        duration_seconds = round(
            (
                max(timestamps)
                - min(timestamps)
            ).total_seconds()
        )

    if distance_values:
        distance_meters = max(
            distance_values
        )
    elif len(route_points) >= 2:
        distance_meters = sum(
            _distance_meters(first, second)
            for first, second in zip(
                route_points,
                route_points[1:],
            )
        )
    else:
        distance_meters = 0.0

    started = (
        min(timestamps)
        if timestamps
        else None
    )

    return {
        "activity_name": fallback_name,
        "activity_type": activity_type,
        "source": "tcx",
        "file_format": "TCX",
        "started_at": (
            started.isoformat()
            if started
            else None
        ),
        "date": (
            started.date().isoformat()
            if started
            else None
        ),
        "duration_seconds": duration_seconds,
        "distance_meters": round(
            distance_meters,
            1,
        ),
        "average_cadence": _average(
            cadence_values
        ),
        "average_heart_rate": _average(
            heart_rate_values
        ),
        "file_calories": (
            round(sum(calories))
            if calories
            else None
        ),
        "route_points": _downsample(
            route_points
        ),
        "series_points": _downsample(
            series_points
        ),
        "original_point_count": max(
            len(route_points),
            len(series_points),
        ),
    }


def parse_fit_activity(
    content: bytes,
    *,
    fallback_name: str,
) -> dict[str, Any]:
    try:
        from fitparse import FitFile

        fit = FitFile(BytesIO(content))
        fit.parse()
    except Exception as exc:
        raise GpxActivityError(
            "Il file non contiene un FIT valido."
        ) from exc

    sessions = list(
        fit.get_messages("session")
    )

    session: dict[str, Any] = {}

    if sessions:
        session = sessions[0].get_values()

    sport = session.get("sport")
    sub_sport = session.get("sub_sport")

    activity_type = (
        _activity_type_from_sport(
            sport,
            sub_sport,
        )
    )

    route_points: list[dict[str, Any]] = []
    series_points: list[dict[str, Any]] = []
    timestamps: list[datetime] = []
    cadence_values: list[float] = []
    heart_rate_values: list[float] = []
    distance_values: list[float] = []

    record_count = 0

    for message in fit.get_messages("record"):
        values = message.get_values()
        record_count += 1

        timestamp = _parse_time(
            values.get("timestamp")
        )
        latitude = _fit_position(
            values.get("position_lat")
        )
        longitude = _fit_position(
            values.get("position_long")
        )

        elevation = _safe_float(
            values.get(
                "enhanced_altitude",
                values.get("altitude"),
            )
        )
        cadence = _safe_float(
            values.get("cadence")
        )
        heart_rate = _safe_float(
            values.get("heart_rate")
        )
        distance = _safe_float(
            values.get("distance")
        )

        if timestamp is not None:
            timestamps.append(timestamp)

        if cadence is not None:
            cadence_values.append(cadence)

        if heart_rate is not None:
            heart_rate_values.append(
                heart_rate
            )

        if distance is not None:
            distance_values.append(distance)

        if (
            latitude is not None
            and longitude is not None
        ):
            route_point: dict[str, Any] = {
                "latitude": latitude,
                "longitude": longitude,
            }

            if elevation is not None:
                route_point["elevation"] = (
                    elevation
                )

            if timestamp is not None:
                route_point["time"] = (
                    timestamp.isoformat()
                )

            route_points.append(route_point)

        if (
            cadence is not None
            or heart_rate is not None
        ):
            series_point: dict[str, Any] = {
                "index": record_count - 1,
            }

            if timestamp is not None:
                series_point["time"] = (
                    timestamp.isoformat()
                )

            if cadence is not None:
                series_point["cadence"] = (
                    cadence
                )

            if heart_rate is not None:
                series_point["heart_rate"] = (
                    heart_rate
                )

            series_points.append(series_point)

    started = _parse_time(
        session.get("start_time")
    )

    if started is None and timestamps:
        started = min(timestamps)

    duration_seconds = _safe_float(
        session.get("total_timer_time")
    )

    if duration_seconds is None:
        duration_seconds = _safe_float(
            session.get(
                "total_elapsed_time"
            )
        )

    if (
        duration_seconds is None
        and len(timestamps) >= 2
    ):
        duration_seconds = (
            max(timestamps)
            - min(timestamps)
        ).total_seconds()

    distance_meters = _safe_float(
        session.get("total_distance")
    )

    if (
        distance_meters is None
        and distance_values
    ):
        distance_meters = max(
            distance_values
        )

    if (
        distance_meters is None
        and len(route_points) >= 2
    ):
        distance_meters = sum(
            _distance_meters(first, second)
            for first, second in zip(
                route_points,
                route_points[1:],
            )
        )

    calories = _safe_float(
        session.get("total_calories")
    )

    average_cadence = _safe_float(
        session.get("avg_cadence")
    )

    if average_cadence is None:
        average_cadence = _average(
            cadence_values
        )

    average_heart_rate = _safe_float(
        session.get("avg_heart_rate")
    )

    if average_heart_rate is None:
        average_heart_rate = _average(
            heart_rate_values
        )

    return {
        "activity_name": fallback_name,
        "activity_type": activity_type,
        "source": "fit",
        "file_format": "FIT",
        "started_at": (
            started.isoformat()
            if started
            else None
        ),
        "date": (
            started.date().isoformat()
            if started
            else None
        ),
        "duration_seconds": (
            round(duration_seconds)
            if duration_seconds is not None
            else None
        ),
        "distance_meters": round(
            distance_meters or 0,
            1,
        ),
        "average_cadence": (
            round(average_cadence, 1)
            if average_cadence is not None
            else None
        ),
        "average_heart_rate": (
            round(average_heart_rate, 1)
            if average_heart_rate is not None
            else None
        ),
        "file_calories": (
            round(calories)
            if calories is not None
            else None
        ),
        "route_points": _downsample(
            route_points
        ),
        "series_points": _downsample(
            series_points
        ),
        "original_point_count": record_count,
    }


def parse_activity_file(
    content: bytes,
    *,
    file_name: str,
    fallback_name: str = "Attività",
) -> dict[str, Any]:
    if not content:
        raise GpxActivityError(
            "Il file attività è vuoto."
        )

    if len(content) > MAX_ACTIVITY_FILE_BYTES:
        raise GpxActivityError(
            "Il file attività supera il limite di 10 MB."
        )

    suffix = Path(file_name).suffix.lower()

    if suffix not in SUPPORTED_ACTIVITY_EXTENSIONS:
        raise GpxActivityError(
            "Formato non supportato. Usa GPX, FIT o TCX."
        )

    if suffix == ".gpx":
        result = parse_gpx_activity(
            content,
            fallback_name=fallback_name,
        )

        result["file_format"] = "GPX"
        result["activity_type"] = (
            normalize_activity_type(
                result.get("activity_name")
            )
        )
        return result

    if suffix == ".tcx":
        return parse_tcx_activity(
            content,
            fallback_name=fallback_name,
        )

    return parse_fit_activity(
        content,
        fallback_name=fallback_name,
    )
