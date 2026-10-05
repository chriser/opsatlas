"""The suite never reaches a live service or the network (REF S70): tests/live_guard.py, installed by tests/conftest.py.

Each test first checks that the guard is installed, so with the guard switched off (its proof in the guard register) it
fails before any connection is tried, and nothing live is reached even then.
"""
from __future__ import annotations

import socket

import pytest

from tests import live_guard


def _installed() -> None:
    assert socket.socket.connect is live_guard.guarded_connect
    assert socket.socket.connect_ex is live_guard.guarded_connect_ex


@pytest.mark.parametrize("port", sorted(live_guard.LIVE_PORTS))
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_a_live_service_on_this_mac_is_refused_at_once(host, port):
    _installed()
    with pytest.raises(ConnectionRefusedError, match="tests never reach a live service"):
        socket.create_connection((host, port), timeout=1)
    probe = socket.socket()
    try:
        with pytest.raises(ConnectionRefusedError, match="tests never reach a live service"):
            probe.connect_ex(("127.0.0.1", port))
    finally:
        probe.close()


def test_an_address_off_this_machine_is_refused_at_once():
    _installed()
    with pytest.raises(ConnectionRefusedError, match="tests never reach the network"):
        socket.create_connection(("192.0.2.1", 80), timeout=1)  # TEST-NET-1: documentation only, never routed


def test_a_port_of_the_tests_own_is_still_reachable():
    _installed()
    server = socket.socket()
    try:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        assert port not in live_guard.LIVE_PORTS
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    finally:
        server.close()


def test_the_list_covers_every_service_the_settings_name():
    from assistant import settings
    assert {settings.SALES_PORT, settings.TIBI_PORT, settings.DIAGRAMS_PORT, settings.CORE_PORT, 11434, 11435} <= \
        live_guard.LIVE_PORTS
