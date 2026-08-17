from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Match the orientation marker anywhere in the name: " - A#" plus optional trailing
# text before the extension (e.g. "Bracket - Op1 - A0.gcode", "Part - A90 - finish.nc").
# Greedy head so we bind to the last " - A#" occurrence.
ORIENTATION_FILENAME_RE = re.compile(
    r"^(?P<head>.+) - A(?P<angle>\d+(?:\.\d+)?)(?P<tail>.*)\.(?P<ext>gcode|nc|g)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OrientationFile:
    angle: float
    path: Path
    head: str
    tail: str


@dataclass(frozen=True)
class JobDiscovery:
    job_dir: Path
    model: str
    orientations: tuple[OrientationFile, ...]
    warnings: tuple[str, ...]


def _parse_angle(raw: str) -> float:
    value = float(raw)
    if value.is_integer():
        return float(int(value))
    return value


def discover_job(
    job_dir: Path,
    *,
    required_angles: tuple[float, ...] | None = None,
) -> JobDiscovery:
    job_dir = job_dir.expanduser().resolve()
    if not job_dir.is_dir():
        raise FileNotFoundError(f"Job directory not found: {job_dir}")

    matches: list[OrientationFile] = []
    for path in sorted(job_dir.iterdir()):
        if not path.is_file():
            continue
        m = ORIENTATION_FILENAME_RE.match(path.name)
        if not m:
            continue
        matches.append(
            OrientationFile(
                angle=_parse_angle(m.group("angle")),
                path=path,
                head=m.group("head"),
                tail=m.group("tail") or "",
            )
        )

    if not matches:
        raise ValueError(
            f"No orientation files matching '* - A#*.{{gcode|nc|g}}' in {job_dir}"
        )

    # Model name comes from the job directory; filenames may include Op1/Op2/etc.
    model = job_dir.name

    by_angle: dict[float, OrientationFile] = {}
    for item in matches:
        if item.angle in by_angle:
            raise ValueError(
                f"Duplicate orientation A{item.angle} in {job_dir}: "
                f"{by_angle[item.angle].path.name} and {item.path.name}"
            )
        by_angle[item.angle] = item

    angles = tuple(sorted(by_angle))
    if required_angles is not None:
        missing = [a for a in required_angles if a not in by_angle]
        if missing:
            missing_s = ", ".join(f"A{a}" for a in missing)
            raise ValueError(f"Missing required orientations in {job_dir}: {missing_s}")

    warnings: list[str] = []
    if 0.0 not in by_angle:
        warnings.append("No A0 orientation file found; tool order cannot use A0 reference")

    orientations = tuple(by_angle[angle] for angle in angles)
    return JobDiscovery(
        job_dir=job_dir,
        model=model,
        orientations=orientations,
        warnings=tuple(warnings),
    )
