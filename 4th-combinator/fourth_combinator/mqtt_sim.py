from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fourth_combinator.sim import SimEvent

# DSF SBC raises "Failed to serialize code" when a G-code line exceeds ~256 bytes
# (SPI buffer). Keep embedded M118 well under that.
M118_MAX_LINE_LEN = 240

# Flat keys only — nested objects (gcode_summary, tool_snapshot) blow the limit.
_M118_KEYS_BY_LEAF: dict[str, tuple[str, ...]] = {
    "status": ("state", "device_id", "mode", "session_id", "job_file"),
    "session": (
        "event",
        "event_type",
        "session_id",
        "device_id",
        "mode",
        "job_file",
        "tool_number",
    ),
    "tool": (
        "event",
        "event_type",
        "session_id",
        "seq",
        "t_s",
        "tool_number",
        "previous_tool",
        "job_file",
    ),
}


def _device_id() -> str:
    return os.environ.get("TAP_MQTT_DEVICE_ID", "").strip() or socket.gethostname()


def _session_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


@dataclass
class MqttEnvelope:
    topic: str
    payload: dict[str, Any]


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if v is not None}


def _shorten_number(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def compact_payload_for_m118(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten/trim a payload so the M118 line fits DSF's serialize limit."""
    leaf = topic.rsplit("/", 1)[-1]
    keys = _M118_KEYS_BY_LEAF.get(leaf)
    if keys is None:
        raw = _drop_none(payload)
    else:
        raw = {k: payload[k] for k in keys if k in payload and payload[k] is not None}
    return {k: _shorten_number(v) for k, v in raw.items()}


def m118_publish_line(topic: str, payload: dict[str, Any]) -> str:
    """Format an RRF MQTT publish for Jarvis (RRF 3.6+ / DSF SBC).

    MQTT destination is ``P6`` (MessageType), not ``L6`` — ``L`` is the log
    level (0–3) and ``L6`` raises ``L parameter is too high``.

    M118 requires a **quoted string** for ``S`` (see RRF ``GetQuotedString``).
    Brace form ``S{...}`` is an RRF *expression*, not JSON — ``"key":"value"``
    is invalid there and yields ``M118: expected '}'``. Spaces in values
    (e.g. job file names) also break unquoted ``S{...}`` at the G-code lexer.

    Correct form (RRF escapes ``"`` as ``""``)::

        M118 P6 S"{""event"":""start"",""mode"":""sim""}" T"cam/milo/session"

    Payloads are compacted (flat, no nested objects) so the whole line stays
    under ``M118_MAX_LINE_LEN`` — longer lines trigger DSF
    ``Failed to serialize code``.
    """
    compact = compact_payload_for_m118(topic, payload)

    def render(data: dict[str, Any]) -> str:
        body = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
        # RRF quoted-string escape: double the quote characters.
        escaped = body.replace('"', '""')
        return f'M118 P6 S"{escaped}" T"{topic}"'

    line = render(compact)
    # Shrink job_file, then drop optional fields, until under the limit.
    drop_order = ("job_file", "previous_tool", "device_id", "seq", "t_s")
    while len(line) > M118_MAX_LINE_LEN:
        jf = compact.get("job_file")
        if isinstance(jf, str) and len(jf) > 12:
            compact["job_file"] = jf[: max(8, len(jf) - 16)].rstrip() + "~"
            line = render(compact)
            continue
        dropped = False
        for key in drop_order:
            if key in compact:
                del compact[key]
                dropped = True
                line = render(compact)
                break
        if not dropped:
            raise ValueError(
                f"M118 line still {len(line)} chars after compacting "
                f"(limit {M118_MAX_LINE_LEN}): {line[:80]}…"
            )
    return line


def envelopes_to_m118_lines(envelopes: list[MqttEnvelope]) -> list[str]:
    return [m118_publish_line(env.topic, env.payload) for env in envelopes]


def build_sim_mqtt_envelopes(
    events: list[SimEvent],
    *,
    job_file: str,
    device_id: str | None = None,
    session_id: str | None = None,
    stable_ids: bool = False,
) -> list[MqttEnvelope]:
    """Build session/tool/status envelopes for a sim run (tap-testing payload shape).

    Topics use ``cam/{device_id}/…`` (CAM / 4th-combinator sim), distinct from
    live-spindle ``tap/…`` and Duet macro ``duet/…``.

    Full payloads are kept for JSONL / host publish; ``m118_publish_line``
    compacts them when embedding into G-code.
    """
    dev = device_id or _device_id()
    sid = session_id or _session_id()
    ts0 = time.time()
    tools_used = sorted(
        {e.tool_number for e in events if e.kind == "tool_change" and e.tool_number is not None}
    )
    tool_changes = [e for e in events if e.kind == "tool_change"]

    envelopes: list[MqttEnvelope] = [
        MqttEnvelope(
            topic=f"cam/{dev}/status",
            payload={
                "state": "connected",
                "device_id": dev,
                "ts": ts0,
                "mode": "sim",
                "session_id": sid,
                "job_file": job_file,
            },
        ),
        MqttEnvelope(
            topic=f"cam/{dev}/session",
            payload={
                "event": "start",
                "event_type": "start_session",
                "session_id": sid,
                "device_id": dev,
                "mode": "sim",
                "sample_rate_hz": 0.0,
                "ts": ts0,
                "job_file": job_file,
                "tool_number": tool_changes[0].tool_number if tool_changes else None,
                "tool_name": tool_changes[0].tool_name if tool_changes else None,
                "gcode_summary": {
                    "source": "fourth_combinator_sim",
                    "tools_used": tools_used,
                    "n_tool_changes": len(tool_changes),
                    "n_ops_first_layer": sum(1 for e in events if e.kind == "op_first_layer"),
                },
            },
        ),
    ]

    seq = 0
    t_s = 0.0
    for ev in tool_changes:
        seq += 1
        t_s += 1.0
        if stable_ids:
            event_id = f"tevt-{sid}-{seq - 1}"
        else:
            event_id = f"tevt-{uuid.uuid4().hex[:16]}"
        envelopes.append(
            MqttEnvelope(
                topic=f"cam/{dev}/tool",
                payload={
                    "schema_version": 2,
                    "event_id": event_id,
                    "event": "start" if seq == 1 else "change",
                    "event_type": "tool_selected",
                    "session_id": sid,
                    "seq": seq - 1,
                    "t_s": t_s,
                    "ts": ts0 + t_s,
                    "time_basis": "recording_monotonic",
                    "tool_number": ev.tool_number,
                    "previous_tool": ev.previous_tool,
                    "tool_name": ev.tool_name,
                    "job_file": job_file,
                    "rrf_slot": ev.tool_number,
                    "tool_snapshot": {
                        "number": ev.tool_number,
                        "name": ev.tool_name,
                    },
                },
            )
        )

    final_tool = tool_changes[-1].tool_number if tool_changes else None
    envelopes.append(
        MqttEnvelope(
            topic=f"cam/{dev}/session",
            payload={
                "event": "stop",
                "event_type": "end_session",
                "session_id": sid,
                "device_id": dev,
                "mode": "sim",
                "sample_rate_hz": 0.0,
                "ts": ts0 + t_s + 1.0,
                "n_batches": 0,
                "tool_number": final_tool,
                "job_file": job_file,
            },
        )
    )
    envelopes.append(
        MqttEnvelope(
            topic=f"cam/{dev}/status",
            payload={
                "state": "idle",
                "device_id": dev,
                "ts": ts0 + t_s + 1.0,
                "mode": "sim",
                "session_id": sid,
                "job_file": job_file,
            },
        )
    )
    return envelopes


def write_mqtt_jsonl(path: Path, envelopes: list[MqttEnvelope]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"topic": env.topic, "payload": env.payload}, separators=(",", ":"))
        for env in envelopes
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def publish_mqtt_envelopes(envelopes: list[MqttEnvelope]) -> tuple[bool, str]:
    """Publish envelopes to TAP_MQTT_HOST. Fail-open; returns (ok, message)."""
    host = os.environ.get("TAP_MQTT_HOST", "").strip()
    if not host:
        return False, "TAP_MQTT_HOST not set; skipped live MQTT publish"

    try:
        import paho.mqtt.client as mqtt  # type: ignore
    except ImportError:
        return False, "paho-mqtt not installed; skipped live MQTT publish"

    port_s = os.environ.get("TAP_MQTT_PORT", "1883")
    try:
        port = int(port_s)
    except ValueError:
        port = 1883

    client_id = os.environ.get("TAP_MQTT_CLIENT_ID", "").strip() or f"fourth-sim-{_device_id()}"
    client = mqtt.Client(client_id=client_id)
    user = os.environ.get("TAP_MQTT_USERNAME") or None
    password = os.environ.get("TAP_MQTT_PASSWORD") or None
    if user:
        client.username_pw_set(user, password)

    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
        for env in envelopes:
            qos = 0 if env.topic.endswith("/accel/batch") or env.topic.endswith("/modbus") else 1
            client.publish(
                env.topic,
                json.dumps(env.payload, separators=(",", ":")),
                qos=qos,
            )
        time.sleep(0.2)
        client.loop_stop()
        client.disconnect()
    except Exception as exc:  # noqa: BLE001 — fail-open for broker errors
        return False, f"MQTT publish failed: {exc}"

    return True, f"Published {len(envelopes)} MQTT messages to {host}:{port}"
