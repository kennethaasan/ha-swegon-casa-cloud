# Reading Swegon CASA MQTT messages

This is an observed protocol note for maintainers of the Home Assistant
integration. It describes the binary application payload carried over MQTT
3.1.1 over secure WebSockets. It is not an official Swegon protocol contract.

The REST endpoints exchange JSON, but the MQTT messages sent to the CASA
gateway do not. Treat `message.payload` as `bytes`; do not call a JSON
decoder on it.

## Topics and frame layout

The authenticated mobile summary supplies `thing.group`, `thing.name`, and
temporary AWS IoT connection details. The integration uses these topics:

```text
up2020/{group}/{name}/req
up2020/{group}/{name}/res/{client-uuid}
```

Every application frame starts with five bytes, decoded as the Python struct
format `<HHB`:

| Offset | Size | Type | Meaning |
| ---: | ---: | --- | --- |
| 0 | 2 | little-endian `uint16` | transaction/correlation number |
| 2 | 2 | little-endian `uint16` | request type |
| 4 | 1 | `uint8` | protocol version; currently `1` |

Request frames then contain a fixed 128-byte response topic, encoded as
Latin-1 and padded on the right with NUL bytes. The protobuf-like request body
starts at byte 133. Response frames do not contain that topic; their body
starts at byte 5.

The response must be correlated by both transaction and request type. A
response with another transaction, request type, or protocol version should
be ignored or treated as an error.

## Protobuf-like body

The body uses the protobuf field-key rule:

```text
field_key = (field_number << 3) | wire_type
```

The integration currently needs two wire types:

* wire type `0`: an unsigned varint;
* wire type `2`: a length-delimited field containing consecutive packed
  varints.

Do not interpret every varint identically. Read-register request fields and
the status field are unsigned. The register-read response values and the
mode-write value are zigzag encoded:

```text
zigzag_encode(n) = (n << 1) ^ (n >> 31)
zigzag_decode(u) = (u >> 1) ^ -(u & 1)
```

Unknown fields may be skipped only when their wire type is known and can be
skipped safely. The vendor payload is only partially mapped, so a decoder
should reject truncated varints and unsupported wire types.

## Register read

The integration sends request type `3`. The body is field `1`, wire type `2`,
with packed unsigned varints `[register, quantity]`; quantity is currently
always `1`.

For register `1039`, the body is:

```text
0a 03 8f 08 01
```

This means:

```text
0a       field 1, length-delimited
03       three body bytes follow
8f 08    unsigned varint 1039
01       unsigned varint quantity 1
```

A successful response contains field `1` with packed zigzag varints
`[register, quantity, value]` and field `2` with unsigned status `0`. For
example, a response body for register `1039`, quantity `1`, value `65` can be:

```text
0a 05 9e 10 02 82 01 10 00
```

The field order is not part of the contract. Parse by field number rather than
by byte position.

## Operating-mode write

The integration sends request type `2` and writes only register `1039`. The
body uses:

```text
field 1, wire type 0: register number 1039
field 2, wire type 0: quantity 1
field 3, wire type 2: packed zigzag-encoded mode value
```

For mode value `100` (`boost`), the illustrative body is:

```text
08 8f 08 10 01 1a 02 c8 01
```

The integration accepts only its explicit mode allow-list and reads register
`1039` back after the write. This prevents an accepted MQTT publish from being
mistaken for a confirmed ventilation-mode change.

## Minimal Python reference

This is a decoding sketch, not a replacement for the error handling in
`custom_components/swegon_casa_cloud/mqtt.py`:

```python
import struct

HEADER = struct.Struct("<HHB")


def read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if pos >= len(data) or shift > 35:
            raise ValueError("invalid or truncated varint")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7


def zigzag_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def read_frame(raw: bytes, *, request: bool) -> tuple[dict, bytes]:
    if len(raw) < HEADER.size:
        raise ValueError("frame is too short")
    transaction, request_type, version = HEADER.unpack_from(raw)
    pos = HEADER.size
    response_topic = None
    if request:
        if len(raw) < pos + 128:
            raise ValueError("request is missing its response topic")
        response_topic = raw[pos : pos + 128].rstrip(b"\0").decode("latin-1")
        pos += 128
    return {
        "transaction": transaction,
        "request_type": request_type,
        "protocol_version": version,
        "response_topic": response_topic,
    }, raw[pos:]
```

The remaining body parser should read a field key, dispatch on its wire type,
and collect packed values until the declared length is consumed. See
`_parse_protobuf`, `_read_register`, and `write_mode` in the integration for
the complete bounded implementation.

## Safety and privacy

The authorizer headers, endpoint, topics, group/name identifiers, and unit
serial numbers are runtime data. Keep them out of logs, fixtures, examples,
and issue reports. Never commit a captured MQTT frame unless all identifiers
and credentials have been removed.
