from __future__ import annotations

# Park without stopping the spindle (G27-minus-spindle), then rotate A.
PARK_LINES = (
    "; --- 4th-combinator: park (spindle running) ---",
    "if { move.axes[2].homed }",
    "    G53 G0 Z{move.axes[2].max}",
    "if { !exists(param.Z) && move.axes[0].homed && move.axes[1].homed }",
    "    G53 G0 X{(move.axes[0].max - move.axes[0].min)/2} Y{move.axes[1].max}",
    "M400",
)


def fmt_angle(angle: float) -> str:
    if angle.is_integer():
        return str(int(angle))
    return str(angle)


def park_and_rotate(angle: float) -> tuple[str, ...]:
    lines = list(PARK_LINES)
    lines.append("; --- rotate A ---")
    lines.append(f"G0 A{fmt_angle(angle)}")
    return tuple(lines)
