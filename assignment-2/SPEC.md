# BHTTP/1 — HTTP semantics in binary frames

Version 1. Everything a stranger needs to write an interoperating server or
client. Written to be implemented twice, independently.

## 0. Words used here

| Term | Meaning |
|---|---|
| TCP (Transmission Control Protocol) | The reliable byte stream this runs on. BHTTP adds message boundaries that TCP does not provide. |
| Frame | One length-prefixed unit on the wire: an 8-byte fixed header plus a payload. |
| Message | One request or one response. It is one HEADERS frame, optionally followed by DATA frames. |
| Peer / receiver | Whichever side is currently reading. |
| Octet | Eight bits. Used where "byte" could be ambiguous. |
| Big-endian | Most significant byte first, the ordering every field here uses. |
| HPACK | HTTP/2's header compression scheme. BHTTP borrows its first two ideas and names them in §4. |
| MUST / MAY | Requirement levels. MUST is not negotiable; ignoring one makes an implementation non-conforming. |

## 1. Connection

The client opens **one** TCP connection and sends an 8-octet preface before
anything else:

`42 48 54 54 50 01 0d 0a`  —  `B H T T P` then version `0x01` then CR LF.

The server reads exactly 8 octets. If they are not that sequence it answers
400 and closes. The version octet is how a future BHTTP/2 announces itself
without ambiguity on the first byte of a connection.

The client then sends request frames and reads response frames. The server
**keeps the connection open** until the client closes it. There is no
per-request teardown; that is the whole point of framing.

## 2. The frame header — 8 octets, fixed

Every frame, of every type, in every version, begins with these 8 octets.

| Offset | Width | Field | Meaning |
|---|---|---|---|
| 0 | 24 bits | Length | Payload octets that follow this header. Does not include the header. |
| 3 | 8 bits | Type | What the payload is. §3. |
| 4 | 8 bits | Flags | Per-type bit flags. §3.1. |
| 5 | 16 bits | Request ID | Names the request this frame belongs to. |
| 7 | 8 bits | Reserved | Senders MUST write 0. Receivers MUST ignore it. |

### 2.1 Why these widths

**Length, 24 bits.** A receiver must size a buffer *before* it knows what the
frame is, so the cap on this field is the cap on what a stranger can make you
allocate. 24 bits caps one frame at 16,777,215 octets (16 mebibytes). At 32
bits a hostile sender asks for 4 gibibytes in four octets. At 16 bits every
file over 64 kibibytes needs splitting, which is bookkeeping bought for
nothing. HTTP/2 chose 24 bits for this same reason.

**Type, 8 bits.** 256 types; this version defines two. A 4-bit type would
save half an octet and spend the room that §6 depends on.

**Flags, 8 bits.** This version defines one. Flags are interpreted *per type*,
so the space does not run out globally.

**Request ID, 16 bits.** A response must be able to name the request it
answers, or a client that sent three requests cannot match the replies.
65,535 is far more than one connection will have outstanding. HTTP/2 spends
31 bits here because it multiplexes interleaved streams; BHTTP/1 answers in
order and does not, so the extra 15 bits would be decoration.

**Reserved, 8 bits.** It pads the header to 8 octets, so reading one is a
single aligned 64-bit read rather than HTTP/2's awkward 9. More importantly it
is pre-agreed space: because receivers MUST ignore it today, a later version
can define it without changing the header size or breaking anyone.

## 3. Frame types

| Value | Name | Payload |
|---|---|---|
| 0x01 | HEADERS | An encoded header list (§4). Starts a message. |
| 0x02 | DATA | Raw body octets. |
| all others | — | Undefined in this version. MUST be skipped. See §6. |

### 3.1 Flags

| Bit | Name | Meaning |
|---|---|---|
| 0x01 | END_MESSAGE | This is the last frame of this message. |

A response with a body is HEADERS (no flag) then DATA (END_MESSAGE). A
response with no body is a single HEADERS frame carrying END_MESSAGE. A GET
request is a single HEADERS frame carrying END_MESSAGE.

## 4. Header encoding

Two mechanisms, both lifted from HPACK, in the order HPACK introduces them.

**Mechanism one — index the names you actually send.** Ten names cover every
header these programs exchange, so they are numbered 1 to 10:

| # | Name | # | Name |
|---|---|---|---|
| 1 | `:method` | 6 | `content-type` |
| 2 | `:path` | 7 | `date` |
| 3 | `:status` | 8 | `server` |
| 4 | `host` | 9 | `connection` |
| 5 | `content-length` | 10 | `user-agent` |

Names beginning with a colon are *pseudo-headers*: fields that were part of
the request or status line in textual HTTP and have nowhere else to live once
the line is gone.

**Mechanism two — length-prefix everything else.** A field is encoded as one
prefix octet, then possibly a name, then a value:

| Prefix octet | Meaning | What follows |
|---|---|---|
| High bit set (`0x80` + n) | Name is static table entry n (1..10) | The value |
| High bit clear (1..127) | Name is a literal of that many octets | The name octets, then the value |

A value is itself length-prefixed: one octet of length, or the escape `0xFF`
followed by a 16-bit length for values of 255 octets or more.

The header list ends when the payload ends. The frame header already said how
long the payload is, so no terminator and no count is needed.

BHTTP/1 deliberately omits HPACK's third mechanism, Huffman coding of string
literals. It saves roughly a fifth of the header octets and costs a canonical
code table plus a bit-level decoder, which is the wrong trade for a spec that
has to be implemented twice in an evening.

## 5. Requests, responses, errors

A request MUST carry `:method` and `:path`. A response MUST carry `:status`,
a decimal string. The server maps `:path` to a file beneath its root. A path
that resolves outside the root is treated as not found — never as a file.

| Status | When |
|---|---|
| 200 | The file was read and is in the DATA frames. |
| 400 | The frame did not parse: a bad preface, a length that runs past the payload, an index not in the table, a request with no `:method` or `:path`. |
| 404 | No such file, or a path that escaped the root. |

A 400 means the reader has lost its place in the stream, because the thing
that went wrong was the framing itself. The server answers once and closes.
404 is an ordinary answer and the connection stays open.

## 6. The rule you may not skip

**A receiver that meets a frame type it does not recognise MUST read Length
octets, discard them, and carry on reading the next frame header.** It MUST
NOT close the connection, error, or guess.

This works because Length sits in the fixed header at a known offset and its
meaning does not depend on Type. A receiver can therefore step over a frame it
cannot interpret without understanding one octet of its contents.

That single rule is what leaves room for a version 2. A future sender can
introduce a SETTINGS or PUSH frame and send it to a BHTTP/1 receiver, which
will step over it and keep working, rather than dying on a type it was written
before. An extension nobody can ignore is not an extension; it is a new
protocol. `./bcurl --probe-unknown` sends a type `0x42` frame to prove a
conforming server does this.

## 7. Limits

A receiver MAY refuse a frame whose Length exceeds its buffer limit and answer
400. The 24-bit field makes 16 mebibytes the ceiling nobody can exceed.
