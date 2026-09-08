; LOOPCOUNT.ASM — CH0 loop-count calibration probe
; Target: IBM PCjr 4860/4861, 8088 real mode, no DOS
; Bridge: Contract-A (Rule 1), position-independent (Rule 4)
; Purpose: measure CH0 ticks per LOOP iteration to pin CH0's rate.
; N=1 is the control; N=1000 is the measurement. Only the CX
; immediate differs between the two builds.
; Latch idiom: OUT 43h / NOP / NOP / IN — BIOS settle pattern.

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
    out  0A0h,al            ; mask NMI (D7=0), D5=0 keeps CH0 select
    mov  [bp+0],al          ; status = 0

    mov  al,0               ; latch CH0
    out  43h,al
    nop
    nop
    in   al,40h             ; CH0 t0 LSB
    mov  [bp+2],al
    in   al,40h             ; CH0 t0 MSB
    mov  [bp+3],al

    mov  cx,1000            ; N=1000 for the reference build
spin:
    loop spin

    mov  al,0
    out  43h,al
    nop
    nop
    in   al,40h             ; CH0 t1 LSB
    mov  [bp+4],al
    in   al,40h             ; CH0 t1 MSB
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
