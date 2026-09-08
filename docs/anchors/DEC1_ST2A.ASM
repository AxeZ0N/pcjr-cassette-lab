; DEC1_ST2A.ASM - PC0 one-shot latch probe (57B)
; Origin: O = VARPTR(A(0)); invoked via Cartridge BASIC CALL O (far call).
; CPU: 8088 real mode, no DOS.
;
; Result map (position-independent, BP = entry + 128):
;   [bp+0]  status: 0=timeout, 2=PC0 seen
;   [bp+1]  pc6 raw: 40h=HIGH, 00h=LOW
;
; Contract id DEC1_ST2A. Regression IRPING -> DEC1_ST1.
; Recovery cold_power_cycle.
; Emission gate: pjasm assemble 57B, debug_asm selfloc 8DAE7A00,
;   decode clean, branch 3/3.
;
; New risk: 8255 PC0 (62h bit 0) one-shot latch read via polling bridge.
; PC0 semantics manual-verified (entry 32), first polled here.

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

    ; ---- finite arm on PC0 (62h bit 0) ----
    xor  cx, cx
w1:
    in   al, 0x62
    and  al, 0x01
    jne  seen
    loop w1
    mov  al, 0               ; timeout
    mov  [bp+0], al
    mov  [bp+1], al
    jmp  restore

seen:
    mov  al, 2               ; PC0 seen
    mov  [bp+0], al
    in   al, 0x62            ; sanity: PC6 should be HIGH at this instant
    and  al, 0x40
    mov  [bp+1], al

restore:
    in   al, 0xA0            ; clear latch
    mov  al, 0x80
    out  0xA0, al            ; restore NMI (D7=1, empirical)

    pop  bp
    retf
code ends
    end start
