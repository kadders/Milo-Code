from __future__ import annotations

import re
import time
from dataclasses import dataclass

from fourth_combinator.combine import _block_for_step, build_execution_plan
from fourth_combinator.index import JobIndex, find_first_tool_block
from fourth_combinator.mqtt_sim import (
    MqttEnvelope,
    build_sim_mqtt_envelopes,
    m118_publish_line,
)
from fourth_combinator.park import fmt_angle, park_and_rotate
from fourth_combinator.parse import BEGIN_OP_RE, TOOL_SELECT_RE
from fourth_combinator.scrub import extract_trailing_spindle_stop

Z_WORD_RE = re.compile(r"([Zz])\s*([-+]?(?:\d+\.?\d*|\.\d+))", re.IGNORECASE)
AXIS_WORD_RE = re.compile(r"([XYZABCxyzabc])\s*([-+]?(?:\d+\.?\d*|\.\d+))")
MOTION_RE = re.compile(r"^G(?:0|1|2|3)\b", re.IGNORECASE)
FEED_MOTION_RE = re.compile(r"^G(?:1|2|3)\b", re.IGNORECASE)
SPINDLE_DROP_RE = re.compile(r"^M[345](?:\.\d+)?\b|^M700[01]\b", re.IGNORECASE)
COOLANT_DROP_RE = re.compile(r"^M[789]\b", re.IGNORECASE)
M4000_RE = re.compile(r"^M4000\b", re.IGNORECASE)
M4001_RE = re.compile(r"^M4001\b", re.IGNORECASE)

SPINDLE_COMMENT_SUBSTR = (
    "start spindle",
    "enable variable spindle",
    "disable variable spindle",
    "double-check spindle",
)
COOLANT_AIR_COMMENT_SUBSTR = (
    "enable mist",
    "enable flood",
    "disable coolant",
    "air blast",
    "enable air",
)


@dataclass(frozen=True)
class SimEvent:
    kind: str
    message: str
    tool_number: int | None = None
    previous_tool: int | None = None
    angle: float | None = None
    tool_name: str | None = None
    op_name: str | None = None


def _code_part(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _comment_text(line: str) -> str:
    s = line.strip()
    if s.startswith("(") and s.endswith(")"):
        return s[1:-1].strip()
    if s.startswith(";"):
        return s[1:].strip()
    return ""


def extract_z(line: str) -> float | None:
    code = _code_part(line)
    if not code:
        return None
    m = Z_WORD_RE.search(code)
    if not m:
        return None
    return float(m.group(2))


def force_z0(line: str) -> str:
    """Rewrite any Z word to Z0; leave lines without Z unchanged."""
    if extract_z(line) is None:
        return line

    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}0"

    # Prefer rewriting the code portion only when a trailing ; comment exists
    if ";" in line:
        code, rest = line.split(";", 1)
        return Z_WORD_RE.sub(repl, code) + ";" + rest
    return Z_WORD_RE.sub(repl, line)


def _has_xy(line: str) -> bool:
    code = _code_part(line)
    return bool(re.search(r"[Xx]\s*[-+]?(?:\d|\.)", code) or re.search(r"[Yy]\s*[-+]?(?:\d|\.)", code))


def _is_z_only_move(line: str) -> bool:
    code = _code_part(line)
    if not MOTION_RE.match(code):
        return False
    axes = {m.group(1).upper() for m in AXIS_WORD_RE.finditer(code)}
    return axes == {"Z"}


def _drop_spindle_coolant_comment(line: str) -> bool:
    text = _comment_text(line).lower()
    if not text:
        return False
    return any(s in text for s in SPINDLE_COMMENT_SUBSTR + COOLANT_AIR_COMMENT_SUBSTR)


def should_strip_line(line: str) -> bool:
    if _drop_spindle_coolant_comment(line):
        return True
    code = _code_part(line)
    if not code:
        return False
    if SPINDLE_DROP_RE.match(code) or COOLANT_DROP_RE.match(code):
        return True
    return False


def comment_out_line(line: str) -> str:
    """Prefix an executable line with ';' so RRF ignores it."""
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    if stripped.startswith(";"):
        return line
    return f"{indent}; {stripped}"


