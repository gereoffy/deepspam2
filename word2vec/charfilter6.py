#! /usr/local/bin/pypy3

import sys
from unicodedata import normalize

ZERO_WIDTH_CF = [0, 173, 847, 8203, 8204, 8205, 8206, 8207, 8232, 8233, 8234, 8235, 8236, 8237, 8238, 8288, 8289, 8290, 8291, 65038, 65039, 65279]

orosz={1029: 'S', 1030: 'I', 1032: 'J', 1040: 'A', 1042: 'B', 1045: 'E', 1050: 'K', 1052: 'M', 1053: 'H', 1054: 'O', 1056: 'P', 1057: 'C', 1058: 'T', 1061: 'X',
       1072: 'a', 1077: 'e', 1086: 'o', 1088: 'p', 1089: 'c', 1091: 'y', 1093: 'x', 1109: 's', 1110: 'i', 1112: 'j'}

chars="\n"
unimap={}
# nullazni: 7F-A0, 2B0-370, 200B-200F,2028-202E, 2060-2063
for line in open("unicodes6x.map","rt",encoding="utf-8"):
    l=line.split("\t")
    unimap[l[1]]=l[2]
    for c in l[2]:
        if not c in chars: chars+=c
for c in ZERO_WIDTH_CF: unimap[chr(c)]=""
unimap["\n"]="\n"

# !"#$%&'()*+,-./0123456789:;<=>?@[\]^_`abcdefghijklmnopqrstuvwxyz{|}~
# ¡¢£¤¥¦§©¬®°±²³µ¶·¹¿
# ×ßáãäåæçéëíïðñóö÷øúüýþÿ
# őűƩǝ
# ɔəɛɪʃʒʼΣάέήίΰαβγδεζηθικλμνξοπρςστυφχψωϊϋόύώ
# абвгдежзийклмнопрстуфхцчшщъыьэюяѐёђѓєѕіїјљњћќѝўџ
# †•‰€∈∞≈≤≥♭
print(len(chars),chars)

for c in chars:
    if c in unimap and unimap[c]!=c:
        print("BAD map for %s -> %s"%(c,unimap[c]))

#input_stream=open(sys.argv[1],"rt",encoding="utf-8",errors="ignore")
input_stream=open("all.txt","rt",encoding="utf-8",errors="ignore")
output_stream=open("all.out6","wt",encoding="utf-8")

lok=lno=lout=0
for line in input_stream:
    line="".join(orosz[ord(c)] if ord(c) in orosz else c for c in line) # pre-fix russian a/e/o... chars
    lno+=1
    if (lno%1000)==0: print(lno,lok,lout)

#    l=line.lower()
#    line2="".join(c for c in l if c in chars)
#    if l==line2: lok+=1  # all chars in the charset!

    # remove unicode shit (emojis etc)
    line=normalize('NFKC', line) # Compatibility Decomposition,followed by Canonical Composition  https://unicode.org/reports/tr15/#Introduction
    line2="".join(unimap[c] if c in unimap else " " for c in line) # lowercase & fix unicode shit...
    line2=" ".join(line2.strip().split()) # remove extra whitespace
    if len(line2)>=100: output_stream.write(line2+"\n") ; lout+=1

