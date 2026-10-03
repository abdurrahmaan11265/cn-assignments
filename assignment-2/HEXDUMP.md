# One complete request and response, annotated

Captured from a real run, not written by hand:

```
./bserve ./www 9000 &
./bcurl -v localhost:9000/hello.txt
```

`www/hello.txt` contains the 12 octets `plain bytes\n`. The date field will
differ on your run; nothing else will.

---

## 1. The preface — 8 octets, sent once

```
0000  42 48 54 54 50 01 0d 0a                          BHTTP...
```

| Octets | Value | Meaning |
|---|---|---|
| 0–4 | `42 48 54 54 50` | The letters `BHTTP` |
| 5 | `01` | Protocol version 1 |
| 6–7 | `0d 0a` | Carriage return, line feed |

---

## 2. The request — one HEADERS frame, 50 octets

```
0000  00 00 2a 01 01 00 01 00 81 03 47 45 54 82 0a 2f  ..*.......GET../
0010  68 65 6c 6c 6f 2e 74 78 74 84 0e 6c 6f 63 61 6c  hello.txt..local
0020  68 6f 73 74 3a 39 30 30 30 8a 07 62 63 75 72 6c  host:9000..bcurl
0030  2f 31                                            /1
```

### The fixed header, octets 0–7

| Octets | Value | Field | Reading |
|---|---|---|---|
| 0–2 | `00 00 2a` | Length | 42 octets of payload follow the header. 8 + 42 = 50. |
| 3 | `01` | Type | HEADERS |
| 4 | `01` | Flags | END_MESSAGE set — a GET has no body, so this frame is the whole request |
| 5–6 | `00 01` | Request ID | 1 |
| 7 | `00` | Reserved | Sent as zero, as every sender MUST |

### The payload, octets 8–49

| Octets | Value | Reading |
|---|---|---|
| 8 | `81` | High bit set, so static index 1: the name is `:method` |
| 9 | `03` | The value is 3 octets long |
| 10–12 | `47 45 54` | `GET` |
| 13 | `82` | Static index 2: `:path` |
| 14 | `0a` | Value is 10 octets |
| 15–24 | `2f 68 65 6c 6c 6f 2e 74 78 74` | `/hello.txt` |
| 25 | `84` | Static index 4: `host` |
| 26 | `0e` | Value is 14 octets |
| 27–40 | `6c 6f ... 30 30` | `localhost:9000` |
| 41 | `8a` | Static index 10: `user-agent` |
| 42 | `07` | Value is 7 octets |
| 43–49 | `62 63 75 72 6c 2f 31` | `bcurl/1` |

Four header fields, 42 octets. The four names cost one octet each because
they are in the table; in textual HTTP the words `:method`, `:path`, `host`
and `user-agent` alone would have cost 26 octets before their values.

---

## 3. The response head — one HEADERS frame, 70 octets

```
0000  00 00 3e 01 00 00 01 00 83 03 32 30 30 86 0a 74  ..>.......200..t
0010  65 78 74 2f 70 6c 61 69 6e 85 02 31 32 88 08 62  ext/plain..12..b
0020  73 65 72 76 65 2f 31 87 1d 53 61 74 2c 20 30 33  serve/1..Sat, 03
0030  20 4f 63 74 20 32 30 32 36 20 30 37 3a 35 30 3a   Oct 2026 07:50:
0040  34 33 20 47 4d 54                                43 GMT
```

### The fixed header, octets 0–7

| Octets | Value | Field | Reading |
|---|---|---|---|
| 0–2 | `00 00 3e` | Length | 62 octets of payload. 8 + 62 = 70. |
| 3 | `01` | Type | HEADERS |
| 4 | `00` | Flags | END_MESSAGE **clear** — this is the head, a body follows |
| 5–6 | `00 01` | Request ID | 1, naming the request above |
| 7 | `00` | Reserved | Zero |

### The payload, octets 8–69

| Octets | Value | Reading |
|---|---|---|
| 8–9 | `83 03` | Static index 3 `:status`, value 3 octets |
| 10–12 | `32 30 30` | `200` |
| 13–14 | `86 0a` | Static index 6 `content-type`, value 10 octets |
| 15–24 | `74 65 ... 69 6e` | `text/plain` |
| 25–26 | `85 02` | Static index 5 `content-length`, value 2 octets |
| 27–28 | `31 32` | `12` — matches the DATA frame below |
| 29–30 | `88 08` | Static index 8 `server`, value 8 octets |
| 31–38 | `62 73 ... 2f 31` | `bserve/1` |
| 39–40 | `87 1d` | Static index 7 `date`, value 29 octets |
| 41–69 | `53 61 74 ... 4d 54` | `Sat, 03 Oct 2026 07:50:43 GMT` |

Five fields: 5 + 12 + 4 + 10 + 31 = 62 octets, exactly what the Length field
promised. A decoder knows the list is finished because the payload is, not
because of any terminator.

---

## 4. The response body — one DATA frame, 20 octets

```
0000  00 00 0c 02 01 00 01 00 70 6c 61 69 6e 20 62 79  ........plain by
0010  74 65 73 0a                                      tes.
```

| Octets | Value | Field | Reading |
|---|---|---|---|
| 0–2 | `00 00 0c` | Length | 12 octets, agreeing with `content-length: 12` |
| 3 | `02` | Type | DATA |
| 4 | `01` | Flags | END_MESSAGE — the message is complete, the client stops reading |
| 5–6 | `00 01` | Request ID | 1 |
| 7 | `00` | Reserved | Zero |
| 8–19 | `70 6c 61 69 6e 20 62 79 74 65 73 0a` | `plain bytes\n`, written to stdout verbatim |

The connection is still open. The next request would begin at octet 20 with
another 8-octet frame header.

---

## 5. A frame nobody understands

`./bcurl --probe-unknown localhost:9000/hello.txt` sends this before the
request:

```
0000  00 00 1c 42 00 00 00 00 74 68 69 73 20 69 73 20  ...B....this is
0010  6e 6f 74 20 61 20 66 72 61 6d 65 20 79 6f 75 20  not a frame you
0020  6b 6e 6f 77                                      know
```

| Octets | Value | Reading |
|---|---|---|
| 0–2 | `00 00 1c` | 28 octets of payload |
| 3 | `42` | Type 0x42 — defined by no version of this protocol |
| 4–7 | `00 00 00 00` | Flags, request ID and reserved, all zero |
| 8–35 | `74 68 69 73 ...` | 28 octets of nothing the server can interpret |

The server reads the Length from the fixed header, discards 28 octets, logs
`skipped unknown frame type 0x42 (28 bytes)`, and answers the real request
that follows on the same connection. It never had to know what type `0x42`
meant — which is the property that makes a version 2 possible.
