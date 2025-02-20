# CNC Facing Operation Macro

A comprehensive facing operation macro for RepRap-based CNC machines with an optional DuetWebControl plugin interface.

## Features

- Automated facing operation with configurable parameters
- Optional automatic probing if work offset isn't set
- Configurable roughing and finishing passes
- Integrated coolant control
- DuetWebControl plugin for easy parameter input

## Installation

### Macro Installation
1. Copy `facing_macro.gcode` to your `macros` directory
2. Ensure your machine has proper probing capabilities set up (if using automatic probing)

### DuetWebControl Plugin Installation
1. Create directory: `/plugins/FacingPlugin/`
2. Copy `index.js` and `plugin.json` to the FacingPlugin directory
3. Restart DuetWebControl

## Usage

### Via G-code
Basic usage:
```gcode
M98 P"face_macro" P100 Q100 R0.2 S3
```

### Required Parameters
- `P` - Width of material (X axis) in mm
- `Q` - Depth of material (Y axis) in mm
- `S` - Number of passes to complete

### Optional Parameters
#### Roughing Parameters
- `R` - Depth of cut per pass (Z axis) in mm (default: 0.2mm)
- `F` - Feed rate in mm/min (default: 1500)
- `T` - Spindle speed in RPM (default: 15000)
- `O` - Stock offset in mm (default: 2)
- `C` - Coolant option (0=off, 1=on, default: 0)
- `W` - Step over width in mm (default: 1)

#### Finishing Parameters (Optional)
- `RF` - Finishing depth of cut in mm (default: 0.1)
- `FF` - Finishing feed rate in mm/min (default: 1000)
- `TF` - Finishing spindle speed in RPM (default: 15000)
- `WF` - Finishing step over in mm (defaults to roughing step over)

### Via DuetWebControl Plugin
1. Navigate to the Facing Operation panel in DuetWebControl
2. Input your desired parameters
3. Toggle finishing pass if needed
4. Click "Run Facing Operation"

## Workflow

1. **Setup**
   - Mount your workpiece securely
   - If using probing:
     - Ensure probe is calibrated
     - Position probe over front left corner of workpiece
   - If not using probing:
     - Set your work offset (G54) manually

2. **Parameter Selection**
   - Set material dimensions (width and depth)
   - Choose cutting parameters based on your material and tool
   - Enable finishing pass if needed

3. **Operation**
   - The macro will:
     - Probe the workpiece if no work offset is set
     - Perform roughing passes at specified depth
     - Execute finishing pass if enabled
     - Return to safe position when complete

## Safety Features

- Automatic work offset verification
- Spindle warm-up dwell
- Controlled plunge rates
- Safe retract heights
- Coolant control integration

## Troubleshooting

### Common Issues

1. **"Missing required parameters" Error**
   - Ensure P, Q, and S parameters are specified
   - Check parameter formatting

2. **Probing Failures**
   - Verify probe is correctly positioned
   - Check probe wiring and settings
   - Ensure workpiece is properly secured

3. **Unexpected Cutting Depth**
   - Verify work offset is correctly set
   - Check R parameter value
   - Ensure proper tool length offset

## Support

For issues and feature requests, please open an issue in the repository.

## License

This project is licensed under GPL-3.0-or-later. See LICENSE file for details.
