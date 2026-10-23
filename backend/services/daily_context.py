from __future__ import annotations

import time
from datetime import date
from typing import Any

import requests


OPEN_METEO_GEOCODING_URL = (
    "https://geocoding-api.open-meteo.com/v1/search"
)
OPEN_METEO_FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
)
WIKIMEDIA_ON_THIS_DAY_URL = (
    "https://en.wikipedia.org/api/rest_v1/"
    "feed/onthisday/events"
)

_CACHE_TTL_SECONDS = 6 * 60 * 60
_CONTEXT_CACHE: dict[
    tuple[str, str],
    tuple[float, dict[str, Any]],
] = {}


def _weather_label(code: int) -> str:
    if code == 0:
        return "sereno"
    if code in {1, 2}:
        return "poco nuvoloso"
    if code == 3:
        return "nuvoloso"
    if code in {45, 48}:
        return "nebbioso"
    if code in {51, 53, 55, 56, 57}:
        return "con pioviggine"
    if code in {
        61, 63, 65, 66, 67, 80, 81, 82,
    }:
        return "piovoso"
    if code in {
        71, 73, 75, 77, 85, 86,
    }:
        return "nevoso"
    if code in {95, 96, 99}:
        return "con temporali"
    return "variabile"


class DailyContextService:
    def __init__(
        self,
        *,
        client: Any | None = None,
        timeout: float = 3.0,
    ) -> None:
        self.client = client or requests
        self.timeout = timeout

    def build(
        self,
        *,
        city: str,
        day_date: date,
    ) -> dict[str, Any]:
        normalized_city = city.strip()

        if not normalized_city:
            return {}

        cache_key = (
            normalized_city.casefold(),
            str(day_date),
        )
        cached = _CONTEXT_CACHE.get(cache_key)

        if cached is not None:
            expires_at, value = cached
            if expires_at > time.monotonic():
                return value

            _CONTEXT_CACHE.pop(cache_key, None)

        result: dict[str, Any] = {
            "location": normalized_city,
        }

        weather = self._weather(
            city=normalized_city,
            day_date=day_date,
        )
        if weather is not None:
            result["weather"] = weather
            result["location"] = weather["location"]

        events = self._on_this_day(day_date)
        if events:
            result["on_this_day"] = events

        _CONTEXT_CACHE[cache_key] = (
            time.monotonic() + _CACHE_TTL_SECONDS,
            result,
        )

        return result

    def _weather(
        self,
        *,
        city: str,
        day_date: date,
    ) -> dict[str, Any] | None:
        try:
            geocoding = self.client.get(
                OPEN_METEO_GEOCODING_URL,
                params={
                    "name": city,
                    "count": 1,
                    "language": "it",
                    "format": "json",
                },
                timeout=self.timeout,
            )
            geocoding.raise_for_status()
            results = (
                geocoding.json().get("results")
                or []
            )

            if not results:
                return None

            place = results[0]
            latitude = float(place["latitude"])
            longitude = float(place["longitude"])

            forecast = self.client.get(
                OPEN_METEO_FORECAST_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "daily": (
                        "weather_code,"
                        "temperature_2m_min,"
                        "temperature_2m_max"
                    ),
                    "timezone": "auto",
                    "start_date": str(day_date),
                    "end_date": str(day_date),
                },
                timeout=self.timeout,
            )
            forecast.raise_for_status()
            daily = forecast.json().get("daily") or {}

            codes = daily.get("weather_code") or []
            minimums = (
                daily.get("temperature_2m_min")
                or []
            )
            maximums = (
                daily.get("temperature_2m_max")
                or []
            )

            if not codes or not minimums or not maximums:
                return None

            code = int(codes[0])

            location_parts = [
                str(place.get("name") or city),
                str(place.get("country") or ""),
            ]

            return {
                "location": ", ".join(
                    part
                    for part in location_parts
                    if part
                ),
                "condition": _weather_label(code),
                "weather_code": code,
                "minimum_c": round(
                    float(minimums[0]),
                    1,
                ),
                "maximum_c": round(
                    float(maximums[0]),
                    1,
                ),
            }
        except (
            requests.RequestException,
            KeyError,
            TypeError,
            ValueError,
        ):
            return None

    def _on_this_day(
        self,
        day_date: date,
    ) -> list[dict[str, Any]]:
        url = (
            f"{WIKIMEDIA_ON_THIS_DAY_URL}/"
            f"{day_date.month:02d}/"
            f"{day_date.day:02d}"
        )

        try:
            response = self.client.get(
                url,
                headers={
                    "User-Agent": (
                        "SanoSync/0.3 "
                        "(daily wellbeing briefing)"
                    ),
                    "Accept-Language": "it,en;q=0.8",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            events = (
                response.json().get("events")
                or []
            )
        except (
            requests.RequestException,
            AttributeError,
            TypeError,
            ValueError,
        ):
            return []

        normalized: list[dict[str, Any]] = []

        for event in events:
            if not isinstance(event, dict):
                continue

            text = str(
                event.get("text") or ""
            ).strip()
            year = event.get("year")

            if not text or year is None:
                continue

            normalized.append({
                "year": year,
                "text": text[:320],
            })

            if len(normalized) >= 3:
                break

        return normalized


def clear_daily_context_cache() -> None:
    _CONTEXT_CACHE.clear()
