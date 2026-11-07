from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from backend.services.activity_file import (
    parse_activity_file,
)
from backend.services.gpx_activity import GpxActivityError


def test_parse_tcx_activity():
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase
  xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities>
    <Activity Sport="Biking">
      <Id>2026-09-12T08:00:00Z</Id>
      <Lap StartTime="2026-09-12T08:00:00Z">
        <TotalTimeSeconds>600</TotalTimeSeconds>
        <DistanceMeters>5000</DistanceMeters>
        <Calories>120</Calories>
        <Track>
          <Trackpoint>
            <Time>2026-09-12T08:00:00Z</Time>
            <Position>
              <LatitudeDegrees>52.4</LatitudeDegrees>
              <LongitudeDegrees>4.8</LongitudeDegrees>
            </Position>
            <AltitudeMeters>10</AltitudeMeters>
            <DistanceMeters>0</DistanceMeters>
            <HeartRateBpm>
              <Value>120</Value>
            </HeartRateBpm>
            <Cadence>80</Cadence>
          </Trackpoint>

          <Trackpoint>
            <Time>2026-09-12T08:10:00Z</Time>
            <Position>
              <LatitudeDegrees>52.41</LatitudeDegrees>
              <LongitudeDegrees>4.81</LongitudeDegrees>
            </Position>
            <AltitudeMeters>12</AltitudeMeters>
            <DistanceMeters>5000</DistanceMeters>
            <HeartRateBpm>
              <Value>140</Value>
            </HeartRateBpm>
            <Cadence>90</Cadence>
          </Trackpoint>
        </Track>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>
"""

    result = parse_activity_file(
        content,
        file_name="ride.tcx",
        fallback_name="Morning ride",
    )

    assert result["file_format"] == "TCX"
    assert result["source"] == "tcx"
    assert result["activity_type"] == "Bicicletta"
    assert result["activity_name"] == "Morning ride"
    assert result["date"] == "2026-09-12"
    assert result["duration_seconds"] == 600
    assert result["distance_meters"] == 5000
    assert result["file_calories"] == 120
    assert result["average_cadence"] == 85
    assert result["average_heart_rate"] == 130
    assert len(result["route_points"]) == 2


def test_parse_fit_activity(monkeypatch):
    class FakeMessage:
        def __init__(self, values):
            self._values = values

        def get_values(self):
            return self._values

    class FakeFitFile:
        def __init__(self, _stream):
            pass

        def parse(self):
            return None

        def get_messages(self, name):
            if name == "session":
                return [
                    FakeMessage(
                        {
                            "sport": "running",
                            "start_time": "2026-09-12T07:00:00+00:00",
                            "total_timer_time": 1800,
                            "total_distance": 5000,
                            "total_calories": 350,
                            "avg_cadence": 170,
                            "avg_heart_rate": 150,
                        }
                    )
                ]

            if name == "record":
                return [
                    FakeMessage(
                        {
                            "timestamp": "2026-09-12T07:00:00+00:00",
                            "position_lat": 52.4,
                            "position_long": 4.8,
                            "heart_rate": 140,
                            "cadence": 168,
                            "distance": 0,
                        }
                    ),
                    FakeMessage(
                        {
                            "timestamp": "2026-09-12T07:30:00+00:00",
                            "position_lat": 52.41,
                            "position_long": 4.81,
                            "heart_rate": 160,
                            "cadence": 172,
                            "distance": 5000,
                        }
                    ),
                ]

            return []

    monkeypatch.setitem(
        sys.modules,
        "fitparse",
        SimpleNamespace(FitFile=FakeFitFile),
    )

    result = parse_activity_file(
        b"fake-fit-data",
        file_name="run.fit",
        fallback_name="Morning run",
    )

    assert result["file_format"] == "FIT"
    assert result["source"] == "fit"
    assert result["activity_type"] == "Corsa"
    assert result["activity_name"] == "Morning run"
    assert result["date"] == "2026-09-12"
    assert result["duration_seconds"] == 1800
    assert result["distance_meters"] == 5000
    assert result["file_calories"] == 350
    assert result["average_cadence"] == 170
    assert result["average_heart_rate"] == 150


def test_rejects_unsupported_activity_file():
    with pytest.raises(
        GpxActivityError,
        match="Formato non supportato",
    ):
        parse_activity_file(
            b"data",
            file_name="activity.csv",
        )
