"""Synchronous Swegon CASA MQTT/Modbus transport.

The official app requests short-lived AWS IoT custom-authorizer credentials from
the mobile API, then exchanges a compact Modbus protobuf over MQTT WebSockets.
Only an allow-listed mode write and documented read-only status registers are
exposed by this integration.
"""

from __future__ import annotations

from collections.abc import Iterable
import logging
import ssl
import struct
import threading
import time
from typing import Any
from urllib.parse import urlparse
import uuid

import paho.mqtt.client as mqtt

from .const import (
    APPLICATION_REGISTER,
    CONTROL_SOURCE_REGISTER,
    MODE_REGISTER,
    MQTT_USER_AGENT,
    SUMMER_MODE_BOOST_REGISTER,
    SUMMER_MODE_SETTING_REGISTER,
    SUMMER_MODE_STATE_REGISTER,
)

_LOGGER = logging.getLogger(__name__)


class SwegonCasaMqttError(Exception):
    """Swegon MQTT request failed."""


def _varint(value: int) -> bytes:
    value &= 0xFFFFFFFF
    output = bytearray()
    while value > 0x7F:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def _read_varint(data: bytes, position: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if position >= len(data) or shift > 35:
            raise SwegonCasaMqttError("Invalid protobuf response")
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7


def _zigzag_encode(value: int) -> int:
    return (value << 1) ^ (value >> 31)


def _zigzag_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def _packed_field(number: int, values: Iterable[int]) -> bytes:
    packed = b"".join(_varint(value) for value in values)
    return _varint((number << 3) | 2) + _varint(len(packed)) + packed


def _parse_protobuf(data: bytes) -> dict[int, list[int]]:
    fields: dict[int, list[int]] = {}
    position = 0
    while position < len(data):
        tag, position = _read_varint(data, position)
        field_number = tag >> 3
        wire_type = tag & 7
        if wire_type == 0:
            value, position = _read_varint(data, position)
            fields.setdefault(field_number, []).append(value)
        elif wire_type == 2:
            size, position = _read_varint(data, position)
            end = position + size
            if end > len(data):
                raise SwegonCasaMqttError("Truncated protobuf response")
            while position < end:
                value, position = _read_varint(data, position)
                fields.setdefault(field_number, []).append(value)
        else:
            raise SwegonCasaMqttError(f"Unsupported protobuf wire type {wire_type}")
    return fields


class SwegonCasaMqttClient:
    """Open one short-lived MQTT session for a read or bounded write."""

    def __init__(self, summary: dict[str, Any]) -> None:
        connection = summary["connectionDetails"]
        thing = summary["thing"]
        self._connection = connection
        self._client_id = str(uuid.uuid4())
        self._response_topic = (
            f"up2020/{thing['group']}/{thing['name']}/res/{self._client_id}"
        )
        self._request_topic = f"up2020/{thing['group']}/{thing['name']}/req"
        self._ready = threading.Event()
        self._response_ready = threading.Event()
        self._error: str | None = None
        self._expected_transaction = 0
        self._response: tuple[int, dict[int, list[int]]] | None = None
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._client_id,
            protocol=mqtt.MQTTv311,
            transport="websockets",
            reconnect_on_failure=False,
        )
        self._client.on_connect = self._on_connect
        self._client.on_subscribe = self._on_subscribe
        self._client.on_message = self._on_message

        headers = {
            "X-Amz-CustomAuthorizer-Name": connection["customAuthorizer"],
            connection["tokenKeyName"]: connection["token"],
            "X-Amz-CustomAuthorizer-Signature": connection["tokenSignature"],
            "User-Agent": MQTT_USER_AGENT,
        }
        self._client.ws_set_options(path="/mqtt", headers=headers)
        self._client.username_pw_set(MQTT_USER_AGENT)
        self._client.tls_set_context(ssl.create_default_context())

    def __enter__(self) -> SwegonCasaMqttClient:
        endpoint = str(self._connection["endpoint"])
        parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
        if parsed.hostname is None:
            raise SwegonCasaMqttError("Invalid Swegon MQTT endpoint")
        self._client.connect(parsed.hostname, parsed.port or 443, keepalive=60)
        self._client.loop_start()
        if not self._ready.wait(10):
            self.close()
            raise SwegonCasaMqttError(self._error or "MQTT connection timed out")
        if self._error is not None:
            self.close()
            raise SwegonCasaMqttError(self._error)
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()

    def read_mode(self) -> int:
        """Read the Swegon operating-mode register."""
        return self.read_register(MODE_REGISTER)

    def read_register(self, register: int) -> int:
        """Read one register through the mobile gateway's supported path."""
        return self._read_register(3, register)

    def _read_register(self, request_type: int, register: int) -> int:
        request = _packed_field(1, [register, 1])
        fields = self._request(request_type, request)
        status = (fields.get(2) or [0])[0]
        values = [_zigzag_decode(value) for value in fields.get(1, [])]
        if status != 0 or values[:2] != [register, 1] or len(values) < 3:
            raise SwegonCasaMqttError(
                f"Swegon rejected register {register} read"
            )
        return values[2]

    def write_mode(self, value: int) -> None:
        """Write one validated operating-mode value and verify it."""
        encoded_values = _packed_field(3, [_zigzag_encode(value)])
        request = (
            _varint(1 << 3)
            + _varint(MODE_REGISTER)
            + _varint(2 << 3)
            + _varint(1)
            + encoded_values
        )
        fields = self._request(2, request)
        status = (fields.get(1) or [0])[0]
        if status != 0:
            raise SwegonCasaMqttError("Swegon rejected mode write")
        for attempt in range(5):
            if self.read_mode() == value:
                return
            if attempt < 4:
                time.sleep(0.5)
        raise SwegonCasaMqttError("Swegon mode write could not be verified")

    def _request(self, request_type: int, protobuf: bytes) -> dict[int, list[int]]:
        self._expected_transaction += 1
        transaction = self._expected_transaction
        self._response = None
        self._response_ready.clear()
        header = struct.pack("<HHB", transaction, request_type, 1)
        topic = self._response_topic.encode("latin-1")
        if len(topic) > 128:
            raise SwegonCasaMqttError("Swegon response topic is too long")
        packet = header + topic.ljust(128, b"\0") + protobuf
        publish = self._client.publish(self._request_topic, packet, qos=1)
        if publish.rc != mqtt.MQTT_ERR_SUCCESS:
            raise SwegonCasaMqttError("Unable to publish Swegon MQTT request")
        if not self._response_ready.wait(10):
            raise SwegonCasaMqttError("Swegon MQTT response timed out")
        if self._error is not None:
            raise SwegonCasaMqttError(self._error)
        if self._response is None:
            raise SwegonCasaMqttError("Swegon MQTT response was empty")
        response_type, fields = self._response
        if response_type != request_type:
            raise SwegonCasaMqttError("Swegon returned an unexpected response")
        return fields

    def _on_connect(
        self,
        client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code != 0:
            self._error = f"MQTT connection failed: {reason_code}"
            self._ready.set()
            return
        client.subscribe(self._response_topic, qos=1)

    def _on_subscribe(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        _mid: int,
        _reason_codes: list[mqtt.ReasonCode],
        _properties: mqtt.Properties | None,
    ) -> None:
        self._ready.set()

    def _on_message(
        self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        if len(message.payload) < 5:
            return
        transaction, request_type, version = struct.unpack(
            "<HHB", message.payload[:5]
        )
        if transaction != self._expected_transaction or version != 1:
            return
        try:
            fields = _parse_protobuf(message.payload[5:])
        except SwegonCasaMqttError as error:
            self._error = str(error)
            self._response_ready.set()
            return
        self._response = (request_type, fields)
        self._response_ready.set()


def read_status(summary: dict[str, Any]) -> dict[str, int | None]:
    """Read the bounded operating and summer-cooling status registers."""
    with SwegonCasaMqttClient(summary) as client:
        status: dict[str, int | None] = {
            "mode": client.read_mode(),
            "summer_mode_setting": None,
            "summer_mode_boost": None,
            "summer_mode_state": None,
            "control_source": None,
            "application": None,
        }
        optional_registers = (
            (
                "summer_mode_setting",
                client.read_register,
                SUMMER_MODE_SETTING_REGISTER,
            ),
            (
                "summer_mode_boost",
                client.read_register,
                SUMMER_MODE_BOOST_REGISTER,
            ),
            (
                "summer_mode_state",
                client.read_register,
                SUMMER_MODE_STATE_REGISTER,
            ),
            (
                "control_source",
                client.read_register,
                CONTROL_SOURCE_REGISTER,
            ),
            (
                "application",
                client.read_register,
                APPLICATION_REGISTER,
            ),
        )
        for key, reader, register in optional_registers:
            try:
                status[key] = reader(register)
            except SwegonCasaMqttError as error:
                _LOGGER.warning("Unable to read optional %s: %s", key, error)
        return status


def write_mode(summary: dict[str, Any], value: int) -> None:
    """Write and verify a mode in a worker thread."""
    with SwegonCasaMqttClient(summary) as client:
        client.write_mode(value)
