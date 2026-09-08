; CH1LOOP.ASM — CH1 loop-count calibration probe
; Target: IBM PCjr 4860/4861, 8088 real mode, no DOS
; Bridge: Contract-A (Rule 1), position-independent (Rule 4)
; Purpose: measure CH1 ticks per LOOP iteration to test the manual
; 1.1925 MHz CH1 rate (A0h D5=0) against the R~1.145 prior.
; N=1 is the control; N=1000 is the measurement. Only the CX
; immediate differs between the two builds (mov cx,1 for the control).
; Latch idiom: OUT 43h / NOP / NOP / IN — BIOS settle pattern.
; CH1 latch command = 40h at 43h; reads via 41h. Authorized iff NMI
; masked first (out 0A0h,00h), which also holds D5=0 for the 1.1925
; MHz CH1 input selection.
;
; Result layout at O+128:
;   [bp+0] status (0 = armed, 1 = done)
;   [bp+2]/[bp+3] t0 LSB/MSB
;   [bp+4]/[bp+5] t1 LSB/MSB
; BASIC computes dCH1 = t0 - t1, +65536 on wrap.

code segment para
assume cs:code
start:
push cs
pop  ds
push bp
push es
call get_ip
get_ip:
pop  bp
lea  bp,[bp+121]        ; results at O+128

xor  ax,ax
out  0A0h,al            ; mask NMI (D7=0), D5=0 keeps CH1 select
mov  [bp+0],al          ; status = 0

mov  al,40h             ; latch CH1
out  43h,al
nop
nop
in   al,41h             ; CH1 t0 LSB
mov  [bp+2],al
in   al,41h             ; CH1 t0 MSB
mov  [bp+3],al

mov  cx,1000            ; N=1000 for the reference build
spin:
loop spin

mov  al,40h
out  43h,al
nop
nop
in   al,41h             ; CH1 t1 LSB
mov  [bp+4],al
in   al,41h             ; CH1 t1 MSB
mov  [bp+5],al

mov  al,1
mov  [bp+0],al          ; status = 1

in   al,0A0h            ; clear latch
mov  al,80h
out  0A0h,al            ; restore NMI
pop  es
pop  bp
retf
code ends
end start