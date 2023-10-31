#! /usr/bin/python3

import sys

#input_stream=open(sys.argv[1],"rt",encoding="utf-8",errors="ignore")
input_stream=open("all.txt","rt",encoding="utf-8",errors="ignore")
output_stream=open("all.out","wt",encoding="utf-8")

chars={}
for c in " abcdefghijklmnopqrstuvwxyzáéíóöőúüűABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÖŐÚÜŰ!#$%&'()*+,-./0123456789:;<=>?@[\]^_`{|}~°«»…‘’“„”€¥£§×äëßµ®©": chars[c]=c
for c in range(0xC0,0x460): chars[chr(c)]=chr(c) # latin 1/2 greek cyril...
# fixes:
chars['\n']='\n'
chars[' ']=' ' # nbsp
chars[' ']=' ' # Narrow No-Break Space
chars['̶']='̶' # –—−̶
chars['–']='̶' # –—−̶
chars['—']='̶' # –—−̶
chars['−']='̶' # –—−̶
chars['́']="'"
chars['̋']='"'
chars['″']='"'
chars['"']='"'
chars['•']='-'
chars['‑']='-'
chars['­']='-' # Soft hyphen

chars['õ']='ő'
chars['ô']='ő'
chars['û']='ű'
#chars['à']='á'
#chars['ă']='á'
#chars['è']='é'

#chars['š']='s'
#chars['ç']='c'
#chars['č']='c'
#chars['ć']='c'
#chars['ń']='n'
#chars['ñ']='n'
#chars['ğ']='g'
#chars['Š']='S'


for line in input_stream:
    line2="".join(chars[x] if x in chars else " " for x in line.lower())
    line2=" ".join(line2.strip().split())
    if len(line2)>=50: output_stream.write(line2+"\n")
