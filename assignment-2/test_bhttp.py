#!/usr/bin/env python3
"""Checks bserve against SPEC.md. Start the server first:

    ./bserve ./www 9000 &
    python3 test_bhttp.py
"""

import socket
import sys

PORT        = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
PREFACE     = b"BHTTP\x01\r\n"
HEADERS     = 0x01
END_MESSAGE = 0x01


def frame(kind, flags, request_id, payload=b""):
    return (len(payload).to_bytes(3, "big") + bytes([kind, flags])
            + request_id.to_bytes(2, "big") + b"\x00" + payload)


def get_request(path):
    """:method GET, :path <path> -- static indexes 1 and 2."""
    return bytes([0x81, 3]) + b"GET" + bytes([0x82, len(path)]) + path.encode()


def read_frame(sock):
    head = b""
    while len(head) < 8:
        chunk = sock.recv(8 - len(head))
        if not chunk:
            return None
        head += chunk
    length = int.from_bytes(head[0:3], "big")
    payload = b""
    while len(payload) < length:
        payload += sock.recv(length - len(payload))
    return head[3], head[4], int.from_bytes(head[5:7], "big"), payload


def status_of(payload):
    """Find :status (static index 3, byte 0x83) and read its value."""
    i = payload.index(0x83)
    return int(payload[i + 2:i + 2 + payload[i + 1]])


def read_message(sock):
    """One HEADERS frame plus any DATA frames. Returns (status, body)."""
    status, body = 0, b""
    while True:
        kind, flags, _, payload = read_frame(sock)
        if kind == HEADERS:
            status = status_of(payload)
        elif kind == 0x02:
            body += payload
        if flags & END_MESSAGE:
            return status, body


def connect():
    sock = socket.create_connection(("localhost", PORT))
    sock.sendall(PREFACE)
    return sock


CHECKS = []


def check(name):
    def wrap(fn):
        CHECKS.append((name, fn))
        return fn
    return wrap


@check("a file is served with status 200 and its bytes")
def _():
    sock = connect()
    sock.sendall(frame(HEADERS, END_MESSAGE, 1, get_request("/hello.txt")))
    status, body = read_message(sock)
    sock.close()
    return status == 200 and body == b"plain bytes\n"


@check("three requests travel down ONE connection")
def _():
    sock = connect()
    results = []
    for request_id, path in enumerate(["/index.html", "/hello.txt", "/index.html"], 1):
        sock.sendall(frame(HEADERS, END_MESSAGE, request_id, get_request(path)))
        results.append(read_message(sock)[0])
    sock.close()
    return results == [200, 200, 200]


@check("a missing file is 404, and the connection survives it")
def _():
    sock = connect()
    sock.sendall(frame(HEADERS, END_MESSAGE, 1, get_request("/nope.html")))
    missing = read_message(sock)[0]
    sock.sendall(frame(HEADERS, END_MESSAGE, 2, get_request("/hello.txt")))
    after = read_message(sock)[0]
    sock.close()
    return missing == 404 and after == 200


@check("a path escaping the root is never served")
def _():
    sock = connect()
    sock.sendall(frame(HEADERS, END_MESSAGE, 1, get_request("/../bserve")))
    status, body = read_message(sock)
    sock.close()
    return status == 404 and b"bserve" not in body


@check("an unknown frame type is skipped cleanly (SPEC.md section 6)")
def _():
    sock = connect()
    sock.sendall(frame(0x42, 0x00, 0, b"a frame from a later version"))
    sock.sendall(frame(HEADERS, END_MESSAGE, 1, get_request("/hello.txt")))
    status, body = read_message(sock)
    sock.close()
    return status == 200 and body == b"plain bytes\n"


@check("a malformed header block is 400")
def _():
    sock = connect()
    sock.sendall(frame(HEADERS, END_MESSAGE, 1, bytes([40]) + b"short"))
    status, _ = read_message(sock)
    sock.close()
    return status == 400


@check("a bad preface is refused")
def _():
    sock = socket.create_connection(("localhost", PORT))
    sock.sendall(b"GET / HTTP/1.1\r\n")      # textual HTTP, wrong protocol
    status, _ = read_message(sock)
    sock.close()
    return status == 400


def main():
    failures = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as err:
            ok, name = False, "%s  [%s]" % (name, err)
        failures += not ok
        print("%-5s %s" % ("ok" if ok else "FAIL", name))
    print("\n%d/%d checks passed" % (len(CHECKS) - failures, len(CHECKS)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
