1 ' DEC1_ST2A.BAS - PC0 one-shot latch probe
2 ' contract DEC1_ST2A. 57 machine-code bytes, gate-verified.
3 ' result map o+128: st=status, pc=pc6 raw (40h=HIGH).
10 defint a-z
20 dim a(300)
30 i=0:o=0:d=0:x=0
40 st=0:pc=0
50 i=0
60 read d
70 if d=-1 then 110
80 poke varptr(a(0))+i,d
90 i=i+1
100 goto 60
110 print "loaded ";i;" bytes. press enter, then send one key..."
120 input x
130 o=varptr(a(0))
140 call o
150 print "returned ok"
160 st=peek(varptr(a(0))+128)
170 pc=peek(varptr(a(0))+129)
200 print "status=";st;" pc6=";hex$(pc)
210 end
1000 DATA &H0E,&H1F,&H55,&HE8,&H00,&H00,&H5D,&H8D,&HAE,&H7A,&H00
1010 DATA &HB0,&H00,&HE6,&HA0,&HE4,&HA0,&H31,&HC9,&HE4,&H62,&H24
1020 DATA &H01,&H75,&H0C,&HE2,&HF8,&HB0,&H00,&H88,&H46,&H00,&H88
1030 DATA &H46,&H01,&HEB,&H0C,&HB0,&H02,&H88,&H46,&H00,&HE4,&H62
1040 DATA &H24,&H40,&H88,&H46,&H01,&HE4,&HA0,&HB0,&H80,&HE6,&HA0
1050 DATA &H5D,&HCB
1060 DATA -1
