# 4th-combinator

Combine per-orientation MillenniumOS/NeXT Fusion G-code exports into a single A-axis job file.

## Requirements

- Python 3.10+ (stdlib only: no pip installs)
- Optional for `--mqtt-publish`: `paho-mqtt` (fail-open if missing)

## Job directory layout

Each job lives in its own directory. Orientation files are recognized by the
` - A#` marker before the extension (extra name parts like Op1/Op2 are fine):

```
/path/to/jobs/Bracket/
  Bracket - A0.gcode
  Bracket - Op1 - A45.gcode
  Bracket - A90.gcode
  Bracket - A135.5 - finish.gcode
  Bracket - A270.gcode
```

The combiner uses the **directory name** as the model (e.g. output
`Bracket - 4th axis.gcode`). No `--model` flag is required.

**Orientations are not limited to 0/90/180/270.** Any angle present in a
filename as ` - A{angle}` is used — integers or decimals (e.g. `A15`, `A45`,
`A135.5`). Discovery sorts whatever set it finds. Use `--orientations` when
you need to require a specific custom set (missing angles then error).

## Usage

Run from this directory so Python resolves the package:

```bash
cd 4th-combinator

python3 -m fourth_combinator /path/to/jobs/Bracket

python3 -m fourth_combinator /path/to/jobs/Bracket --dry-run

# Require a non-cardinal orientation set
python3 -m fourth_combinator /path/to/jobs/Bracket --orientations 0,45,120 --dry-run

# T2 then T6 deferred (list order); both keep natural order on A0
python3 -m fourth_combinator /path/to/jobs/Bracket \
  --final-tool T2,T6 --final-exclude A0 --dry-run

python3 -m fourth_combinator /path/to/jobs/Bracket -o /tmp/out.gcode --verbose

# Datum-in-spindle first-layer sim (MQTT events embedded for Jarvis)
python3 -m fourth_combinator /path/to/jobs/Bracket --sim --mqtt-device-id milo

# Cutting file + sim
python3 -m fourth_combinator /path/to/jobs/Bracket --sim-also --mqtt-device-id milo
```

### Flags

**`job_dir`** (positional, required)

Directory containing orientation files matching `* - A#*.{gcode|nc|g}`.
The directory name becomes the model name for default outputs.

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket
```

**`-o` / `--output`** (optional)

Output path for the cutting file (or, with `--sim` alone, the sim path).

- Default cutting file: `{job_dir}/{model} - 4th axis.gcode`
- Default sim file (when `--sim` / `--sim-also`): `{job_dir}/{model} - 4th axis sim.gcode`
- With `--sim` alone, `-o` overrides the sim path; with `--sim-also`, `-o` still
  sets the cutting path and the sim uses the default name beside the job dir.

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket -o /tmp/Bracket-combined.gcode
python3 -m fourth_combinator /path/to/jobs/Bracket --sim -o /tmp/Bracket-sim.gcode
```

**`--dry-run`** (flag, default: off)

Print the planned tool + orientation order (and detected toolpaths) without
writing any output file.

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --dry-run
```

**`--orientations`** (optional, default: none / discover all)

Comma-separated angles that **must** exist in the job directory. Accepts
`0,90` or `A0,A45,A120`. Does not limit discovery to cardinals — it only
errors if a listed angle is missing. Omit to use every ` - A#` file found.

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --orientations 0,45,120
```

**`--final-tool`** (optional, default: none)

Tool(s) deferred to last passes, comma-separated in deferred order
(e.g. `T2,T6` or `2,6`). Those tools run after all other tools, in the
order listed.

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --final-tool T2,T6 --dry-run
```

**`--final-exclude`** (optional, default: none; requires `--final-tool`)

Orientations that keep final tools in **natural** file order (not deferred).
Comma-separated angles, with or without an `A` prefix (e.g. `A0` or `0`).

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket \
  --final-tool T2,T6 --final-exclude A0 --dry-run
```

**`--strict`** (flag, default: off)

When a reference tool is missing at an orientation, error instead of warning
and skipping that step.

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --strict
```

