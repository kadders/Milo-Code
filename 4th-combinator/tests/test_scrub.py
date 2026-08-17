from __future__ import annotations

import unittest

from fourth_combinator.parse import ToolBlock
from fourth_combinator.scrub import (
    extract_trailing_spindle_stop,
    scrub_inter_op_spindle_stops,
    scrub_orientation_hop,
    scrub_spindle,
)


INTER_OP_BRIDGE = (
    "(Disable Variable Spindle Speed Control)",
    "M7001",
    "(Disable Coolant)",
    "M9",
    "(Begin postamble)",
    "(Park)",
    "G27",
    "(Double-check spindle is stopped)",
    "M5.9",
    "",
    "(Park ready for WCS change)",
    "(Enable Variable Spindle Speed Control)",
    "M7000 P4000 V200",
    "",
    "(Start spindle at requested RPM and wait for it to accelerate)",
    "M3.9 S18000",
    "",
    "(Enable Mist Coolant)",
    "M7",
)


class TestScrubSpindle(unittest.TestCase):
    def test_strips_spindle_bookends(self) -> None:
        block = ToolBlock(
            tool_number=1,
            lines=(
                "M5.9",
                "M3.9 S10000",
                "G4 P2",
                "G0 A90",
                "G1 X10 Y10",
                "M5.9",
            ),
        )
        scrubbed = scrub_spindle(block)
        self.assertEqual(scrubbed.lines, ("G1 X10 Y10",))

    def test_orientation_hop_strips_tool_select(self) -> None:
        block = ToolBlock(
            tool_number=1,
            lines=(
                "T1",
                "M3.9 S10000",
                "G1 X10",
                "M5.9",
            ),
        )
        scrubbed = scrub_orientation_hop(block)
        self.assertEqual(scrubbed.lines, ("G1 X10",))

    def test_preserves_cutting_moves(self) -> None:
        block = ToolBlock(
            tool_number=1,
            lines=("G1 X1", "G1 X2", "G1 X3"),
        )
        self.assertEqual(scrub_spindle(block).lines, block.lines)

    def test_inter_op_removes_stop_and_restart_keeps_ops(self) -> None:
        block = ToolBlock(
            tool_number=1,
            lines=(
                "T1",
                "(Enable Variable Spindle Speed Control)",
                "M7000 P4000 V200",
                "(Start spindle at requested RPM and wait for it to accelerate)",
                "M3.9 S18000",
                "(Enable Mist Coolant)",
                "M7",
                "(Begin operation adaptive: Adaptive1 1)",
                "G1 X1",
                *INTER_OP_BRIDGE,
                "(Begin operation adaptive: Adaptive2 1)",
                "G1 X2",
                "(Disable Variable Spindle Speed Control)",
                "M7001",
                "(Disable Coolant)",
                "M9",
                "(Begin postamble)",
                "(Park)",
                "G27",
                "(Double-check spindle is stopped)",
                "M5.9",
            ),
        )
        scrubbed = scrub_inter_op_spindle_stops(block)
        text = "\n".join(scrubbed.lines)
        self.assertIn("(Begin operation adaptive: Adaptive1 1)", text)
        self.assertIn("(Begin operation adaptive: Adaptive2 1)", text)
        self.assertIn("G1 X1", text)
        self.assertIn("G1 X2", text)
        # First start kept
        self.assertIn("M7000 P4000 V200", text)
        self.assertIn("M3.9 S18000", text)
        self.assertIn("M7", text)
        # Mid-bridge removed: only the trailing postamble stop remains (one each)
        self.assertEqual(text.count("G27"), 1)
        self.assertEqual(text.count("M7001"), 1)
        self.assertEqual(text.count("M5.9"), 1)
        self.assertEqual(text.count("M7000 P4000 V200"), 1)
        self.assertEqual(text.count("M3.9 S18000"), 1)
        # Between the two Begin operation lines there must be no stop bridge
        op1 = text.index("(Begin operation adaptive: Adaptive1 1)")
        op2 = text.index("(Begin operation adaptive: Adaptive2 1)")
        between = text[op1:op2]
        self.assertNotIn("G27", between)
        self.assertNotIn("M7001", between)
        self.assertNotIn("M5.9", between)
        self.assertNotIn("M7000", between)

    def test_orientation_hop_strips_full_restart_and_stop(self) -> None:
        block = ToolBlock(
            tool_number=1,
            lines=(
                "T1",
                "(Enable Variable Spindle Speed Control)",
                "M7000 P4000 V200",
                "(Start spindle at requested RPM and wait for it to accelerate)",
                "M3.9 S18000",
                "(Enable Mist Coolant)",
                "M7",
                "(Begin operation contour: Contour1 1)",
                "G1 X10",
                "(Disable Variable Spindle Speed Control)",
                "M7001",
                "M9",
                "G27",
                "M5.9",
            ),
        )
        scrubbed = scrub_orientation_hop(block)
        text = "\n".join(scrubbed.lines)
        self.assertIn("(Begin operation contour: Contour1 1)", text)
        self.assertIn("G1 X10", text)
        self.assertNotIn("T1", text)
        self.assertNotIn("M7000", text)
        self.assertNotIn("M3.9", text)
        self.assertNotIn("M7", text)
        self.assertNotIn("G27", text)
        self.assertNotIn("M5.9", text)

    def test_extract_trailing_peels_full_stop_cluster(self) -> None:
        block = ToolBlock(
            tool_number=1,
            lines=(
                "T1",
                "G1 X1",
                "(Disable Variable Spindle Speed Control)",
                "M7001",
                "(Disable Coolant)",
                "M9",
                "(Begin postamble)",
                "(Park)",
                "G27",
                "(Double-check spindle is stopped)",
                "M5.9",
            ),
        )
        trimmed, peeled = extract_trailing_spindle_stop(block)
        self.assertEqual(trimmed.lines, ("T1", "G1 X1"))
        self.assertIn("G27", "\n".join(peeled))
        self.assertIn("M5.9", "\n".join(peeled))
        self.assertIn("M7001", "\n".join(peeled))
