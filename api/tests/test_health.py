"""L'endpoint /health ha de comprovar Postgres, Redis, i el heartbeat del
worker de Celery de veritat, no ser un no-op. A l'entorn de tests no hi ha
cap Redis real escoltant, així que el cas per defecte exercita el camí de
fallada; mockejem `get_redis_client` per exercitar els altres casos."""

from app import routers


class _FakeRedis:
    def __init__(self, heartbeat=b"2026-01-01T00:00:00+00:00", queue_depth=0):
        self._heartbeat = heartbeat
        self._queue_depth = queue_depth

    def ping(self):
        return True

    def get(self, key):
        return self._heartbeat

    def llen(self, key):
        return self._queue_depth


def test_health_sense_redis_dona_503_i_marca_redis_i_worker(client):
    """Sense Redis real a l'entorn de tests, redis i worker han de fallar
    net (no petar la petició) i respondre 503 amb el detall de cada check."""
    resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is False
    assert body["checks"]["worker"]["ok"] is False
    assert body["queue_depth"] is None


def test_health_tot_ok_amb_heartbeat_recent(client, monkeypatch):
    monkeypatch.setattr(routers.health, "get_redis_client", lambda: _FakeRedis(queue_depth=3))
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["redis"]["ok"] is True
    assert body["checks"]["worker"]["ok"] is True
    assert body["checks"]["worker"]["last_heartbeat"] == "2026-01-01T00:00:00+00:00"
    assert body["queue_depth"] == 3


def test_health_worker_sense_heartbeat_dona_503(client, monkeypatch):
    """Redis respon (broker viu) però no hi ha cap heartbeat — worker/beat
    penjats o mai arrencats. Ha de distingir-se d'un fallo de Redis."""
    monkeypatch.setattr(routers.health, "get_redis_client", lambda: _FakeRedis(heartbeat=None))
    resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["checks"]["redis"]["ok"] is True
    assert body["checks"]["worker"]["ok"] is False
