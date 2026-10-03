# BHTTP/1 — HTTP, in binary

Course project: design a binary framing layer with HTTP semantics, write the
spec, then implement both ends of it.

| File | What it is |
|---|---|
| [SPEC.md](SPEC.md) | **The protocol.** The deliverable. Enough for a stranger to implement either end. |
| [HEXDUMP.md](HEXDUMP.md) | One complete request and response, annotated octet by octet. |
| `bserve` | Track 1 — the server. |
| `bcurl` | Track 2 — the client. |
| `test_bhttp.py` | Seven conformance checks against the spec. |
| `www/` | A web root to serve. |

## Run it

```
./bserve ./www 9000 &
./bcurl -v localhost:9000/index.html      # -v hexdumps every frame
python3 test_bhttp.py                     # 7/7
```

`bcurl` writes the body to stdout and exits non-zero on 4xx and 5xx, so it
composes with a shell the way curl does.

## The design, in one paragraph

The frame header is 8 octets: a 24-bit length, an 8-bit type, 8 bits of
flags, a 16-bit request id, and one reserved octet. Length comes first and
its meaning never depends on type, which is what lets a receiver step over a
frame it has never heard of. 24 bits caps a frame at 16 mebibytes, so a
stranger cannot make you allocate a gibibyte before you know what the frame
even is. The reserved octet pads the header to one aligned 64-bit read and
gives version 2 somewhere to put a field. Headers borrow HPACK's first two
mechanisms: the ten names these programs actually send are numbered, and
everything else is length-prefixed. SPEC.md section 2.1 defends each width.

## The rule that matters

A receiver meeting a frame type it does not know **must** read the length,
discard that many octets, and carry on. Prove it:

```
./bcurl --probe-unknown localhost:9000/hello.txt
```

That sends a type `0x42` frame — defined by no version of this protocol —
down the connection ahead of a real request. The server logs
`skipped unknown frame type 0x42 (28 bytes)` and answers the request anyway.
An extension nobody can ignore is not an extension; it is a new protocol.

## A note on the two tracks

The project is meant for a pair, one person per track, with only the spec
crossing between them. Done solo, so `bserve` and `bcurl` **share no code** —
no common module, no imported codec. Each encodes and decodes from SPEC.md
alone, and the duplicated functions in the two files are duplicated on
purpose. A client that only works against its own server is an
implementation, not a protocol.

## Known limits

- `bserve` handles one connection at a time. Framing was the exercise;
  concurrency is an accept loop and a thread away.
- No Huffman coding of header literals — HPACK's third mechanism, deliberately
  left out. SPEC.md section 4 explains the trade.
- No request bodies in practice: `bserve` reads DATA frames on a request and
  discards them, since a file server has nothing to do with them.
