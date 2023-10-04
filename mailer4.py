#! /usr/bin/python3

import time
import os
import sys
import time
import pickle
import traceback

from hdrdecode import parse_from,hdrdecode3,decodeline
from eml2str import eml2str,get_mimedata,vocab_split
from widechars import wcfixstr,ucsremove
from ttykeymap import NonBlockingInput,getch2,clrscr,box_message,box_input

ds=None


#sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'xmlcharrefreplace')
sys.stdout.reconfigure(encoding='utf-8',errors="xmlcharrefreplace") # FIXes: UnicodeEncodeError: 'utf-8' codec can't encode characters in position 354-355: surrogates not allowed
sys.stdin = sys.stdin.detach()
sys.stdin = sys.stdin.detach()
term_w,term_h=os.get_terminal_size(0)
#print(term_w,term_h,sys.stdin.isatty())
term_pl=term_w*6 # preview len, kb 1000 karakter itermben
term_w-=2
term_h-=2
term_w1=term_w//2-12
term_w2=term_w//2

mails_meta=[]
mails_flag=bytearray()
mails_text=[]
mails_deep=[]
mails_dedup={}

def do_eml(eml,endpos):
    eml["_size"]=endpos-eml["_fpos"]
#    eml['subject'] = hdrdecode(cleanupspaces(eml.get('subject',b'')))
    eml['subject'] = hdrdecode3( " ".join(eml.get('subject','').split()) )
#    eml['subject'] = hdrdecode(eml.get('subject','').strip())
    eml['from'] = parse_from(eml.get('from','<>'))
    mails_meta.append(eml)


def readfolder(f):
  eml=None
  in_hdr=0
  fpos=f.tell()
  for rawline in f:

    if in_hdr:
        fpos+=len(rawline)

        line=rawline.rstrip(b'\r\n')
        if len(line)==0:
            in_hdr=0
            eml["_hsize"]=fpos-eml["_fpos"]
        elif line[0] in [9,32]:
            hdr+=line
            continue

        if hdr:
            try:
                hdrname,hdrbody = hdr.split(b':',1)
                hdrname=hdrname.lower()
                if hdrname in [b'from',b'subject',b'x-deepspam']: # csak ezek kellenek
                    eml[hdrname.decode("us-ascii")]=decodeline(hdrbody)
            except:
                print("INVALID:",hdr,"\n   EXC:", traceback.format_exc() )

        hdr=line
        continue

    # in body:
    if rawline[0:5]==b'From ':
        if eml: do_eml(eml,fpos)
        in_hdr=1
        hdr=b''
        eml={"_fpos":fpos,"_from":decodeline(rawline.rstrip(b'\r\n'))}

    elif not eml: # and (rawline[:10]==b'X-Grey-ng:' or rawline[:9]==b'Received:'):
        in_hdr=1
        hdr=rawline.rstrip(b'\r\n')
        eml={"_fpos":fpos}

    elif rawline.startswith(b'Content-Disposition: attachment'):
        eml['_attach']=decodeline(rawline.rstrip(b'\r\n'))  # fixme multiline/parsing...
#        print(eml['_attach'])

    fpos+=len(rawline)

  if eml: do_eml(eml,fpos)
  print(fpos,eml)


def get_preview(yy):
    # preview?
    preview=mails_text[yy]
    if preview==None:
        mboxf.seek(mails_meta[yy]["_fpos"])
        preview=eml2str(mboxf.read(mails_meta[yy]["_size"]))
        preview=ucsremove(preview) # remove unicode shit
        preview=" ".join(preview.split()) # fix whitespace
#        preview=preview[:term_pl] # truncate to ~1000 chars
        mails_text[yy]=preview
        if ds: mails_deep[yy]=ds(preview) # use deepspam model

    if preview:
        try:
            if yy<mails_dedup[preview]:
                mails_flag[mails_dedup[preview]]|=2 # set DUP flag
                mails_dedup[preview]=yy
            elif yy>mails_dedup[preview]:
                mails_flag[yy]|=2 # set DUP flag
        except:
            mails_dedup[preview]=yy # never seen diz

    return preview

