import pytest

from backend.services.gpx_activity import (
    GpxActivityError,
    MAX_GPX_BYTES,
    parse_gpx_activity,
)


GPX_WITH_METRICS = b"""<?xml version="1.0"?>
<gpx
  version="1.1"
  xmlns="http://www.topografix.com/GPX/1/1"
  xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
>
  <trk>
    <name>Corsa serale</name>
    <trkseg>
      <trkpt lat="45.0000" lon="9.0000">
        <ele>100</ele>
        <time>2026-09-01T18:00:00Z</time>
        <extensions>
          <gpxtpx:TrackPointExtension>
            <gpxtpx:hr>140</gpxtpx:hr>
            <gpxtpx:cad>160</gpxtpx:cad>
          </gpxtpx:TrackPointExtension>
        </extensions>
      </trkpt>

      <trkpt lat="45.0010" lon="9.0010">
        <ele>102</ele>
        <time>2026-09-01T18:01:00Z</time>
        <extensions>
          <gpxtpx:TrackPointExtension>
            <gpxtpx:hr>150</gpxtpx:hr>
            <gpxtpx:cad>170</gpxtpx:cad>
          </gpxtpx:TrackPointExtension>
        </extensions>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""


def test_parses_route_and_optional_metrics():
    result = parse_gpx_activity(
        GPX_WITH_METRICS
    )

    assert result["activity_name"] == "Corsa serale"
    assert result["source"] == "gpx"
    assert result["date"] == "2026-09-01"
    assert result["duration_seconds"] == 60
    assert result["distance_meters"] > 100
    assert result["average_cadence"] == 165
    assert result["average_heart_rate"] == 145
    assert len(result["route_points"]) == 2
    assert len(result["series_points"]) == 2


def test_metrics_remain_missing_when_not_in_file():
    result = parse_gpx_activity(
        b"""<gpx version="1.1">
        <trk>
          <trkseg>
            <trkpt lat="45" lon="9"/>
            <trkpt lat="45.1" lon="9.1"/>
          </trkseg>
        </trk>
        </gpx>"""
    )

    assert result["average_cadence"] is None
    assert result["average_heart_rate"] is None
    assert result["duration_seconds"] is None
    assert result["series_points"] == []


def test_uses_fallback_name_when_track_has_no_name():
    result = parse_gpx_activity(
        b"""<gpx version="1.1">
        <trk>
          <trkseg>
            <trkpt lat="45" lon="9"/>
          </trkseg>
        </trk>
        </gpx>""",
        fallback_name="Camminata",
    )

    assert result["activity_name"] == "Camminata"


def test_rejects_invalid_document():
    with pytest.raises(
        GpxActivityError,
        match="GPX valido",
    ):
        parse_gpx_activity(b"<gpx>")


def test_rejects_document_without_route():
    with pytest.raises(
        GpxActivityError,
        match="punti del percorso",
    ):
        parse_gpx_activity(
            b'<gpx version="1.1"></gpx>'
        )


def test_rejects_xml_entities():
    with pytest.raises(
        GpxActivityError,
        match="non consentite",
    ):
        parse_gpx_activity(
            b'<!DOCTYPE gpx [<!ENTITY x "bad">]>'
            b"<gpx>&x;</gpx>"
        )


def test_rejects_oversized_file():
    with pytest.raises(
        GpxActivityError,
        match="5 MB",
    ):
        parse_gpx_activity(
            b"x" * (MAX_GPX_BYTES + 1)
        )
