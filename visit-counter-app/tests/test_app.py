import fakeredis
import pytest
import redis

from counter import create_app


@pytest.fixture
def client():
    app = create_app(redis_client=fakeredis.FakeRedis(decode_responses=True))
    app.testing = True
    return app.test_client()


class BrokenRedis:
    """Simulates Redis being unreachable."""

    def __getattr__(self, _name):
        def fail(*_a, **_kw):
            raise redis.ConnectionError("connection refused")
        return fail


@pytest.fixture
def broken_client():
    app = create_app(redis_client=BrokenRedis())
    app.testing = True
    return app.test_client()


def test_index_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"You are visitor" in res.data
    assert "X-Served-By" in res.headers


def test_health_always_ok(broken_client):
    assert broken_client.get("/health").status_code == 200


def test_ready(client, broken_client):
    assert client.get("/ready").status_code == 200
    assert broken_client.get("/ready").status_code == 503


def test_visit_increments(client):
    first = client.post("/api/visit").get_json()
    second = client.post("/api/visit").get_json()
    assert first["you"]["number"] == 1
    assert second["you"]["number"] == 2
    assert second["total"] == 2
    assert second["today"] == 2
    assert second["hourly"][-1]["count"] == 2
    assert len(second["hourly"]) == 24


def test_returning_visitor_cookie(client):
    first = client.post("/api/visit").get_json()
    second = client.post("/api/visit").get_json()
    assert first["you"]["returning"] is False
    assert second["you"]["returning"] is True
    assert second["unique"] == 1


def test_stats_shape(client):
    client.post("/api/visit")
    data = client.get("/api/stats").get_json()
    for field in ("total", "today", "unique", "hourly", "served_by", "recent", "instance"):
        assert field in data
    assert data["served_by"][0]["count"] == 1
    assert data["recent"][0]["n"] == 1


def test_api_returns_503_when_redis_down(broken_client):
    res = broken_client.post("/api/visit")
    assert res.status_code == 503
    assert res.get_json()["error"] == "redis_unavailable"


def test_metrics(client, broken_client):
    client.post("/api/visit")
    body = client.get("/metrics").get_data(as_text=True)
    assert "visit_counter_visits_total 1" in body
    assert "visit_counter_redis_up 1" in body
    assert "visit_counter_redis_up 0" in broken_client.get("/metrics").get_data(as_text=True)
