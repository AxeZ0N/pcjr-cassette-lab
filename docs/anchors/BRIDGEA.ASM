; BRIDGEA.ASM — pure Contract-A bridge positive-control lint fixture
; NOT a hardware anchor. Emission gate passed (stage 6, shape bridge,
; result 128); stage gate not run.
;
; Proves: entry 0E 1F 55 06, selfloc disp 79 (R-7), latch-read,
; nmi-mask, nmi-restore, epilogue 07 5D CB. Writes marker 42h at O+128.

option casemap:none
option segment:use16

code segment
    assume cs:code
    org 0

start:
    push cs
    pop  ds
    push bp
    push es
    call get_ip
get_ip:
    pop  bp
    lea  bp, [bp + 128 - 7]   ; BP = O + 128
    mov  byte ptr [bp], 42h   ; marker at result offset
    mov  al, 00h              ; mask NMI
    out  0A0h, al
    in   al, 0A0h             ; clear latch
    mov  al, 80h              ; restore NMI
    out  0A0h, al
    pop  es
    pop  bp
    retf

code ends
end start