def maybe_comment_m4000(line: str) -> str | None:
    """Comment out M4000 tool-table loads; return None if not an M4000 line."""
    code = _code_part(line)
    if code and M4000_RE.match(code):
        return comment_out_line(line)
    return None


def tool_change_popup(tool_number: int) -> tuple[str, ...]:
    return (
        f"; --- sim: tool change to T{tool_number} (no real Tn) ---",
        f'M291 P"Sim tool change to T{tool_number} — confirm" R"4th-combinator sim" S3',
        f'echo {{ "4th-combinator sim: tool change to T{tool_number}" }}',
    )


def _partition_envelopes(
    envelopes: list[MqttEnvelope],
) -> tuple[list[MqttEnvelope], list[MqttEnvelope], list[MqttEnvelope]]:
    """Split into (session_start_block, tool events, session_end_block)."""
    tools = [e for e in envelopes if e.topic.endswith("/tool")]
    starts: list[MqttEnvelope] = []
    ends: list[MqttEnvelope] = []
    seen_tool = False
    for env in envelopes:
        if env.topic.endswith("/tool"):
            seen_tool = True
            continue
        if not seen_tool:
            starts.append(env)
        else:
            ends.append(env)
    return starts, tools, ends


def extract_first_layer(
    op_lines: list[str],
    *,
    layer_eps: float = 0.05,
) -> list[str]:
    """Keep XY motion belonging to the first cutting Z layer of one operation."""
    modal_z: float | None = None
    max_approach_z: float | None = None
    z_layer: float | None = None
    out: list[str] = []
    emitting = False

    for line in op_lines:
        code = _code_part(line)
        z = extract_z(line)
        if z is not None:
            modal_z = z
            if max_approach_z is None or z > max_approach_z:
                # Only grow approach while not yet in a cutting layer
                if z_layer is None:
                    max_approach_z = z

        is_feed = bool(code and FEED_MOTION_RE.match(code))
        is_motion = bool(code and MOTION_RE.match(code))

        if z_layer is None:
            # Establish first cutting Z from a feed move that drops from approach
            if is_feed and modal_z is not None:
                approach = max_approach_z if max_approach_z is not None else modal_z
                if modal_z < approach - layer_eps or modal_z < 0:
                    z_layer = modal_z
                    emitting = True
                elif max_approach_z is None:
                    # No clearance pair yet - treat first feed Z as layer if XY present
                    if _has_xy(line):
                        z_layer = modal_z
                        emitting = True

            # Keep Begin operation / setup comments before layer starts
            if not emitting:
                if not is_motion:
                    out.append(line)
                elif is_motion and _has_xy(line):
                    # Approach XY before first cut - keep for positioning at Z0 later
                    out.append(line)
                continue

        assert z_layer is not None
        # Past first layer start
        if modal_z is not None and modal_z < z_layer - layer_eps:
            break  # next depth pass

        if is_motion and _is_z_only_move(line):
            continue  # drop pure Z plunges/retracts within layer
        out.append(line)

    return out


def split_operations(lines: list[str]) -> list[tuple[str | None, list[str]]]:
    """Split into (op_label_or_None, lines) segments on Begin operation."""
    segments: list[tuple[str | None, list[str]]] = []
    current_label: str | None = None
    current: list[str] = []

    for line in lines:
        m = BEGIN_OP_RE.match(line.strip())
        if m:
            if current or current_label is not None:
                segments.append((current_label, current))
            current_label = f"{m.group(2).strip()} ({m.group(1).strip()})"
            current = [line]
            continue
        current.append(line)

    if current or current_label is not None:
        segments.append((current_label, current))
    return segments


