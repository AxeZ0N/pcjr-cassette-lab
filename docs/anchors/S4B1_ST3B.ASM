; S4B1_ST3B.ASM - instrumented CH0 probe + fixed-anchor majority (180B)
; Origin: O = VARPTR(A(0)), invoked via Cartridge BASIC CALL O (far call).
; CPU: 8088 real mode, no DOS.
;
; Contract: {"id":"S4B1_ST3B","source":"S4B1_ST3B.BAS",
;   "expected":{"return":"RETURNED OK","st":"3","half":"0|1",
;   "rise/trail/burst reported","keyboard_after":"intact"},
;   "regression":"IRPING -> S4A","recovery":"cold_power_cycle"}
;
; Result map (position-independent, BP = entry + 180):
;   [bp+0]  status: 0=no rise, 1=no trail, 3=sampled
;   [bp+1]  rise_lo  [bp+2] rise_hi
;   [bp+3]  trail_lo [bp+4] trail_hi
;   [bp+5]  burst_lo [bp+6] burst_hi   (rise - trail, positive)
;   [bp+7]  half-cell majority 0|1
;
; Timing: after start-burst trailing edge, wait until (trail - cur)
; >= 0x2E4 (740 counts = 310us) on the CH0 down-counter, then 5x
; majority sample PC6. This anchor is now KNOWN-BAD for decode: the
; AGC envelope stretches the start burst to ~250us and the fixed
; offset flip-flops on the bit0 boundary (see facts
; s4b1_stage3b_boundary). Retained as an instrumented probe, not a
; decoder.
;
; VERIFY: 0x2E4 = 310us x 2.38636MHz empirical clock.

code segment para 'code'
    assume cs:code
start:
    push cs
    pop  ds                  ; DS = CS

    push bp                  ; preserve BASIC frame pointer
    call get_ip
get_ip:
    pop  bp
    lea  bp, [bp + 174]      ; BP = entry + 180 (result region)

    mov  al, 0
    out  0A0h, al            ; mask NMI (D7=0)

    ; ---- finite arm on PC6 rising edge (start burst) ----
    xor  cx, cx
rise_loop:
    in   al, 62h
    and  al, 40h
    jne  rise_seen
    loop rise_loop
    mov  al, 0
    mov  [bp+0], al
    jmp  exit_common

rise_seen:
    ; ---- latch CH0 + read 16-bit rise timestamp ----
    mov  al, 0
    out  43h, al
    in   al, 40h
    mov  [bp+1], al
    mov  bl, al
    in   al, 40h
    mov  [bp+2], al
    mov  bh, al

    ; ---- wait trailing edge ----
    mov  cx, 0
trail_loop:
    in   al, 62h
    and  al, 40h
    je   trail_seen
    loop trail_loop
    mov  al, 1
    mov  [bp+0], al
    jmp  restore

exit_common:
    jmp  restore

trail_seen:
    ; ---- latch CH0 + read 16-bit trail timestamp ----
    mov  al, 0
    out  43h, al
    in   al, 40h
    mov  [bp+3], al
    mov  dl, al
    in   al, 40h
    mov  [bp+4], al
    mov  dh, al

    ; ---- burst = rise - trail, store lo/hi ----
    mov  ax, bx
    sub  ax, dx
    mov  [bp+5], al
    mov  al, ah
    mov  [bp+6], al

    ; ---- fixed 740-anchor wait from trailing edge ----
    mov  cx, 0
grid_wait:
    mov  al, 0
    out  43h, al
    in   al, 40h
    mov  bl, al
    in   al, 40h
    mov  bh, al
    mov  ax, dx
    sub  ax, bx
    cmp  ax, 0x2E4
    jc   grid_wait

    ; ---- 5x majority sample of PC6, >=3 -> 1 ----
    mov  bx, 0
    mov  cx, 5
maj_loop:
    in   al, 62h
    and  al, 40h
    je   maj_zero
    inc  bx
maj_zero:
    loop maj_loop

    mov  ax, 3
    cmp  bx, ax
    jc   half_lo
    mov  al, 1
    jmp  half_done
half_lo:
    mov  al, 0
half_done:
    mov  [bp+7], al
    mov  al, 3
    mov  [bp+0], al          ; status 3: sampled

    ; ---- end-quiet wait: mask entire press incl break frame ----
    mov  cx, 400
quiet_wait:
    in   al, 62h
    and  al, 40h
    jne  quiet_wait
    loop quiet_wait

restore:
    in   al, 0A0h            ; clear keyboard latch
    mov  al, 80h
    out  0A0h, al            ; re-enable NMI

    pop  bp
    retf
code ends
    end start