**`--verbose`** (flag, default: off)

Log when spindle bookends are scrubbed between hops / ops.

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --verbose
```

**`--sim`** (flag, default: off)

Write a datum-safe first-layer sim gcode **instead of** the cutting file
(mutually exclusive with `--sim-also`). Also writes MQTT JSONL beside the sim.

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --sim
```

**`--sim-also`** (flag, default: off)

Write **both** the cutting file and the sim gcode
(mutually exclusive with `--sim`).

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --sim-also
```

**`--sim-layer-eps`** (optional, default: `0.05`)

First-layer Z tolerance in mm when building the sim path (how close a Z must
be to the first cutting depth to count as the same layer).

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --sim --sim-layer-eps 0.1
```

**`--mqtt-device-id`** (optional)

Device segment for embedded `cam/{device}/…` MQTT topics. Defaults to
`TAP_MQTT_DEVICE_ID` or the hostname. Use the same id Jarvis already knows
(e.g. `milo`).

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --sim --mqtt-device-id milo
```

**`--no-mqtt-embed`** (flag, default: off)

Skip embedding `M118 P6` publishes in the sim gcode (not recommended for
mill → Jarvis runs).

**`--mqtt-jsonl`** (flag, default: off)

Also write a `{sim}.mqtt.jsonl` sidecar for offline inspection. The mill path
does **not** need this — events ride in the gcode via `M118 P6`.

**`--mqtt-publish`** (flag, default: off)

Also live-publish the same session/tool envelopes from this host when
`TAP_MQTT_HOST` is set (fail-open). Useful for dry-testing Jarvis without
running the mill; on-machine publishes still come from embedded `M118 P6`.

```bash
python3 -m fourth_combinator /path/to/jobs/Bracket --sim --mqtt-device-id milo
```

## Simulation mode (datum in spindle)

`--sim` / `--sim-also` emit a **machine-runnable air-trace** of the combined job, meant to be run with a **datum (or probe) in the spindle — not a cutter**.

**Default:** `{model} - 4th axis sim.gcode` (MQTT events are **inside** that file).

| Behavior | Detail |
|----------|--------|
| First layer only | For each Fusion `(Begin operation …)`, keep XY of the **first cutting Z depth**, then fly that path at **Z0** |
| Z plane | Every remaining Z word is rewritten to **Z0** — no plunge below zero |
| Spindle | All `M3`/`M4`/`M5` (+ `.9`), `M7000`/`M7001`, and spindle comments stripped |
| Coolant / air | Leading `M9` forces mist/flood/air off; body enables (`M7`/`M8`, MOS mist/flood/air comments) are stripped |
| Tool change | No real `Tn` / `M4001` — `M291` popup + RRF `echo` only; confirm before continuing |
| Tool table | `M4000` lines are **commented out** (`; M4000 …`) so sim does not reload tooling |
| A sides | Same park + `G0 A#` sequence as the cutting combiner (any discovered angle) |
| Console | `[sim] …` event log (session, tool changes, first-layer ops, park+rotate) |
| Jarvis MQTT | Embedded compact `M118 P6 S"{""…""}" T"cam/{device}/…"` (RRF **quoted** JSON with `""` escapes — not `S{…}` expression braces). Flat payloads, **≤240 chars/line**. Nested summary fields omitted from G-code; use `--mqtt-jsonl` for the full payload. |

### Mill → Jarvis (recommended)

1. Enable MQTT **publish** on the Duet (RRF 3.6+), e.g. in `config.g` / `dsf-config.g`:

```gcode
M586.4 C"milo"
M586 P4 H"mqtt.jarvis.lan" R1883 S1
```

Do **not** subscribe Duet to `cam/#` or `tap/#` (subscribe only shows DWC text; it does not run G-code).

2. Build the sim with the device id Jarvis expects:

```bash
python3 -m fourth_combinator /path/to/job --sim --mqtt-device-id milo
```

