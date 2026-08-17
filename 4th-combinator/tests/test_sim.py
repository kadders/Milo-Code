from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from fourth_combinator.combine import load_and_combine
from fourth_combinator.mqtt_sim import (
    build_sim_mqtt_envelopes,
    m118_publish_line,
    write_mqtt_jsonl,
)
from fourth_combinator.sim import (
    build_sim_gcode,
    extract_first_layer,
    force_z0,
    format_sim_console_log,
    should_strip_line,
)


class TestFirstLayerExtract(unittest.TestCase):
    def test_keeps_first_layer_xy_drops_second(self) -> None:
        op = [
            "G0 Z10",
            "G0 X0 Y0",
            "G1 Z-1.0 F300",
            "G1 X10 Y0 F500",
            "G1 X10 Y10",
            "G1 Z-2.0 F300",
            "G1 X0 Y10",
            "G1 X0 Y0",
        ]
        layer = extract_first_layer(op, layer_eps=0.05)
        text = "\n".join(layer)
        self.assertIn("G1 X10 Y0", text)
        self.assertIn("G1 X10 Y10", text)
        self.assertNotIn("X0 Y10", text)
        self.assertNotIn("Z-2", text)

    def test_force_z0(self) -> None:
        self.assertEqual(force_z0("G1 X1 Y2 Z-1.5 F100"), "G1 X1 Y2 Z0 F100")
        self.assertEqual(force_z0("G0 Z10"), "G0 Z0")