def get_deep(yy):
    if not ds: return "n/a",""
    d=mails_deep[yy]
    if not d: return "",""
    if d<0: return "short",""
    # !!!
    if d>=99.9: color=196
    elif d>=99: color=202
    elif d>=98: color=208
    elif d>=90: color=214
    elif d>=80: color=226
    elif d>=20: color=100 #fixme
    elif d>=10: color=154
    elif d>=2: color=118
    else: color=46
    return "%5.2f%%"%(d),"\x1b[30m\x1b[48;5;%dm"%(color)


####################################################################################################
###########                                   M A I N                                    ###########
####################################################################################################

t0=time.time()

fnev="test.mbox" if len(sys.argv)<2 else sys.argv[1]
mboxf=open(fnev,"rb")
if not mboxf.readline().startswith(b"From "): exit(0)

# META?
try:
    mails_meta=pickle.load(open(fnev+".meta","rb"))
    # seek after last known mail:
    lm=mails_meta[-1]
    mboxf.seek(lm["_fpos"]+lm["_size"])
except:
    mboxf.seek(0)

num_mails=len(mails_meta)
readfolder(mboxf)
if len(mails_meta)>num_mails:
    print("NUM changed %d -> %d"%(num_mails,len(mails_meta)))
    num_mails=len(mails_meta)
    if num_mails>10000: pickle.dump(mails_meta, open(fnev+".meta","wb")) # SAVE

# FLAGS?
try:
    mails_flag=pickle.load(open(fnev+".flag","rb"))
except:
    pass
mails_flag+=bytearray(num_mails-len(mails_flag))

# DEEPSPAM?
try:
    sys.path.append("/home/mailer4")
    from model import DeepSpam
    ds=DeepSpam(path="/home/mailer4/model/",device="cuda")   # load model
except:
    pass

# PREVIEW?
try:
    mails_text=open(fnev+".text","rt",encoding="utf-8",errors="ignore").read().split("\n")
    if ds:    # DEEPSPAM?
        print("Calculating deepspam values...")
        yy=0
        while yy<len(mails_text):
            mails_deep+=ds.evalbatch(mails_text[yy:yy+256]) # Batch eval
            yy+=256
            print(yy,end="\r")
except:
    pass

mails_text+=[None]*(num_mails-len(mails_text))
if ds: mails_deep+=[None]*(num_mails-len(mails_deep))

print("LOADED %d emails in %5.3f seconds"%(num_mails,time.time()-t0))

vocab={}
try:
    for line in open("/home/vocab/vocab.txt","rt",encoding="utf8"):
        l=line.split()
        vocab[l[0]]=int(l[1])
    print("VOCAB:",len(vocab))
except:
    pass

####################################################################################################

eol="\x1b[0K" # Note: Erasing the line won't move the cursor, meaning that the cursor will stay at the last position

MAILFLAG_SELECTED=1
MAILFLAG_DUP=2
MAILFLAG_READ=4
MAILFLAG_NEW=8
#MAILFLAG_ATTACH=16
MAILFLAG_DEL=32
MAILFLAG_EXTRA=64
MAILFLAG_LIST=128

filter_attach=0
filter_duplicate=1
filter_deleted=0
filter_selected=0
filter_extra=0
filter_list=0
mode_from=2
mode_preview=0

yy=num_mails-1
y0=0
xx=0
last_yy=-1
last_y0=-1
last_xx=-1


def m_step(old,dist):
    d=-1 if dist<0 else 1
    dist*=d
    while dist>0:
        old+=d
        if old<0 or old>=num_mails: break
        fl=mails_flag[old]
        if filter_deleted==0 and (fl&MAILFLAG_DEL): continue
        if filter_duplicate and (fl&MAILFLAG_DUP): continue
        if filter_deleted==2 and not (fl&MAILFLAG_DEL): continue
        if filter_selected==2 and (fl&MAILFLAG_SELECTED): continue
        if filter_selected==1 and not (fl&MAILFLAG_SELECTED): continue
        if filter_extra and not (fl&MAILFLAG_EXTRA): continue
