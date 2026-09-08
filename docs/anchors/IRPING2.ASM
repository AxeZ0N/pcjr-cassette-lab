; IRPING2.ASM - minimal transport sanity probe (supersedes IRPING)
; Detect BOTH a high and a low sample of 62h bit 6 in one finite
; masked poll. No timestamps, no decode, no counter. Pass: result=3.
; Origin: org 0, position-independent via selfloc.
; Facts: port C = 62h, IR bit 6 -> facts.md hardware_map;
;        NMI mask/clear/restore -> facts.md nmi_chain_detail.
; Stage: 5 (polling loop, NMI masked). Not a functional decode probe.

option casemap:none
option segment:use16

code segment
    assume cs:code
    org 0

start:
    push cs                  ; Rule 1 bridge: DS = CS
    pop  ds
    push bp                  ; preserve interpreter frame
    call get_ip
get_ip:
    pop  bp                  ; BP = entry + 6
    lea  bp, [bp + 128 - 6]  ; BP = entry + 128 = O+128 (Rule 4 selfloc)

    mov  byte ptr [bp], 0    ; result byte = 0

    mov  al, 00h
    out  0A0h, al            ; mask NMI (D7=0) before touching 62h
    in   al, 0A0h            ; dummy read: clear pending latch

    mov  cx, 0FFFFh          ; finite poll cap, no unbounded arm

poll_loop:
    in   al, 62h             ; 8255 port C
    test al, 40h             ; bit 6 = IR input
    jz   saw_low
    or   byte ptr [bp], 01h  ; saw_high
    jmp  check_done
saw_low:
    or   byte ptr [bp], 02h  ; saw_low
check_done:
    mov  al, [bp]
    cmp  al, 03h
    je   done                ; both edges seen -> early exit
    loop poll_loop

done:
    in   al, 0A0h            ; clear latch
    mov  al, 80h
    out  0A0h, al            ; restore NMI (D7=1) before RETF
    pop  bp
    retf

code ends
end start