class TestSimSafety(unittest.TestCase):
    def _job(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "Widget"
        root.mkdir()
        for angle in (0, 90):
            body = "\n".join(
                [
                    "G54",
                    "(TC: Endmill)",
                    'M4000 P3 R3 F3 L18 S"Endmill"',
                    "T3",
                    "M4001",
                    "M7000",
                    "M3.9 S12000",
                    "(Enable Mist)",
                    "M7",
                    f"(Begin operation adaptive: Adaptive{angle} 1)",
                    "G0 Z15",
                    "G0 X1 Y1",
                    "G1 Z-0.5 F200",
                    f"G1 X{10 + angle} Y1 F800",
                    "G1 X10 Y5",
                    "G1 Z-1.5 F200",
                    "G1 X0 Y5",
                    "(Disable Coolant)",
                    "M9",
                    "M5.9",
                    "M7001",
                ]
            )
            (root / f"Widget - A{angle}.gcode").write_text(body + "\n", encoding="utf-8")
        return root

    def test_sim_gcode_safety_and_first_layer(self) -> None:
        root = self._job()
        _, index, _ = load_and_combine(root)
        gcode, events, envelopes = build_sim_gcode(
            index,
            layer_eps=0.05,
            mqtt_device_id="milo",
            mqtt_session_id="20260101_120000",
        )

        self.assertTrue(gcode.lstrip().startswith(";") or "M9" in gcode.splitlines()[:10])
        lines = [ln.strip() for ln in gcode.splitlines() if ln.strip()]
        self.assertIn("M9", lines[:8])

        self.assertNotRegex(gcode, r"(?m)^T\d+\b")
        self.assertNotIn("M4001", gcode)
        # M4000 must be commented out (not executed) so tooling is not reloaded
        self.assertNotRegex(gcode, r"(?m)^M4000\b")
        self.assertRegex(gcode, r"(?m)^; M4000\b")
        self.assertNotRegex(gcode, r"(?m)^M3(?:\.\d+)?\b")
        self.assertNotRegex(gcode, r"(?m)^M4(?:\.\d+)?\b")
        self.assertNotRegex(gcode, r"(?m)^M5(?:\.\d+)?\b")
        self.assertNotIn("M7000", gcode)
        self.assertNotIn("M7001", gcode)
        self.assertNotRegex(gcode, r"(?m)^M7\b")
        self.assertNotRegex(gcode, r"(?m)^M8\b")
        self.assertNotIn("Enable Mist", gcode)
        self.assertIn("M291", gcode)
        self.assertIn("4th-combinator sim: tool change to T3", gcode)
        self.assertIn("G0 A90", gcode)
        self.assertIn("G53", gcode)

        self.assertIn("G1 X10 Y1", gcode)
        self.assertIn("G1 X10 Y5", gcode)
        self.assertNotIn("G1 X0 Y5", gcode)
        self.assertNotRegex(gcode, r"[Zz]\s*-\d")
        self.assertRegex(gcode, r"[Zz]0")
        self.assertIn("M400", gcode)

        # Mill → Jarvis: compact quoted M118 P6 embeds on cam/{device}/…
        self.assertIn('T"cam/milo/session"', gcode)
        self.assertIn('T"cam/milo/tool"', gcode)
        self.assertIn('M118 P6 S"', gcode)
        self.assertNotIn(" S{", gcode)
        self.assertIn("start_session", gcode)
        self.assertIn("tool_selected", gcode)
        self.assertIn("end_session", gcode)
        self.assertNotIn("gcode_summary", gcode)
        self.assertNotIn("tool_snapshot", gcode)
        from fourth_combinator.mqtt_sim import M118_MAX_LINE_LEN

        for ln in gcode.splitlines():
            if ln.startswith("M118 P6"):
                self.assertLessEqual(
                    len(ln),
                    M118_MAX_LINE_LEN,
                    msg=f"M118 too long ({len(ln)}): {ln}",
                )
        self.assertTrue(any(e.topic.endswith("/tool") for e in envelopes))

        kinds = [e.kind for e in events]
        self.assertIn("tool_change", kinds)
        self.assertIn("park_rotate", kinds)
        self.assertIn("op_first_layer", kinds)

        log = format_sim_console_log(events, job_name="Widget - 4th axis sim.gcode")
        self.assertIn("[sim] session start", log)
        self.assertIn("[sim] session end", log)

    def test_should_strip_spindle_coolant(self) -> None:
        self.assertTrue(should_strip_line("M3.9 S10000"))
        self.assertTrue(should_strip_line("M7"))
        self.assertTrue(should_strip_line("(Enable Flood)"))
        self.assertFalse(should_strip_line("G1 X1 Y1 Z0"))


class TestM118Format(unittest.TestCase):
    def test_quoted_string_form_with_rrf_escaped_quotes(self) -> None:
        line = m118_publish_line(
            "cam/milo/tool",
            {"event": "change", "event_type": "tool_selected", "tool_number": 3},
        )
        self.assertTrue(line.startswith('M118 P6 S"'), line)
        self.assertIn('T"cam/milo/tool"', line)
        # Must NOT use brace expression form (RRF treats {…} as expressions, not JSON)
        self.assertNotIn(" S{", line)
        self.assertIn('""event""', line)
        self.assertIn('""tool_number"":3', line)

    def test_spaces_in_job_file_stay_inside_quoted_s(self) -> None:
        """Spaces in job_file must not break G-code lexing (root cause of expected '}')."""
        line = m118_publish_line(
            "cam/milo/session",
            {
                "event": "start",
                "event_type": "start_session",
                "session_id": "20260801_114900",
                "device_id": "milo",
                "mode": "sim",
                "job_file": "AB Block - 4th axis sim.gcode",
                "tool_number": 3,
            },
        )
        self.assertTrue(line.startswith('M118 P6 S"'), line)
        self.assertIn("AB Block - 4th axis sim.gcode", line.replace('""', '"'))
        # Entire JSON payload is one S"…" token — no raw space outside quotes before T
        self.assertRegex(line, r'^M118 P6 S".*" T"cam/milo/session"$')

    def test_compacts_nested_payload_under_dsf_limit(self) -> None:
        from fourth_combinator.mqtt_sim import M118_MAX_LINE_LEN

        line = m118_publish_line(
            "cam/milo/session",
            {
                "event": "start",
                "event_type": "start_session",
                "session_id": "20260801_082400",
                "device_id": "milo",
                "mode": "sim",
                "sample_rate_hz": 0.0,
                "ts": 1710000000.123,
                "job_file": "AB Block - 4th axis sim.gcode",
                "tool_number": 3,
                "tool_name": "3 Flute DLC L=18mm very long name",
                "gcode_summary": {
                    "source": "fourth_combinator_sim",
                    "tools_used": [3, 5, 6, 16],
                    "n_tool_changes": 4,
                    "n_ops_first_layer": 12,
                },
            },
        )
        self.assertLessEqual(len(line), M118_MAX_LINE_LEN)
        self.assertNotIn("gcode_summary", line)
        self.assertNotIn("sample_rate_hz", line)
        self.assertIn("start_session", line)

    def test_tool_line_drops_snapshot_and_stays_short(self) -> None:
        from fourth_combinator.mqtt_sim import M118_MAX_LINE_LEN

        line = m118_publish_line(
            "cam/milo/tool",
            {
                "schema_version": 2,
                "event_id": "tevt-20260801_082400-0",
                "event": "start",
                "event_type": "tool_selected",
                "session_id": "20260801_082400",
                "seq": 0,
                "t_s": 1.0,
                "ts": 1710000001.0,
                "time_basis": "recording_monotonic",
                "tool_number": 3,
                "previous_tool": None,
                "tool_name": "Endmill",
                "job_file": "AB Block - 4th axis sim.gcode",
                "rrf_slot": 3,
                "tool_snapshot": {"number": 3, "name": "Endmill"},
            },
        )
        self.assertLessEqual(len(line), M118_MAX_LINE_LEN)
        self.assertNotIn("tool_snapshot", line)
        self.assertNotIn("schema_version", line)
        self.assertNotIn("null", line)
        self.assertIn('""t_s"":1', line)



class TestMqttJsonl(unittest.TestCase):
    def test_session_tool_order(self) -> None:
        root_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(root_tmp.cleanup)
        root = Path(root_tmp.name) / "Part"
        root.mkdir()
        for angle in (0, 90):
            (root / f"Part - A{angle}.gcode").write_text(
                "\n".join(
                    [
                        "T1",
                        "(Begin operation contour: C1 1)",
                        "G0 Z5",
                        "G1 Z-0.2 F100",
                        "G1 X1 Y0",
                        "T2",
                        "(Begin operation contour: C2 1)",
                        "G0 Z5",
                        "G1 Z-0.2 F100",
                        "G1 X2 Y0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
        _, index, _ = load_and_combine(root)
        _, events, envelopes = build_sim_gcode(
            index,
            mqtt_device_id="test-dev",
            mqtt_session_id="20260101_000000",
        )
        self.assertEqual(envelopes[0].topic, "cam/test-dev/status")
        types = [
            env.payload.get("event_type") or env.payload.get("state")
            for env in envelopes
        ]
        self.assertEqual(types[0], "connected")
        self.assertEqual(types[1], "start_session")
        self.assertIn("tool_selected", types)
        self.assertEqual(types[-2], "end_session")
        self.assertEqual(types[-1], "idle")

        rebuilt = build_sim_mqtt_envelopes(
            events,
            job_file="Part - 4th axis sim.gcode",
            device_id="test-dev",
            session_id="20260101_000000",
            stable_ids=True,
        )
        self.assertEqual(rebuilt[1].payload["mode"], "sim")

        out = Path(root_tmp.name) / "out.mqtt.jsonl"
        write_mqtt_jsonl(out, envelopes)
        rows = [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[0]["topic"], "cam/test-dev/status")


class TestSimCli(unittest.TestCase):
    def _write_job(self) -> Path:
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
                    f"(Begin operation adaptive: Adaptive{angle} 1)",
                    "G0 Z10",
                    "G1 Z-1 F200",
                    f"G1 X{angle} Y0",
                    "G1 Z-2 F200",
                    "G1 X0 Y1",
                    "M5.9",
                ]
            )
            (root / f"Bracket - A{angle}.gcode").write_text(body + "\n", encoding="utf-8")
        return root

    def test_sim_embeds_m118_no_jsonl_by_default(self) -> None:
        root = self._write_job()
        buf = StringIO()
        with patch("sys.stdout", buf):
            from fourth_combinator.__main__ import main

            code = main([str(root), "--sim", "--mqtt-device-id", "milo"])
        self.assertEqual(code, 0)
        sim = root / "Bracket - 4th axis sim.gcode"
        mqtt = root / "Bracket - 4th axis sim.mqtt.jsonl"
        self.assertTrue(sim.is_file())
        self.assertFalse(mqtt.exists())
        text = sim.read_text(encoding="utf-8")
        self.assertIn('T"cam/milo/session"', text)
        self.assertIn('T"cam/milo/tool"', text)
        self.assertIn('M118 P6 S"', text)
        self.assertNotIn(" S{", text)
        out = buf.getvalue()
        self.assertIn("[sim] session start", out)
        self.assertIn("M118 P6", out)

    def test_sim_mqtt_jsonl_opt_in(self) -> None:
        root = self._write_job()
        buf = StringIO()
        with patch("sys.stdout", buf):
            from fourth_combinator.__main__ import main

            code = main([str(root), "--sim", "--mqtt-jsonl"])
        self.assertEqual(code, 0)
        self.assertTrue((root / "Bracket - 4th axis sim.mqtt.jsonl").is_file())

    def test_sim_also_writes_both(self) -> None:
        root = self._write_job()
        buf = StringIO()
        with patch("sys.stdout", buf):
            from fourth_combinator.__main__ import main

            code = main([str(root), "--sim-also", "--mqtt-device-id", "milo"])
        self.assertEqual(code, 0)
        self.assertTrue((root / "Bracket - 4th axis.gcode").is_file())
        sim = root / "Bracket - 4th axis sim.gcode"
        self.assertTrue(sim.is_file())
        self.assertIn("M118 P6", sim.read_text(encoding="utf-8"))
        self.assertFalse((root / "Bracket - 4th axis sim.mqtt.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
