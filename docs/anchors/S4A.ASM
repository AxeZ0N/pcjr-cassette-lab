; S4A.ASM - frame-sync + first half-cell sampler (S4 ladder stage 1)
; Origin: O = VARPTR(A(0)), invoked via Cartridge BASIC CALL O (far call).
; CPU: 8088 real mode, no DOS. 112 bytes.
;
; Contract: {"id":"S4A","source":"S4A.BAS",
;   "expected":{"return":"RETURNED OK","st":3,"half":"0|1",
;   "keyboard_after":"intact"},
;   "regression":"IRPING -> CH0CAL","recovery":"cold_power_cycle"}
;
; Result map (position-independent, BP = entry + 128):
;   [bp+0]  status: 0=no rising edge, 1=no trailing edge, 3=sampled
;   [bp+1]  first half-cell majority 0|1
;
; Timing: LOOP-constant delays, NOT the CH0-latched grid.
;   CX=90    start-phase wait (trailing edge -> first half-cell)
;   CX=190h  end-quiet wait (400 consecutive quiet PC6 polls)
; The end-quiet wait completes in post-keypress silence, masking the
; entire press including the break frame.
; VERIFY: LOOP constants calibrated for one h run only; CH0 grid
;         deferred. See facts s4a_loop_timing_substitution.
;
; Defect fixed in v2: v1 restored NMI immediately after the sample,
; mid-make-frame; KBDNMI then decoded garbage -> softlock. The
; end-quiet wait holds NMI masked until the IR link is silent.

code segment para 'code'
    assume cs:code
start:
    push cs
    pop  ds                  ; DS = CS

    push bp                  ; preserve BASIC frame pointer
    call get_ip
get_ip:
    pop  bp
    lea  bp, [bp + 122]      ; BP = entry + 128 (result region)

    mov  al, 0
    out  0A0h, al            ; mask NMI (D7=0)

    ; ---- wait rising edge on PC6 (start burst), finite arm ----
    mov  cx, 0
rise_loop:
    in   al, 62h
    and  al, 40h
    jne  rise_seen
    loop rise_loop
    mov  [bp+0], 0           ; status 0: no rising edge
    jmp  restore

rise_seen:
    mov  [bp+0], 1           ; status 1: rising seen

    ; ---- wait trailing edge ----
    mov  cx, 0
trail_loop:
    in   al, 62h
    and  al, 40h
    je   trail_seen
    loop trail_loop
    jmp  restore             ; status stays 1: no trailing edge

trail_seen:
    mov  [bp+0], 2           ; transient

    ; ---- start-phase wait: land on first half-cell ----
    mov  cx, 90
wait_start:
    loop wait_start

    ; ---- 5x majority sample, >=3 -> 1 ----
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
    jc   sample_lo
    mov  al, 1
    jmp  sample_done
sample_lo:
    mov  al, 0
sample_done:
    mov  [bp+1], al          ; first half-cell majority
    mov  [bp+0], 3           ; status 3: sampled

    ; ---- end-quiet wait: any burst resets the count ----
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