#        if filter_attach and not (fl&MAILFLAG_ATTACH): continue
        if filter_attach and not "_attach" in mails_meta[old]: continue
        dist-=1
    return old

def drawline(pos,sel=False):
    if pos<0 or pos>=num_mails:
#        print(" "*term_w)
        print(eol) # erase from cursor to end of line
        return
    m=mails_meta[pos]
    fr=m["from"]
    fr=fr[1]+"  <"+fr[0]+">" if mode_from>1 else fr[mode_from]
#    fr=str(fr) if mode_from>1 else fr[mode_from]
    s=m["_size"]-m["_hsize"]
    fl=mails_flag[pos]
    dp,dc=get_deep(pos)
#    print("%s%s%s%s %*s%8d%s %*s%s"%(
    if ds: print("\x1b[0m"+dc+"%*s\x1b[0m"%(7,dp),end="")
    print("%s%s%s%s%s %*s\x1b[%dG%8d%s %*s%s"%(
        '\x1b[7m' if sel else '\x1b[0m',
        '\x1b[2m' if (fl & MAILFLAG_DUP) else '',
        '\x1b[1m' if (fl & MAILFLAG_SELECTED) else '',
        'D' if fl & (MAILFLAG_DEL) else ' ',
        '*' if fl & MAILFLAG_EXTRA else ' ',
        -term_w1, wcfixstr(fr)[xx:xx+term_w1],           # "from" shifted/trimmed
        term_w1, s, '+' if "_attach" in m else ' ',      # bodysize, attachment flag
        -term_w2, wcfixstr(m["subject"])[xx:xx+term_w2], # "subject" shifted/trimmed
        eol ))

#    if(yy==y){ set_color(7); g_y=i+2; } else set_color(0);
#      if(M_FLAGS(y)&MAILFLAG_SELECTED) set_color(1);


def drawall():
    global xx,yy,y0,last_yy,last_y0,last_xx
    if yy<m_step(-1,1): yy=m_step(-1,1)
    if yy>m_step(num_mails,-1): yy=m_step(num_mails,-1)
    if yy<y0: y0=yy
    if yy>=m_step(y0,term_h): y0=m_step(yy,-(term_h-1))
    if y0<m_step(-1,1): y0=m_step(-1,1)

    dedup=-1
    if mode_preview:
        preview=get_preview(yy) # prepare for proper DS results!
        if preview and preview in mails_dedup: dedup=mails_dedup[preview]

    # header:  [eadS+L+] 90749/90749 [172x37]  P:2108154475 S:6723  [2phWI]
    sys.stdout.write('\x1b[H')  # goto 0,0
    print("\x1b[0m\x1b[1m  [%s%s%s%s%s%s] %d/%d [%dx%d]  P:%d S:%d D:%s 1st:%d \x1b[0m%s"%(
        'E' if filter_extra else 'e',
        'A' if filter_attach else 'a',
        'D' if filter_deleted else 'd',
        '+' if filter_deleted==1 else '',
        'S' if filter_selected<2 else 's',
        '' if filter_selected else '+',
        yy,num_mails,term_w,term_h,mails_meta[yy]["_fpos"],mails_meta[yy]["_size"],get_deep(yy)[0],dedup,eol))

    # list of emails
    y=y0
    for j in range(term_h):
        sys.stdout.write('\x1b[%d;%df'%(j+2,1)) # screen goto x,y
        if (last_y0!=y0) or (last_xx!=xx) or (y==yy) or (y==last_yy): # minimal update
            drawline(y,y==yy)
