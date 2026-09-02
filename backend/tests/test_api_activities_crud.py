import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_weight_repository,
)
from backend.api.main import app


class FakeActivitiesRepository:
    def __init__(self):
        self.last_create = None
        self.last_update = None
        self.last_delete = None

    def list_for_date(self, user_id, log_date):
        return [{"id": "activity-1", "activity_name": "Padel", "burned_calories": 500}]

    def create(self, payload):
        self.last_create = payload
        return {"id": "activity-2", **payload}

    def update(self, activity_id, user_id, payload):
        self.last_update = (activity_id, user_id, payload)
        return {"id": activity_id, **payload}

    def delete(self, activity_id, user_id):
        self.last_delete = (activity_id, user_id)
        return True

    def upsert_named_for_date(
        self,
        user_id,
        log_date,
        activity_name,
        burned_calories,
    ):
        return {
            "id": "steps-activity",
            "user_id": user_id,
            "date": str(log_date),
            "activity_name": activity_name,
            "burned_calories": burned_calories,
        }


class FakeDailyLogsRepository:
    def get_for_date_compatible(
        self,
        user_id,
        log_date,
    ):
        return {
            "user_id": user_id,
            "date": str(log_date),
            "steps": 10000,
        }


fake_repo = FakeActivitiesRepository()
fake_daily_logs_repo = FakeDailyLogsRepository()


class FakeWeightRepository:
    def latest(self, user_id):
        return {"weight": 80}


fake_weight_repo = FakeWeightRepository()


def override_current_user():
    return CurrentUser(id="authenticated-user", access_token="fake-token")


def override_repo():
    return fake_repo


def override_daily_logs_repo():
    return fake_daily_logs_repo


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_activities_repository] = override_repo
    app.dependency_overrides[get_daily_logs_repository] = (
        override_daily_logs_repo
    )
    app.dependency_overrides[get_weight_repository] = (
        lambda: fake_weight_repo
    )
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_list_activities():
    response = client.get("/activities/2026-08-22")
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_create_activity_uses_authenticated_user():
    response = client.post(
        "/activities",
        json={
            "date": "2026-08-22",
            "activity_name": "Bici",
            "burned_calories": 320,
        },
    )
    assert response.status_code == 201
    assert fake_repo.last_create["user_id"] == "authenticated-user"


def test_update_activity_is_user_scoped():
    response = client.patch(
        "/activities/activity-1",
        json={"burned_calories": 550},
    )
    assert response.status_code == 200
    assert fake_repo.last_update == (
        "activity-1",
        "authenticated-user",
        {"burned_calories": 550},
    )


def test_update_activity_rejects_empty_body():
    response = client.patch("/activities/activity-1", json={})
    assert response.status_code == 400


def test_delete_activity_is_user_scoped():
    response = client.delete("/activities/activity-1")
    assert response.status_code == 200


def test_preview_gpx_requires_valid_file():
    import base64

    content = b"""<?xml version="1.0"?>
    <gpx
      version="1.1"
      xmlns="http://www.topografix.com/GPX/1/1"
      xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
    >
      <trk>
        <name>Corsa mattutina</name>
        <trkseg>
          <trkpt lat="45.0" lon="9.0">
            <time>2026-09-01T07:00:00Z</time>
            <extensions>
              <gpxtpx:TrackPointExtension>
                <gpxtpx:hr>130</gpxtpx:hr>
                <gpxtpx:cad>158</gpxtpx:cad>
              </gpxtpx:TrackPointExtension>
            </extensions>
          </trkpt>
          <trkpt lat="45.001" lon="9.001">
            <time>2026-09-01T07:01:00Z</time>
            <extensions>
              <gpxtpx:TrackPointExtension>
                <gpxtpx:hr>150</gpxtpx:hr>
                <gpxtpx:cad>162</gpxtpx:cad>
              </gpxtpx:TrackPointExtension>
            </extensions>
          </trkpt>
        </trkseg>
      </trk>
    </gpx>"""

    response = client.post(
        "/activities/gpx/preview",
        json={
            "file_name": "corsa.gpx",
            "content_base64": base64.b64encode(
                content
            ).decode("ascii"),
        },
    )

    assert response.status_code == 200

    preview = response.json()["preview"]

    assert preview["activity_name"] == "Corsa mattutina"
    assert preview["date"] == "2026-09-01"
    assert preview["duration_seconds"] == 60
    assert preview["average_cadence"] == 160
    assert preview["average_heart_rate"] == 140
    assert len(preview["route_points"]) == 2


