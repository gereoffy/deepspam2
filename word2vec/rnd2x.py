#! /usr/bin/python3

import sys
import random

l=0
of=open("all.txt","wb")
files=[]
for fn in sys.argv[1:]: files.append(open(fn,"rb"))
print(files)
while True:
  i=random.randint(0, len(files)-1)
#  print(i)
  try:
    j=random.randint(2, 5)
    while j>0:
      line=files[i].readline()
#      if len(line)<100: continue
      j-=1
    if len(line)>200: of.write(line[:10000])
    l+=1
    if (l%1000)==0: print(i,j,l)
  except Exception as e:
    print(i,e)
    files.pop(i)


of.close()
