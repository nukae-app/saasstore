"""Limitador de llamadas a Discogs compartido por Redis (services/ratelimit.py)."""

import httpx
import pytest
import redis

from app.services import discogs, ratelimit


class FakeRedis:
    """Redis mínimo (set NX/PX y pttl) con reloj controlado por el test."""

    def __init__(self, clock):
        self.clock = clock
        self.data = {}  # key -> expira (ms)

    def _alive(self, key):
        return key in self.data and self.data[key] > self.clock["ms"]

    def set(self, key, value, nx=False, px=None):
        if nx and self._alive(key):
            return None
        self.data[key] = self.clock["ms"] + (px or 10**12)
        return True

    def pttl(self, key):
        return int(self.data[key] - self.clock["ms"]) if self._alive(key) else -2


@pytest.fixture
def rl(monkeypatch):
    clock = {"ms": 1_000_000}
    fake = FakeRedis(clock)

    def sleep(seconds):
        clock["ms"] += int(seconds * 1000)

    monkeypatch.setattr(ratelimit, "_redis", lambda: fake)
    monkeypatch.setattr(ratelimit, "_sleep", sleep)
    monkeypatch.setattr(ratelimit, "_now", lambda: clock["ms"] / 1000)
    monkeypatch.setattr(ratelimit, "_down_until", 0.0)
    return SimpleNamespaceLike(clock=clock, fake=fake)


class SimpleNamespaceLike:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_primera_llamada_pasa_y_la_segunda_espera_el_hueco(rl):
    assert ratelimit.acquire("tok") is True
    t0 = rl.clock["ms"]
    assert ratelimit.acquire("tok") is True
    assert rl.clock["ms"] - t0 >= ratelimit.SPACING_MS


def test_tokens_distintos_no_se_bloquean_entre_si(rl):
    ratelimit.acquire("tok-a")
    t0 = rl.clock["ms"]
    ratelimit.acquire("tok-b")
    assert rl.clock["ms"] == t0


def test_la_clave_no_contiene_el_token(rl):
    ratelimit.acquire("secreto-super-largo")
    assert all("secreto" not in k for k in rl.fake.data)


def test_429_provoca_pausa_comun_de_un_minuto(rl):
    ratelimit.acquire("tok")
    ratelimit.note_response("tok", 429, {})
    t0 = rl.clock["ms"]
    ratelimit.acquire("tok")
    assert rl.clock["ms"] - t0 >= ratelimit.PAUSE_ON_429_MS - 1100


def test_poco_margen_en_la_cabecera_provoca_pausa_corta(rl):
    ratelimit.note_response("tok", 200, {"X-Discogs-Ratelimit-Remaining": "2"})
    t0 = rl.clock["ms"]
    ratelimit.acquire("tok")
    assert rl.clock["ms"] - t0 >= ratelimit.PAUSE_LOW_REMAINING_MS - 100


def test_con_margen_suficiente_no_hay_pausa(rl):
    ratelimit.note_response("tok", 200, {"X-Discogs-Ratelimit-Remaining": "40"})
    t0 = rl.clock["ms"]
    ratelimit.acquire("tok")
    assert rl.clock["ms"] == t0


def test_cabecera_ausente_o_rara_se_ignora(rl):
    ratelimit.note_response("tok", 200, {})
    ratelimit.note_response("tok", 200, {"X-Discogs-Ratelimit-Remaining": "n/a"})
    assert rl.fake.data == {}


def test_sin_redis_devuelve_false_y_no_reintenta_durante_un_rato(monkeypatch):
    llamadas = []

    def broken():
        llamadas.append(1)
        raise redis.ConnectionError("sin redis")

    monkeypatch.setattr(ratelimit, "_redis", broken)
    monkeypatch.setattr(ratelimit, "_down_until", 0.0)
    assert ratelimit.acquire("tok") is False
    assert ratelimit.acquire("tok") is False
    assert len(llamadas) == 1  # el segundo no vuelve a intentar Redis


def test_el_cliente_usa_el_limitador_en_cada_peticion_con_token(monkeypatch):
    llamadas = []
    monkeypatch.setattr(ratelimit, "acquire", lambda token: llamadas.append(token) or True)
    client = discogs._client("tok")

    def handler(request):
        return httpx.Response(200, json={})

    client._transport = httpx.MockTransport(handler)
    client.get("/oauth/identity")
    client.get("/oauth/identity")
    assert llamadas == ["tok", "tok"]


def test_el_cliente_sin_token_no_usa_el_limitador(monkeypatch):
    monkeypatch.setattr(ratelimit, "acquire", lambda token: pytest.fail("no debe limitar sin token"))
    client = discogs._client(None)
    client._transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    client.get("/database/search")


def test_una_escritura_bloqueada_no_gasta_turno(monkeypatch):
    monkeypatch.setattr(ratelimit, "acquire", lambda token: pytest.fail("no debe gastar turno"))
    with discogs._client(discogs.ReadOnlyToken("tok")) as c:
        with pytest.raises(discogs.DiscogsReadOnlyError):
            c.post("/marketplace/listings")
