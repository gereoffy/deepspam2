
from unicodedata import normalize

ZERO_WIDTH_CF = [0, 173, 847, 8203, 8204, 8205, 8206, 8207, 8232, 8233, 8234, 8235, 8236, 8237, 8238, 8288, 8289, 8290, 8291, 65038, 65039, 65279]

orosz={1029: 'S', 1030: 'I', 1032: 'J', 1040: 'A', 1042: 'B', 1045: 'E', 1050: 'K', 1052: 'M', 1053: 'H', 1054: 'O', 1056: 'P', 1057: 'C', 1058: 'T', 1061: 'X',
       1072: 'a', 1077: 'e', 1086: 'o', 1088: 'p', 1089: 'c', 1091: 'y', 1093: 'x', 1109: 's', 1110: 'i', 1112: 'j'}

class DS2Preprocessor:

  def __init__(self,charmap):
    chars="\n"
    self.unimap={}
    # nullazni: 7F-A0, 2B0-370, 200B-200F,2028-202E, 2060-2063
    for line in open(charmap,"rt",encoding="utf-8"):
        l=line.split("\t")
        self.unimap[l[1]]=l[2]
        for c in l[2]:
            if not c in chars: chars+=c
    for c in ZERO_WIDTH_CF: self.unimap[chr(c)]=""
    self.unimap["\n"]="\n"

    print("Charset[%d]:"%len(chars),chars)
    for c in chars:
        if self.unimap[c]!=c: print("BAD map for %s -> %s"%(c,self.unimap[c]))

  def __call__(self,texts):
    result=[]
    for row in texts:
        line=row if type(row)==str else "|\n".join(row)
        line="".join(orosz[ord(c)] if ord(c) in orosz else c for c in line) # pre-fix russian a/e/o... chars
        line=normalize('NFKC', line) # Compatibility Decomposition,followed by Canonical Composition  https://unicode.org/reports/tr15/#Introduction
        line="".join(self.unimap[c] for c in line if c in self.unimap) # lowercase & fix unicode shit...
        line=" ".join(line.strip().split()) # remove extra whitespace
        result.append(line)
    return result
