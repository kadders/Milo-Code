from __future__ import annotations

import argparse
import os
import re
import sys
import warnings
from pathlib import Path

from fourth_combinator.combine import build_execution_plan, load_and_combine
from fourth_combinator.index import JobIndex, find_first_tool_block
from fourth_combinator.mqtt_sim import publish_mqtt_envelopes, write_mqtt_jsonl
from fourth_combinator.park import fmt_angle
from fourth_combinator.sim import build_sim_gcode, format_sim_console_log


def _parse_angles(raw: str | None) -> tuple[float, ...] | None:
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    angles: list[float] = []
    for part in parts:
        part = re.sub(r"^[Aa]", "", part)
        value = float(part)
        if value.is_integer():
            value = float(int(value))
        angles.append(value)
    return tuple(angles)


def _parse_tools(raw: str | None) -> tuple[int, ...]:
    """Parse comma-separated tools: '2,T6,15' -> (2, 6, 15)."""
    if raw is None or not raw.strip():
        return ()
    tools: list[int] = []
    for part in raw.split(","):
        text = part.strip()
        if not text:
            continue
        m = re.fullmatch(r"[Tt]?(\d+)", text)
        if not m:
            raise ValueError(f"Invalid tool number: {part!r} (expected e.g. 2 or T2)")
        tools.append(int(m.group(1)))
    return tuple(tools)


def format_dry_run(index: JobIndex, out_path: Path) -> str:
    """Human-readable plan with toolpaths per step for validation."""
    lines: list[str] = [
        f"Model: {index.discovery.model}",
        f"Output: {out_path}",
    ]
    if index.final_tools:
        finals = ", ".join(f"T{t}" for t in index.final_tools)
        excl = ", ".join(
            f"A{fmt_angle(a)}" for a in sorted(index.final_exclude_angles)
        ) or "(none)"
        lines.append(
            f"Final tools (deferred order): {finals} "
            f"(natural order at: {excl})"
        )
    lines.append("Order (tool, orientation, toolpaths):")

    for step in build_execution_plan(index):
        orientation = index.by_angle[step.angle]
        block = find_first_tool_block(orientation, tool_number=step.tool_number)
        lines.append(f"  T{step.tool_number}  A{fmt_angle(step.angle)}")
        lines.append(f"    file: {step.source_file}")
        if block is not None and block.description:
            lines.append(f"    tool: {block.description}")
        if block is not None:
            paths = block.toolpaths()
            if paths:
                lines.append("    toolpaths:")
                for tp in paths:
                    lines.append(f"      - {tp.display()}")
            else:
                lines.append("    toolpaths: (none detected)")
        else:
            lines.append("    toolpaths: (missing block)")

    return "\n".join(lines) + "\n"


