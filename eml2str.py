
import io
import codecs
import email
import email.policy
import re
from bs4 import BeautifulSoup
from html import unescape  #  https://docs.python.org/3/library/html.html
#from html.entities import name2codepoint

def mixed_decoder(unicode_error):
    position = unicode_error.start
    new_char = unicode_error.object[position:position+1]
    new_char = new_char.decode("iso8859-2","ignore")
#    print(type(new_char))
#    print(len(new_char))
    return new_char, position + 1

codecs.register_error("mixed", mixed_decoder)


#HTML_RE = re.compile(r'&([^;]+);')
#def html_unescape(mystring):
#  return HTML_RE.sub(lambda m: chr(name2codepoint.get(m.group(1),63)), mystring)

def replaceEntities(s):
    x = s.group(0)
    s = s.group(1)
#    print(s) #  '#43'
    if s[0] == "#":
        if s[1] in ['x','X']:
            c = int(s[2:], 16)
        else:
            c = int(s[1:])
        if 0xD800 <= c <= 0xDFFF or c > 0x10FFFF:
            return '\uFFFD'
        if c>=128: # ekezetes karakter, nem irasjel
            return chr(c)
    return x # beken hagyjuk

#    r_unescape = re.compile(r"&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));") # ez erre is matchel:   &nbsp;
r_unescape = re.compile(r"&(#[xX]?[0-9a-fA-F]+);") # de nekunk csak az ekezetes betu unikodok kellenek!
def xmldecode(data):
  return r_unescape.sub(replaceEntities, data)


#  <meta content="text/html; charset=utf-8" http-equiv="Content-Type"/>
#  <meta content="utf-8" name="charset"/>
#  <meta charset="utf-8"/>

def parse_htmlhead(data,charset=None):
  for ret in data.split(b'<'):
    tag=ret.split(b'>')[0].lower()
    if tag.startswith(b'meta'):
      p=tag.find(b'charset=')
      if p>=0:
#        print(tag)
        charset=""
        for c in tag[p+8:]:
          if c<=32: continue  # whitespace
          if c==34 or c==39:  # idezojelek
            if charset: break
            continue
          if not c in b'-0123456789abcdefghijklmnopqrstuvwxyz': break
          charset+=chr(c)
#        print('CHARSET='+charset)
        if charset: break
  return charset


def html2text(data):
  in_style=0
  in_script=0

#  data=HTML_comment.sub("<comment>",data)
  p=data.find(b'<!--')
  while p>=0:
    q=data.find(b'-->',p)
    if q<p:
      data=data[:p]
      break
#    data=data[:p]+" HTMLcomment "+data[q+3:]
    data=data[:p]+data[q+3:]
    p=data.find(b'<!--',p)

  text=b''
  for ret in data.split(b'<'):
    try:
      tag,txt=ret.rsplit(b'>',1) # pl.: <img width="600" height="87" alt="Csak a Minősített Fogyasztóbarát Lakáshitel érdekel >>" style="display:block...">text
    except:
      text+=ret
      continue
#      print(ret.encode("utf-8"))
#      break
#    print("TAG: '%s'"%(tag))

    tag=tag.lower()
    if b'style' in tag: # detect hidden text!
#  <span style="display:none;font-size:1px;color:#ffffff;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
#  <div style="display:none !important; font-size:1px; color:#f0f0f0; line-height:1px; font-family:arial,helvetica,sans-serif; max-height:0px; max-width:0px; opacity:0; overflow:hidden; mso-hide:all;">
#  <div style="mso-hide:all; display:none!important; height:0; width:0px; max-height:0px; overflow:hidden; line-height:0px; float:left; font-size:0px;">
#  Teams: <div itemprop="signedAdaptiveCard" style="mso-hide:all;display:none;max-height:0px;overflow:hidden;">eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsIng1YyI6Ik1JSUhIekND...
# {{ uCteNf>}} Hell{{ Eywzmggb>}}o part{{ GYWmIbcB>}}ner {{ LEFWx>}} uni-obuda outgoing We are th{{ WoXAGS>}}e biggest distributor and fac{{ xRCXTNI>}}tory of or{{ TvUsbw
# ATTN:rudas@uni-obuda.hu {{emilia daniel oscar}} How are you? Greeting from Retek Logistics This is Victoria, Wish you {{grace nancy}}to {{amy thomas}}enjoy {{arthur alex
# <div style="font-size:0px;line-height:1px;mso-line-height-rule:exactly;display:none;max-width:0px;max-height:0px;opacity:0;overflow:hidden;mso-hide:all;">preview
#   <span style="FONT-SIZE: 0px; FONT-FAMILY: q; LINE-HEIGHT: normal; font-stretch: normal"> random...
#   <div class="preheader" style="display:none;font-size:1px;color:#333333;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">preview
#  <span class="es-preheader" style="display:block !important;font-size:0px;font-color:#ffffff;">
        tag=tag.replace(b': ',b':')
