"""The suite never reaches a live service or the network (REF S70): tests/live_guard.py, installed by tests/conftest.py.

Each test checks first that the guard is installed, so with it switched off (one of its proofs) a test fails before
trying any connection. The refusal tests also stand in for the network: a connection the guard let through would fail
the test instead of leaving the process. So nothing live is reached even when the guard is broken.
"""
from __future__ import annotations

import _socket
import asyncio
import socket

import pytest

from tests import live_guard


def _installed() -> None:
    assert live_guard.installed()


@pytest.fixture
def no_network(monkeypatch):
    def reached(self, address):
        pytest.fail(f"the guard let a connection through to {address}")
    monkeypatch.setattr(live_guard, "real_connect", reached)
    monkeypatch.setattr(live_guard, "real_connect_ex", reached)


@pytest.mark.parametrize("port", sorted(live_guard.LIVE_PORTS))
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_a_live_service_on_this_mac_is_refused_at_once(no_network, host, port):
    _installed()
    with pytest.raises(ConnectionRefusedError, match="tests never reach a live service"):
        socket.create_connection((host, port), timeout=1)
    probe = socket.socket()
    try:
        with pytest.raises(ConnectionRefusedError, match="tests never reach a live service"):
            probe.connect_ex(("127.0.0.1", port))
    finally:
        probe.close()


def test_an_address_off_this_machine_is_refused_at_once(no_network):
    _installed()
    with pytest.raises(ConnectionRefusedError, match="tests never reach the network"):
        socket.create_connection(("192.0.2.1", 80), timeout=1)  # TEST-NET-1: documentation only, never routed


def test_a_loopback_port_the_test_did_not_open_is_refused(no_network):
    """A port some other process might be listening on, a local proxy among them (the red team's L1)."""
    _installed()
    scratch = _socket.socket()  # the C class: binding it is not recorded, as another process's port would not be
    scratch.bind(("127.0.0.1", 0))
    port = scratch.getsockname()[1]
    scratch.close()
    with pytest.raises(ConnectionRefusedError, match="tests connect only to ports they opened"):
        socket.create_connection(("127.0.0.1", port), timeout=1)


def test_a_connection_through_asyncio_is_refused_too(no_network):
    _installed()

    async def dial():
        await asyncio.open_connection("127.0.0.1", 11434)

    with pytest.raises(ConnectionRefusedError, match="tests never reach a live service"):
        asyncio.run(dial())


def test_uvloop_is_blocked_so_every_loop_is_asyncios():
    """uvloop connects from its own C code, which the guard cannot see (the red team's M1)."""
    _installed()
    with pytest.raises(ImportError):
        import uvloop  # noqa: F401


def test_a_port_of_the_tests_own_is_still_reachable():
    _installed()
    server = socket.socket()
    try:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        assert port in live_guard.OWN_PORTS and port not in live_guard.LIVE_PORTS
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    finally:
        server.close()


def test_the_list_is_every_live_service_on_this_mac():
    from assistant import settings
    assert live_guard.LIVE_PORTS == {settings.SALES_PORT, settings.TIBI_PORT, settings.DIAGRAMS_PORT, settings.CORE_PORT,
                                     11434, 11435, 5200, 8791}
    assert live_guard.LIVE_PORTS == {8780, 8773, 5300, 8010, 11434, 11435, 5200, 8791}
