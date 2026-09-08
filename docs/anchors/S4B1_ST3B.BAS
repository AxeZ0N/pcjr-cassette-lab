1 ' S4B1_ST3B.BAS - instrumented CH0 probe + 740-anchor + majority (180B)
2 ' ASM: 180 bytes, gate-verified (selfloc + pjasm + decode + branch 14/14).
3 ' Contract: {"id":"S4B1_ST3B","source":"S4B1_ST3B.BAS",
4 '   "expected":{"return":"RETURNED OK","st":"3","half":"0|1",
5 '   "rise/trail/burst reported","keyboard_after":"intact"},
6 '   "regression":"IRPING -> S4A","recovery":"cold_power_cycle"}
7 ' Result region at O+180..O+187 (raised ceiling):
8 '   [+0]=status (0=no rise,1=no trail,3=sampled)
9 '   [+1]=rise_lo [+2]=rise_hi [+3]=trail_lo [+4]=trail_hi
10 '   [+5]=burst_lo [+6]=burst_hi [+7]=half majority
11 ' CH0 counts DOWN: burst = rise - trail. 0x2E4 = 740 = 310us.
12 ' The 740-anchor is KNOWN-BAD for decode (AGC boundary flip-flop).
13 ' Send one key from the Pi during the arm window.
20 defint a-z
30 dim a(100)
40 i=0:o=0:d=0:x$="":st=0:rl=0:rh=0:tl=0:th=0:bl=0:bh=0:hf=0
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
220 bl=peek(varptr(a(0))+185)
230 bh=peek(varptr(a(0))+186)
240 hf=peek(varptr(a(0))+187)
250 r!=rl+256!*rh
260 t!=tl+256!*th
270 b!=bl+256!*bh
280 print "st=";st
290 print "rise=&h";hex$(rh);hex$(rl)
300 print "trail=&h";hex$(th);hex$(tl)
310 print "burst=&h";hex$(bh);hex$(bl)
320 print "half=";hf
330 end
1000 data &h0e,&h1f,&h55,&he8,&h00,&h00,&h5d,&h8d,&hae,&hae,&h00
1010 data &hb0,&h00,&he6,&ha0,&h31,&hc9,&he4,&h62,&h24,&h40,&h75
1020 data &h09,&he2,&hf8,&hb0,&h00,&h88,&h46,&h00,&heb,&h24,&hb0
1030 data &h00,&he6,&h43,&he4,&h40,&h88,&h46,&h01,&h88,&hc3,&he4
1040 data &h40,&h88,&h46,&h02,&h88,&hc7,&hb9,&h00,&h00,&he4,&h62
1050 data &h24,&h40,&h74,&h0b,&he2,&hf8,&hb0,&h01,&h88,&h46,&h00
1060 data &heb,&h68,&heb,&h66,&hb0,&h00,&he6,&h43,&he4,&h40,&h88
1070 data &h46,&h03,&h88,&hc2,&he4,&h40,&h88,&h46,&h04,&h88,&hc6
1080 data &h89,&hd8,&h2b,&hc2,&h88,&h46,&h05,&h88,&he0,&h88,&h46
1090 data &h06,&hb9,&h00,&h00,&hb0,&h00,&he6,&h43,&he4,&h40,&h88
1100 data &hc3,&he4,&h40,&h88,&hc7,&h89,&hd0,&h2b,&hc3,&h81,&hf8
1110 data &he4,&h02,&h72,&hea,&hbb,&h00,&h00,&hb9,&h05,&h00,&he4
1120 data &h62,&h24,&h40,&h74,&h01,&h43,&he2,&hf7,&hb8,&h03,&h00
1130 data &h39,&hc3,&h72,&h04,&hb0,&h01,&heb,&h02,&hb0,&h00,&h88
1140 data &h46,&h07,&hb0,&h03,&h88,&h46,&h00,&hb9,&h90,&h01,&he4
1150 data &h62,&h24,&h40,&h75,&hfa,&he2,&hf8,&he4,&ha0,&hb0,&h80
1160 data &he6,&ha0,&h5d,&hcb
1170 data -1