def sim_transform_block_lines(
    lines: tuple[str, ...] | list[str],
    *,
    layer_eps: float,
    events: list[SimEvent],
    angle: float,
    tool_number: int,
) -> list[str]:
    """First-layer extract per op, Z0 plane, strip spindle/coolant/Tn."""
    out: list[str] = []
    segments = split_operations(list(lines))

    for op_label, seg in segments:
        working = list(seg)
        if op_label is not None:
            # First line is Begin operation - keep label, extract body
            header = working[:1]
            body = working[1:]
            layer = extract_first_layer(body, layer_eps=layer_eps)
            working = header + layer
            events.append(
                SimEvent(
                    kind="op_first_layer",
                    message=f"op first-layer  {op_label}  @ A{fmt_angle(angle)}",
                    tool_number=tool_number,
                    angle=angle,
                    op_name=op_label,
                )
            )
        else:
            # Preamble within block (before first Begin op)
            working = extract_first_layer(working, layer_eps=layer_eps) if any(
                extract_z(ln) is not None for ln in working
            ) else working

        for line in working:
            code = _code_part(line)
            if code and TOOL_SELECT_RE.match(code):
                # Real Tn handled at step boundaries; drop stray selects in body
                continue
            if code and M4001_RE.match(code):
                continue
            commented = maybe_comment_m4000(line)
            if commented is not None:
                out.append(commented)
                continue
            if should_strip_line(line):
                continue
            if _is_z_only_move(line):
                continue
            out.append(force_z0(line))

    return out


