"""Tests never reach a live service or the network (REF S70).

On this Mac the Sales workspace, Tibi, the diagram service, a lone core, a branch check, OpsAtlas Classic and two model
servers (ours, and another project's that nothing here may touch) listen on fixed ports. Before S70, every gate run
connected 13 times to our model server and once to the diagram service; the tests passed either way. tests/conftest.py
installs this guard before any test module is imported, so code that runs at import is covered too: a connection to one
of those ports, or to any address off this machine, is refused at once, as if it were down.

Outside it: a subprocess a test starts, and name lookups (only connections are refused).
"""
from __future__ import annotations

import _socket
import socket
from urllib.parse import urlsplit

from assistant.settings import CORE_PORT, DIAGRAMS_PORT, OLLAMA_URL, SALES_PORT, TIBI_PORT

OTHER_PROJECTS_MODEL_PORT = 11435  # another project's model server on this Mac
CLASSIC_PORT = 5200  # OpsAtlas Classic, frozen in its own folder
BRANCH_CHECK_PORT = 8791  # a branch checked in the browser from its worktree
LIVE_PORTS = frozenset({SALES_PORT, TIBI_PORT, DIAGRAMS_PORT, CORE_PORT, urlsplit(OLLAMA_URL).port,
                        OTHER_PROJECTS_MODEL_PORT, CLASSIC_PORT, BRANCH_CHECK_PORT})
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


def refused(address) -> str | None:
    """Why a connection to ``address`` is refused, or None when it may go ahead (a port of the test's own on this
    machine, or a local socket)."""
    if not (isinstance(address, tuple) and len(address) >= 2):
        return None
    host, port = str(address[0]), address[1]
    if host not in LOOPBACK:
        return f"tests never reach the network ({host}:{port})"
    if port in LIVE_PORTS:
        return f"tests never reach a live service ({host}:{port})"
    return None


def guarded_connect(self, address):
    if why := refused(address):
        raise ConnectionRefusedError(why)
    return _socket.socket.connect(self, address)


def guarded_connect_ex(self, address):
    if why := refused(address):
        raise ConnectionRefusedError(why)
    return _socket.socket.connect_ex(self, address)


def install() -> None:
    socket.socket.connect, socket.socket.connect_ex = guarded_connect, guarded_connect_ex


def uninstall() -> None:
    """Only for the guard's proof (tests/guard_register.py): the socket class's own methods again."""
    for name in ("connect", "connect_ex"):
        if name in vars(socket.socket):
            delattr(socket.socket, name)
