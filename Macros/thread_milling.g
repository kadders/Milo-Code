; THREADMILL MACRO for RepRapFirmware
; Parameters: X_pos, Y_pos, Z_start, Z_end, F, D, M, H, W
; Usage: Set global variables before calling this macro
; Example: global.X_pos=0, global.Y_pos=0, global.Z_start=-1, global.Z_end=0.1, global.F=25, global.D=0.65, global.M=1.25, global.H=0.0625, global.W=0.5

; Calculate radius
var radius = (global.M - global.D) / 2
var currentZ = global.Z_start

; Move to start position
G0 G17 G90 X{global.X_pos} Y{global.Y_pos}
G0 Z{global.W}
G0 Z{global.Z_start}
G91

; Arc in
G3 X{radius/2} Y{radius/2} Z{global.H/8} R{radius/2} F{global.F}
G3 X{-radius/2} Y{radius/2} Z{global.H/8} R{radius/2}

; Thread cutting loop
while var.currentZ + global.H <= global.Z_end
    G1 X{-radius} Y{-radius} Z{global.H/4} F{global.F}
    G1 X{radius} Y{-radius} Z{global.H/4}
    G1 X{radius} Y{radius} Z{global.H/4}
    G1 X{-radius} Y{radius} Z{global.H/4}
    set var.currentZ = var.currentZ + global.H

; Arc out
G3 X{-radius/2} Y{-radius/2} Z{global.H/8} R{radius/2}
G3 X{radius/2} Y{-radius/2} Z{global.H/8} R{radius/2}

; Return to safe Z
G0 G90 Z{global.W}

M99