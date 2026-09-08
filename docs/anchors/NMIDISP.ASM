option casemap:none
option segment:use16

; NMIDISP.ASM — custom INT 02h dispatch probe, Probe A (ground truth anchor)
; Target: IBM PCjr 4860/4861, 8088 real mode, Cartridge BASIC bridge.
; Origin: org 0. Result flag at offset 128 from code base.
;
; Hardware pass 2026-08-31: dispatch flag=1 on a single IR keystroke,
; control flag=0 with no key. Keyboard dead (stock KBDNMI replaced),
; cursor blinking (IF restored). IRPING2 status=3 before each run.
;
; TWO routines in one 72-byte image — the reason default bridge lint
; (single-routine shaped) does not apply. Built with `jr build` stage 0
; (lint toggle); verdict gate = disasm, per user decision 2026-08-31.
;
;   start   (offset 0x00)  bridge INSTALLER, entered via CALL O, far RETF.
;   handler (offset 0x2E)  NMI HANDLER, entered via IVT[2], ends IRET.
;
; Rule 9 lifted for this scope only (facts rule9_nmidisp_carveout).
; Prohibition stands for Probe B and all other scopes.
;
; DATA block byte-matches this source via `jr build` stage 0 (72 bytes).

FLAG_OFF EQU 128           ; result region offset from code base

code segment
    assume cs:code
    org 0

;--------------------------------------------------------------
; INSTALLER  (CALL O entry, Contract A, returns to BASIC)
;--------------------------------------------------------------
start:
    push cs                 ; 0E        bridge entry: DS = CS
    pop  ds                 ; 1F
    push bp                 ; 55        preserve BASIC BP
    push es                 ; 06        preserve BASIC ES (Contract A)
    mov  al, 0              ; B0 00     mask NMI (A0h D7=0) before IVT write
    out  0A0h, al           ; E6 A0
    call get_ip             ; E8 0000   push return offset (0x0B)
get_ip:
    pop  bp                 ; 5D        BP = 0x0B
    lea  bp, [bp + FLAG_OFF - (get_ip - start)]
                            ; 8D 6E 75  BP = 0x0B + 0x75 = 0x80 (result base)
    mov  byte ptr [bp], 0   ; C6 46 00 00   clear dispatch flag -> O+128
    lea  bx, [bp + (handler - start) - FLAG_OFF]
                            ; 8D 5E AE  BX = 0x80 - 0x52 = 0x2E (handler)
    xor  ax, ax             ; 33 C0     ES = 0000 (IVT segment)
    mov  es, ax             ; 8E C0
    mov  es:[0008h], bx     ; 26 89 1E 0800  IVT[2] offset = our handler
    mov  ax, cs             ; 8C C8     IVT[2] segment = CS
    mov  es:[000Ah], ax     ; 26 A3 0A00
    in   al, 0A0h           ; E4 A0     clear pending keyboard latch
    mov  al, 80h            ; B0 80     re-enable NMI (A0h D7=1)
    out  0A0h, al           ; E6 A0
    pop  es                 ; 07        restore BASIC ES
    pop  bp                 ; 5D        restore BASIC BP
    retf                    ; CB        far return to Cartridge BASIC

;--------------------------------------------------------------
; HANDLER  (entered at CS:handler via NMI; returns via IRET)
;--------------------------------------------------------------
; 8088 NMI entry already clears IF; no CLI needed. Save exactly the
; registers we touch so the interrupted BASIC state is byte-identical.
handler:
    push ds                 ; 1E        preserve interrupted DS
    push ax                 ; 50        preserve interrupted AX
    push bp                 ; 55        preserve interrupted BP
    push cs                 ; 0E        DS = CS for our result store
    pop  ds                 ; 1F
    call get_ip_h           ; E8 0000   push return offset (0x36)
get_ip_h:
    pop  bp                 ; 5D        BP = 0x36
    lea  bp, [bp + FLAG_OFF - (get_ip_h - start)]
                            ; 8D 6E 4A  BP = 0x36 + 0x4A = 0x80 (result base)
    mov  byte ptr [bp], 1   ; C6 46 00 01   set dispatch flag -> O+128
    in   al, 0A0h           ; E4 A0     clear keyboard latch
    mov  al, 80h            ; B0 80     re-enable NMI before IRET
    out  0A0h, al           ; E6 A0
    pop  bp                 ; 5D        restore BP
    pop  ax                 ; 58        restore AX
    pop  ds                 ; 1F        restore DS
    iret                    ; CF        return to interrupted BASIC

code ends
end start
