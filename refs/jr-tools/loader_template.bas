10 DEFINT A-Z
20 DIM A(__DIM__)
30 I = 0 : O = 0 : X$ = "" : B = 0 : D = 0
40 ST = 0 : RI = 0 : FA = 0
50 I = 0
60 READ D
70 IF D = -1 THEN 110
80 POKE VARPTR(A(0)) + I, D
90 I = I + 1
100 GOTO 60
110 PRINT "Loaded "; I; " bytes. Press Enter to CALL..."
120 INPUT X$
130 O = VARPTR(A(0))
140 CALL O
150 PRINT "RETURNED OK"
160 ST = PEEK(VARPTR(A(0)) + __RESULT__)
170 RI = PEEK(VARPTR(A(0)) + __RESULT__ + 2) + 256! * PEEK(VARPTR(A(0)) + __RESULT__ + 3)
180 FA = PEEK(VARPTR(A(0)) + __RESULT__ + 4) + 256! * PEEK(VARPTR(A(0)) + __RESULT__ + 5)
190 PRINT "status="; ST; " rising="; RI; " falling="; FA
200 END
