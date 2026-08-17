from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fourth_combinator.discover import discover_job


class TestDiscoverJob(unittest.TestCase):
    def _write_job(self, files: dict[str, str], *, dirname: str | None = None) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        if dirname is not None:
            root = root / dirname
            root.mkdir()
        for name, body in files.items():
            (root / name).write_text(body, encoding="utf-8")
        return root

    def test_discovers_model_and_angles(self) -> None:
        root = self._write_job(
            {
                "Bracket - A0.gcode": "T1\n",
                "Bracket - A90.gcode": "T1\n",
                "Bracket - A180.gcode": "T1\n",
                "Bracket - A270.gcode": "T1\n",
            },
            dirname="Bracket",
        )
        job = discover_job(root)
        self.assertEqual(job.model, "Bracket")
        self.assertEqual(
            tuple(o.angle for o in job.orientations),
            (0.0, 90.0, 180.0, 270.0),
        )

    def test_discovers_non_cardinal_angles(self) -> None:
        root = self._write_job(
            {
                "Bracket - A0.gcode": "T1\n",
                "Bracket - A45.gcode": "T1\n",
                "Bracket - A120.gcode": "T1\n",
            },
            dirname="Bracket",
        )
        job = discover_job(root)
        self.assertEqual(
            tuple(o.angle for o in job.orientations),
            (0.0, 45.0, 120.0),
        )
        job = discover_job(root, required_angles=(0.0, 45.0, 120.0))
        self.assertEqual(len(job.orientations), 3)

    def test_matches_op_tags_before_or_after_angle(self) -> None:
        root = self._write_job(
            {
                "Widget - Op1 - A0.gcode": "T1\n",
                "Widget - Op2 - A90.gcode": "T1\n",
                "Widget - A180 - finish.gcode": "T1\n",
            },
            dirname="Widget",
        )
        job = discover_job(root)
        self.assertEqual(job.model, "Widget")
        self.assertEqual(
            tuple(o.angle for o in job.orientations),
            (0.0, 90.0, 180.0),
        )
        self.assertEqual(job.orientations[0].path.name, "Widget - Op1 - A0.gcode")
        self.assertEqual(job.orientations[2].tail, " - finish")

    def test_ignores_files_without_orientation_marker(self) -> None:
        root = self._write_job(
            {
                "readme.txt": "nope",
                "Widget - notes.gcode": "T1\n",
                "Widget - A0.gcode": "T1\n",
            },
            dirname="Widget",
        )
        job = discover_job(root)
        self.assertEqual(len(job.orientations), 1)
        self.assertEqual(job.orientations[0].angle, 0.0)

    def test_errors_on_duplicate_angles(self) -> None:
        root = self._write_job(
            {
                "Bracket - Op1 - A0.gcode": "",
                "Bracket - Op2 - A0.gcode": "",
            },
            dirname="Bracket",
        )
        with self.assertRaisesRegex(ValueError, "Duplicate orientation A0"):
            discover_job(root)

    def test_errors_on_no_matches(self) -> None:
        root = self._write_job({"readme.txt": "nope"})
        with self.assertRaisesRegex(ValueError, "No orientation files"):
            discover_job(root)

    def test_required_orientations(self) -> None:
        root = self._write_job(
            {"Bracket - A0.gcode": ""},
            dirname="Bracket",
        )
        with self.assertRaisesRegex(ValueError, "Missing required orientations"):
            discover_job(root, required_angles=(0.0, 90.0))
