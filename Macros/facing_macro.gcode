; Facing Operation Macro for RepRap Firmware 3.5+
; Parameters:
; W = Width of material (X axis) in mm
; D = Depth of material (Y axis) in mm
; N = Number of passes to complete
; H = Depth of cut per pass (Z axis) in mm - default 0.2
; F = Feed rate (mm/min) - default 1500
; S = Spindle speed (RPM) - default 15000
; O = Stock offset (mm) - default 2
; C = Coolant option (0=off, 1=on) - default 0
; T = Step over width (mm) - default 1
; I = Finishing depth of cut (mm) - default 0.1
; J = Finishing feed rate (mm/min) - default 1000
; K = Finishing spindle speed (RPM) - default 15000
; L = Finishing step over (mm) - defaults to T if not specified
; Z = Start position (0=corner, 1=center) - default 0
; E = Tool diameter (mm) - required

; Machine-specific constants
var MAX_SPINDLE_SPEED = 24000  ; Maximum spindle speed in RPM
var MAX_FEED_RATE = 5000      ; Maximum feed rate in mm/min
var MAX_Z_HEIGHT = 50         ; Maximum Z height in mm
var MIN_Z_HEIGHT = -50        ; Minimum Z height in mm
var SPINDLE_RAMP_TIME = 5     ; Time in seconds for spindle to reach speed

M581 T1 P1

; Declare variables
var width = 0
var depth = 0
var num_passes = 0
var cut_depth = 0.2
var feed_rate = 1500
var spindle_speed = 15000
var stock_offset = 2
var use_coolant = 0
var step_over = 1
var do_finishing = 0
var finish_doc = 0.1
var finish_feed = 1000
var finish_speed = 15000
var finish_step = 1
var wcs_at_center = 0
var tool_diameter = 0
var current_z = 0
var starting_height = 0
var start_x = 0
var start_y = 0
var end_x = 0
var end_y = 0
var pass_count = 0
var current_y = 0
var move_error = 0
var error_message = ""

; Get parameters from command line
set var.width = param.W
set var.depth = param.D
set var.num_passes = param.N
set var.cut_depth = {exists(param.H) ? param.H : 0.2}
set var.feed_rate = {exists(param.F) ? param.F : 1500}
set var.spindle_speed = {exists(param.S) ? param.S : 15000}
set var.stock_offset = {exists(param.O) ? param.O : 2}
set var.use_coolant = {exists(param.C) ? param.C : 0}
set var.step_over = {exists(param.T) ? param.T : 1}
set var.do_finishing = {exists(param.I) ? 1 : 0}
set var.finish_doc = {exists(param.I) ? param.I : 0.1}
set var.finish_feed = {exists(param.J) ? param.J : 1000}
set var.finish_speed = {exists(param.K) ? param.K : 15000}
set var.finish_step = {exists(param.L) ? param.L : var.step_over}
set var.wcs_at_center = {exists(param.Z) ? param.Z : 0}
set var.tool_diameter = param.E

; Debug parameter values
echo { "Parameter validation:" }
echo { "  W: " ^ {exists(param.W) ? "YES" : "NO"} ^ " = " ^ {param.W} }
echo { "  D: " ^ {exists(param.D) ? "YES" : "NO"} ^ " = " ^ {param.D} }
echo { "  N: " ^ {exists(param.N) ? "YES" : "NO"} ^ " = " ^ {param.N} }
echo { "  E: " ^ {exists(param.E) ? "YES" : "NO"} ^ " = " ^ {param.E} }

; Validate parameters
if var.width <= 0
  abort "Width must be greater than 0"
if var.depth <= 0
  abort "Depth must be greater than 0"
if var.num_passes <= 0
  abort "Number of passes must be greater than 0"
if var.cut_depth <= 0
  abort "Cut depth must be greater than 0"
if var.feed_rate <= 0
  abort "Feed rate must be greater than 0"
if var.spindle_speed <= 0
  abort "Spindle speed must be greater than 0"
if var.step_over <= 0
  abort "Step over must be greater than 0"
if var.tool_diameter <= 0
  abort "Tool diameter must be greater than 0"
if var.do_finishing == 1
  if var.finish_doc <= 0
    abort "Finishing depth must be greater than 0"
  if var.finish_feed <= 0
    abort "Finishing feed rate must be greater than 0"
  if var.finish_speed <= 0
    abort "Finishing spindle speed must be greater than 0"
  if var.finish_step <= 0
    abort "Finishing step over must be greater than 0"

; Validate parameters with machine limits
if var.spindle_speed > var.MAX_SPINDLE_SPEED
  abort "Spindle speed exceeds maximum allowed speed of " ^ var.MAX_SPINDLE_SPEED ^ " RPM"
