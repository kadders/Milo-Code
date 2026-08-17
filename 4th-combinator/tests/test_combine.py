from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path

from fourth_combinator.combine import build_execution_plan, load_and_combine


def _sample_block(tool: int, cut: str, *, start_spindle: bool = True, end_spindle: bool = True) -> list[str]:
    lines = [f"T{tool}"]
    if start_spindle:
        lines.extend(["M3.9 S10000", "G4 P1"])
    lines.append(f"G1 {cut}")
    if end_spindle:
        lines.append("M5.9")
    return lines


class TestCombineJob(unittest.TestCase):
    def _write_job(self, model: str = "Bracket") -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / model
        root.mkdir()
        orientations = {
            0: ("X0", "X0b"),
            90: ("X90", "X90b"),
            180: ("X180", "X180b"),
            270: ("X270", "X270b"),
        }
        for angle, cuts in orientations.items():
            body = ["G54", "G21", ""]
            body.extend(_sample_block(1, cuts[0]))
            body.append("")
            body.extend(_sample_block(2, cuts[1]))
            (root / f"{model} - A{angle}.gcode").write_text(
                "\n".join(body) + "\n",
                encoding="utf-8",
            )
        return root

    def test_non_numeric_tool_order_in_execution_plan(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "Bracket"
        root.mkdir()
        for angle in (0, 90):
            body = "\n".join(
                [
                    "G54",
                    "T1",
                    "M3.9 S10000",
                    f"G1 X{angle}",
                    "M5.9",
                    "T6",
                    "M3.9 S10000",
                    f"G1 Y{angle}",
                    "M5.9",
                    "T3",
                    "M3.9 S10000",
                    f"G1 Z{angle}",
                    "M5.9",
                ]
            )
            (root / f"Bracket - A{angle}.gcode").write_text(body + "\n", encoding="utf-8")

        _, index, _ = load_and_combine(root)
        self.assertEqual(
            [(s.tool_number, s.occurrence) for s in index.tool_sequence],
            [(1, 0), (6, 0), (3, 0)],
        )
        steps = build_execution_plan(index)
        tool_order = [s.tool_number for s in steps]
        self.assertEqual(tool_order, [1, 1, 6, 6, 3, 3])

    def test_execution_plan_order(self) -> None:
        root = self._write_job()
        _, index, _ = load_and_combine(root)
        steps = build_execution_plan(index)
        labels = [(s.tool_number, s.angle) for s in steps]
        self.assertEqual(
            labels,
            [
                (1, 0.0),
                (1, 90.0),
                (1, 180.0),
                (1, 270.0),
                (2, 0.0),
                (2, 90.0),
                (2, 180.0),
                (2, 270.0),
            ],
        )

    def test_park_between_orientation_changes(self) -> None:
        root = self._write_job()
        gcode, _, _ = load_and_combine(root)
        self.assertIn("4th-combinator: park (spindle running)", gcode)
        self.assertIn("G53 G0 Z{move.axes[2].max}", gcode)
        self.assertIn("G0 A90", gcode)
        self.assertIn("G0 A180", gcode)

    def test_scrubs_spindle_between_same_tool_orientation_hops(self) -> None:
        root = self._write_job()
        gcode, _, _ = load_and_combine(root)
        t1_a90_marker = gcode.index("T1 @ A90")
        t1_a180_marker = gcode.index("T1 @ A180")
        segment = gcode[t1_a90_marker:t1_a180_marker]
        self.assertNotIn("M3.9 S10000", segment)
        self.assertNotIn("M5.9", segment)
        self.assertIn("G1 X90", segment)

    def test_unequal_tool_counts_match_by_tool_number(self) -> None:
        """Other orientations need not share the reference tool-block count."""
        root = self._write_job()
        # A90 only has T1; T2 is absent at that orientation.
        (root / "Bracket - A90.gcode").write_text(
            "\n".join(["G54", "T1", "M3.9 S10000", "G1 X90", "M5.9"]) + "\n",
            encoding="utf-8",
        )
        gcode, index, _ = load_and_combine(root)
        steps = build_execution_plan(index)
        labels = [(s.tool_number, s.angle) for s in steps]
        self.assertIn((1, 90.0), labels)
        self.assertNotIn((2, 90.0), labels)
        self.assertIn((2, 0.0), labels)
        self.assertIn("G1 X90", gcode)
        self.assertEqual(
            [(s.tool_number, s.occurrence) for s in index.tool_sequence],
            [(1, 0), (2, 0)],
        )

    def test_union_includes_tools_only_on_later_orientations(self) -> None:
        """Tools present only on non-A0 ops (e.g. T16 on A180) must appear."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "AB Block"
        root.mkdir()
        (root / "16 Part - A0 - Op1.gcode").write_text(
            "\n".join(["T1", "G1 X0", "T3", "G1 Y0", "T11", "G1 Z0", "T6", "G1 A0"])
            + "\n",
            encoding="utf-8",
        )
        (root / "19 Part - A90 - Op4.gcode").write_text(
            "\n".join(["T1", "G1 X90", "T2", "G1 Y90", "T3", "G1 Z90"]) + "\n",
            encoding="utf-8",
        )
        (root / "17 Part - A180 - Op2.gcode").write_text(
            "\n".join(["T1", "G1 X180", "T16", "G1 Y180", "T11", "G1 Z180", "T6", "G1 A180"])
            + "\n",
            encoding="utf-8",
        )
        (root / "18 Part - A270 - Op3.gcode").write_text(
            "\n".join(
                ["T1", "G1 X270", "T11", "G1 Y270", "T2", "G1 Z270", "T6", "G1 A270", "T3", "G1 B270"]
            )
            + "\n",
            encoding="utf-8",
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _, index, _ = load_and_combine(root)

        self.assertEqual(
            [w for w in caught if "missing" in str(w.message).lower()],
            [],
        )
        self.assertEqual(
            [s.tool_number for s in index.tool_sequence],
            [1, 3, 11, 6, 2, 16],
        )
        steps = build_execution_plan(index)
        labels = [(s.tool_number, s.angle) for s in steps]
        self.assertIn((16, 180.0), labels)
        self.assertIn((3, 90.0), labels)
        self.assertIn((2, 90.0), labels)
        self.assertIn((2, 270.0), labels)
        self.assertNotIn((16, 0.0), labels)
        self.assertNotIn((3, 180.0), labels)

    def test_repeated_tools_match_by_occurrence(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "Bracket"
        root.mkdir()
        for angle in (0, 90):
            body = "\n".join(
                [
                    "G54",
                    "T1",
                    f"G1 X{angle}a",
                    "T6",
                    f"G1 Y{angle}",
                    "T1",
                    f"G1 X{angle}b",
                ]
            )
            (root / f"Bracket - A{angle}.gcode").write_text(body + "\n", encoding="utf-8")

        _, index, _ = load_and_combine(root)
        self.assertEqual(
            [(s.tool_number, s.occurrence) for s in index.tool_sequence],
            [(1, 0), (6, 0), (1, 1)],
        )
        steps = build_execution_plan(index)
        self.assertEqual(
            [(s.tool_number, s.occurrence, s.angle) for s in steps],
            [
                (1, 0, 0.0),
                (1, 0, 90.0),
                (6, 0, 0.0),
                (6, 0, 90.0),
                (1, 1, 0.0),
                (1, 1, 90.0),
            ],
        )

    def test_final_tool_runs_last_with_exclusions(self) -> None:
        """Excluded orientations keep final tool in natural order; others defer."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "AB Block"
        root.mkdir()
        # A0: T2, T1, T11, T15, T6 — T2 first as its own tool change
        (root / "Part - A0.gcode").write_text(
            "\n".join(
                [
                    "T2",
                    "G1 A0",
                    "T1",
                    "G1 X0",
                    "T11",
                    "G1 Y0",
                    "T15",
                    "G1 Z0",
                    "T6",
                    "G1 B0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "Part - A90.gcode").write_text(
            "\n".join(["T1", "G1 X90", "T2", "G1 Y90", "T6", "G1 Z90"]) + "\n",
            encoding="utf-8",
        )
        (root / "Part - A180.gcode").write_text(
            "\n".join(["T1", "G1 X180", "T2", "G1 Y180", "T11", "G1 Z180"]) + "\n",
            encoding="utf-8",
        )

        _, index, _ = load_and_combine(
            root,
            final_tools=(2,),
            final_exclude_angles=frozenset({0.0}),
        )
        self.assertEqual(
            [s.tool_number for s in index.tool_sequence],
            [2, 1, 11, 15, 6],
        )
        steps = build_execution_plan(index)
        labels = [(s.tool_number, s.angle) for s in steps]
        self.assertEqual(
            labels,
            [
                (2, 0.0),  # natural: T2 first on A0
                (1, 0.0),
                (1, 90.0),
                (1, 180.0),
                (11, 0.0),
                (11, 180.0),
                (15, 0.0),
                (6, 0.0),
                (6, 90.0),
                (2, 90.0),  # deferred last pass
                (2, 180.0),
            ],
        )

    def test_final_tool_without_exclude_defers_all(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "Part"
        root.mkdir()
        (root / "Part - A0.gcode").write_text(
            "\n".join(["T2", "G1 A0", "T1", "G1 X0"]) + "\n",
            encoding="utf-8",
        )
        (root / "Part - A90.gcode").write_text(
            "\n".join(["T1", "G1 X90", "T2", "G1 Y90"]) + "\n",
            encoding="utf-8",
        )
        _, index, _ = load_and_combine(root, final_tools=(2,))
        labels = [(s.tool_number, s.angle) for s in build_execution_plan(index)]
        self.assertEqual(
            labels,
            [
                (1, 0.0),
                (1, 90.0),
                (2, 0.0),
                (2, 90.0),
            ],
        )

    def test_multiple_final_tools_deferred_in_list_order(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "Part"
        root.mkdir()
        (root / "Part - A0.gcode").write_text(
            "\n".join(
                [
                    "T2",
                    "G1 A0",
                    "T1",
                    "G1 X0",
                    "T6",
                    "G1 B0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "Part - A90.gcode").write_text(
            "\n".join(["T1", "G1 X90", "T2", "G1 Y90", "T6", "G1 Z90"]) + "\n",
            encoding="utf-8",
        )
        _, index, _ = load_and_combine(
            root,
            final_tools=(2, 6),
            final_exclude_angles=frozenset({0.0}),
        )
        labels = [(s.tool_number, s.angle) for s in build_execution_plan(index)]
        self.assertEqual(
            labels,
            [
                (2, 0.0),
                (1, 0.0),
                (1, 90.0),
                (6, 0.0),
                (2, 90.0),  # deferred T2 before T6
                (6, 90.0),
            ],
        )

    def test_final_exclude_requires_final_tool(self) -> None:
        root = self._write_job()
        with self.assertRaisesRegex(ValueError, "--final-exclude requires --final-tool"):
            load_and_combine(root, final_exclude_angles=frozenset({0.0}))

    def test_output_default_name(self) -> None:
        root = self._write_job()
        out_path = root / "Bracket - 4th axis.gcode"
        if out_path.exists():
            out_path.unlink()
        gcode, index, _ = load_and_combine(root)
        out_path.write_text(gcode, encoding="utf-8")
        self.assertTrue(out_path.exists())
        self.assertIn("Model: Bracket", gcode)
        self.assertEqual(index.discovery.model, "Bracket")
