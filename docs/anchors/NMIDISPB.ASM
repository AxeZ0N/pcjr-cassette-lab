option casemap:none
option segment:use16

; NMIDISPB.ASM — Probe B no-op redirect (ground truth anchor)
; Target: IBM PCjr 4860/4861, 8088 real mode, Cartridge BASIC bridge.
; Origin: org 0. Result flag intentionally absent — zero-work handler.
; Hardware pass 2026-08-31: keyboard alive, keystroke echoed after chain.
;
;   start   (offset 0x00) bridge INSTALLER, entered via CALL O, far RETF.
;   handler (offset 0x30) NMI HANDLER, entered via IVT[2], chains to KBDNMI.
;
; The handler is a PURE REDIRECT: one far-indirect jmp through a
; CS-relative pointer. No register touched, no flag store, no stack
; perturbation beyond the NMI entry frame itself. At KBDNMI start SP is
; byte-identical to a stock keystroke.
;
; Installer stamps the runtime chain-target address into the handler's
; jmp disp16 field (handler+3) before re-enabling NMI. The placeholder
; 0x1234 in source is never executed; it is overwritten at install time.
; Position-independent per Rule 4.

flag_off equ 128          ; result region offset from code base

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
    push es                 ; 06        preserve BASIC ES
    mov  al, 0              ; B0 00     mask NMI before IVT write
    out  0a0h, al           ; E6 A0
    call get_ip             ; E8 0000   push return offset (0x0B)
get_ip:
    pop  bp                 ; 5D        BP = 0x0B
    lea  bp, [bp + flag_off - (get_ip - start)]
                            ; 8D 6E 75  BP = result base O+128
    lea  bx, [bp + (handler - start) - flag_off]
                            ; 8D 5E B0  BX = handler (0x30)
    lea  cx, [bp + (chain_target - start) - flag_off]
                            ; 8D 4E B5  CX = chain_target (0x35)
    mov  word ptr [bx+3], cx
                            ; 89 4F 03  stamp runtime ptr into jmp disp16
    xor  ax, ax             ; 33 C0     ES = 0000 (IVT segment)
    mov  es, ax             ; 8E C0
    mov  es:[0008h], bx     ; 26 89 1E 0800  IVT[2] offset = handler
    mov  ax, cs             ; 8C C8     IVT[2] segment = CS
    mov  es:[000ah], ax     ; 26 A3 0A00
    in   al, 0a0h           ; E4 A0     clear pending keyboard latch
    mov  al, 80h            ; B0 80     re-enable NMI
    out  0a0h, al           ; E6 A0
    pop  es                 ; 07        restore BASIC ES
    pop  bp                 ; 5D        restore BASIC BP
    retf                    ; CB        far return to Cartridge BASIC

;--------------------------------------------------------------
; HANDLER  (entered at CS:handler via NMI; chains to stock KBDNMI)
;--------------------------------------------------------------
; Zero work: no register save/restore, no flag store, no memory write.
; The far-indirect jmp loads F000:0F78 from chain_target and transfers
; control with SP identical to a stock NMI entry. KBDNMI then runs its
; own transparent save/restore and its own IRET.
handler:
    jmp  dword ptr cs:[1234h]
                            ; 2E FF 2E <disp16 stamped at install>

; Far pointer target: offset 0F78, segment F000 (stock KBDNMI entry).
chain_target:
    dw 0f78h                ; 78 0F
    dw 0f000h               ; 00 F0

code ends
end start