if var.feed_rate > var.MAX_FEED_RATE
  abort "Feed rate exceeds maximum allowed rate of " ^ var.MAX_FEED_RATE ^ " mm/min"
if var.finish_feed > var.MAX_FEED_RATE
  abort "Finishing feed rate exceeds maximum allowed rate of " ^ var.MAX_FEED_RATE ^ " mm/min"

; Calculate and validate Z heights
set var.starting_height = 0
if var.do_finishing == 1
  set var.starting_height = var.starting_height + var.finish_doc
set var.starting_height = var.starting_height + 5 ; Add 5mm safety margin

if var.starting_height > var.MAX_Z_HEIGHT
  abort "Starting Z height exceeds maximum allowed height of " ^ var.MAX_Z_HEIGHT ^ " mm"
if (var.starting_height - (var.num_passes * var.cut_depth)) < var.MIN_Z_HEIGHT
  abort "Final Z depth exceeds minimum allowed height of " ^ var.MIN_Z_HEIGHT ^ " mm"

; Log parameters to console
echo { "Facing operation parameters:" }
echo { "Width: " ^ {var.width} ^ "mm" }
echo { "Depth: " ^ {var.depth} ^ "mm" }
echo { "Number of passes: " ^ {var.num_passes} }
echo { "Cut depth per pass: " ^ {var.cut_depth} ^ "mm" }
echo { "Feed rate: " ^ {var.feed_rate} ^ "mm/min" }
echo { "Spindle speed: " ^ {var.spindle_speed} ^ "RPM" }
echo { "Stock offset: " ^ {var.stock_offset} ^ "mm" }
echo { "Step over: " ^ {var.step_over} ^ "mm" }
echo { "Coolant: " ^ {var.use_coolant == 1 ? "ON" : "OFF"} }
echo { "Tool diameter: " ^ {var.tool_diameter} ^ "mm" }

if var.do_finishing == 1
  echo { "Finishing pass: YES" }
  echo { "  Finishing depth: " ^ {var.finish_doc} ^ "mm" }
  echo { "  Finishing feed rate: " ^ {var.finish_feed} ^ "mm/min" }
  echo { "  Finishing spindle speed: " ^ {var.finish_speed} ^ "RPM" }
  echo { "  Finishing step over: " ^ {var.finish_step} ^ "mm" }
else
  echo { "Finishing pass: NO" }

echo { "WCS at center: " ^ {var.wcs_at_center == 1 ? "YES" : "NO"} }
echo { "Starting height: " ^ {var.starting_height} ^ "mm" }

; Set tool diameter in M4000 command
M4000 P1 R{var.tool_diameter/2} S"Facing Tool"
echo { "Tool set to diameter: " ^ {var.tool_diameter} ^ "mm (radius: " ^ {var.tool_diameter/2} ^ "mm)" }

; Set starting position based on WCS origin (center or corner)
if var.wcs_at_center == 1
  ; If WCS is at center, calculate the operation boundaries
  set var.start_x = -{(var.width / 2) + var.stock_offset}
  set var.start_y = -{(var.depth / 2) + var.stock_offset}
  set var.end_x = {(var.width / 2) + var.stock_offset}
  set var.end_y = {(var.depth / 2) + var.stock_offset}
else
  ; If WCS is at corner, calculate the operation boundaries
  set var.start_x = -{var.stock_offset}
  set var.start_y = -{var.stock_offset}
  set var.end_x = {var.width + var.stock_offset}
  set var.end_y = {var.depth + var.stock_offset}

; Log calculated start position
echo { "Calculated start position:" }
echo { "  Start X: " ^ {var.start_x} ^ "mm" }
echo { "  Start Y: " ^ {var.start_y} ^ "mm" }
echo { "  End X: " ^ {var.end_x} ^ "mm" }
echo { "  End Y: " ^ {var.end_y} ^ "mm" }

; Check machine limits
; Convert WCS coordinates to machine coordinates for limit checking
var machine_start_x = {var.wcs_at_center == 1 ? var.start_x + move.axes[0].min : var.start_x}
var machine_end_x = {var.wcs_at_center == 1 ? var.end_x + move.axes[0].min : var.end_x}
var machine_start_y = {var.wcs_at_center == 1 ? var.start_y + move.axes[1].min : var.start_y}
var machine_end_y = {var.wcs_at_center == 1 ? var.end_y + move.axes[1].min : var.end_y}

if machine_start_x < move.axes[0].min || machine_end_x > move.axes[0].max
  abort "X movement out of machine limits (WCS adjusted)"
if machine_start_y < move.axes[1].min || machine_end_y > move.axes[1].max
  abort "Y movement out of machine limits (WCS adjusted)"
if var.starting_height - (var.num_passes * var.cut_depth) < move.axes[2].min
  abort "Z movement out of machine limits"

