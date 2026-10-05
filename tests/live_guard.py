"""Tests never reach a live service or the network (REF S70).

On this Mac the Sales workspace, Tibi, the diagram service, a lone core, a branch check, OpsAtlas Classic and two model
servers (ours, and another project's that nothing here may touch) listen on fixed ports. Before S70, every gate run
connected 13 times to our model server and once to the diagram service; the tests passed either way.

The rule: a test connects only to a loopback port that this test process opened itself, and never to a live service's
port. Any other connection is refused at once: ``connect`` and ``connect_ex`` raise ``ConnectionRefusedError`` naming
the rule. A proxy set in the environment is just another port the process did not open (S70's red team, L1).

uvloop is blocked in the test process. It connects from its own C code, which this guard cannot see, and uvicorn uses it
by default (S70's red team, M1), so asyncio's own loop, which goes through the guarded methods, is always used.

tests/conftest.py installs the guard before any test module is imported, so code that runs at import is covered too, and
checks after every test that it is still installed.

Outside it: a subprocess or a multiprocessing child (each starts without it), UDP datagrams (``sendto``), the C socket
class used directly (``_socket.socket``, ``socket.SocketType``), and name lookups.
"""
from __future__ import annotations

import _socket
import operator
import socket
import sys
from urllib.parse import urlsplit

from assistant.settings import CORE_PORT, DIAGRAMS_PORT, OLLAMA_URL, SALES_PORT, TIBI_PORT

OTHER_PROJECTS_MODEL_PORT = 11435  # another project's model server on this Mac
CLASSIC_PORT = 5200  # OpsAtlas Classic, frozen in its own folder
BRANCH_CHECK_PORT = 8791  # a branch checked in the browser from its worktree
LIVE_PORTS = frozenset({SALES_PORT, TIBI_PORT, DIAGRAMS_PORT, CORE_PORT, urlsplit(OLLAMA_URL).port,
                        OTHER_PROJECTS_MODEL_PORT, CLASSIC_PORT, BRANCH_CHECK_PORT})
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
OWN_PORTS: set[int] = set()  # the ports this process has bound; a port stays here after its socket closes

# The socket class's own methods, as module names so that a test can stand in for the network (tests/test_live_guard.py).
real_connect = _socket.socket.connect
real_connect_ex = _socket.socket.connect_ex


def refused(address) -> str | None:
    """Why a connection to ``address`` is refused, or None when it may go ahead: a loopback port this process opened, or
    a local (Unix) socket."""
    if not (isinstance(address, tuple) and len(address) >= 2):
        return None
    host = str(address[0])
    try:
        port = operator.index(address[1])
    except TypeError:
        return f"tests never reach the network ({host}:{address[1]!r})"
    if host not in LOOPBACK:
        return f"tests never reach the network ({host}:{port})"
    if port in LIVE_PORTS:
        return f"tests never reach a live service ({host}:{port})"
    if port not in OWN_PORTS:
        return f"tests connect only to ports they opened ({host}:{port})"
    return None


def guarded_connect(self, address):
    if why := refused(address):
        raise ConnectionRefusedError(why)
    return real_connect(self, address)


def guarded_connect_ex(self, address):
    if why := refused(address):
        raise ConnectionRefusedError(why)
    return real_connect_ex(self, address)


def guarded_bind(self, address):
    _socket.socket.bind(self, address)
    if self.family in (socket.AF_INET, socket.AF_INET6):
        OWN_PORTS.add(self.getsockname()[1])


def install() -> None:
    if sys.modules.get("uvloop") is not None:
        raise RuntimeError("uvloop was imported before the live-service guard; tests never use it (REF S70)")
    sys.modules["uvloop"] = None  # `import uvloop` fails, so uvicorn's "auto" loop is asyncio's
    socket.socket.connect, socket.socket.connect_ex = guarded_connect, guarded_connect_ex
    socket.socket.bind = guarded_bind


def installed() -> bool:
    own = vars(socket.socket)
    return (own.get("connect") is guarded_connect and own.get("connect_ex") is guarded_connect_ex
            and own.get("bind") is guarded_bind and "uvloop" in sys.modules and sys.modules["uvloop"] is None)


def uninstall() -> None:
    """Only for the guard's proof (tests/guard_register.py): the socket class's own methods, and uvloop, again."""
    for name in ("connect", "connect_ex", "bind"):
        if name in vars(socket.socket):
            delattr(socket.socket, name)
    if "uvloop" in sys.modules and sys.modules["uvloop"] is None:
        del sys.modules["uvloop"]
