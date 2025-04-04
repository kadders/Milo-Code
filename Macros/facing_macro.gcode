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
; HF = Finishing depth of cut (mm) - default 0.1
; FF = Finishing feed rate (mm/min) - default 1000
; SF = Finishing spindle speed (RPM) - default 15000
; TF = Finishing step over (mm) - defaults to T if not specified
; Z = Start position (0=corner, 1=center) - default 0

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
set var.do_finishing = {exists(param.HF) ? 1 : 0}
set var.finish_doc = {exists(param.HF) ? param.HF : 0.1}
set var.finish_feed = {exists(param.FF) ? param.FF : 1000}
set var.finish_speed = {exists(param.SF) ? param.SF : 15000}
set var.finish_step = {exists(param.TF) ? param.TF : var.step_over}
set var.wcs_at_center = {exists(param.Z) ? param.Z : 0}

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
if var.do_finishing == 1
  if var.finish_doc <= 0
    abort "Finishing depth must be greater than 0"
  if var.finish_feed <= 0
    abort "Finishing feed rate must be greater than 0"
  if var.finish_speed <= 0
    abort "Finishing spindle speed must be greater than 0"
  if var.finish_step <= 0
    abort "Finishing step over must be greater than 0"

; Calculate starting height based on Z0
set var.starting_height = 0
if var.do_finishing == 1
  set var.starting_height = var.starting_height + var.finish_doc
set var.starting_height = var.starting_height + 5 ; Add 5mm safety margin

; Log parameters to console
M118 P0 S"Facing operation parameters:"
M118 P0 S"Width: " ^ var.width ^ "mm"
M118 P0 S"Depth: " ^ var.depth ^ "mm"
M118 P0 S"Number of passes: " ^ var.num_passes
M118 P0 S"Cut depth per pass: " ^ var.cut_depth ^ "mm"
M118 P0 S"Feed rate: " ^ var.feed_rate ^ "mm/min"
M118 P0 S"Spindle speed: " ^ var.spindle_speed ^ "RPM"
M118 P0 S"Stock offset: " ^ var.stock_offset ^ "mm"
M118 P0 S"Step over: " ^ var.step_over ^ "mm"
M118 P0 S"Coolant: " ^ (var.use_coolant == 1 ? "ON" : "OFF")

if var.do_finishing == 1
  M118 P0 S"Finishing pass: YES"
  M118 P0 S"  Finishing depth: " ^ var.finish_doc ^ "mm"
  M118 P0 S"  Finishing feed rate: " ^ var.finish_feed ^ "mm/min"
  M118 P0 S"  Finishing spindle speed: " ^ var.finish_speed ^ "RPM"
  M118 P0 S"  Finishing step over: " ^ var.finish_step ^ "mm"
else
  M118 P0 S"Finishing pass: NO"
endif

M118 P0 S"WCS at center: " ^ (var.wcs_at_center == 1 ? "YES" : "NO")
M118 P0 S"Starting height: " ^ var.starting_height ^ "mm"



; Check tool and probe tool offset
M291 P"Please confirm the correct tool is installed and ready for facing operation" R"Tool Check" S3
if result == 1
  abort "Operation cancelled by user"

G37 ; Probe tool offset
G4 S1 ; Wait for probing to complete

; Check machine limits
if var.start_x < move.axes[0].min || var.end_x > move.axes[0].max
  abort "X movement out of machine limits"
if var.start_y < move.axes[1].min || var.end_y > move.axes[1].max
  abort "Y movement out of machine limits"
if var.starting_height - (var.num_passes * var.cut_depth) < move.axes[2].min
  abort "Z movement out of machine limits"

G90                   ; Absolute positioning
G21                   ; Set units to millimeters
M3 S{var.spindle_speed} ; Start spindle at specified or default speed
if var.use_coolant == 1
  if exists(global.mosCMID) && global.mosCMID != null
    M42 P{global.mosCMID} S1  ; Turn on mist coolant if pin defined
  else
    M7                        ; Fallback to M7 if no pin defined
