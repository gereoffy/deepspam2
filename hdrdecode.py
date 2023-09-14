
import os
import sys
import syslog
import codecs
from email.header import decode_header,make_header


try:
    import encodings
    encodings.aliases.aliases['238'] = 'cp1250'
    encodings.aliases.aliases['win_1251'] = 'cp1251'
    encodings.aliases.aliases['204'] = 'cp1251'
except:
    pass


syslog_levels=[syslog.LOG_DEBUG,syslog.LOG_INFO,syslog.LOG_WARNING,syslog.LOG_ERR,syslog.LOG_INFO]

def str_sanitize(s):
    ret=""
    for c in s:
        if ord(c)>=32 and ord(c)<127 or ord(c)==10:
            ret+=c
        else:
#            ret+="#%02X"%(ord(c))
            ret+="&#%d;"%(ord(c))
    return ret

log_name=""
log_syslog=False

def init_log(name,sl=True):
    global log_name
    global log_syslog
    if name: log_name="%s[%d] "%(name,os.getpid())
    if sl:
        try:
            syslog.openlog(name,syslog.LOG_PID,syslog.LOG_MAIL)
            log_syslog=True
#  log(1,"PPID: %d"%(os.getppid()))
        except:
            print("SYSLOG error !!!!!!!!!")

    if sys.stderr.encoding != 'UTF-8':
        log(0,"stderr.encoding: "+sys.stderr.encoding)
        try:
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'xmlcharrefreplace')
        except:
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr, 'xmlcharrefreplace')

def log(level,text):

#    if type(text)==unicode:
##        sys.stderr.write("mail2sql[%d] %d: %s\n"%(os.getpid(),3,"log() called with unicode string!"))
##        log_data.append((3,"log() called with unicode string!"))
#        text=text.encode("latin2","xmlcharrefreplace")

    stext=str_sanitize(text)

#    if logout:
#        logout.write(text+"\n")

#    log_data.append((level,text))

    if level>=0:
        try:
            sys.stderr.write(log_name+"%d: %s\n"%(level,text))
        except:
            sys.stderr.write(log_name+"%d: %s\n"%(level,stext))

    if log_syslog and level>0:
        syslog.syslog(syslog_levels[level],stext)

#    print "%s: %s" % (level,text)



def cleanupspaces(s,split=0):
    q=0
    e=0
    z=0
    a=0
    s2=""
    comm=""
    addr=""
    p=0
    for c in s:
        if e:
            e=0
        elif c=='\\':
            e=1
        else:
            if c=='"':
                q=1-q
            if q==0:
                if c=='(':
                    z+=1
                elif c==')':
                    z-=1
                    if split:
                        comm+=c
                        continue
                elif c=='<':
                    a+=1
                elif c=='>':
                    a-=1
                    if split:
                        addr+=c
                        continue
                elif c=='\t' or c=='\n' or c=='\r':
                    c=' '
                if c==' ' and p==c and z==0 and a==0:
                    continue
        if split:
            if z>0:
                comm+=c
                continue
            if a>0:
                addr+=c
                continue
        s2+=c
        p=c
    if e:
        log(1,"WARNING! escape?")
    if q:
        log(1, "WARNING! doublequote? "+s)
    if z!=0:
        log(1, "WARNING! parenthesis? "+s)
#        print "!%d!s='"%(mailno) +s+ "'"
    if split:
        return (s2.strip(),comm,addr)
    return s2.strip()

def splithdr(s,sep=' '):
    sa=[]
    q=0
    e=0
    z=0
    s2=""
    for c in s:
        if e:
            e=0
        elif c=='\\':
            e=1
        else:
            if c=='"':
                q=1-q
            if q==0:
                if c=='(':
                    z+=1
                elif c==')':
                    z-=1
                elif z==0 and c==sep:
                    sa.append(s2.strip())
                    s2=""
                    continue
        s2+=c
    if z!=0:
        log(1, "WARNING! parenthesis?")
    sa.append(s2.strip())
    return sa

def qstrip(s):
    try:
        while s[0:1]==' ':
            s=s[1:]
        while s[-1:]==' ':
            s=s[:-1]
        if s[0:1]=='"' and s[-1:]=='"':
            s=s[1:-1]
        if s[0:1]=="'" and s[-1:]=="'":
            s=s[1:-1]
#        if s[0:1]=='<' and s[-1:]=='>':
#            s=s[1:-1]
        if s[0:1]=='(' and s[-1:]==')':
            s=s[1:-1]
        if s[0:1]=='[' and s[-1:]==']':
            s=s[1:-1]
        if s[0:1]=='{' and s[-1:]=='}':
            s=s[1:-1]
        while s[0:1]==' ':
            s=s[1:]
        while s[-1:]==' ':
            s=s[:-1]
    except:
        log(1, "QSTRIP:"+s+" EXC:%s" % (traceback.format_exc()) )
    return s

