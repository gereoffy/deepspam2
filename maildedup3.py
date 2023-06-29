#! /usr/bin/python3

import io
import os
import sys
import pickle
import traceback

try:
  from io import BytesIO
except:
  from StringIO import StringIO as BytesIO

from eml2str import eml2str

sys.stdout.reconfigure(encoding='utf-8',errors="xmlcharrefreplace") # FIXes: UnicodeEncodeError: 'utf-8' codec can't encode characters in position 354-355: surrogates not allowed

###########################################################################################################
################################################### DEDUP #################################################
###########################################################################################################

wmem=bytearray(8*65536*65536)  # 16GB ram!!!
maxhash=8*len(wmem)-1

# hl=mozgo ablak merete amit hashel.  nn=maximum egyezesek szama
def dedup(tokens,hl,nn):
        # fuzzy search
        ok=0
        n=len(tokens)-(hl-1)
        for i in range(n):
            w=" ".join(tokens[i:i+hl])
            wh=hash(w)
            wh^=(wh>>40)
            wh&=maxhash
#            print(wh)
#            try:
            if wmem[wh>>3] & (1<<(wh&7)):
                ok+=1
                if ok>nn:
                    return 0
#                break
#            except:
#              print(type(wh))
        if ok<=nn:
#        if ok:
#            o=" ".join(tokens)
#            print(o)
            for i in range(n):
                w=" ".join(tokens[i:i+hl])
                #wh=hash(w) & maxhash
                wh=hash(w)
                wh^=(wh>>40)
                wh&=maxhash
                wmem[wh>>3]|=(1<<(wh&7))
            return 1
#        print(o.encode("utf-8"))
#	print str(label)+" "+" ".join(tokens)
        return 0

def dedup1(tokens):
        w=" ".join(tokens)
        wh=hash(w)
        wh^=(wh>>40)
        wh&=maxhash
#            print(wh)
#            try:
        if wmem[wh>>3] & (1<<(wh&7)):
            return 0
        wmem[wh>>3]|=(1<<(wh&7))
        return 1


#################################################################################################################################################################

ZERO_WIDTH_CF = set([
    0,       # Null (Cc)
    0xAD,    # Soft hyphen
    0x034F,  # Combining grapheme joiner (Mn)  # https://www.compart.com/en/unicode/U+034F
    0x200B,  # Zero width space
    0x200C,  # Zero width non-joiner
    0x200D,  # Zero width joiner
    0x200E,  # Left-to-right mark
    0x200F,  # Right-to-left mark
    0x2028,  # Line separator (Zl)
    0x2029,  # Paragraph separator (Zp)
    0x202A,  # Left-to-right embedding
    0x202B,  # Right-to-left embedding
    0x202C,  # Pop directional formatting
    0x202D,  # Left-to-right override
    0x202E,  # Right-to-left override
    0x2060,  # Word joiner
    0x2061,  # Function application
    0x2062,  # Invisible times
    0x2063,  # Invisible separator
             # https://unicode.org/emoji/charts/emoji-variants.html
    0xFE0E,  # Variation selector:  The character U+FE0E VARIATION SELECTOR-15 (VS15), used to request a text presentation for an emoji character.
    0xFE0F,  # Variation selector:  The character U+FE0F VARIATION SELECTOR-16 (VS16), used to request an emoji presentation for an emoji character.
    0xFEFF   # BOM, ZWNBSP, ZERO WIDTH NO-BREAK SPACE. Unicode Hexadecimal: 0xFEFF. Unicode Decimal: 65279
])

def ucsremove(s): # unicode shit remover
    return "".join(["" if ord(c) in ZERO_WIDTH_CF else c for c in s])

###########################################################################################################

vocab={}

def do_eml(eml,out_txt):
#    print("Parsing email (%d bytes)"%(len(eml)))

    preview=eml2str(eml)
    preview=ucsremove(preview) # remove unicode shit
    preview=" ".join(preview.split()) # fix whitespace
#    print(eml["_fpos"],preview[:100])

#    line="".join([" " if c in '#".,!?;:-+/*()[]0123456789' else c for c in preview.lower()])
#    line="".join([c if c.isalpha() else " " for c in preview.lower()])
    line="".join([c if c.isalnum() else " " for c in preview.lower()])
    line=line.split()
#    print(line)
    tokens=[str(vocab.get(t,0)) for t in line]

    words=sum(t!="0" for t in tokens)

#    if len(tokens)<10:
    if words>3 and len(tokens)>=10:
        ok=dedup1(tokens[:100]) & dedup1(tokens[5:100])
#        ok=dedup1(tokens[:25]) & dedup1(tokens[5:100]) & dedup1(tokens[-10:])
#        ok=dedup(tokens,7,(len(tokens)-10)*4/5)
#        ok=dedup(tokens,7,(len(tokens)-10)/3)
    else:
        ok=dedup1(line)*2

#    print(["dup","ok","short"][ok],words,"/",len(tokens))

    if ok:
#        print(" ".join(tokens)+"\n")
        out_txt.write(preview+"\n")

    return ok



########## MAIN ##############

#input_stream = io.TextIOWrapper(sys.stdin.buffer, encoding='iso-8859-2',errors='ignore')
#input_stream = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8',errors='ignore')
#output_stream= open("maildedup.mbox","wt",encoding="utf-8",errors='ignore'):
#input_stream = sys.stdin
#output_stream = sys.stdout
#output_txt = open("maildedup.txt","wt",encoding="utf-8",errors='ignore')
input_stream= open(sys.argv[1],"rb")
output_stream= [open(sys.argv[1]+".dup","wb"), open(sys.argv[1]+".out","wb"),open(sys.argv[1]+".short","wb")]
output_txt = open(sys.argv[1]+".txt","w")


try:
    i=0
    for line in open("/home/vocab/vocab.txt","rt",encoding="utf8"):
        i+=1
        vocab[line.split()[0]]=i
    print("VOCAB:",len(vocab),i)
except:
    pass



in_hdr=0
eml=None
lineno=0
#debug=0
for line in input_stream:
    lineno+=1
#    if debug: print(lineno,line)
    if in_hdr:
#	eml+=line
        if len(line.rstrip())==0:
            in_hdr=0
    elif line[0:5]==b'From ':
#        print(lineno,line)
        if eml:
            eml.seek(0)
            res=do_eml(eml,output_txt)
            output_stream[res].write(eml.getvalue())
            eml.close()
            eml=None
        in_hdr=1
    if not eml: eml=BytesIO()
    eml.write(line)
if eml:
    eml.seek(0)
    res=do_eml(eml,output_txt)
    output_stream[res].write(eml.getvalue())

for f in output_stream: f.close()
output_txt.close()
