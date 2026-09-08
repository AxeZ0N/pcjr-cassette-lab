1  ' AGCPROBE.BAS - compact probe capture (ENVSHAPE variant)
2  ' ASM: frozen CH0CAL image, 100 bytes, reused byte-for-byte.
3  ' Contract: {"id":"AGCPROBE","source":"AGCPROBE.BAS",
4  '  "expected":{"st":1,"ed":">=4","in0":"0|64","keyboard_after":"intact"},
5  '  "regression":"IRPING -> ENVSHAPE","recovery":"cold_power_cycle"}
10 defint a-z
20 dim a(300)
30 i=0:o=0:d=0:j=0:fl=0:st=0:ed=0:in0=0:lv=0:x$=""
40 t!=0:u!=0:g!=0:it!=0
41 h$="":l$=""
50 i=0
60 read d
70 if d=-1 then 110
80 poke varptr(a(0))+i,d
90 i=i+1
100 goto 60
110 print "loaded ";i;" bytes"
120 input x$
130 for fl=1 to 100:next fl
135 o=varptr(a(0))
140 call o
150 st=peek(varptr(a(0))+128)
160 ed=peek(varptr(a(0))+130)+256!*peek(varptr(a(0))+131)
170 in0=peek(varptr(a(0))+132)
180 it!=peek(varptr(a(0))+134)+256!*peek(varptr(a(0))+135)
190 if ed>=3 then 210
195 print "st=";st;" ed=";ed;" in=";in0;" it=";it!
200 goto 400
210 lv=in0
220 t!=peek(varptr(a(0))+136)+256!*peek(varptr(a(0))+137)
230 for j=2 to ed
240 u!=peek(varptr(a(0))+136+(j-1)*2)+256!*peek(varptr(a(0))+137+(j-1)*2)
250 g!=t!-u!:if g!<0 then g!=g!+65536!
260 lv=64-lv
265 if lv=64 then 272
267 l$=l$+str$(int(g!))+" "
270 goto 290
272 h$=h$+str$(int(g!))+" "
290 t!=u!
300 next j
310 print "st=";st;" ed=";ed;" in=";in0;" it=";it!
320 print "H:";h$; "L:";l$
400 end
1000 data &h0e,&h1f,&h55,&he8,&h00,&h00,&h5d,&h8d,&hae,&h7a,&h00
1010 data &h55,&h31,&hc0,&he6,&ha0,&he4,&ha0,&h31,&hc0,&h88,&h46
1020 data &h00,&h89,&h46,&h02,&h89,&h46,&h06,&hba,&h62,&h00,&hec
1030 data &h24,&h40,&h88,&h46,&h04,&h88,&hc3,&h8d,&h6e,&h08,&h31
1040 data &hff,&h31,&hf6,&hb9,&h00,&hf0,&hec,&h24,&h40,&h46,&h3a
1050 data &hc3,&h74,&h14,&h88,&hc3,&hb0,&h00,&he6,&h43,&he4,&h40
1060 data &h88,&h46,&h00,&he4,&h40,&h88,&h46,&h01,&h8d,&h6e,&h02
1070 data &h47,&he2,&he2,&h5d,&h89,&h7e,&h02,&h89,&h76,&h06,&hb0
1080 data &h01,&h88,&h46,&h00,&he4,&ha0,&hb0,&h80,&he6,&ha0,&h5d
1090 data &hcb
1100 data -1
