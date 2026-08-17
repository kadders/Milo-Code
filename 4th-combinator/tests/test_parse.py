from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fourth_combinator.parse import parse_orientation_file


class TestParseOrientation(unittest.TestCase):
    def test_splits_on_tool_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Part - A0.gcode"
            path.write_text(
                "\n".join(
                    [
                        "G54",
                        "T1 ; tool 1",
                        "M3.9 S10000",
                        "G1 X1",
                        "M5.9",
                        "T2",
                        "M3.9 S12000",
                        "G1 X2",
                    ]
                ),
                encoding="utf-8",
            )
            parsed = parse_orientation_file(path, angle=0.0)
            self.assertEqual(parsed.preamble, ("G54",))
            self.assertEqual(len(parsed.blocks), 2)
            self.assertEqual(parsed.blocks[0].tool_number, 1)
            self.assertEqual(parsed.blocks[1].tool_number, 2)
            self.assertIn("G1 X1", parsed.blocks[0].lines)
            self.assertIn("G1 X2", parsed.blocks[1].lines)

    def test_preserves_non_numeric_tool_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Part - A0.gcode"
            path.write_text(
                "\n".join(
                    [
                        "T1",
                        "G1 X1",
                        "T6",
                        "G1 X6",
                        "T3",
                        "G1 X3",
                    ]
                ),
                encoding="utf-8",
            )
            parsed = parse_orientation_file(path, angle=0.0)
            self.assertEqual(
                tuple(b.tool_number for b in parsed.blocks),
                (1, 6, 3),
            )

    def test_ignores_commented_tool_like_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Part - A0.gcode"
            path.write_text(
                "\n".join(
                    [
                        "; T99 not a tool change",
                        "T1",
                        "G1 X0",
                    ]
                ),
                encoding="utf-8",
            )
            parsed = parse_orientation_file(path, angle=0.0)
            self.assertEqual(len(parsed.blocks), 1)
            self.assertEqual(parsed.blocks[0].tool_number, 1)