def _emit_sim(
    index: JobIndex,
    *,
    sim_path: Path,
    layer_eps: float,
    mqtt_publish: bool,
    mqtt_jsonl: bool,
    mqtt_device_id: str | None,
    embed_mqtt: bool,
    verbose: bool,
) -> int:
    sim_path = sim_path.expanduser()
    sim_gcode, events, envelopes = build_sim_gcode(
        index,
        layer_eps=layer_eps,
        verbose=verbose,
        job_file=sim_path.name,
        mqtt_device_id=mqtt_device_id,
        embed_mqtt=embed_mqtt,
    )
    sim_path.parent.mkdir(parents=True, exist_ok=True)
    sim_path.write_text(sim_gcode, encoding="utf-8")

    sys.stdout.write(format_sim_console_log(events, job_name=sim_path.name))
    print(f"Wrote {sim_path}")
    if embed_mqtt:
        n_m118 = sum(1 for ln in sim_gcode.splitlines() if ln.startswith("M118 P6"))
        print(f"Embedded {n_m118} M118 P6 MQTT publishes for Jarvis (cam/…)")

    if mqtt_jsonl:
        mqtt_path = sim_path.with_suffix(".mqtt.jsonl")
        write_mqtt_jsonl(mqtt_path, envelopes)
        print(f"Wrote {mqtt_path}")

    if mqtt_publish:
        ok, msg = publish_mqtt_envelopes(envelopes)
        print(msg, file=sys.stderr if not ok else sys.stdout)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Combine per-orientation MOS/NeXT Fusion G-code files "
            "into one A-axis job."
        ),
    )
    parser.add_argument(
        "job_dir",
        type=Path,
        help="Directory containing '* - A#*.gcode' orientation files",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help='Output path (default: {job_dir}/{model} - 4th axis.gcode)',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print tool/orientation order and toolpaths (no file written)",
    )
    parser.add_argument(
        "--orientations",
        type=str,
        help="Required orientation angles, comma-separated (e.g. 0,45,120 or A0,A135.5)",
    )
    parser.add_argument(
        "--final-tool",
        type=str,
        help=(
            "Tool(s) to defer to last passes, comma-separated in deferred order "
            "(e.g. T2,T6). With --final-exclude, listed orientations still run "
            "those tools in natural file order."
        ),
    )
    parser.add_argument(
        "--final-exclude",
        type=str,
        help=(
            "Orientations that keep final tools in natural order "
            "(not deferred), comma-separated (e.g. 0 or A0). Requires --final-tool."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Error when a reference tool is missing at an orientation (default: warn and skip)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log when spindle bookends are scrubbed",
    )
    parser.add_argument(
        "--sim",
        action="store_true",
        help=(
            "Write datum-safe first-layer sim gcode "
            "(default: {model} - 4th axis sim.gcode) instead of the cutting file"
        ),
    )
    parser.add_argument(
        "--sim-also",
        action="store_true",
        help="Write both the cutting file and the sim gcode",
    )
    parser.add_argument(
        "--sim-layer-eps",
        type=float,
        default=0.05,
        help="First-layer Z tolerance in mm (default: 0.05)",
    )
    parser.add_argument(
        "--mqtt-device-id",
        type=str,
        default=None,
        help=(
            "Device id for cam/{device}/… topics embedded in sim gcode "
            "(default: TAP_MQTT_DEVICE_ID or hostname)"
        ),
    )
    parser.add_argument(
        "--no-mqtt-embed",
        action="store_true",
        help="Do not embed M118 P6 MQTT publishes in sim gcode",
    )
    parser.add_argument(
        "--mqtt-jsonl",
        action="store_true",
        help="Also write {sim}.mqtt.jsonl sidecar (optional; mill path uses M118 in gcode)",
    )
    parser.add_argument(
        "--mqtt-publish",
        action="store_true",
        help="Also live-publish from this host when TAP_MQTT_HOST is set (fail-open)",
    )

    args = parser.parse_args(argv)
    if args.sim and args.sim_also:
        print("error: use --sim or --sim-also, not both", file=sys.stderr)
        return 2
    required = _parse_angles(args.orientations)

    try:
        final_tools = _parse_tools(args.final_tool)
        exclude = _parse_angles(args.final_exclude)
        gcode, index, discovery_warnings = load_and_combine(
            args.job_dir,
            required_angles=required,
            strict=args.strict,
            verbose=args.verbose,
            final_tools=final_tools,
            final_exclude_angles=frozenset(exclude) if exclude else None,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for msg in discovery_warnings:
        warnings.warn(msg)

    discovery = index.discovery
    default_cut = f"{discovery.model} - 4th axis.gcode"
    default_sim = f"{discovery.model} - 4th axis sim.gcode"
    cut_path = args.output if args.output is not None else discovery.job_dir / default_cut
    if args.sim and args.output is not None:
        sim_path = args.output
    else:
        sim_path = discovery.job_dir / default_sim

    if args.dry_run:
        preview = sim_path if args.sim else cut_path
        sys.stdout.write(format_dry_run(index, preview))
        return 0

    write_cut = args.sim_also or not args.sim
    write_sim = args.sim or args.sim_also

    if write_cut:
        cut_path = cut_path.expanduser()
        cut_path.parent.mkdir(parents=True, exist_ok=True)
        cut_path.write_text(gcode, encoding="utf-8")
        print(f"Wrote {cut_path}")

    if write_sim:
        device = args.mqtt_device_id or os.environ.get("TAP_MQTT_DEVICE_ID") or None
        return _emit_sim(
            index,
            sim_path=sim_path,
            layer_eps=args.sim_layer_eps,
            mqtt_publish=args.mqtt_publish,
            mqtt_jsonl=args.mqtt_jsonl,
            mqtt_device_id=device,
            embed_mqtt=not args.no_mqtt_embed,
            verbose=args.verbose,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
