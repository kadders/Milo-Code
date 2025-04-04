# Facing Macro Plugin for DuetWebControl

This plugin provides a user interface for running the facing operation macro on your CNC machine. It integrates with DuetWebControl 3.5.x+ to provide a convenient way to execute facing operations with customizable parameters.

## Features

- User-friendly interface for setting facing operation parameters
- Support for both roughing and finishing passes
- Configurable parameters including:
  - Width and depth of material
  - Number of passes
  - Depth of cut
  - Feed rate
  - Spindle speed
  - Stock offset
  - Step over width
  - Coolant control
  - Finishing pass options

## Installation

1. Clone this repository or download the plugin files
2. Copy the `facing_macro` folder to your DuetWebControl plugins directory
3. Restart DuetWebControl

## Usage

1. Navigate to the "Facing Macro" section in the DuetWebControl interface
2. Fill in the required parameters (width, depth, and number of passes)
3. Adjust optional parameters as needed
4. Click "Run Facing Operation" to execute the macro

## Requirements

- DuetWebControl 3.5.x or higher
- The facing_macro.gcode file must be present in your machine's macro directory

## License

This plugin is licensed under the GPL-3.0-or-later license. 