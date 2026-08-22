from backend.api.routers.activities import router as activities_router


def test_activities_range_route_is_registered():
    paths = {
        route.path
        for route in activities_router.routes
    }

    assert "/activities/range" in paths
