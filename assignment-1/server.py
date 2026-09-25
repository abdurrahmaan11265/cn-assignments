#!/usr/bin/env python3
"""HTTP/1.1 calculator. One socket, many requests.

Run: python3 server.py [port]      (default 8080)
"""

import socket
import sys
import threading

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
IDLE_TIMEOUT = 30          # close a connection that sits silent this long

OPS = {
    "/add": lambda a, b: a + b,
    "/sub": lambda a, b: a - b,
    "/mul": lambda a, b: a * b,
    "/div": lambda a, b: a / b,
}


def number(text):
    """'5' -> 5, '2.5' -> 2.5, 'x' -> ValueError."""
    try:
        return int(text)
    except ValueError:
        return float(text)


def show(value):
    """5.0 prints as 5, 2.5 stays 2.5."""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def parse_query(query):
    """'a=2&b=3' -> {'a': '2', 'b': '3'}"""
    out = {}
    for pair in query.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            out[key] = value
    return out


def build(status, reason, body, keep_alive, extra=""):
    body = body.encode()
    head = (
        "HTTP/1.1 %d %s\r\n"
        "Content-Type: text/plain\r\n"
        "Content-Length: %d\r\n"
        "Connection: %s\r\n"
        "%s"
        "\r\n" % (status, reason, len(body),
                  "keep-alive" if keep_alive else "close", extra)
    )
    return head.encode() + body


def route(method, target, has_host):
    """Return (status, reason, body)."""
    path, _, query = target.partition("?")

    if not has_host:                       # HTTP/1.1 requires Host
        return 400, "Bad Request", "missing Host header"
    if path not in OPS:
        return 404, "Not Found", "no such operation"
    if method != "GET":
        return 405, "Method Not Allowed", "use GET"

    args = parse_query(query)
    if "a" not in args or "b" not in args:
        return 400, "Bad Request", "need a and b"
    try:
        a, b = number(args["a"]), number(args["b"])
    except ValueError:
        return 400, "Bad Request", "a and b must be numbers"
    if path == "/div" and b == 0:
        return 400, "Bad Request", "division by zero"

    return 200, "OK", show(OPS[path](a, b))


def handle(sock, addr):
    """Serve every request on this one socket until somebody hangs up."""
    buffer = b""
    count = 0
    sock.settimeout(IDLE_TIMEOUT)
    try:
        while True:
            # 1. read until we have a full header block. recv() gives us
            #    whatever TCP felt like: half a request, or three of them.
            while b"\r\n\r\n" not in buffer:
                chunk = sock.recv(4096)
                if not chunk:
                    return                 # peer closed, we are done
                buffer += chunk

            head, buffer = buffer.split(b"\r\n\r\n", 1)
            lines = head.decode().split("\r\n")
            method, target, _ = lines[0].split(" ")

            headers = {}
            for line in lines[1:]:
                name, _, value = line.partition(":")
                headers[name.lower().strip()] = value.strip()

            # 2. consume exactly Content-Length bytes and not one more --
            #    byte n+1 is the start of the next request.
            length = int(headers.get("content-length", 0))
            while len(buffer) < length:
                buffer += sock.recv(4096)
            buffer = buffer[length:]

            # 3. answer, and decide whether the line stays up
            keep_alive = headers.get("connection", "").lower() != "close"
            status, reason, body = route(method, target, "host" in headers)
            extra = "Allow: GET\r\n" if status == 405 else ""
            sock.sendall(build(status, reason, body, keep_alive, extra))

            count += 1
            print("[%s:%d] %s %s -> %d" % (addr[0], addr[1], method, target, status))
            if not keep_alive:
                return
    except (socket.timeout, ConnectionError, ValueError, IndexError):
        pass                               # timed out or sent us nonsense
    finally:
        sock.close()
        print("[%s:%d] closed after %d request(s)" % (addr[0], addr[1], count))


def main():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("", PORT))
    listener.listen(5)
    print("listening on port %d" % PORT)

    while True:
        sock, addr = listener.accept()
        threading.Thread(target=handle, args=(sock, addr), daemon=True).start()


if __name__ == "__main__":
    main()
