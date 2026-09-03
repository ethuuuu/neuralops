"""Egress guard: blocks and records every outbound connection attempt.

This is the evidence for the sovereign claim. Rather than asserting that
nothing leaves the machine, we intercept every socket connection at the
Python level, allow only loopback, and log the rest as blocked.

Import and call install() before anything else in main.
"""
import socket, ipaddress
from . import trace

_ATTEMPTS = []
_allowed = {"127.0.0.1", "localhost", "::1"}


def attempts():
    return list(_ATTEMPTS)


def _is_local(host: str) -> bool:
    if host in _allowed:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def install(allowed_hosts=None):
    if allowed_hosts:
        _allowed.update(allowed_hosts)

    real_connect = socket.socket.connect

    def guarded_connect(self, address, *a, **kw):
        host = address[0] if isinstance(address, tuple) else str(address)
        allowed = _is_local(str(host))
        rec = {"host": str(host), "allowed": allowed}
        _ATTEMPTS.append(rec)
        trace.emit("egress", **rec)
        if not allowed:
            raise PermissionError(
                f"Blocked outbound connection to {host}. "
                "This system is air-gapped by design."
            )
        return real_connect(self, address, *a, **kw)

    socket.socket.connect = guarded_connect
    trace.emit("egress_guard", status="installed", allowed=sorted(_allowed))


def summary():
    external = [a for a in _ATTEMPTS if not a["allowed"]]
    return {
        "total_attempts": len(_ATTEMPTS),
        "local": len(_ATTEMPTS) - len(external),
        "external_blocked": len(external),
        "external_hosts": sorted({a["host"] for a in external}),
    }
