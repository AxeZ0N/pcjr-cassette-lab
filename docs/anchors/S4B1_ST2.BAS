1 ' S4B1_ST2.BAS - CH0 edge-synchronized timestamp capture (103B)
2 ' ASM: 103 bytes, gate-verified (selfloc + pjasm + decode + branch 8/8).
3 ' Contract: {"id":"S4B1_ST2","source":"S4B1_ST2.BAS",
4 '   "expected":{"return":"RETURNED OK","st":"2","rise/trail stored",
5 '   "delta_nonzero":"1","keyboard_after":"intact"},
6 '   "regression":"IRPING -> S4A","recovery":"cold_power_cycle"}
7 ' Result region at O+180..O+184 (raised ceiling):
8 '   [+0]=status (0=no rise, 1=no trail, 2=sampled)
9 '   [+1]=rise_lo [+2]=rise_hi [+3]=trail_lo [+4]=trail_hi
10 ' CH0 counts DOWN: burst = rise - trail (positive).
11 ' Send one key from the Pi during the arm window.
20 defint a-z
30 dim a(100)
40 i=0:o=0:d=0:x$="":st=0:rl=0:rh=0:tl=0:th=0
50 r!=0:t!=0:b!=0
60 i=0
70 read d
80 if d=-1 then 120
90 poke varptr(a(0))+i,d
100 i=i+1
110 goto 70
120 print "loaded ";i;" bytes. enter to arm"
130 input x$
140 o=varptr(a(0))
150 call o
160 print "returned ok"
170 st=peek(varptr(a(0))+180)
180 rl=peek(varptr(a(0))+181)
190 rh=peek(varptr(a(0))+182)
200 tl=peek(varptr(a(0))+183)
210 th=peek(varptr(a(0))+184)
220 r!=rl+256!*rh
230 t!=tl+256!*th
240 b!=r!-t!
250 if b!<0 then b!=b!+65536!
260 print "st=";st
270 print "rise=&h";hex$(rh);hex$(rl)
280 print "trail=&h";hex$(th);hex$(tl)
290 print "burst=&h";hex$(cint(b!)\256);hex$(cint(b!) mod 256)
300 end
1000 data &h0e,&h1f,&h55,&he8,&h00,&h00,&h5d,&h8d,&hae,&hae,&h00
1010 data &hb0,&h00,&he6,&ha0,&hb9,&h00,&h00,&he4,&h62,&h24,&h40
1020 data &h75,&h09,&he2,&hf8,&hb0,&h00,&h88,&h46,&h00,&heb,&h3e
1030 data &hb0,&h00,&he6,&h43,&he4,&h40,&h88,&h46,&h01,&he4,&h40
1040 data &h88,&h46,&h02,&hb9,&h00,&h00,&he4,&h62,&h24,&h40,&h74
1050 data &h09,&he2,&hf8,&hb0,&h01,&h88,&h46,&h00,&heb,&h1e,&hb0
1060 data &h00,&he6,&h43,&he4,&h40,&h88,&h46,&h03,&he4,&h40,&h88
1070 data &h46,&h04,&hb0,&h02,&h88,&h46,&h00,&hb9,&h90,&h01,&he4
1080 data &h62,&h24,&h40,&h75,&hfa,&he2,&hf8,&he4,&ha0,&hb0,&h80
1090 data &he6,&ha0,&h5d,&hcb
1100 data -1