def build_sim_gcode(
    index: JobIndex,
    *,
    layer_eps: float = 0.05,
    verbose: bool = False,
    job_file: str | None = None,
    mqtt_device_id: str | None = None,
    mqtt_session_id: str | None = None,
    embed_mqtt: bool = True,
) -> tuple[str, list[SimEvent], list[MqttEnvelope]]:
    """Build datum-safe first-layer sim gcode + events + MQTT envelopes.

    When ``embed_mqtt`` is true (default), RRF ``M118 P6`` publishes are written
    into the gcode so Jarvis sees session/tool events as the mill runs.
    """
    del verbose
    ref = index.by_angle[index.reference_angle]
    steps = build_execution_plan(index)
    events: list[SimEvent] = []
    job_name = job_file or f"{index.discovery.model} - 4th axis sim.gcode"

    # Pre-scan tool changes so MQTT envelopes (and embedded M118) match the plan.
    prev_tool_scan: int | None = None
    for step in steps:
        source = find_first_tool_block(
            index.by_angle[step.angle],
            tool_number=step.tool_number,
        )
        if prev_tool_scan is None or step.tool_number != prev_tool_scan:
            events.append(
                SimEvent(
                    kind="tool_change",
                    message=(
                        f"tool change  "
                        f"{'—' if prev_tool_scan is None else f'T{prev_tool_scan}'} → "
                        f"T{step.tool_number}  (A{fmt_angle(step.angle)})"
                    ),
                    tool_number=step.tool_number,
                    previous_tool=prev_tool_scan,
                    angle=step.angle,
                    tool_name=source.description if source is not None else None,
                )
            )
            prev_tool_scan = step.tool_number

    # Op / park events are appended during the emit loop below; seed envelopes
    # with tool changes first, then rebuild after full event list if needed.
    session_id = mqtt_session_id or time.strftime("%Y%m%d_%H%M%S")
    # Temporary envelopes from tool-change events only (op counts filled later).
    envelopes = build_sim_mqtt_envelopes(
        events,
        job_file=job_name,
        device_id=mqtt_device_id,
        session_id=session_id,
        stable_ids=True,
    )
    start_envs, tool_envs, end_envs = _partition_envelopes(envelopes)
    tool_env_i = 0

    out: list[str] = [
        "; Generated by fourth_combinator — SIMULATION (datum in spindle)",
        f"; Model: {index.discovery.model}",
        "; Mode: first-layer XY @ Z0 — no spindle, no coolant/air, no real tool changes",
        "; M4000 tool-table loads are commented out (do not reload tooling).",
        "; Confirm each M291 tool-change popup before continuing.",
        f"; MQTT session_id={session_id} (M118 P6 → cam/{{device}}/… for Jarvis)",
        "",
        "; Ensure coolant/air off",
        "M9",
        "",
    ]

    if embed_mqtt and start_envs:
        out.append("; --- sim MQTT: session start (Jarvis tap-collector) ---")
        for env in start_envs:
            out.append(m118_publish_line(env.topic, env.payload))
        out.append("")

    # Soft-strip unsafe bits from preamble; keep WCS setup-ish lines
    if ref.preamble:
        for line in ref.preamble:
            if should_strip_line(line):
                continue
            code = _code_part(line)
            if code and (TOOL_SELECT_RE.match(code) or M4001_RE.match(code)):
                continue
            commented = maybe_comment_m4000(line)
            if commented is not None:
                out.append(commented)
                continue
            if _is_z_only_move(line):
                continue
            out.append(force_z0(line))
        out.append("")

    # Replace pre-scanned tool events with a fresh list built in emit order,
    # keeping the same tool_change sequence for MQTT alignment.
    emit_events: list[SimEvent] = []
    tool_change_iter = iter(e for e in events if e.kind == "tool_change")

    prev_angle: float | None = None
    prev_tool: int | None = None

    for step_idx, step in enumerate(steps):
        is_last = step_idx == len(steps) - 1
        source = find_first_tool_block(
            index.by_angle[step.angle],
            tool_number=step.tool_number,
        )
        tool_name = source.description if source is not None else None

        out.append(
            f"; === SIM T{step.tool_number} @ A{fmt_angle(step.angle)} "
            f"({step.source_file}) ==="
        )

        if prev_angle is not None and step.angle != prev_angle:
            out.extend(park_and_rotate(step.angle))
            emit_events.append(
                SimEvent(
                    kind="park_rotate",
                    message=(
                        f"park+rotate  A{fmt_angle(prev_angle)} → "
                        f"A{fmt_angle(step.angle)}"
                    ),
                    angle=step.angle,
                    tool_number=step.tool_number,
                )
            )

        if prev_tool is None or step.tool_number != prev_tool:
            out.extend(tool_change_popup(step.tool_number))
            tc = next(tool_change_iter)
            emit_events.append(tc)
            if embed_mqtt and tool_env_i < len(tool_envs):
                env = tool_envs[tool_env_i]
                tool_env_i += 1
                out.append("; --- sim MQTT: tool_selected ---")
                out.append(m118_publish_line(env.topic, env.payload))
            # tool_name already on pre-scanned event; keep in sync if missing
            if tc.tool_name is None and tool_name is not None:
                emit_events[-1] = SimEvent(
                    kind=tc.kind,
                    message=tc.message,
                    tool_number=tc.tool_number,
                    previous_tool=tc.previous_tool,
                    angle=tc.angle,
                    tool_name=tool_name,
                    op_name=tc.op_name,
                )

        block = _block_for_step(
            index,
            step,
            prev_tool=prev_tool,
            first_step=step_idx == 0,
        )
        if not is_last:
            block, _ = extract_trailing_spindle_stop(block)

        body = sim_transform_block_lines(
            block.lines,
            layer_eps=layer_eps,
            events=emit_events,
            angle=step.angle,
            tool_number=step.tool_number,
        )
        out.extend(body)
        out.append("")

        prev_angle = step.angle
        prev_tool = step.tool_number

    if embed_mqtt and end_envs:
        out.append("; --- sim MQTT: session end ---")
        for env in end_envs:
            out.append(m118_publish_line(env.topic, env.payload))
        out.append("")

    # Final envelopes include op_first_layer counts for JSONL / host publish.
    final_envelopes = build_sim_mqtt_envelopes(
        emit_events,
        job_file=job_name,
        device_id=mqtt_device_id,
        session_id=session_id,
        stable_ids=True,
    )
    # Embedded M118 used the pre-op envelopes (same session/tool topics & ids);
    # refresh gcode_summary on the start_session payload is JSONL-only detail.
    return "\n".join(out).rstrip() + "\n", emit_events, final_envelopes


def format_sim_console_log(
    events: list[SimEvent],
    *,
    job_name: str,
) -> str:
    lines = [
        f"[sim] session start  job={job_name}  (datum mode, first layer @ Z0)",
    ]
    for ev in events:
        lines.append(f"[sim] {ev.message}")
    lines.append("[sim] session end")
    return "\n".join(lines) + "\n"
