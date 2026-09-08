1 ' basload.bas - generic sentinel-loader harness (no machine code)
2 ' loads a machine-code data block from 1000+, calls it, reads o+128.
3 ' append a program's data lines at 1000.., ending in -1 before running.
10 defint a-z
20 dim a(300)
30 i=0:o=0:d=0:x=0
40 fl=0:sv=0:sg=0:st=0
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
170 sv=peek(varptr(a(0))+130)+256*peek(varptr(a(0))+131)
180 sg=peek(varptr(a(0))+132)+256*peek(varptr(a(0))+133)
190 st=peek(varptr(a(0))+134)
200 print "flag=";fl;" saved=";sv;":";sg;" status=";st
210 end
