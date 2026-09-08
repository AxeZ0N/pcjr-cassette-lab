; DEC1_ST1.ASM - edge-sync decoder stage 1: two-edge span capture (106B)
; Origin: O = VARPTR(A(0)); invoked via Cartridge BASIC CALL O (far call).
; CPU: 8088 real mode, no DOS.
;
; Result map (position-independent, BP = entry + 128):
;   [bp+0]  status: 0=timeout, 2=both edges seen
;   [bp+2]  r0 lo  [bp+3] r0 hi   first rising edge CH0 latch
;   [bp+4]  r1 lo  [bp+5] r1 hi   second rising edge CH0 latch
;
; Contract id DEC1_ST1. Regression IRPING -> S4B1_ST3B.
; Recovery cold_power_cycle.
; Emission gate: pjasm assemble 106B, debug_asm selfloc 8DAE7A00,
;   decode clean, branch 11/11. Hardware pass 2/2 (892/894 ct spans).
;
; NOTE: first detected edge is bit0, not the start bit; the start
; burst is swallowed by the arming window (see facts
; dec1_first_edge_bit0_inference).

code segment para 'code'
    assume cs:code
start:
    push cs
    pop  ds                  ; DS = CS (bridge contract)
    push bp                  ; preserve BASIC frame pointer

    call get_ip
get_ip:
    pop  bp
    lea  bp,[bp+122]         ; BP = entry + 128 (result region)

    mov  al, 0
    out  0xA0, al            ; mask NMI (D7=0)
    in   al, 0xA0            ; clear pending keyboard latch

    ; ---- finite arm on first rising edge ----
    xor  cx, cx
w1:
    in   al, 0x62
    and  al, 0x40
    jne  r0_seen
    loop w1
    mov  al, 0
    mov  [bp+0], al
    jmp  restore

r0_seen:
    ; ---- latch CH0 + store r0 ----
    mov  al, 0
    out  0x43, al            ; latch counter 0
    in   al, 0x40
    mov  [bp+2], al
    in   al, 0x40
    mov  [bp+3], al

    ; ---- wait falling edge ----
    xor  cx, cx
w2:
    in   al, 0x62
    and  al, 0x40
    je   f_seen
    loop w2
    jmp  timeout

f_seen:
    ; ---- finite arm on second rising edge ----
    xor  cx, cx
w3:
    in   al, 0x62
    and  al, 0x40
    jne  r1_seen
    loop w3
    jmp  timeout

r1_seen:
    ; ---- latch CH0 + store r1 ----
    mov  al, 0
    out  0x43, al
    in   al, 0x40
    mov  [bp+4], al
    in   al, 0x40
    mov  [bp+5], al

    mov  al, 2
    mov  [bp+0], al
    jmp  restore

timeout:
    mov  al, 0
    mov  [bp+0], al

restore:
    ; ---- mandatory keyboard re-enable ----
    in   al, 0xA0            ; clear latch
    mov  al, 0x80
    out  0xA0, al            ; restore NMI (D7=1, empirical)

    pop  bp
    retf
code ends
    end start