def test_preview_gpx_rejects_invalid_base64():
    response = client.post(
        "/activities/gpx/preview",
        json={
            "file_name": "corsa.gpx",
            "content_base64": "questo non e base64!",
        },
    )

    assert response.status_code == 400


def test_preview_gpx_rejects_file_without_route():
    import base64

    response = client.post(
        "/activities/gpx/preview",
        json={
            "file_name": "vuoto.gpx",
            "content_base64": base64.b64encode(
                b'<gpx version="1.1"></gpx>'
            ).decode("ascii"),
        },
    )

    assert response.status_code == 422
    assert "punti del percorso" in response.json()["detail"]


def test_import_gpx_saves_parsed_activity():
    import base64

    fake_repo.last_create = None

    content = b"""<gpx
      version="1.1"
      xmlns="http://www.topografix.com/GPX/1/1"
      xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
    >
      <trk>
        <name>Corsa importata</name>
        <trkseg>
          <trkpt lat="45.0" lon="9.0">
            <time>2026-09-01T07:00:00Z</time>
            <extensions>
              <gpxtpx:TrackPointExtension>
                <gpxtpx:hr>130</gpxtpx:hr>
                <gpxtpx:cad>158</gpxtpx:cad>
              </gpxtpx:TrackPointExtension>
            </extensions>
          </trkpt>
          <trkpt lat="45.001" lon="9.001">
            <time>2026-09-01T07:01:00Z</time>
            <extensions>
              <gpxtpx:TrackPointExtension>
                <gpxtpx:hr>150</gpxtpx:hr>
                <gpxtpx:cad>162</gpxtpx:cad>
              </gpxtpx:TrackPointExtension>
            </extensions>
          </trkpt>
        </trkseg>
      </trk>
    </gpx>"""

    response = client.post(
        "/activities/gpx/import",
        json={
            "file_name": "corsa.gpx",
            "content_base64": base64.b64encode(
                content
            ).decode("ascii"),
            "activity_type": "Corsa",
            "burned_calories": 320,
        },
    )

    assert response.status_code == 201
    assert fake_repo.last_create is not None
    assert (
        fake_repo.last_create["user_id"]
        == "authenticated-user"
    )
    assert fake_repo.last_create["source"] == "gpx"
    assert fake_repo.last_create["date"] == "2026-09-01"
    assert (
        fake_repo.last_create["activity_name"]
        == "Corsa importata"
    )
    assert fake_repo.last_create["activity_type"] == "Corsa"
    assert fake_repo.last_create["burned_calories"] == 320
    assert fake_repo.last_create["average_cadence"] == 160
    assert fake_repo.last_create["average_heart_rate"] == 140
    assert len(fake_repo.last_create["route_points"]) == 2


def test_import_gpx_requires_manual_date_when_missing():
    import base64

    content = b"""<gpx version="1.1">
      <trk>
        <trkseg>
          <trkpt lat="45" lon="9"/>
        </trkseg>
      </trk>
    </gpx>"""

    response = client.post(
        "/activities/gpx/import",
        json={
            "file_name": "senza-data.gpx",
            "content_base64": base64.b64encode(
                content
            ).decode("ascii"),
        },
    )

    assert response.status_code == 422
    assert "non contiene una data" in response.json()["detail"]


def test_create_typed_activity_estimates_steps():
    response = client.post(
        "/activities",
        json={
            "date": "2026-08-22",
            "activity_name": "Padel",
            "activity_type": "Padel",
            "duration_seconds": 3600,
            "burned_calories": 500,
        },
    )

    assert response.status_code == 201
    assert fake_repo.last_create["activity_type"] == "Padel"
    assert fake_repo.last_create["estimated_steps"] == 6300
    assert response.json()["movement"]["total_steps"] == 10000


def test_get_activity_movement_summary():
    response = client.get(
        "/activities/movement/2026-08-22"
    )

    assert response.status_code == 200
    assert response.json()["total_steps"] == 10000
    assert "net_daily_steps" in response.json()
    assert "step_calories" in response.json()
