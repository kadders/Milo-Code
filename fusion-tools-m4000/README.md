# Fusion `.tools` → NeXT `M4000`

Small Python 3 utility that reads an Autodesk Fusion 360 exported tool library (`.tools` = ZIP containing `tools.json`) and writes **`M4000`** lines compatible with NeXT `M4000.g` / `nxt-user-tools.g` (RepRapFirmware).

## Requirements

- Python 3.10+ (stdlib only: no pip installs).

## Usage

Run from this directory so Python resolves the package:

```bash
cd fusion-tools-m4000

python3 -m fusion_tools_m4000 "/path/to/MyLibrary.tools"

# Default output file (cwd): tool_load.g
# Useful on Duet: upload then M98 P"tool_load.g" (path depends on your layout).

python3 -m fusion_tools_m4000 "/path/to/MyLibrary.tools" -o /tmp/out.g

python3 -m fusion_tools_m4000 "/path/to/MyLibrary.tools" --output -   # stdout

python3 -m fusion_tools_m4000 "/path/to/MyLibrary.tools" \
  --wrap-load-depth \
  --enrich-description
```

### Flags

| Flag | Meaning |
|------|---------|
| `-o` / `--output` | Output path; default **`tool_load.g`**. Use **`--output -`** for stdout. |
| `--wrap-load-depth` | Wrap with NeXT `nxtUserToolsLoadDepth` block (matches DWC persistence behaviour). |
| `--enrich-description` | Append ` F=… L=… CR=…` to `S"..."` when `geometry.NOF` / `LCF` / `RE` exist. |
| `--bull-nose-radius corner` \| `diameter` | **corner**: use `geometry.RE` when &gt; 0 else `DC/2`; **diameter**: always `DC/2`. |

### Radius mapping

- Most types (**flat**, **ball**, **drill**, **chamfer**, **probe**, etc.): **`R = geometry.DC / 2`**.
- **Bull nose end mill**: default **`R = geometry.RE`** when positive; otherwise **`DC/2`**.

Fusion exports do **not** include NeXT probe deflection **`X`/`Y`**; add those manually to probe lines if needed (see MillenniumOS `GCODE.md`, section `M4000`).

### Not emitted

- **`G10 L1`** tool offsets — machine/setup specific (DWC “Save to board” derives those from the live object model).

## Tests

```bash
cd fusion-tools-m4000
python3 -m unittest discover -v tests
```

The golden test looks for `../Milo-Parts/Tooling/Fusion/Core Milo Tooling.tools` relative to the **Milo-Code** repo root (sibling checkout). If that file is missing, the test is skipped.
