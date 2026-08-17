from __future__ import annotations

from dataclasses import dataclass, field

from fourth_combinator.discover import JobDiscovery
from fourth_combinator.parse import ParsedOrientation, ToolBlock


@dataclass(frozen=True)
class ToolSlot:
    """One entry in the combined tool order."""

    tool_number: int
    # 0-based among blocks with this tool_number in the file that introduced
    # this slot (A0 for tools first seen there; another A# for tools only
    # present on later orientations).
    occurrence: int


@dataclass(frozen=True)
class JobIndex:
    discovery: JobDiscovery
    reference_angle: float
    by_angle: dict[float, ParsedOrientation]
    # Union of tools across orientations: A0 appearance order first, then any
    # tools only found on other A# files (angle order, file appearance).
    # Never sorted by tool number. final_tools are deferred in the execution
    # plan (list order = deferred pass order). Orientations in
    # final_exclude_angles keep those tools in natural placement.
    tool_sequence: tuple[ToolSlot, ...]
    final_tools: tuple[int, ...] = ()
    final_exclude_angles: frozenset[float] = field(default_factory=frozenset)

    @property
    def final_tool_set(self) -> frozenset[int]:
        return frozenset(self.final_tools)


def _reference_orientation(
    discovery: JobDiscovery,
    parsed: dict[float, ParsedOrientation],
) -> float:
    angles = [item.angle for item in discovery.orientations]
    if 0.0 in parsed:
        return 0.0
    return min(angles)


def _slots_from_orientation(orientation: ParsedOrientation) -> list[ToolSlot]:
    counts: dict[int, int] = {}
    slots: list[ToolSlot] = []
    for block in orientation.blocks:
        n = block.tool_number
        occurrence = counts.get(n, 0)
        counts[n] = occurrence + 1
        slots.append(ToolSlot(tool_number=n, occurrence=occurrence))
    return slots


def build_tool_sequence(
    parsed: dict[float, ParsedOrientation],
    *,
    reference_angle: float,
    angle_order: tuple[float, ...],
) -> tuple[ToolSlot, ...]:
    """Build tool order from A0, then append tools first seen on other A# files."""
    reference = parsed[reference_angle]
    slots = _slots_from_orientation(reference)
    seen_numbers = {slot.tool_number for slot in slots}

    for angle in angle_order:
        if angle == reference_angle:
            continue
        for slot in _slots_from_orientation(parsed[angle]):
            if slot.tool_number in seen_numbers:
                continue
            seen_numbers.add(slot.tool_number)
            slots.append(ToolSlot(tool_number=slot.tool_number, occurrence=0))

    return tuple(slots)


def validate_final_tools(
    sequence: tuple[ToolSlot, ...],
    *,
    final_tools: tuple[int, ...],
) -> None:
    if not final_tools:
        return
    present = {s.tool_number for s in sequence}
    missing = [t for t in final_tools if t not in present]
    if missing:
        listed = ", ".join(f"T{t}" for t in missing)
        raise ValueError(
            f"Final tool(s) not found in any orientation file: {listed}"
        )
    if len(set(final_tools)) != len(final_tools):
        raise ValueError(f"Duplicate entries in --final-tool list: {final_tools!r}")


def find_tool_block(
    orientation: ParsedOrientation,
    *,
    tool_number: int,
    occurrence: int = 0,
) -> ToolBlock | None:
    """Find the Nth block with tool_number in file order (occurrence is 0-based)."""
    seen = 0
    for block in orientation.blocks:
        if block.tool_number != tool_number:
            continue
        if seen == occurrence:
            return block
        seen += 1
    return None


def find_first_tool_block(
    orientation: ParsedOrientation,
    *,
    tool_number: int,
) -> ToolBlock | None:
    """First block for tool_number in this orientation (ignore occurrence)."""
    return find_tool_block(orientation, tool_number=tool_number, occurrence=0)


def build_job_index(
    discovery: JobDiscovery,
    parsed: dict[float, ParsedOrientation],
    *,
    strict: bool = False,
    final_tools: tuple[int, ...] = (),
    final_exclude_angles: frozenset[float] | None = None,
) -> JobIndex:
    del strict  # reserved; missing tools at an orientation are skipped, not errors
    ref_angle = _reference_orientation(discovery, parsed)
    angle_order = tuple(item.angle for item in discovery.orientations)
    tool_sequence = build_tool_sequence(
        parsed,
        reference_angle=ref_angle,
        angle_order=angle_order,
    )
    validate_final_tools(tool_sequence, final_tools=final_tools)

    if not tool_sequence:
        raise ValueError(
            f"No tool blocks found in reference orientation A{ref_angle} "
            f"({parsed[ref_angle].path.name})"
        )

    exclude = frozenset(final_exclude_angles or ())
    if exclude and not final_tools:
        raise ValueError(
            "--final-exclude requires --final-tool "
            "(orientations that keep final tools in natural order)"
        )
    unknown = exclude - set(angle_order)
    if unknown:
        bad = ", ".join(
            f"A{int(a) if float(a).is_integer() else a}" for a in sorted(unknown)
        )
        raise ValueError(f"Unknown orientation(s) in --final-exclude: {bad}")

    return JobIndex(
        discovery=discovery,
        reference_angle=ref_angle,
        by_angle=parsed,
        tool_sequence=tool_sequence,
        final_tools=final_tools,
        final_exclude_angles=exclude,
    )