def isatext(s):
    for c in s:
        if not (c in "!#$%&'*+-/=?^_`{|}~0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
#            print "!isatext: "+c
            return 0
    return 1

def isemailaddr1(s):
    if s.find('@')<0:
        if s=="<>":
            return s
        if s.upper()=="MAILER-DAEMON":
            return "MAILER-DAEMON"
        return None
    if s[0:1]=='<':
        if s[-1:]=='>':
            s=s[1:-1].rstrip(' ')
    kukac=0
    for c in s:
        if not (c in ".@_~=!#$%&*/+-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            return None
        if c=='@':
            kukac+=1
    if kukac==1:
        return s
    return None

def isemailaddr(s):
    if s.find('@')<0:
        if s=="<>":
            return s
        if s.upper()=="MAILER-DAEMON":
            return s
        return ""
    if s[0:1]=='<':
        if s[-1:]=='>':
            s=s[1:-1].rstrip(' ')
    kukac=0
    quote=0
    for c in s:
        if c=='"':    # <"@'"@oran.umsa.bo>
            quote^=1
            continue
        if quote:
            continue
        if not (c in ".@_~=!#$%&*+-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            return 0
        if c=='@':
            kukac+=1
    if kukac==1:
        return s
    return ""







def parse_received(s):
    rec={}
    z=0
    state=0
    typ=""
    param=""
    comm=""
    for c in s:
        if c=='(':
            z+=1
            state=2
        elif c==')':
            comm+=c
            z-=1
            continue
        if z>0:
            comm+=c
            continue
        if c==';':
            break;
        if c==' ' or c=='\t' or c=='\n' or c=='\r':
            state+=1
            continue
        # nem zarojel, nem comment es nem whitespace
        # print "state=%d c=%c" % (state,c)
        if state>=2:
#            print "TYPE='"+typ+"' PARAM='"+param+"' COMM='"+comm+"'"
            if typ:
                rec[typ]=(param,comm)
            typ=""
            param=""
            comm=""
            state=0
        if state==0:
            typ+=c
        else:
            param+=c
    if typ:
#        print "TYPE='"+typ+"' PARAM='"+param+"' COMM='"+comm+"'"
        rec[typ]=(param,comm)
    return rec


# From: COMM=(IEEE) ADDR=<noreply@webofscience.com> NEV=Institute of Electrical and Electronics Engineers Inc.
# From: COMM=(Megrendel=C3=A9sek) ADDR=<megrendeles@okosotthon.bolt.hu> NEV==?UTF-8?Q?OkosOtthon=20Bolt=20?=

def parse_from(hdrbody):
            try:
#                    sa=splithdr(cleanupspaces(hdrbody))
#                    print hdrname+":"+str(sa)
                    sa=splithdr(cleanupspaces(hdrbody),',')
#                    has_from+=len(sa)
                    for aa in sa:
                        cim=None
                        nev=""
                        if aa:
                          if aa.find(' ')<0 and aa.find('<')<0:
                            cim=isemailaddr(aa)
                          else:
                            nev,comm,addr=cleanupspaces(aa,1)
#                            log(0,"From: COMM=%s ADDR=%s NEV=%s" % (comm,addr,nev) )
                            if addr:
                                cim=isemailaddr(addr)
                                if cim:
                                    #log(0,hdrname+": "+cim)
                                    if nev:
                                        nev=qstrip(cleanupspaces(nev))
                                        nev=qstrip(hdrdecode(nev))
                                #        if nev!=cim:
                                #            log(0,hdrname+"_name: "+nev)
                                else:
                                    log(1, "HIBAS1:"+addr+" RAW:"+aa)
#                                    has_error+=1
                            else:
                                cim=isemailaddr(nev)
                                if cim:
                                #    log(0,hdrname+": "+cim)
                                    nev=qstrip(comm)
                                #    if nev and nev!=cim:
                                #        log(0,hdrname+"_name: "+comm)
                                else:
                                    log(1, "HIBAS2:"+nev+" RAW:"+aa)
#                                    has_error+=1

                        if cim:
                            if nev and nev!=cim:
#                                log(0,hdrname+": ["+nev+"] <"+cim+">")
                                #add_addr(hdrname,cim,nev)
                                return (cim,nev)
                            else:
#                                log(0,hdrname+": <"+cim+">")
#                                if comm: print(cim,comm)
                                return (cim,cim)
#                                add_addr(hdrname,cim,None)

            except:
                log(1, "INVALID From:"+str(hdrbody)+" EXC:%s" % (traceback.format_exc()) )
#                traceback.print_exc()
            return ("ERROR",hdrbody)

def decodeline(rawline):
        # python3  (stdin binaris (bytes) modban!)
        try:
            line=rawline.decode("us-ascii","strict")
        except:
            try:
                line=rawline.decode("utf-8","strict")
                log(0,str(rawline))
                log(0,"readline: invalid 7bit encoding, fallback to: utf8")
            except UnicodeDecodeError:
                line=rawline.decode("latin2","ignore")
                log(0,str(rawline))
                log(0,"readline: invalid utf8 encoding, fallback to: latin2")
        return line





def hdrdecode3(h):
    # python 3.x
    dh=decode_header(h)
#    return ''.join((item[0].decode(item[1] or 'utf-8') for item in dh))
#    print(dh)
    s=""
    for b,c in dh:
#        print(type(b),b,c)
        if isinstance(b, str): # not encoded
            s+=b
            continue
        if c==None:
            s+=b.decode("raw-unicode-escape") # py3 email lib uses this coding...
            continue
        try:
#            d=b.decode(c or "utf-8",errors="strict")
            d=b.decode(c or "utf-8",errors="backslashreplace")
        except:
            log(1,"MIME: hdr encoding error, unknown encoding... fallback to latin2")
            d=b.decode("latin2",errors="ignore") # fallback
        s+=d
    return s


def hdrdecode(h):

    try:
        # python 2.7
        s=unicode(make_header(decode_header(h.replace("?==?","?= =?"))))
    except UnicodeDecodeError:
        try:
            s=h.decode("utf8",errors="strict")
            log(1,"MIME: hdr encoding error, detected: utf8")
        except UnicodeDecodeError:
            s=h.decode("latin2",errors="ignore")
            log(1,"MIME: hdr encoding error, fallback to: latin2")
    except LookupError:
        s=h.decode("latin2",errors="ignore")
        log(1,"MIME: hdr encoding error, unknown encoding... fallback to latin2!")

    except NameError:
        # python 3.x
        try:
            s=str(make_header(decode_header(h)))
#            print(ssssss)
#        except UnicodeDecodeError:
        except:
            d=[]
            for b,c in decode_header(h):
                if not c:
                    c="us-ascii"
                try:
                    b.decode(c,"strict")
                except:
                    c="utf-8"
                    try:
                        b.decode(c,"strict")
                    except:
                        log(1,"MIME: hdr encoding error, unknown encoding... fallback to latin2")
                        c="latin2"
                d.append((b,c))
            try:
                s=str(make_header(d))
                log(1,"MIME: mixed hdr encoding detected")
            except:
                log(1,"MIME: hdr encoding error")
                s=h

    return s




def hdrdecode_old3(h):
    try:
        # python 2.7
        s=unicode(make_header(decode_header(h.replace("?==?","?= =?"))))
    except UnicodeDecodeError:
        try:
            s=h.decode("utf8",errors="strict")
            log(1,"MIME: hdr encoding error, detected: utf8")
        except UnicodeDecodeError:
            s=h.decode("latin2",errors="ignore")
            log(1,"MIME: hdr encoding error, fallback to: latin2")
    except NameError:
        # python 3.x
        try:
            s=str(make_header(decode_header(h)))
        except UnicodeDecodeError:
            d=[]
            for b,c in decode_header(h):
                if not c:
                    c="us-ascii"
                try:
                    b.decode(c,"strict")
                except:
                    c="utf-8"
                    try:
                        b.decode(c,"strict")
                    except:
                        c="latin2"
                d.append((b,c))
            try:
                s=str(make_header(d))
                log(1,"MIME: mixed hdr encoding detected")
            except:
                log(1,"MIME: hdr encoding error")
                s=h

    return s









def hdrdecode_old2(h):
    try:
        try:
            s=unicode(make_header(decode_header(h.replace("?==?","?= =?"))))    # python 2.7
        except NameError:
            s=str(make_header(decode_header(h)))     # python 3.x
    except UnicodeDecodeError:
        try:
            s=h.decode("utf8",errors="strict")
            log(1,"MIME: hdr encoding error, detected: utf8")
        except UnicodeDecodeError:
            s=h.decode("latin2",errors="ignore")
            log(1,"MIME: hdr encoding error, detected: latin")
    return s





def hdrdecode_old(h):
    try:
        return unicode(make_header(decode_header(h.replace("?==?","?= =?"))))
    except NameError:
        pass
    return str(make_header(decode_header(h)))





#From: Tunyogi =?iso-8859-2?Q?D=F3ra?= <tunyogi.dora@bgk.uni-obuda.hu>


import codecs
try:
    uni_str=unicode  # python2
except NameError:
    uni_str=str      # python3

# inspired by Header.py::__unicode__()
def hdrdecode2(h):
#    log(0,"hdrdecode: '%s'" % h)
    if not h:
        return uni_str("")
    uchunks = []
    last = None

    for s,enc in decode_header(h.replace("?==?","?= =?")):
#    for s,enc in decode_header(h):
#        print("'"+s+"'")
        print("'"+s.decode("latin2","xmlcharrefreplace")+"'")
        print(len(s))
        print(enc)
        if uchunks and 1:
            if last not in (None, 'us-ascii'):
                if enc in (None, 'us-ascii'):
                    uchunks.append(uni_str(' '))
            else:
                if enc not in (None, 'us-ascii'):
                    uchunks.append(uni_str(' '))
        last=enc
        try:
            uchunks.append(codecs.decode(s,enc or "latin2"))
        except:
            uchunks.append(codecs.decode(s,"latin2"))
    return uni_str('').join(uchunks)




if __name__ == "__main__":
#    h="From: Tunyogi =?iso-8859-2?Q?D=F3ra?==?iso-8859-2?Q?=F3ra?= <tunyogi.dora@bgk.uni-obuda.hu>"
#    h='Content-Type: application/octet-stream;	name="=?UTF-8?Q?Pr=C3=A9visualiser_la_pi=C3=A8ce_jointe_Learning_agreement_sem_2_M?=	=?UTF-8?Q?arion_Doublet_=2EpdfLearning_agreement_sem_2_Marion_Doublet_=2Ep?=	=?UTF-8?Q?df846_K=2Eurl?="'
#    h='Subject: =?UTF-8?B?W0U6c3BhbV0g?= =?238?Q?Folyamatok_n=E9lk=FCl_nincs_=FCgyf=E9lszolg=E1lat?='
#    h='Subject: Nemzetk=?UTF-8?B?w7Z6aSB0dWRvbcOhbnlvcyByZW5kZXp2w6lueWVr?=, Bulg=?UTF-8?B?w6FyaWE=?='

    h='Subject: emlékeztető =?utf-8?Q?utols=C3=B3_eml=C3=A9keztet=C5=91_:_=C3=9Aj_=E2=84=A?= =?utf-8?Q?E.on_e-sz=C3=A1mla_k=C3=A9sz=C3=BClt?='
#    h='Subject: =?utf-8?Q?utols=C3=B3_eml=C3=A9keztet=C5=91_:_=C3=9Aj_=E2=84=A?='

    for a,b in decode_header(h): print(a,b)

#    hd=str(make_header(decode_header(h)))
    hd=hdrdecode3(h)

#    print(str_sanitize(hd))
    print(hd)
    exit(1)


#    j='From: "Webmail.Uni-Obuda.Hu" <"@\'"@oran.umsa.bo>'
#    print(parse_from(j))
#    exit()
    


    h='Content-Description:\n =?iso-8859-2?B?TW96Z+Fz6XJ66WtlbOlzX0hvbnbhcmkgRXJpa2FfMjAyMW3hajI2LmRv?=\n =?iso-8859-2?Q?cx?='

#Content-Disposition: attachment;
#    filename="=?iso-8859-2?B?TW96Z+Fz6XJ66WtlbOlzX0hvbnbhcmkgRXJpa2FfMjAyMW3hajI2LmRv?=
# =?iso-8859-2?Q?cx?="; size=1470962;


    hd=hdrdecode(h)
    print(str_sanitize(hd))
    print(hd)

    exit(1)

    hd=hdrdecode2(h)
    print(str_sanitize(hd))
    print(hd)

    hd=hdrdecode3(h)
    print(str_sanitize(hd))
    print(hd)


    hdrbody=' " " <lehotai.lilla@kgk.bmf.hu>'
    sa=splithdr(cleanupspaces(hdrbody),',')
    for aa in sa:
        print(aa)
        if aa:
                          if aa.find(' ')<0 and aa.find('<')<0:
                            print(isemailaddr(aa))
                          else:
                            nev,comm,addr=cleanupspaces(aa,1)
                            print("To: COMM=%s ADDR=%s NEV=%s" % (comm,addr,nev) )
                            if addr:
                                cim=isemailaddr(addr)
                                if cim:
                                    #log(0,hdrname+": "+cim)
                                    if nev:
                                        nev=qstrip(cleanupspaces(nev))
                                        nev=qstrip(hdrdecode(nev))
                                        print("nev='"+nev+"'")

