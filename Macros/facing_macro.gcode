; Facing Operation Macro for RepRap Firmware
; Roughing Parameters:
; P = Width of material (X axis) in mm
; Q = Depth of material (Y axis) in mm
; R = Depth of cut per pass (Z axis) in mm - default 0.2
; S = Number of passes to complete
; F = Feed rate (mm/min) - default 1500
; T = Spindle speed (RPM) - default 15000
; O = Stock offset (mm) - default 2
; C = Coolant option (0=off, 1=on) - default 0
; W = Step over width (mm) - default 1
; Finishing Parameters (Optional):
; RF = Finishing depth of cut (mm) - default 0.1
; FF = Finishing feed rate (mm/min) - default 1000
; TF = Finishing spindle speed (RPM) - default 15000
; WF = Finishing step over (mm) - defaults to W if not specified


M581 P"face_macro"
  var current_z = #54.Z ; Use G54 work coordinate system Z as starting point
  
  ; Check if WCS0 is set by checking if G54 Z is defined
  if !exists(#54.Z)
    M291 P"Please position the probe over the front left corner of your workpiece" S2 ; Notify operator
    G4 S2 ; Give operator time to read message
    G6508 ; Call corner probe directly
    G4 S1 ; Wait for corner probe to complete
    G6510 ; Call single surface probe directly
    G4 S1 ; Wait for surface probe to complete
    set var.current_z = #54.Z ; Get the newly probed Z height
  
  var feed_rate = exists(param.F) ? param.F : 1500  ; Feed rate - default 1500mm/min if not specified
  var spindle_speed = exists(param.T) ? param.T : 15000  ; Default spindle speed 15000 RPM unless specified
  var stock_offset = exists(param.O) ? param.O : 2  ; Stock offset - default 2mm if not specified
  var use_coolant = exists(param.C) ? param.C : 0  ; Coolant option - 0=off, 1=on
  var step_over = exists(param.W) ? param.W : 1  ; Step over width - default 1mm if not specified
  var cut_depth = exists(param.R) ? param.R : 0.2  ; Cut depth - default 0.2mm if not specified
  
  ; Only set finishing parameters if RF is specified (indicating finishing is enabled)
  var do_finishing = exists(param.RF)
  if var.do_finishing
    var finish_doc = exists(param.RF) ? param.RF : 0.1  ; Use specified finishing depth of cut or default to 0.1mm
    var finish_feed = exists(param.FF) ? param.FF : 1000  ; Finishing feed rate - default 1000mm/min
    var finish_speed = exists(param.TF) ? param.TF : 15000  ; Finishing spindle speed - default 15000 RPM
    var finish_step = exists(param.WF) ? param.WF : var.step_over  ; Finishing step over - defaults to regular step over
  
  if !exists(param.P) || !exists(param.Q) || !exists(param.S)
    M291 P"Missing required parameters. Usage: M98 P'face_macro' P{width} Q{depth} R{doc} S{passes} [F{feed_rate}] [T{spindle_speed}] [O{stock_offset}] [C{coolant}] [W{step_over}]" S2
    M99
  
  G90                   ; Absolute positioning
  G21                   ; Set units to millimeters
  M3 S{var.spindle_speed} ; Start spindle at specified or default speed
  if var.use_coolant == 1 || global.mosFeatCoolantControl
    if global.mosCMID != null
      M42 P{global.mosCMID} S1  ; Turn on mist coolant if enabled and pin defined
    else
      M7                        ; Fallback to M7 if no pin defined
  G4 P5                        ; Dwell for 5 seconds to let spindle get up to speed
  G0 Z10               ; Rapid to safe Z height
  G0 X+{var.stock_offset} Y-{var.stock_offset}  ; Rapid to start position with offset from front left
  
  while iterations < param.S
    set var.current_z = var.current_z - var.cut_depth  ; Calculate new Z depth
    var current_y = -var.stock_offset            ; Initialize Y position with offset
    
    G0 Z2                      ; Rapid to clearance height
    G0 X-{var.stock_offset} Y{var.current_y}  ; Move to start position with offset
    G1 Z{var.current_z} F50    ; Plunge to cut depth
    
    while var.current_y <= param.Q + var.stock_offset
      G1 X{param.P + var.stock_offset} F{var.feed_rate}  ; Cut across X with offset
      set var.current_y = var.current_y + var.step_over   ; Increment Y by step over amount
      if var.current_y <= param.Q + var.stock_offset
        G1 Y{var.current_y}                               ; Step over in Y
        G1 X-{var.stock_offset}                          ; Cut back across X
  
  ; Only do finishing pass if finishing parameters were provided
  if var.do_finishing
    M3 S{var.finish_speed}      ; Set finishing spindle speed
    set var.current_z = var.current_z - var.finish_doc  ; Set finishing depth
    var current_y = -var.stock_offset                   ; Reset Y position
    
    G0 Z2                      ; Rapid to clearance height
    G0 X-{var.stock_offset} Y{var.current_y}  ; Move to start position
    G1 Z{var.current_z} F50    ; Plunge to finishing depth
    
    while var.current_y <= param.Q + var.stock_offset
      G1 X{param.P + var.stock_offset} F{var.finish_feed}  ; Finishing cut across X
      set var.current_y = var.current_y + var.finish_step   ; Increment Y by finishing step over amount
      if var.current_y <= param.Q + var.stock_offset
        G1 Y{var.current_y}                                 ; Step over in Y
        G1 X-{var.stock_offset}                            ; Cut back across X
  
  G0 Z10               ; Retract to safe height
  G0 X0 Y0            ; Return to part origin at front left
  M5                  ; Stop spindle
  if var.use_coolant == 1
    M9                ; Turn off all coolant if it was enabled
  M99                 ; End macro
; M98 P"face_macro" P100 Q100 R1 S3
; Where:
; P100 = 100mm width
; Q100 = 100mm depth
; R1 = 1mm depth of cut
; S3 = 3 passes

