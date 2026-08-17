from __future__ import annotations

import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from fourth_combinator.__main__ import main
from fourth_combinator.parse import ToolBlock, ToolpathRef


class TestCli(unittest.TestCase):
    def _write_job(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "Bracket"
        root.mkdir()
        for angle in (0, 90):
            body = "\n".join(
                [
                    "G54",
                    "(TC: Rough endmill)",
                    "T1",
                    "M3.9 S10000",
                    f"(Begin operation adaptive: Adaptive{angle} 1)",
                    f"G1 X{angle}",
                    "M5.9",
                    "(TC: Finish)",
                    "T6",
                    "M3.9 S10000",
                    f"(Begin operation contour: Contour{angle} 1)",
                    f"G1 Y{angle}",
                    "M5.9",
                ]
            )
            (root / f"Bracket - A{angle}.gcode").write_text(body + "\n", encoding="utf-8")
        return root

    def test_dry_run_prints_tool_orientation_order(self) -> None:
        root = self._write_job()
        buf = StringIO()
        with patch("sys.stdout", buf):
            code = main([str(root), "--dry-run"])
        self.assertEqual(code, 0)
        text = buf.getvalue()
        self.assertIn("Order (tool, orientation, toolpaths):", text)
        self.assertIn("T1  A0", text)
        self.assertIn("T1  A90", text)
        self.assertIn("T6  A0", text)
        self.assertIn("T6  A90", text)
        self.assertIn("toolpaths:", text)
        self.assertIn("Adaptive0 1 (adaptive)", text)
        self.assertIn("tool: Rough endmill", text)
        self.assertIn("Bracket - 4th axis.gcode", text)
        self.assertFalse((root / "Bracket - 4th axis.gcode").exists())

    def test_final_tool_dry_run(self) -> None:
        root = self._write_job()
        for angle in (0, 90):
            path = root / f"Bracket - A{angle}.gcode"
            body = path.read_text(encoding="utf-8")
            path.write_text(
                "(TC: Ball)\nT2\n(Begin operation pocket: Pocket1 1)\nG1 Z0\n" + body,
                encoding="utf-8",
            )

        buf = StringIO()
        with patch("sys.stdout", buf):
            code = main(
                [
                    str(root),
                    "--dry-run",
                    "--final-tool",
                    "T2,T6",
                    "--final-exclude",
                    "A0",
                ]
            )
        self.assertEqual(code, 0)
        text = buf.getvalue()
        self.assertIn(
            "Final tools (deferred order): T2, T6 (natural order at: A0)",
            text,
        )
        order_headers = [
            ln.strip()
            for ln in text.splitlines()
            if ln.startswith("  T") and "  A" in ln
        ]
        self.assertEqual(order_headers[0], "T2  A0")
        self.assertEqual(order_headers[-2], "T2  A90")
        self.assertEqual(order_headers[-1], "T6  A90")
        self.assertIn("Pocket1 1 (pocket)", text)

    def test_default_output_uses_4th_axis_name(self) -> None:
        root = self._write_job()
        buf = StringIO()
        with patch("sys.stdout", buf):
            code = main([str(root)])
        self.assertEqual(code, 0)
        out = root / "Bracket - 4th axis.gcode"
        self.assertTrue(out.is_file())
        self.assertIn(str(out), buf.getvalue())


class TestToolpathParse(unittest.TestCase):
    def test_toolpaths_from_begin_operation(self) -> None:
        block = ToolBlock(
            tool_number=1,
            lines=(
                "T1",
                "(Begin operation adaptive: Adaptive5 3)",
                "G1 X0",
                "(Begin operation drill: Drill2 1)",
            ),
            description="3 Flute DLC L=18",
        )
        self.assertEqual(
            block.toolpaths(),
            (
                ToolpathRef(kind="adaptive", name="Adaptive5 3"),
                ToolpathRef(kind="drill", name="Drill2 1"),
            ),
        )