; Check if all axes are homed and home if needed
if !move.axes[0].homed || !move.axes[1].homed || !move.axes[2].homed
  echo "Some axes are not homed. Homing all axes..."
  M291 P"Some axes need to be homed. The machine will now home all axes." R"Home Required" S3
  G28 ; Home all axes
  echo "Homing complete. Continuing with facing operation."

; Check tool and probe tool offset
M291 P"Please confirm the correct tool is installed and ready for facing operation" R"Tool Check" S3
if result == 1
  abort "Operation cancelled by user"

T1 ; Select tool 1
; G37 ; Probe tool offset
; G4 S1 ; Wait for probing to complete

G90                   ; Absolute positioning
G21                   ; Set units to millimeters
G94                   ; Set feed rate units to mm/min

; Start spindle with proper M3 command and ramp-up
M3.9 S{var.spindle_speed} ; Start spindle at specified speed
G4 P{var.SPINDLE_RAMP_TIME} ; Wait for spindle to reach speed

if var.use_coolant == 1
  if exists(global.mosCMID) && global.mosCMID != null
    M42 P{global.mosCMID} S1  ; Turn on mist coolant if pin defined
  else
    M7                        ; Fallback to M7 if no pin defined

G0 Z5                ; Rapid to safe Z height

; Validate movement boundaries
if var.start_x >= var.end_x
  abort "Invalid X movement boundaries"
if var.start_y >= var.end_y
  abort "Invalid Y movement boundaries"

G0 X{var.start_x} Y{var.start_y}  ; Rapid to start position

; Main cutting loop
set var.pass_count = 0
while var.pass_count < var.num_passes
  set var.current_z = {var.starting_height - (var.pass_count * var.cut_depth)}
  set var.current_y = {var.start_y}
  
  ; Calculate pass number for display
  set var.display_pass = {var.pass_count + 1}
  echo "Starting pass " var.display_pass " of " var.num_passes " at Z=" var.current_z "mm"
  
  G0 Z2                      ; Rapid to clearance height
  G0 X{var.start_x} Y{var.current_y}  ; Move to start position
  G1 Z{var.current_z} F50    ; Plunge to cut depth
  
  ; Main cutting loop - improved implementation
  set var.current_y = {var.start_y}
  while var.current_y <= var.end_y
    ; Cut across X axis
    G1 X{var.end_x} Y{var.current_y} F{var.feed_rate}
    
    ; Step over in Y and return cut in opposite direction
    set var.current_y = {var.current_y + var.step_over}
    if var.current_y <= var.end_y
      G1 X{var.start_x} Y{var.current_y} F{var.feed_rate}
      set var.current_y = {var.current_y + var.step_over}
    M400 ; Wait for moves to finish
  
  ; Increment pass counter
  set var.pass_count = {var.pass_count + 1}
  echo "Completed pass " var.pass_count " of " var.num_passes

; Only do finishing pass if finishing parameters were provided
if var.do_finishing == 1
  echo "Starting finishing pass at Z=" var.current_z - var.finish_doc "mm"
  
  ; Change spindle speed for finishing pass
  M5.9                ; Stop spindle with proper deceleration
  G4 P{var.SPINDLE_RAMP_TIME} ; Wait for spindle to stop
  M3.9 S{var.finish_speed} ; Start spindle at finishing speed
  G4 P{var.SPINDLE_RAMP_TIME} ; Wait for spindle to reach speed
  
  set var.current_z = {var.current_z - var.finish_doc}  ; Set finishing depth
  set var.current_y = {var.start_y}                     ; Reset Y position
  
  G0 Z2                      ; Rapid to clearance height
  G0 X{var.start_x} Y{var.current_y}  ; Move to start position
  G1 Z{var.current_z} F50    ; Plunge to finishing depth
  
  ; Finishing pass - improved implementation
  while var.current_y <= var.end_y
    ; Move across X axis with Y position
    G1 X{var.end_x} Y{var.current_y} F{var.finish_feed}
    
    ; Step over in Y and return cut in opposite direction
    set var.current_y = {var.current_y + var.finish_step}
    if var.current_y <= var.end_y
      G1 X{var.start_x} Y{var.current_y} F{var.finish_feed}
      set var.current_y = {var.current_y + var.finish_step}
    M400 ; Wait for moves to finish
  
  echo "Completed finishing pass"

G0 Z10               ; Retract to initial safe height
if var.use_coolant == 1
  M9                ; Turn off all coolant if it was enabled
M5.9                ; Stop spindle with proper deceleration
G27                 ; Park the machine properly
M99                 ; End macro
; Where:
; P100 = 100mm width
; Q100 = 100mm depth
; R1 = 1mm depth of cut
; S3 = 3 passes