3. Ensure Jarvis `tap-collector` subscribes to `cam/#` (e.g. `TAP_COLLECTOR_MQTT_TOPICS=tap/#,duet/#,cam/#`).

4. Run `{model} - 4th axis sim.gcode` on the mill (datum in spindle). As the job hits tool-change popups, RRF publishes compact flat JSON inside a quoted `S"…"` string (RRF `{…}` is an expression, **not** JSON — using braces caused `M118: expected '}'`):

- `cam/{device}/status` — connected / idle
- `cam/{device}/session` — `start_session` / `end_session` (`mode: "sim"`)
- `cam/{device}/tool` — `tool_selected` at each simulated tool change

Regenerate the sim if you still have older `S{…}` lines or oversized nested JSON.

### MQTT environment variables

| Variable | Role |
|----------|------|
| `TAP_MQTT_DEVICE_ID` | Default `--mqtt-device-id` for embedded topics |
| `TAP_MQTT_HOST` | Broker hostname (only needed for optional `--mqtt-publish` from this host) |
| `TAP_MQTT_PORT` | Broker port |
| `TAP_MQTT_USERNAME` | Optional username |
| `TAP_MQTT_PASSWORD` | Optional password |
| `TAP_MQTT_CLIENT_ID` | MQTT client id for host-side publish |

**Warning:** Install a datum (or similar non-cutting tip) and clear the work envelope before running the sim file. The file never starts the spindle or coolant, but it still moves XY and indexes A. Duet MQTT must be configured for Jarvis to see the embedded `M118 P6` events.

## What it does

1. Discovers all `* - A#*.{gcode|nc|g}` files in the job directory (Op tags and other name parts allowed). Angles may be any numeric value found after ` - A`.
2. Uses the job **directory name** as the model. Builds the tool list as a **union** across all A# files: appearance order from the **reference orientation** first (**A0** if present, otherwise the lowest discovered angle), then any tools only present on later orientations (e.g. T16 only on A180), never numeric T-sort.
3. Splits each file on `T{n}` tool-select lines.
4. For each tool in that union, runs it at every orientation where it exists (in discovered angle order): `T1 @ A0 → T1 @ A45 → …`. Skipping an orientation when that tool is not used there is normal (no missing-tool error). Optional `--final-tool T2,T6` defers those tools to last passes **in list order**; `--final-exclude A0` keeps them in natural order on those orientations (e.g. T2 first on A0), then finishes the remaining orientations for each final tool at the end.
5. Between orientation changes, parks with a **G53** safe retract (spindle left running — no `G27`/`M5.9`), waits (`M400`), then rotates A to that step’s angle (`G0 A45`, `G0 A135.5`, etc.).
6. Scrubs redundant same-tool spindle stop/restart bridges (MOS `M7001`/`G27`/`M5.9` and `M7000`/`M3.9`/`M7`) between Fusion ops, and hop bookends when the same tool continues at a new orientation.
7. Uses the **reference** tool block for tool changes when available; otherwise the first orientation that introduces that tool.

## Assumptions

- Post output targets MOS/NeXT Fusion (`M3.9`/`M5.9`, `M4001`, `G54`).
- Each A# file may be a different Op with a different tool subset; shared tools are common. Tool order is not derived from equal block counts across files.
- Filenames contain ` - A{degrees}` before the extension (e.g. `… - A0.gcode`, `… - A45.gcode`); other tokens like Op1/Op2 are allowed. Cardinal angles are common but not required.

## Tests

```bash
cd 4th-combinator
python3 -m unittest discover -v tests
```

## Example

**Before** (separate files per orientation, each with T1 then T2):

```
Bracket - A0.gcode     Bracket - A45.gcode
  T1 → cut @ 0°          T1 → cut @ 45°
  T2 → cut @ 0°          T2 → cut @ 45°
  …                      …
```

**After** (`Bracket - 4th axis.gcode`):

```
T1 @ A0  →  park + G0 A45  →  T1 @ A45  →  park + G0 A120  →  …
→  T2 @ A0 (tool change from A0 reference)  →  …
```
