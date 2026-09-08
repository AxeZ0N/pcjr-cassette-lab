1 ' dec1_st1.bas - edge-sync decoder stage 1: two-edge span capture
2 ' contract DEC1_ST1. 106 machine-code bytes, gate-verified.
3 ' result map o+128: flag=status, r0=first rising edge, r1=second.
10 defint a-z
20 dim a(300)
30 i=0:o=0:d=0:x=0
40 fl=0:sv!=0:sg!=0
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
160 fl=peek(varptr(a(0))+128)
170 sv!=peek(varptr(a(0))+130)+256!*peek(varptr(a(0))+131)
180 sg!=peek(varptr(a(0))+132)+256!*peek(varptr(a(0))+133)
200 print "flag=";fl;" r0=";hex$(sv!);":";hex$(sg!)
210 end
1000 DATA &H0E,&H1F,&H55,&HE8,&H00,&H00,&H5D,&H8D,&HAE,&H7A,&H00
1010 DATA &HB0,&H00,&HE6,&HA0,&HE4,&HA0,&H31,&HC9,&HE4,&H62,&H24
1020 DATA &H40,&H75,&H09,&HE2,&HF8,&HB0,&H00,&H88,&H46,&H00,&HEB
1030 DATA &H40,&HB0,&H00,&HE6,&H43,&HE4,&H40,&H88,&H46,&H02,&HE4
1040 DATA &H40,&H88,&H46,&H03,&H31,&HC9,&HE4,&H62,&H24,&H40,&H74
1050 DATA &H04,&HE2,&HF8,&HEB,&H21,&H31,&HC9,&HE4,&H62,&H24,&H40
1060 DATA &H75,&H04,&HE2,&HF8,&HEB,&H15,&HB0,&H00,&HE6,&H43,&HE4
1070 DATA &H40,&H88,&H46,&H04,&HE4,&H40,&H88,&H46,&H05,&HB0,&H02
1080 DATA &H88,&H46,&H00,&HEB,&H05,&HB0,&H00,&H88,&H46,&H00,&HE4
1090 DATA &HA0,&HB0,&H80,&HE6,&HA0,&H5D,&HCB
1100 DATA -1