#        else:
#            print('')
        y=m_step(y,1)
    last_xx=xx
    last_yy=yy
    last_y0=y0

    # preview
    if mode_preview:
        print('\x1b[0m\x1b[%d;%df'%(term_h+2,1), '═'*term_w) # reset color, goto, hline
        if ds and 0:
            preview=ds.tokenized([preview])[0]
            print(wcfixstr(preview)[:term_pl],'\x1b[0J') # erase to end of screen
        elif len(vocab)<100:
            print(wcfixstr(preview)[:term_pl],'\x1b[0J') # erase to end of screen
        else:
            line=wcfixstr(preview)[:term_pl]
            for t in vocab_split(line):
                sys.stdout.write('\x1b[1m' if t.lower() in vocab else '\x1b[0m') # color
                sys.stdout.write(t)
            sys.stdout.write('\x1b[0J') # clear the rest

    sys.stdout.write('\x1b[0m\x1b[H')  # reset color, goto 0,0
    sys.stdout.flush()

while True:
 clrscr()
 last_y0=-2 # force full redraw!
 with NonBlockingInput():
  try:
   while True:
    drawall()
    ch=getch2()
    if ch=="q": break
    if ch=="up":   
        yy=m_step(yy,-1)
        continue
    if ch=="down":
        yy=m_step(yy,1)
        continue
    if ch=="ins": # Invert selection
        mails_flag[yy]^=MAILFLAG_SELECTED
        if m_step(yy,1)<num_mails: yy=m_step(yy,1)
        elif m_step(yy,-1)>=0: yy=m_step(yy,-1)
        else: yy=0
        if filter_selected==0: continue # no redraw needed
    if ch=="del": # Invert deletion
        mails_flag[yy]^=MAILFLAG_DEL
        if m_step(yy,1)<num_mails: yy=m_step(yy,1)
        elif m_step(yy,-1)>=0: yy=m_step(yy,-1)
        else: yy=0
        if filter_deleted==1: continue # no redraw needed
    if ch=="e": # Extra selection
        mails_flag[yy]^=MAILFLAG_EXTRA
        if m_step(yy,1)<num_mails: yy=m_step(yy,1)
        elif m_step(yy,-1)>=0: yy=m_step(yy,-1)
        else: yy=0
        if filter_extra==0: continue # no redraw needed

    last_y0=-2 # force full redraw!

    if ch=="pgup": yy=m_step(yy,-(term_h-1))
    if ch=="pgdn": yy=m_step(yy,(term_h-1))
    if ch=="home": yy=0
    if ch=="end":  yy=num_mails
    if ch=="left" and xx>0: xx-=5
    if ch=="right": xx+=5
    if ch=="f": mode_from=(mode_from+1)%3
    if ch=='d': filter_deleted=(filter_deleted+1)%3
    if ch=='?': filter_selected=(filter_selected+1)%3
    if ch=='a': filter_attach^=1
    if ch=='E': filter_extra^=1

    if ch=='l':
        ret=box_input(0,0,"Goto line:","")
        try:
            yy=int(ret)
        except:
            pass

    # preview mode/generation:
    if ch=='p':
        term_h+=8 if mode_preview else -8
        mode_preview^=1
#        if not mode_preview: y0=m_step(y0,-8)
    if ch=='P': # generate previews
        for y in range(num_mails):
            if (y%100)==0: box_message(["generating previews","","%10d/%d"%(y,num_mails)])
            get_preview(y)
        if len(mails_text)>=2000: open(fnev+".text","wt",encoding="utf-8",errors="ignore").write("\n".join(mails_text))

    if ch=='enter':
        mboxf.seek(mails_meta[yy]["_fpos"])
        mimeinfo,mimedata=get_mimedata(mboxf.read(mails_meta[yy]["_size"]))
        sel=box_message(mimeinfo,y=0)
        if sel<0: continue
        open("/tmp/mailer4.tmp","wb").write(mimedata[sel])
        break
  except:
#   print("\n!!!!!! EXC:", traceback.format_exc(), "!!!!!!" )
   sel=box_message(traceback.format_exc().splitlines(),y=0)
   if sel<0: break

 clrscr()
 if sum(x!=0 for x in mails_flag):
    pickle.dump(mails_flag, open(fnev+".flag","wb"))
 if ch=="q": break # quit
 if ch=="enter":
    # start viewer!
    os.system("mcedit --nosubshell /tmp/mailer4.tmp")
#    os.system("mcview --nosubshell /tmp/mailer4.tmp")

