
import re
import unicodedata


# Text tokenizer class compatible with DeepSpam v1

TAG_RE1 = re.compile(r'<[^>]+>')
TAG_RE2 = re.compile(r'\[[^[]+\]')
TAG_RE3 = re.compile(r'https? ?: ?//[-._a-zA-Z0-9/?&=]*')
TAG_RE4 = re.compile(r'[-+$_.a-z0-9]*@[-.a-z0-9]*\.[a-z][a-z]*')
TAG_RE5 = re.compile(r'$[0-9][0-9]*')
TAG_RE6 = re.compile(r'[-0-9a-z][-0-9a-z][-0-9a-z]*\.[-0-9a-z][-0-9a-z][-0-9a-z]*\.[-0-9a-z][-0-9a-z][-0-9a-z]?')

def remove_url(text):
    text=TAG_RE3.sub('httpurl', text)
    text=TAG_RE4.sub('emailaddress', text)
    text=TAG_RE6.sub('domainname', text)
    text=TAG_RE5.sub('dollarandnumber', text)
    return text


confusables={}

def load_unicodes(fnev):
    # try to load unicodes.map from file
    for line in open(fnev,"rt",encoding="utf-8",errors="ignore"):
        l=line.rstrip("\n\r").split("\t",1)
        confusables[ord(l[0])]=l[1]
    print("%d entries loaded from %s file" %(len(confusables),fnev))

def remove_accents(input_str):
    if len(confusables)==0:
        try:
            load_unicodes("unicodes.map")
        except:
            # generate it with normalize() (without confusables...)
            for ic in range(128,0x20000):
                nfkd_form = unicodedata.normalize('NFKD', chr(ic))
                oc=nfkd_form.encode('ASCII', 'ignore').decode('ASCII', 'ignore')
                if (oc and oc!=chr(ic) and oc!="()"):
                    confusables[ic]=oc
            confusables[215]='x'
            confusables[216]='O' # athuzott 'O' betu
            confusables[248]='o' # athuzott 'o' betu
            confusables[223]='ss' # nemet
            print("%d entries generated from unicodedata.normalize" %(len(confusables)))
    return "".join(confusables.get(ord(x),"") if ord(x)>=128 else x for x in input_str)



def tokenize(s,vocab,minlen=1):
    ss=""
    tokens=[]
    vtokens=[]
#    print(s.encode("utf-8"))
    s=remove_url(s)
#    s=html_parser.unescape(s)
#    s=html_unescape(s)
#    print(s.encode("utf-8"))
#    s1=s.encode('ASCII', 'ignore').decode('ASCII', 'ignore')
#    if s==s1:
#      s=s.lower()
#    else:
#    s=remove_accents(s).decode('ASCII', 'ignore').lower()
    s=remove_accents(s).lower()
#    print(type(s))
#    s=str(s)
#    print(s.encode("utf-8"))
#    print(html_parser.unescape(s).encode("utf-8"))
#    print(s)
    lastc=' '
    for c in s:
#        print(type(c))
#        if (c>=ord('a') and c<=ord('z')) or c==ord('!') or c==ord('-'):
#        if (c>='a' and c<='z') or c=='-':
        if (c>='0' and c<='9'):
            if lastc!=' ' and lastc!='#':
              ss+=' '
            c='#'
            ss+=c
        elif (c>='a' and c<='z'):
            if lastc=='#':
              ss+=' '
            ss+=c
#        elif c!=lastc and c in ['!',',',';',':','.']:
        elif c!=lastc and c in ['!',';','.']:
            ss+=' '+c+' '
#        elif (c<'0' or c>'9') and c!='-' and c!='_' and c!="'":  # aposztrof kell az angol didn't stb miatt...
        elif (c<'0' or c>'9') and c!='-' and c!='_':
            ss+=' '
        lastc=c

#    print(ss.encode("utf-8"))

    for t in ss.strip().split():
#      print(t)
#        if len(t)<3 or len(t)>20:
#            continue
        # not number :)
#        t=t.lower()
      tokens.append(t)
      if len(t)>=minlen:
        if t in vocab:
          vtokens.append(t)

#    print(tokens)

#    for t in tokens:
#    if n>=10 and nn>=5:
#    return (vtokens,tokens)
#    print(vtokens)
    return vtokens


class DS1Tokenizer:
  def __init__(self,wordmap):
    self.wordmap=wordmap
    x=min(wordmap[k] for k in wordmap)
    y=max(wordmap[k] for k in wordmap)
    print(len(wordmap),type(wordmap),x,y)



  def encode(self,texts):
    return [ [self.wordmap[i] for i in tokenize(t,self.wordmap) ] for t in texts]

  def encode_as_pieces(self,texts):
    return [tokenize(t,self.wordmap) for t in texts]
  

