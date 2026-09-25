#!/usr/bin/env python3
"""Marks the server the way the assignment does: ONE socket, every request."""

import socket
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# (request bytes, expected status, expected body or None)
CASES = [
    ("GET /add?a=2&b=3 HTTP/1.1\r\nHost: localhost\r\n\r\n",  200, "5"),
    ("GET /sub?a=10&b=4 HTTP/1.1\r\nHost: localhost\r\n\r\n", 200, "6"),
    ("GET /mul?a=6&b=7 HTTP/1.1\r\nHost: localhost\r\n\r\n",  200, "42"),
    ("GET /div?a=9&b=3 HTTP/1.1\r\nHost: localhost\r\n\r\n",  200, "3"),
    ("GET /div?a=1&b=0 HTTP/1.1\r\nHost: localhost\r\n\r\n",  400, None),
    ("GET /add?a=x&b=3 HTTP/1.1\r\nHost: localhost\r\n\r\n",  400, None),
    ("GET /pow?a=2&b=8 HTTP/1.1\r\nHost: localhost\r\n\r\n",  404, None),
    ("POST /add HTTP/1.1\r\nHost: localhost\r\nContent-Length: 7\r\n\r\na=2&b=3",
                                                              405, None),
    ("GET /add?a=2&b=3 HTTP/1.1\r\n\r\n",                     400, None),
]


def read_response(sock, buffer):
    """Read exactly one response. Returns (status, body, leftover buffer)."""
    while b"\r\n\r\n" not in buffer:
        buffer += sock.recv(4096)
    head, buffer = buffer.split(b"\r\n\r\n", 1)
    lines = head.decode().split("\r\n")
    status = int(lines[0].split(" ")[1])

    length = 0
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if name.lower() == "content-length":
            length = int(value.strip())
    while len(buffer) < length:
        buffer += sock.recv(4096)
    return status, buffer[:length].decode(), buffer[length:]


def main():
    sock = socket.create_connection(("localhost", PORT))   # 1 TCP handshake
    buffer = b""
    failures = 0

    for request, want_status, want_body in CASES:
        sock.sendall(request.encode())
        status, body, buffer = read_response(sock, buffer)

        ok = status == want_status and (want_body is None or body == want_body)
        failures += not ok
        line = request.split("\r\n")[0]
        print("%-4s %-34s -> %d %-4s %s"
              % ("ok" if ok else "FAIL", line, status,
                 body if want_body else "", "" if ok else "(want %s)" % want_status))

    # still alive? ask it one more thing on the same socket.
    sock.sendall(b"GET /add?a=1&b=1 HTTP/1.1\r\nHost: localhost\r\n\r\n")
    status, body, buffer = read_response(sock, buffer)
    alive = status == 200 and body == "2"

    print("\nsocket still open: %s" % alive)
    print("1 TCP handshake, %d responses" % (len(CASES) + 1))
    sock.close()
    return 1 if failures or not alive else 0


if __name__ == "__main__":
    raise SystemExit(main())
