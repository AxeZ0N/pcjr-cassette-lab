1 ' S4A.BAS - frame-sync + first half-cell sampler (S4 ladder stage 1)
2 ' ASM: 112 bytes, gate-verified via debug_asm (selfloc + rel8/branch + decode).
3 ' Contract: {"id":"S4A","source":"S4A.BAS","expected":{"return":"RETURNED OK",
4 '   "st":3,"half":"0|1","keyboard_after":"intact"},
5 '   "regression":"IRPING -> CH0CAL","recovery":"cold_power_cycle"}
6 ' Result map at O+128: [0]=status,[1]=first half-cell majority.
7 ' status: 0=no rising edge, 1=no trailing edge, 3=sampled.
8 ' Timing: LOOP-constant delays, NOT CH0. CX=90 start-phase, CX=190h end-quiet.
10 defint a-z
20 dim a(240)
30 i=0:o=0:d=0:x$="":st=0:hf=0
40 i=0
50 read d
60 if d=-1 then 100
70 poke varptr(a(0))+i,d
80 i=i+1
90 goto 50
100 print "loaded ";i;" bytes. enter to arm"
110 input x$
120 o=varptr(a(0))
130 call o
140 print "returned ok"
150 st=peek(varptr(a(0))+128)
160 hf=peek(varptr(a(0))+129)
170 print "st=";st;" half=";hf
180 end
1000 data &h0e,&h1f,&h55,&he8,&h00,&h00,&h5d,&h8d,&hae,&h7a
1010 data &h00,&hb0,&h00,&he6,&ha0,&hb9,&h00,&h00,&he4,&h62
1020 data &h24,&h40,&h75,&h08,&he2,&hf8,&hc6,&h46,&h00,&h00
1030 data &heb,&h48,&hc6,&h46,&h00,&h01,&hb9,&h00,&h00,&he4
1040 data &h62,&h24,&h40,&h74,&h04,&he2,&hf8,&heb,&h37,&hc6
1050 data &h46,&h00,&h02,&hb9,&h5a,&h00,&he2,&hfe,&hbb,&h00
1060 data &h00,&hb9,&h05,&h00,&he4,&h62,&h24,&h40,&h74,&h01
1070 data &h43,&he2,&hf7,&hb8,&h03,&h00,&h39,&hc3,&h72,&h04
1080 data &hb0,&h01,&heb,&h02,&hb0,&h00,&h88,&h46,&h01,&hc6
1090 data &h46,&h00,&h03,&hb9,&h90,&h01,&he4,&h62,&h24,&h40
1100 data &h75,&hf7,&he2,&hf8,&he4,&ha0,&hb0,&h80,&he6,&ha0
1110 data &h5d,&hcb
1120 data -1
