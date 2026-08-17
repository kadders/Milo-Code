from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

TOOL_SELECT_RE = re.compile(r"^T(\d+)\b", re.IGNORECASE)
TC_COMMENT_RE = re.compile(r"^\(\s*TC:\s*(.+?)\s*\)$", re.IGNORECASE)
BEGIN_OP_RE = re.compile(
    r"^\(\s*Begin operation\s+([^:]+):\s*(.+?)\s*\)$",
    re.IGNORECASE,
)


def _code_part(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _peel_trailing_tc(lines: list[str]) -> tuple[list[str], str | None]:
    """If the last meaningful line is a (TC: ...) comment, peel it off."""
    i = len(lines) - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    if i < 0:
        return lines, None
    m = TC_COMMENT_RE.match(lines[i].strip())
    if not m:
        return lines, None
    desc = m.group(1).strip()
    return lines[:i], desc


@dataclass(frozen=True)
class ToolpathRef:
    kind: str
    name: str

    def display(self) -> str:
        return f"{self.name} ({self.kind})"


@dataclass(frozen=True)
class ToolBlock:
    tool_number: int
    lines: tuple[str, ...]
    # From the Fusion (TC: ...) comment immediately before the T select.
    description: str | None = None

    def with_lines(self, lines: tuple[str, ...]) -> ToolBlock:
        return replace(self, lines=lines)

    def toolpaths(self) -> tuple[ToolpathRef, ...]:
        found: list[ToolpathRef] = []
        for line in self.lines:
            m = BEGIN_OP_RE.match(line.strip())
            if m:
                found.append(
                    ToolpathRef(kind=m.group(1).strip(), name=m.group(2).strip())
                )
        return tuple(found)


@dataclass(frozen=True)
class ParsedOrientation:
    path: Path
    angle: float
    preamble: tuple[str, ...]
    blocks: tuple[ToolBlock, ...]  # file appearance order, not sorted by T number


def _is_tool_select(line: str) -> re.Match[str] | None:
    code = _code_part(line)
    if not code:
        return None
    return TOOL_SELECT_RE.match(code)


def parse_orientation_file(path: Path, *, angle: float) -> ParsedOrientation:
    path = path.expanduser().resolve()
    raw_lines = path.read_text(encoding="utf-8").splitlines()

    preamble: list[str] = []
    blocks: list[ToolBlock] = []
    current_tool: int | None = None
    current_lines: list[str] = []
    pending_description: str | None = None

    for line in raw_lines:
        match = _is_tool_select(line)
        if match:
            if current_tool is not None:
                body, peeled = _peel_trailing_tc(current_lines)
                blocks.append(
                    ToolBlock(
                        tool_number=current_tool,
                        lines=tuple(body),
                        description=pending_description,
                    )
                )
                pending_description = peeled
                current_lines = []
            else:
                preamble, pending_description = _peel_trailing_tc(preamble)
            current_tool = int(match.group(1))
            current_lines.append(line)
            continue

        if current_tool is None:
            preamble.append(line)
        else:
            current_lines.append(line)

    if current_tool is not None:
        body, _ = _peel_trailing_tc(current_lines)
        blocks.append(
            ToolBlock(
                tool_number=current_tool,
                lines=tuple(body),
                description=pending_description,
            )
        )

    return ParsedOrientation(
        path=path,
        angle=angle,
        preamble=tuple(preamble),
        blocks=tuple(blocks),
    )
