from datetime import date

import requests

from backend.services.daily_context import (
    DailyContextService,
    clear_daily_context_cache,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self):
        self.calls = []

    def get(
        self,
        url,
        *,
        params=None,
        headers=None,
        timeout=None,
    ):
        self.calls.append({
            "url": url,
            "params": params,
            "headers": headers,
            "timeout": timeout,
        })

        if "geocoding-api" in url:
            return FakeResponse({
                "results": [{
                    "name": "Zaandam",
                    "country": "Paesi Bassi",
                    "latitude": 52.44,
                    "longitude": 4.83,
                }]
            })

        if "api.open-meteo.com" in url:
            return FakeResponse({
                "daily": {
                    "weather_code": [2],
                    "temperature_2m_min": [13.4],
                    "temperature_2m_max": [21.2],
                }
            })

        return FakeResponse({
            "events": [
                {
                    "year": 1666,
                    "text": (
                        "The Great Fire of London began."
                    ),
                },
                {
                    "year": 1945,
                    "text": (
                        "Vietnam declared independence."
                    ),
                },
            ]
        })


class FailingClient:
    def get(self, *args, **kwargs):
        raise requests.RequestException(
            "network unavailable"
        )


def test_context_contains_weather_and_events():
    clear_daily_context_cache()
    client = FakeClient()

    result = DailyContextService(
        client=client,
    ).build(
        city="Zaandam",
        day_date=date(2026, 9, 2),
    )

    assert result["location"] == (
        "Zaandam, Paesi Bassi"
    )
    assert result["weather"] == {
        "location": "Zaandam, Paesi Bassi",
        "condition": "poco nuvoloso",
        "weather_code": 2,
        "minimum_c": 13.4,
        "maximum_c": 21.2,
    }
    assert result["on_this_day"][0] == {
        "year": 1666,
        "text": "The Great Fire of London began.",
    }


def test_context_is_cached_by_city_and_date():
    clear_daily_context_cache()
    client = FakeClient()
    service = DailyContextService(client=client)

    first = service.build(
        city="Zaandam",
        day_date=date(2026, 9, 2),
    )
    second = service.build(
        city="zaandam",
        day_date=date(2026, 9, 2),
    )

    assert second == first
    assert len(client.calls) == 3


def test_network_failure_does_not_break_briefing():
    clear_daily_context_cache()

    result = DailyContextService(
        client=FailingClient(),
    ).build(
        city="Zaandam",
        day_date=date(2026, 9, 2),
    )

    assert result == {
        "location": "Zaandam",
    }


def test_empty_city_skips_external_requests():
    clear_daily_context_cache()
    client = FakeClient()

    result = DailyContextService(
        client=client,
    ).build(
        city=" ",
        day_date=date(2026, 9, 2),
    )

    assert result == {}
    assert client.calls == []