#        if b'font-size:0' in tag or b'display:none' in tag or b'max-height:0' in tag or b'mso-hide:all' in tag or b'opacity:0' in tag:
        if b'display:none' in tag or b'font-size:0p' in tag or b'font-size:1p' in tag or b'max-height:0p' in tag or b'mso-hide:all' in tag or b'opacity:0' in tag:
            if b'signedadaptivecard' in tag: continue # ms teams hidden base64 data!!!
#            if len(txt.strip())>=5: 
#            text+=b'HIDE{'+tag+b'|'+txt+b'}' # debug
            if b'display:none' in tag and len(text.strip())==0:
                if len(txt.strip())>=3: text+=b'['+txt+b'] ' # preview header  https://responsivehtmlemail.com/html-email-preheader-text/
#            else:
#                if len(txt.strip())>=3: text+=b'{{'+txt+b'}}' # hidden text
            continue

    try:
      tag1=tag.split()[0].lower()
    except:
#      print("TAG parse error: '%s'"%(str(tag)))
      tag1=""

    if tag1==b'style':
      in_style+=1
    if tag1==b'/style':
      in_style-=1
    if tag1==b'script':
      in_script+=1
    if tag1==b'/script':
      in_script-=1
#    print(tag1)
#    print(text)
    if in_style<=0 and in_script<=0:
#      if tag1 in ["p","span","div"]: print(tag.lower())
#      if tag1 in [b'p',b'br',b'td',b'div',b'li',b'pre',b'blockquote']: text+=b'\n'  # https://www.w3schools.com/html/html_blocks.asp
      if tag==b'div' or tag1 in [b'p',b'br',b'br/',b'tr']: text+=b'<BR>'  # https://www.w3schools.com/html/html_blocks.asp
      else:
#        if tag1.startswith(b'/'): tag1=tag1[1:] # closing tag
        if tag1[:1]==b'/': tag1=tag1[1:] # closing tag
        if not tag1 in [b'span',b'a',b'b',b'i',b'u',b'em',b'strong',b'abbr']: text+=b' ' # not inline elements
#      text+=txt.strip() # test/fixme
#      text+=b' '.join(txt.split()) # whitespace...
      text+=txt

  return (b' '.join(text.split())).replace(b'<BR>',b'\n')

def is_utf8(s):
#    l=len(s)
    n=sum(c>=192 for c in s) # n# of utf8 characters
    m=sum(c>=128 for c in s) # n# of utf8 bytes
    return n>=5 and m>=2*n


def decode_payload(data,ctyp="text/html",charset=None):

    ldata=data.lower()
    if ctyp=="text/html" or ctyp=="text/xml" or ((ctyp!="text/plain" or b'</head>' in ldata) and b'<' in ldata and (ldata.find(b'<body')>=0 or ldata.find(b'<img ')>=0 or ldata.find(b'<style')>=0 or ldata.find(b'<br>')>=0 or ldata.find(b'<center>')>=0 or ldata.find(b'<a href')>=0)):
        p=ldata.find(b'<body')
        if p>0:
            charset=parse_htmlhead(data[:p],charset) # parse charset override from <head>
            data=data[p:] # skip html header, start at <body>
        data=html2text(data)  # binary version

    if not charset:
      charset="iso8859-2"
    elif charset=="cp-850":
      charset="cp850"
    elif charset=="_iso-2022-jp$esc":
      charset="iso-2022-jp"
    elif charset=="iso-8859-8-i":
      charset="iso-8859-8"
    elif charset=="windows-874":
      charset="cp874"
    elif charset=="x-mac-ce":
      charset="maccentraleurope"
    elif charset[0:4]=="utf8":
      charset="utf-8"

    # Try UTF-8:
    if charset=="utf-8" or is_utf8(data):
        try:
            data=data.decode("utf-8", 'strict')
            return unescape(data) # fix &gt; etc
        except UnicodeDecodeError as e:
#            print(repr(e))
            print('BadUTF8, CHARSET='+charset)
            pass

#    print('CHARSET='+charset)
    try:
        data=data.decode(charset, 'mixed')
    except LookupError: # nincs 'charset' nevu kodlap:
        data=data.decode("utf-8", 'mixed') # lehet inkabb latin2 kene eleve?

#    try:
#        data=data.decode(charset, 'mixed')
#    except:
#        data=data.decode("utf-8", 'mixed')
#    data=xmldecode(data) # plaintextre is rafer...
    return unescape(data) # fix &gt; etc

def eml2str(msg):
  if isinstance(msg, io.IOBase):
    msg = email.message_from_binary_file(msg)
  elif type(msg)==bytes:
    msg = email.message_from_bytes(msg)
  text=""
  #pp = msg.get_payload()
  for p in msg.walk():
#    print p.get_content_type()
    charset=p.get_content_charset("utf-8")
    ctyp=p.get_content_type().lower()
    fnev=str(p.get_filename())
    disp=p.get_content_disposition()
