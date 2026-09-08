option casemap:none
option segment:use16

; NMIPEEK.ASM — masked INT 02h vector read (ground truth anchor)
; Target: IBM PCjr 4860/4861, 8088 real mode, Cartridge BASIC bridge
; Origin: org 0; result region at offset 128 from code base
;
; Hardware pass (2026-08-31): returned ok, m1=42,
; saved=3960:61440 (0F78:F000 stock KBDNMI vector), keyboard alive.
;
; Bridge contract (Rule 1 + ES extension): PUSH CS / POP DS, PUSH BP,
; PUSH ES, self-locate into DI, stores via DI, POP ES / POP BP / RETF.
; ES preservation is mandatory — clobbering ES corrupts BASIC on return
; (empirical, 2026-08-31, es_clobber_bridge_contract).
;
; DATA block byte-matches this source via `jr build` (stage 1, result 128).

code segment
    assume cs:code
    org 0

start:
    push cs                     ; 0E    bridge entry: DS = CS
    pop  ds                     ; 1F
    push bp                     ; 55    preserve BASIC BP
    call get_ip                 ; E8 0000
get_ip:
    pop  di                     ; 5F    DI = entry offset + 6
    lea  di, [di + 128 - 6]     ; 8D 7D 7A   DI = entry + 128 (result base)
    push es                     ; 06    preserve BASIC ES (mandatory)
    mov  byte ptr [di], 42      ; C6 05 2A   self-location marker -> O+128
    mov  al, 0                  ; B0 00   mask NMI (A0h D7=0)
    out  0A0h, al               ; E6 A0
    xor  ax, ax                 ; 33 C0   ES = 0000 (IVT segment)
    mov  es, ax                 ; 8E C0
    mov  ax, es:[0008h]         ; 26 A1 0800   read INT 02h offset -> O+130
    mov  [di + 2], ax           ; 89 45 02
    mov  ax, es:[000Ah]         ; 26 A1 0A00   read INT 02h segment -> O+132
    mov  [di + 4], ax           ; 89 45 04
    in   al, 0A0h               ; E4 A0   clear keyboard latch
    mov  al, 80h                ; B0 80   restore NMI (A0h D7=1)
    out  0A0h, al               ; E6 A0
    pop  es                     ; 07    restore BASIC ES
    pop  bp                     ; 5D    restore BASIC BP
    retf                        ; CB    far return to Cartridge BASIC

code ends
end start
