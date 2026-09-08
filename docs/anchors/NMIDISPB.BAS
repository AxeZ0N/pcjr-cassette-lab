10 defint a-z
20 dim a(66)
30 i = 0 : o = 0 : x$ = "" : d = 0 : t = 0
50 i = 0
60 read d
70 if d = -1 then 110
80 poke varptr(a(0)) + i, d
90 i = i + 1
100 goto 60
110 print "loaded "; i; " bytes. press enter to call..."
120 input x$
130 o = varptr(a(0))
140 call o
150 print "returned ok - press one ir key, then enter"
160 for t = 1 to 3000 : next t
170 input x$
180 print "keyboard ok, got ["; x$; "]"
190 end
1000 data &h0e,&h1f,&h55,&h06,&hb0,&h00,&he6,&ha0,&he8,&h00,&h00,&h5d,&h8d,&h6e,&h75,&h8d
1010 data &h5e,&hb0,&h8d,&h4e,&hb5,&h89,&h4f,&h03,&h33,&hc0,&h8e,&hc0,&h26,&h89,&h1e,&h08
1020 data &h00,&h8c,&hc8,&h26,&ha3,&h0a,&h00,&he4,&ha0,&hb0,&h80,&he6,&ha0,&h07,&h5d,&hcb
1030 data &h2e,&hff,&h2e,&h34,&h12,&h78,&h0f,&h00,&hf0
1040 data -1