#    print((ctyp,charset,disp,fnev))
    if ctyp.split('/')[0]=="text" and disp!="attachment":
#      try:
        data=p.get_payload(decode=True)
        data=decode_payload(data,ctyp,charset)
        if not text or len(data)>20: text=data
        if ctyp=="text/html" and len(text)>200: break
#        if len(data)>len(text): text=data
#        print(text)
#      except:
#        print(traceback.format_exc())
  return text


def get_mimedata(eml):
    mimeinfo=["RAW message: %d bytes"%(len(eml))]
    mimedata=[eml]
    msg = email.message_from_bytes(eml, policy=email.policy.default)
    def walker(msg,level=0):
#        print(" "*(level*3), msg.is_multipart(), msg.get_content_type(), msg.get_content_charset(), msg.is_attachment(), msg.get_filename())
#        s=" "*(level*3) + "Multi:"+str(msg.is_multipart())+"  "+str(msg.get_content_type())
        ctyp=msg.get_content_type()
        cset=msg.get_content_charset()
        s=" "*(level*3) + str(ctyp) # + str(msg.is_multipart())
        if cset: s+="["+str(cset)+"]"
        raw=msg.as_bytes()
        s+=" (%d) "%(len(raw))
        pay=msg.get_payload(decode=True)
        html=None
        if pay:
            s+="%d"%(len(pay))
            if ctyp.startswith("text/"):
                html=decode_payload(pay,ctyp,cset) # ez meg a soup-prettify elott kell, mert az elbassza a whitespacet...
                if ctyp=="text/html" or ctyp=="text/xml":
                    html="\n".join([" ".join(s.split()) for s in html.splitlines() if s]) # remove empty lines and redundant spaces
#                soup=BeautifulSoup(pay,features="lxml", from_encoding=cset)
#                soup=BeautifulSoup(pay,"html.parser")
                    soup=BeautifulSoup(pay,"html5lib", from_encoding=cset)
                    pay=soup.prettify(encoding="utf-8")
#                html=soup.get_text()
#            elif cset and cset.lower()!="utf-8":   #  plaintext eseten itt kezeljuk a charset kerdest...
#            else:
#                pay=pay.decode(cset,errors="ignore").encode("utf-8")
#                pay=decode_payload(pay,ctyp,cset).encode("utf-8",errors='xmlcharrefreplace') # plaintexthez is jo
#                s+=" {%d}"%(len(pay))
        mimeinfo.append(s)

        # Attachment file:
        if msg.get_filename():
            mimedata.append(raw)
            s=" "*(level*3+3)
            s+="Attach: " if msg.is_attachment() else "Inline: "
            s+=msg.get_filename()
            mimeinfo.append(s)
        mimedata.append(pay if pay else raw)

        # HTML: add Extracted text
        if html:
            pay2=html.encode("utf-8",errors='xmlcharrefreplace')
            if pay!=pay2:
                mimedata.append(pay2)
                mimeinfo.append(" "*(level*3+3)+"Extracted text: "+str(len(html))+"/"+str(len(pay2)))

#        for subpart in msg.iter_parts():  # policy=email.policy.default
#            walker(subpart,level+1)
        if msg.is_multipart():
            for subpart in msg.get_payload():  # az iter_parts() bugos, csak multipartra jo, message/rfc-re NEM!!!
                walker(subpart,level+1)

#        if msg.is_multipart():
#            for subpart in msg.get_payload(): # policy=email.policy.compat32
#                walker(subpart,level+1)
    walker(msg)
    return mimeinfo,mimedata




def vocab_split(preview):
    tok=[]
    s=""
    inw=False
    for c in preview:
        if c in '\n\t #".,!?;:-+/*()[]0123456789':
            if inw:
                tok.append(s)
                s=c
                inw=False
                continue
            s+=c
            continue
        if inw:
            s+=c
            continue
        tok.append(s)
        s=c
        inw=True
    tok.append(s)
    return tok





if __name__ == "__main__":
#    s='&nbsp;&nbsp; Elküldve: 2023. május 31. 13:06:16 (UTC&#43;01:00) Belgrád, Budapest, Ljubljana, Pozsony, Prága<br>'
#    print(s)
#    print(xmldecode(s))
#    print(html_unescape(s))
    
#    print(eml2str(open("test.eml","rb").read()))
#    print(get_mimedata(open("test.eml","rb").read())[0])

#    msg = email.message_from_bytes(open("test.eml","rb").read(), policy=email.policy.default)
#    print(type(msg))
#    help(msg)

#    print(parse_htmlhead(b'  <meta charset="utf-8"/>'))
#    print(parse_htmlhead(b'<meta content="text/html; charset=utf-8" http-equiv="Content-Type"/>'))
#    t=b'<p>Hello<em>World</em>!!! em</p>'
    t=b'<p>Hello<i>World</em>!!! em</p>'
    print(t)
    print(html2text(t))

