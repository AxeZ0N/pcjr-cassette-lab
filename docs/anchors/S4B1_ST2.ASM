; S4B1_ST2.ASM - CH0 edge-synchronized timestamp capture (stage 2, 103B)
; Origin: O = VARPTR(A(0)), invoked via Cartridge BASIC CALL O (far call).
; CPU: 8088 real mode, no DOS.
;
; Contract: {"id":"S4B1_ST2","source":"S4B1_ST2.BAS",
;   "expected":{"return":"RETURNED OK","st":"2","rise/trail stored",
;   "delta_nonzero":"1","keyboard_after":"intact"},
;   "regression":"IRPING -> S4A","recovery":"cold_power_cycle"}
;
; Result map (position-independent, BP = entry + 180):
;   [bp+0]  status: 0=no rise, 1=no trail, 2=sampled
;   [bp+1]  rise_lo   [bp+2] rise_hi
;   [bp+3]  trail_lo  [bp+4] trail_hi
;
; CH0 counts DOWN: burst = rise - trail (positive). Latch path per
; CH0CAL anchor: mov al,0 / out 43h,al / in al,40h (lo) / in al,40h
; (hi). Never bare IN on a counter port.
;
; VERIFY: CH0 latch/read under NMI mask per CH0CAL idiom.

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
    mov  cx, 0
rise_loop:
    in   al, 62h
    and  al, 40h
    jne  rise_seen
    loop rise_loop
    mov  al, 0
    mov  [bp+0], al          ; status 0: no rising edge
    jmp  restore

rise_seen:
    ; ---- latch CH0 + read 16-bit rise timestamp ----
    mov  al, 0
    out  43h, al
    in   al, 40h
    mov  [bp+1], al
    in   al, 40h
    mov  [bp+2], al

    ; ---- wait trailing edge ----
    mov  cx, 0
trail_loop:
    in   al, 62h
    and  al, 40h
    je   trail_seen
    loop trail_loop
    mov  al, 1
    mov  [bp+0], al          ; status 1: no trailing edge
    jmp  restore

trail_seen:
    ; ---- latch CH0 + read 16-bit trail timestamp ----
    mov  al, 0
    out  43h, al
    in   al, 40h
    mov  [bp+3], al
    in   al, 40h
    mov  [bp+4], al

    mov  al, 2
    mov  [bp+0], al          ; status 2: sampled

    ; ---- end-quiet wait: mask entire press incl break frame ----
    mov  cx, 400
quiet_wait:
    in   al, 62h
    and  al, 40h
    jne  quiet_wait          ; burst -> reset counter
    loop quiet_wait          ; quiet -> keep polling

restore:
    in   al, 0A0h            ; clear keyboard latch
    mov  al, 80h
    out  0A0h, al            ; re-enable NMI

    pop  bp
    retf
code ends
    end start
