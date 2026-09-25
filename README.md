# A calculator that stays on the line

HTTP/1.1 over a raw socket. No framework, no `http.server`.

```
python3 server.py          # listens on 8080
python3 test_client.py     # one socket, every request
```

`test_client.py` opens **one** connection with `socket.create_connection`,
sends all nine requests down it, and checks the socket is still usable
afterwards.

## What it answers

| request                  | status | body |
|--------------------------|--------|------|
| `GET /add?a=2&b=3`       | 200    | 5    |
| `GET /sub?a=10&b=4`      | 200    | 6    |
| `GET /mul?a=6&b=7`       | 200    | 42   |
| `GET /div?a=9&b=3`       | 200    | 3    |
| `GET /div?a=1&b=0`       | 400    | division by zero |
| `GET /add?a=x&b=3`       | 400    | not numbers |
| `GET /pow?a=2&b=8`       | 404    | no such operation |
| `POST /add`              | 405    | `Allow: GET` |
| `GET /add` with no Host  | 400    | HTTP/1.1 requires one |

## The part that is actually hard

`recv()` is not a message. It hands back whatever TCP felt like delivering:
half a request, or three of them glued together. So the loop in `handle()`
keeps a `buffer` that survives between requests and does two things:

1. Reads until `\r\n\r\n` appears — the end of the header block. Whatever
   came after it stays in the buffer.
2. Consumes **exactly** `Content-Length` bytes of body. Byte n+1 is the
   first byte of the next request, so it is left where it is.

That is why this works in a single write:

```
POST /add HTTP/1.1\r\nHost: x\r\nContent-Length: 7\r\n\r\na=2&b=3GET /mul?a=6&b=7 HTTP/1.1\r\nHost: x\r\n\r\n
```

The server replies 405 then 200 42, in order. That is pipelining, and it
falls out for free once you stop confusing a read with a message.

## Stretch bits that are in

- **`Connection: close`** is honoured — the server echoes it and hangs up.
- **Idle timeout, 30s.** A connection that has been answered and then goes
  silent is closed. The number is a guess at "a browser might click again
  soon" balanced against "a thread is not free"; it is a knob at the top of
  the file, not a law.
- **Pipelining**, per above.

Chunked encoding is not implemented — the server only frames bodies by
`Content-Length`.