G4 P5                        ; Dwell for 5 seconds to let spindle get up to speed
G0 Z10               ; Rapid to safe Z height

; Set starting position based on WCS origin (center or corner)
if var.wcs_at_center == 1
  ; If WCS is at center, calculate the operation boundaries
  set var.start_x = -(var.width / 2) - var.stock_offset
  set var.start_y = -(var.depth / 2) - var.stock_offset
  set var.end_x = (var.width / 2) + var.stock_offset
  set var.end_y = (var.depth / 2) + var.stock_offset
else
  ; If WCS is at corner, calculate the operation boundaries
  set var.start_x = -var.stock_offset
  set var.start_y = -var.stock_offset
  set var.end_x = var.width + var.stock_offset
  set var.end_y = var.depth + var.stock_offset

; Validate movement boundaries
if var.start_x >= var.end_x
  abort "Invalid X movement boundaries"
if var.start_y >= var.end_y
  abort "Invalid Y movement boundaries"

G0 X{var.start_x} Y{var.start_y}  ; Rapid to start position

set var.pass_count = 0
while var.pass_count < var.num_passes
  set var.current_z = var.starting_height - (var.pass_count * var.cut_depth) ; Calculate new Z depth based on starting height and current pass
  set var.current_y = var.start_y            ; Initialize Y position with offset
  
  G0 Z2                      ; Rapid to clearance height
  G0 X{var.start_x} Y{var.current_y}  ; Move to start position
  G1 Z{var.current_z} F50    ; Plunge to cut depth
  
  while var.current_y <= var.end_y
    ; Check for movement errors
    set var.move_error = 0
    G1 X{var.end_x} F{var.feed_rate}  ; Cut across X
    if result != 0
      set var.move_error = 1
      set var.error_message = "Error during X movement"
      break
    
    set var.current_y = var.current_y + var.step_over   ; Increment Y by step over amount
    if var.current_y <= var.end_y
      G1 Y{var.current_y}                               ; Step over in Y
      if result != 0
        set var.move_error = 1
        set var.error_message = "Error during Y movement"
        break
      
      G1 X{var.start_x}                                ; Cut back across X
      if result != 0
        set var.move_error = 1
        set var.error_message = "Error during return X movement"
        break
  
  if var.move_error == 1
    abort var.error_message
  
  set var.pass_count = var.pass_count + 1

; Only do finishing pass if finishing parameters were provided
if var.do_finishing == 1
  M3 S{var.finish_speed}      ; Set finishing spindle speed
  set var.current_z = var.current_z - var.finish_doc  ; Set finishing depth
  set var.current_y = var.start_y                         ; Reset Y position
  
  G0 Z2                      ; Rapid to clearance height
  G0 X{var.start_x} Y{var.current_y}  ; Move to start position
  G1 Z{var.current_z} F50    ; Plunge to finishing depth
  
  while var.current_y <= var.end_y
    ; Check for movement errors
    set var.move_error = 0
    G1 X{var.end_x} F{var.finish_feed}  ; Finishing cut across X
    if result != 0
      set var.move_error = 1
      set var.error_message = "Error during finishing X movement"
      break
    
    set var.current_y = var.current_y + var.finish_step   ; Increment Y by finishing step over amount
    if var.current_y <= var.end_y
      G1 Y{var.current_y}                                 ; Step over in Y
      if result != 0
        set var.move_error = 1
        set var.error_message = "Error during finishing Y movement"
        break
      
      G1 X{var.start_x}                                  ; Cut back across X
      if result != 0
        set var.move_error = 1
        set var.error_message = "Error during finishing return X movement"
        break
  
  if var.move_error == 1
    abort var.error_message

G0 Z10               ; Retract to initial safe height
if var.use_coolant == 1
  M9                ; Turn off all coolant if it was enabled
M5                  ; Stop spindle
G0 Z0               ; Raise spindle to Z0
G0 X{move.axes[0].max/2} Y{move.axes[1].max}  ; Move to X center and Y max
M99                 ; End macro
; Where:
; P100 = 100mm width
; Q100 = 100mm depth
; R1 = 1mm depth of cut
; S3 = 3 passes

