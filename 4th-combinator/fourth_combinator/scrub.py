from __future__ import annotations

import re

from fourth_combinator.parse import ToolBlock, TOOL_SELECT_RE

SPINDLE_CMD_RE = re.compile(r"^M[345](?:\.\d+)?\b", re.IGNORECASE)
DWELL_RE = re.compile(r"^G4\b", re.IGNORECASE)
PURE_A_MOVE_RE = re.compile(
    r"^G(?:0|1)\b(?:(?!.*\b[XYZIJKF]\b).)*\bA[-+]?\d",
    re.IGNORECASE,
)
BEGIN_OP_RE = re.compile(r"^\(\s*Begin operation\b", re.IGNORECASE)
MOTION_RE = re.compile(r"^G(?:0|1|2|3)\b.*\b[XYZ]", re.IGNORECASE)

# Stop half of MOS inter-op bridge
STOP_CMD_RE = re.compile(r"^(?:M7001|M9|G27|M5(?:\.\d+)?)\b", re.IGNORECASE)
# Restart half
RESTART_CMD_RE = re.compile(
    r"^(?:M7000\b|M[34](?:\.\d+)?\b|M7\b|M8\b)",
    re.IGNORECASE,
)

STOP_COMMENT_SUBSTR = (
    "disable variable spindle",
    "disable coolant",
    "begin postamble",
    "double-check spindle",
)
RESTART_COMMENT_SUBSTR = (
    "enable variable spindle",
    "start spindle",
    "enable mist coolant",
    "enable flood",
    "park ready for wcs",
)


