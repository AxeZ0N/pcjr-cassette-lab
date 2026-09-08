code segment para 'code'
    assume cs:code
start:
    push cs
    pop  ds
    push bp
    call get_ip
get_ip:
    pop  bp
    lea  bp, [bp + 122]

    push bp

    xor  ax, ax
    out  0A0h, al
    in   al, 0A0h
    xor  ax, ax

    mov  [bp+0], al
    mov  [bp+2], ax
    mov  [bp+6], ax

    mov  dx, 62h
    in   al, dx
    and  al, 40h
    mov  [bp+4], al
    mov  bl, al

    lea  bp, [bp + 8]
    xor  di, di
    xor  si, si
    mov  cx, 0F000h

poll:
    in   al, dx
    and  al, 40h
    inc  si
    cmp  al, bl
    je   same

    mov  bl, al
    mov  al, 0
    out  43h, al
    in   al, 40h
    mov  [bp+0], al
    in   al, 40h
    mov  [bp+1], al
    lea  bp, [bp + 2]
    inc  di

same:
    loop poll

done:
    pop  bp
    mov  [bp+2], di
    mov  [bp+6], si
    mov  al, 1
    mov  [bp+0], al

    in   al, 0A0h
    mov  al, 80h
    out  0A0h, al

    pop  bp
    retf
code ends
    end start
