10 defint a-z
20 dim a(200)
30 i=0:o=0:d=0
40 m1=0:sv=0:sg!=0
50 i=0
60 read d
70 if d=-1 then 110
80 poke varptr(a(0))+i,d
90 i=i+1
100 goto 60
110 print "loaded ";i;" bytes"
120 o=varptr(a(0))
130 call o
140 print "returned ok"
150 m1=peek(varptr(a(0))+128)
160 sv=peek(varptr(a(0))+130)+256!*peek(varptr(a(0))+131)
170 sg!=peek(varptr(a(0))+132)+256!*peek(varptr(a(0))+133)
180 print "m1=";m1
190 print "saved=";sv;":";sg!
200 end
1000 data &h0e,&h1f,&h55,&he8,&h00,&h00,&h5f,&h8d,&h7d,&h7a,&h06,&hc6,&h05,&h2a,&hb0,&h00
1010 data &he6,&ha0,&h33,&hc0,&h8e,&hc0,&h26,&ha1,&h08,&h00,&h89,&h45,&h02,&h26,&ha1,&h0a
1020 data &h00,&h89,&h45,&h04,&he4,&ha0,&hb0,&h80,&he6,&ha0,&h07,&h5d,&hcb
1030 data -1