def _code_part(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _comment_text(line: str) -> str:
    s = line.strip()
    if s.startswith("(") and s.endswith(")"):
        return s[1:-1].strip()
    if s.startswith(";"):
        return s[1:].strip()
    return ""


def _is_blank(line: str) -> bool:
    return not line.strip()


def _is_begin_operation(line: str) -> bool:
    return bool(BEGIN_OP_RE.match(line.strip()))


def _is_bare_park_comment(line: str) -> bool:
    text = _comment_text(line).lower()
    return text == "park"


def _is_stop_comment(line: str) -> bool:
    text = _comment_text(line).lower()
    if not text:
        return False
    if _is_bare_park_comment(line):
        return True
    return any(s in text for s in STOP_COMMENT_SUBSTR)


def _is_restart_comment(line: str) -> bool:
    text = _comment_text(line).lower()
    if not text:
        return False
    return any(s in text for s in RESTART_COMMENT_SUBSTR)


def _is_stop_cmd(code: str) -> bool:
    return bool(code and STOP_CMD_RE.match(code))


def _is_restart_cmd(code: str) -> bool:
    return bool(code and RESTART_CMD_RE.match(code))


def _is_stop_bridge_line(line: str) -> bool:
    if _is_blank(line):
        return True
    if _is_stop_comment(line):
        return True
    code = _code_part(line)
    return _is_stop_cmd(code) or bool(code and DWELL_RE.match(code))


def _is_restart_bridge_line(line: str) -> bool:
    if _is_blank(line):
        return True
    if _is_restart_comment(line):
        return True
    code = _code_part(line)
    return _is_restart_cmd(code) or bool(code and DWELL_RE.match(code))


def _is_spindle_or_dwell(code: str) -> bool:
    return bool(SPINDLE_CMD_RE.match(code) or DWELL_RE.match(code))


def _is_pure_a_move(code: str) -> bool:
    return bool(PURE_A_MOVE_RE.match(code))


def _looks_like_stop_cluster_start(line: str) -> bool:
    """True if this line can begin an MOS stop postamble cluster."""
    if _is_stop_comment(line):
        return True
    code = _code_part(line)
    return _is_stop_cmd(code)


def _is_motion(code: str) -> bool:
    return bool(code and MOTION_RE.match(code))


def _is_bridge_region_line(line: str) -> bool:
    """Line allowed inside a stop→restart bridge (no cutting moves)."""
    if _is_blank(line):
        return True
    if _is_begin_operation(line):
        return False
    if _is_stop_comment(line) or _is_restart_comment(line):
        return True
    # Other paren/semicolon comments (WCS probe boilerplate, TC:, Fusion notes, …)
    stripped = line.strip()
    if stripped.startswith("(") or stripped.startswith(";"):
        return True
    code = _code_part(line)
    if not code:
        return True
    if _is_motion(code):
        return False
    if _is_stop_cmd(code) or _is_restart_cmd(code) or DWELL_RE.match(code):
        return True
    # Unknown executable — do not treat as bridge filler
    return False


def scrub_inter_op_spindle_stops(block: ToolBlock) -> ToolBlock:
    """Remove MOS stop→restart bridges between ops under the same tool.

    Keeps the first spindle/VSSC/coolant start (before the first Begin operation)
    and any trailing postamble after the last operation.
    """
    lines = list(block.lines)
    if not lines:
        return block

    first_op = next((i for i, ln in enumerate(lines) if _is_begin_operation(ln)), None)
    if first_op is None:
        return block

    out: list[str] = list(lines[: first_op + 1])
    i = first_op + 1
    n = len(lines)

    while i < n:
        line = lines[i]
        if _looks_like_stop_cluster_start(line):
            j = i
            saw_stop_cmd = False
            saw_restart_cmd = False
            while j < n and not _is_begin_operation(lines[j]):
                if not _is_bridge_region_line(lines[j]):
                    break
                code = _code_part(lines[j])
                if _is_stop_cmd(code):
                    saw_stop_cmd = True
                if _is_restart_cmd(code):
                    saw_restart_cmd = True
                j += 1
            if (
                saw_stop_cmd
                and saw_restart_cmd
                and j < n
                and _is_begin_operation(lines[j])
                and all(_is_bridge_region_line(lines[k]) for k in range(i, j))
            ):
                i = j  # skip bridge; keep Begin operation on next iteration
                continue

        out.append(line)
        i += 1

    return block.with_lines(tuple(out))


def _strip_leading_restart(lines: list[str]) -> list[str]:
    """Strip leading restart/stop preamble until the first Begin operation or cut."""
    if any(_is_begin_operation(ln) for ln in lines):
        while lines and not _is_begin_operation(lines[0]):
            code = _code_part(lines[0])
            if _is_motion(code):
                break
            lines.pop(0)
        return lines

    while lines:
        line = lines[0]
        if _is_blank(line):
            lines.pop(0)
            continue
        if _is_restart_comment(line) or _is_stop_comment(line):
            lines.pop(0)
            continue
        stripped = line.strip()
        if stripped.startswith("(") or stripped.startswith(";"):
            lines.pop(0)
            continue
        code = _code_part(line)
        if not code:
            lines.pop(0)
            continue
        if (
            _is_restart_cmd(code)
            or _is_stop_cmd(code)
            or _is_spindle_or_dwell(code)
            or _is_pure_a_move(code)
        ):
            lines.pop(0)
            continue
        break
    return lines


def _strip_trailing_stop(lines: list[str]) -> list[str]:
    """Strip trailing MOS stop cluster and following WCS/boilerplate comments."""
    while lines:
        line = lines[-1]
        if _is_blank(line):
            lines.pop()
            continue
        if _is_begin_operation(line):
            break
        stripped = line.strip()
        if stripped.startswith("(") or stripped.startswith(";"):
            lines.pop()
            continue
        code = _code_part(line)
        if not code:
            lines.pop()
            continue
        if (
            _is_stop_cmd(code)
            or _is_restart_cmd(code)
            or _is_spindle_or_dwell(code)
            or DWELL_RE.match(code)
        ):
            lines.pop()
            continue
        break
    # Trim trailing blanks left behind
    while lines and _is_blank(lines[-1]):
        lines.pop()
    return lines


def _strip_leading(lines: list[str]) -> list[str]:
    return _strip_leading_restart(lines)


def _strip_trailing(lines: list[str]) -> list[str]:
    return _strip_trailing_stop(lines)


def scrub_spindle(block: ToolBlock) -> ToolBlock:
    """Remove spindle bookends and leading pure-A moves when spindle stays running."""
    lines = list(block.lines)
    lines = _strip_leading(lines)
    lines = _strip_trailing(lines)
    return block.with_lines(tuple(lines))


def scrub_orientation_hop(block: ToolBlock) -> ToolBlock:
    """Same tool at a new orientation: drop T select and full stop/restart bookends."""
    lines = list(block.lines)
    if lines:
        code = _code_part(lines[0])
        if code and TOOL_SELECT_RE.match(code):
            lines.pop(0)
    lines = _strip_leading(lines)
    lines = _strip_trailing(lines)
    return block.with_lines(tuple(lines))


def extract_trailing_spindle_stop(block: ToolBlock) -> tuple[ToolBlock, tuple[str, ...]]:
    """Peel trailing MOS stop cluster from a block (for non-final steps)."""
    lines = list(block.lines)
    original = list(lines)
    lines = _strip_trailing_stop(lines)
    peeled = tuple(original[len(lines) :])
    # Drop leading blanks from peeled for cleaner join if re-emitted
    return block.with_lines(tuple(lines)), peeled
