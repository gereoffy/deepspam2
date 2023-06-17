
import io
import codecs
import email
import email.policy
import re
from bs4 import BeautifulSoup
from html import unescape  #  https://docs.python.org/3/library/html.html
#import html5lib # testing
#from html.entities import name2codepoint


charset_mapping = {
    'cp-850':              'cp850',
    '_iso-2022-jp$esc':    'iso-2022-jp',
    'windows-874':         'cp874',
    'x-mac-ce':            'maccentraleurope',
    'iso-8859-8-i':        'iso-8859-8',
    'utf8':                'utf-8',
    'unicode-1-1-utf-8':   'utf-8',
    'utf-16':              'utf-16le',

    # source: /usr/local/lib/python3.10/dist-packages/webencodings/labels.py
    '866':                 'ibm866',
    'cp866':               'ibm866',
    'csibm866':            'ibm866',
    'csisolatin2':         'iso-8859-2',
    'iso-ir-101':          'iso-8859-2',
    'iso8859-2':           'iso-8859-2',
    'iso88592':            'iso-8859-2',
    'iso_8859-2':          'iso-8859-2',
    'iso_8859-2:1987':     'iso-8859-2',
    'l2':                  'iso-8859-2',
    'latin2':              'iso-8859-2',
    'csisolatin3':         'iso-8859-3',
    'iso-ir-109':          'iso-8859-3',
    'iso8859-3':           'iso-8859-3',
    'iso88593':            'iso-8859-3',
    'iso_8859-3':          'iso-8859-3',
    'iso_8859-3:1988':     'iso-8859-3',
    'l3':                  'iso-8859-3',
    'latin3':              'iso-8859-3',
    'csisolatin4':         'iso-8859-4',
    'iso-ir-110':          'iso-8859-4',
    'iso8859-4':           'iso-8859-4',
    'iso88594':            'iso-8859-4',
    'iso_8859-4':          'iso-8859-4',
    'iso_8859-4:1988':     'iso-8859-4',
    'l4':                  'iso-8859-4',
    'latin4':              'iso-8859-4',
    'csisolatincyrillic':  'iso-8859-5',
    'cyrillic':            'iso-8859-5',
    'iso-ir-144':          'iso-8859-5',
    'iso8859-5':           'iso-8859-5',
    'iso88595':            'iso-8859-5',
    'iso_8859-5':          'iso-8859-5',
    'iso_8859-5:1988':     'iso-8859-5',
    'arabic':              'iso-8859-6',
    'asmo-708':            'iso-8859-6',
    'csiso88596e':         'iso-8859-6',
    'csiso88596i':         'iso-8859-6',
    'csisolatinarabic':    'iso-8859-6',
    'ecma-114':            'iso-8859-6',
    'iso-8859-6-e':        'iso-8859-6',
    'iso-8859-6-i':        'iso-8859-6',
    'iso-ir-127':          'iso-8859-6',
    'iso8859-6':           'iso-8859-6',
    'iso88596':            'iso-8859-6',
    'iso_8859-6':          'iso-8859-6',
    'iso_8859-6:1987':     'iso-8859-6',
    'csisolatingreek':     'iso-8859-7',
    'ecma-118':            'iso-8859-7',
    'elot_928':            'iso-8859-7',
    'greek':               'iso-8859-7',
    'greek8':              'iso-8859-7',
    'iso-ir-126':          'iso-8859-7',
    'iso8859-7':           'iso-8859-7',
    'iso88597':            'iso-8859-7',
    'iso_8859-7':          'iso-8859-7',
    'iso_8859-7:1987':     'iso-8859-7',
    'sun_eu_greek':        'iso-8859-7',
    'csiso88598e':         'iso-8859-8',
    'csisolatinhebrew':    'iso-8859-8',
    'hebrew':              'iso-8859-8',
    'iso-8859-8-e':        'iso-8859-8',
    'iso-ir-138':          'iso-8859-8',
    'iso8859-8':           'iso-8859-8',
    'iso88598':            'iso-8859-8',
    'iso_8859-8':          'iso-8859-8',
    'iso_8859-8:1988':     'iso-8859-8',
    'visual':              'iso-8859-8',
#    'csiso88598i':         'iso-8859-8-i',  # LookupError: unknown encoding: iso-8859-8-i
#    'iso-8859-8-i':        'iso-8859-8-i',
#    'logical':             'iso-8859-8-i',
    'csisolatin6':         'iso-8859-10',
    'iso-ir-157':          'iso-8859-10',
    'iso8859-10':          'iso-8859-10',
    'iso885910':           'iso-8859-10',
    'l6':                  'iso-8859-10',
    'latin6':              'iso-8859-10',
    'dos-874':             'iso-8859-11',
    'iso8859-11':          'iso-8859-11',
    'iso885911':           'iso-8859-11',
    'tis-620':             'iso-8859-11',
    'windows-874':         'iso-8859-11',
    'iso8859-13':          'iso-8859-13',
    'iso885913':           'iso-8859-13',
    'iso8859-14':          'iso-8859-14',
    'iso885914':           'iso-8859-14',
    'csisolatin9':         'iso-8859-15',
    'iso8859-15':          'iso-8859-15',
    'iso885915':           'iso-8859-15',
    'iso_8859-15':         'iso-8859-15',
    'l9':                  'iso-8859-15',
    'cskoi8r':             'koi8-r',
    'koi':                 'koi8-r',
    'koi8':                'koi8-r',
    'koi8_r':              'koi8-r',
    'koi8-u':              'koi8-u',
    'csmacintosh':         'macintosh',
    'mac':                 'macintosh',
    'x-mac-roman':         'macintosh',
    'cp1250':              'windows-1250',
    'x-cp1250':            'windows-1250',
    'cp1251':              'windows-1251',
    'x-cp1251':            'windows-1251',
    'ansi_x3.4-1968':      'windows-1252',
    'ascii':               'windows-1252',
    'cp1252':              'windows-1252',
    'cp819':               'windows-1252',
    'csisolatin1':         'windows-1252',
    'ibm819':              'windows-1252',
    'iso-8859-1':          'windows-1252',
    'iso-ir-100':          'windows-1252',
    'iso8859-1':           'windows-1252',
    'iso88591':            'windows-1252',
    'iso_8859-1':          'windows-1252',
    'iso_8859-1:1987':     'windows-1252',
    'l1':                  'windows-1252',
    'latin1':              'windows-1252',
    'us-ascii':            'windows-1252',
    'x-cp1252':            'windows-1252',
    'cp1253':              'windows-1253',
    'x-cp1253':            'windows-1253',
    'cp1254':              'windows-1254',
    'csisolatin5':         'windows-1254',
    'iso-8859-9':          'windows-1254',
    'iso-ir-148':          'windows-1254',
    'iso8859-9':           'windows-1254',
    'iso88599':            'windows-1254',
    'iso_8859-9':          'windows-1254',
    'iso_8859-9:1989':     'windows-1254',
    'l5':                  'windows-1254',
    'latin5':              'windows-1254',
    'x-cp1254':            'windows-1254',
    'cp1255':              'windows-1255',
    'x-cp1255':            'windows-1255',
    'cp1256':              'windows-1256',
    'x-cp1256':            'windows-1256',
    'cp1257':              'windows-1257',
    'x-cp1257':            'windows-1257',
    'cp1258':              'windows-1258',
    'x-cp1258':            'windows-1258',
    'x-mac-cyrillic':      'mac-cyrillic',
    'x-mac-ukrainian':     'mac-cyrillic',
    'chinese':             'gbk',
    'csgb2312':            'gbk',
    'csiso58gb231280':     'gbk',
    'gb2312':              'gbk',
    'gb_2312':             'gbk',
    'gb_2312-80':          'gbk',
    'iso-ir-58':           'gbk',
    'x-gbk':               'gbk',
#    'gb18030':             'gb18030',
#    'hz-gb-2312':          'hz-gb-2312',
#    'big5':                'big5',
    'big5-hkscs':          'big5',
    'cn-big5':             'big5',
    'csbig5':              'big5',
    'x-x-big5':            'big5',
    'cseucpkdfmtjapanese': 'euc-jp',
    'x-euc-jp':            'euc-jp',
    'csiso2022jp':         'iso-2022-jp',
    'csshiftjis':          'shift_jis',
    'ms_kanji':            'shift_jis',
    'shift-jis':           'shift_jis',
    'sjis':                'shift_jis',
    'windows-31j':         'shift_jis',
    'x-sjis':              'shift_jis',
    'cseuckr':             'euc-kr',
    'csksc56011987':       'euc-kr',
    'iso-ir-149':          'euc-kr',
    'korean':              'euc-kr',
    'ks_c_5601-1987':      'euc-kr',
    'ks_c_5601-1989':      'euc-kr',
    'ksc5601':             'euc-kr',
    'ksc_5601':            'euc-kr',
    'windows-949':         'euc-kr',
    'csiso2022kr':         'iso-2022-kr',
}


invalid_charrefs = {
    0x80: '\u20ac',  # EURO SIGN
    0x82: '\u201a',  # SINGLE LOW-9 QUOTATION MARK
    0x83: '\u0192',  # LATIN SMALL LETTER F WITH HOOK
    0x84: '\u201e',  # DOUBLE LOW-9 QUOTATION MARK
    0x85: '\u2026',  # HORIZONTAL ELLIPSIS
    0x86: '\u2020',  # DAGGER
    0x87: '\u2021',  # DOUBLE DAGGER
    0x88: '\u02c6',  # MODIFIER LETTER CIRCUMFLEX ACCENT
    0x89: '\u2030',  # PER MILLE SIGN
    0x8a: '\u0160',  # LATIN CAPITAL LETTER S WITH CARON
    0x8b: '\u2039',  # SINGLE LEFT-POINTING ANGLE QUOTATION MARK
    0x8c: '\u0152',  # LATIN CAPITAL LIGATURE OE
    0x8e: '\u017d',  # LATIN CAPITAL LETTER Z WITH CARON
    0x91: '\u2018',  # LEFT SINGLE QUOTATION MARK
    0x92: '\u2019',  # RIGHT SINGLE QUOTATION MARK
    0x93: '\u201c',  # LEFT DOUBLE QUOTATION MARK
    0x94: '\u201d',  # RIGHT DOUBLE QUOTATION MARK
    0x95: '\u2022',  # BULLET
    0x96: '\u2013',  # EN DASH
    0x97: '\u2014',  # EM DASH
    0x98: '\u02dc',  # SMALL TILDE
    0x99: '\u2122',  # TRADE MARK SIGN
    0x9a: '\u0161',  # LATIN SMALL LETTER S WITH CARON
    0x9b: '\u203a',  # SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
    0x9c: '\u0153',  # LATIN SMALL LIGATURE OE
    0x9e: '\u017e',  # LATIN SMALL LETTER Z WITH CARON
    0x9f: '\u0178',  # LATIN CAPITAL LETTER Y WITH DIAERESIS
}


def mixed_decoder(unicode_error):
    position = unicode_error.start
#    new_char = unicode_error.object[position:position+1]
#    new_char = new_char.decode("iso8859-1","ignore")
    new_char = unicode_error.object[position] # csak 1 byte kell!
    new_char = invalid_charrefs.get(new_char, chr(new_char))  #  80..9F kozott mindenfele specko irasjelek vannak, afolott meg az unicode ugyanaz mint a latin1
#    print(new_char)
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
          if not c in b'_-0123456789abcdefghijklmnopqrstuvwxyz': break
          charset+=chr(c)
#        print('CHARSET='+charset)
        if charset: break
  return charset




fileno=1000

def html2text(data):
#  global fileno
  in_style=0
  in_script=0
  warning=''

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


  p=data.find(b'<')
  if p<0: return data # not html!?
  text=data[:p] # initial text before 1st tag
  while p<len(data):  #for ret in data.split(b'<'):

    # FIND end of tag!
    q=p+1
#    while q<len(data) and data[p]<=32: continue # skip whitespace
    ijel=None
    eqsn=False

    # handle special CDATA block:        van meg mas is:  if sectName in {"temp", "cdata", "ignore", "include", "rcdata"}:
    if data[p:p+9]==b'<![CDATA[':  # https://stackoverflow.com/questions/2784183/what-does-cdata-in-xml-mean
      q=data.find(b']]>',p)
      warning+="CDATA block found: %d-%d\n"%(p,q)
      if q<0: q=p+1 # broken...

    while q<len(data):
      c=data[q]
      q+=1
      if ijel:
        if c==62 or c==60:
            warning+="WARN! %c inside %c at %d\n"%(c,ijel,q)
        if c==ijel: ijel=None # idezet vege
        continue
      if eqsn:
        if c==34 or c==39: # idezojelek = utan oke
            ijel=c
        if c>32:           # nem whitespace (9,10,13,32)
            eqsn=False
      else:
        # WTF!???  <img src="..." alt="Russell Hobbs 25710-56/RH Velocity turmixgép" "="" width="240" border="0">
        # WTF!!!?  <span style="font-family: "playfair display", georgia, "times new roman", serif; color: #e6007e;">
        # <div align="center" arial,="" helvetica="" helvetica,="" neue",="" sans-serif;"="" style="outline: currentcolor none 0px; font-size: 13px;
        if c==34 or c==39: # idezojelek = jel nelkul:
            # kivetel persze ez mivel itt megengedett...
            # <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional //EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
            if data[p+1]!=33: # !
                warning+="WARN! %c without = at %d\n"%(c,q)
      if c==61: eqsn=True #  =
      if c==62: break     #  >
    # 
    tag=data[p+1:q-1].lower() # tag without < >
#    print(p,q,tag) # debug

    try:
      tag1=tag.split()[0] #.lower()
    except:
#      print("TAG parse error: '%s'"%(str(tag)))
      tag1=tag

    # FIND next tag:
    p=data.find(b'<',q)
    while True:
      if p<0 or p+2>=len(data):
        p=len(data) # EOF
        break
      c=data[p+1]
      if tag1 in [b'style',b'script',b'title',b'svg',b'annotation']: # TODO FIXME: svg kell ide?
        if c==47 and data[p+2:p+2+len(tag1)].lower()==tag1:
#          warning+=str(tag1)+" block found: %d-%d\n"%(q,p)
          break # found end-tag pair
        if c==33 and data[p:p+9]==b'<![CDATA[':  # https://stackoverflow.com/questions/2784183/what-does-cdata-in-xml-mean
          pp=data.find(b']]>',p)
          warning+="CDATA block found in %s: %d-%d\n"%(str(tag1),p,pp)
          if pp>0: p=pp+3
      else:
        # <?xml:namespace prefix = "o" ns = "urn:schemas-microsoft-com:office:office" />
        if c==47 or c==33 or 97<=c<=122 or 65<=c<=90 or c==63: break  #  </ or <! or <tag (a-z,A-Z) or <?xml
      warning+="WARN! skip <%c at %d\n"%(c,p)
      p=data.find(b'<',p+1) # skip this < and find next one


    txt=data[q:p]
#    print(q,p,txt) # debug

#    try:
#      tag,txt=ret.rsplit(b'>',1) # pl.: <img width="600" height="87" alt="Csak a Minősített Fogyasztóbarát Lakáshitel érdekel >>" style="display:block...">text
#    except:
#      text+=ret
#      continue
#      print(ret.encode("utf-8"))
#      break
#    print("TAG: '%s'"%(tag))
#    tag=tag.lower()

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

    if tag1==b'style': in_style+=1
    elif tag1==b'/style': in_style-=1
    elif tag1==b'script': in_script+=1
    elif tag1==b'/script': in_script-=1

#    print(q,p,in_style,in_script,txt) # debug

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

#  if warning and fileno:
#     open("debug_%d.html"%(fileno),"wb").write(data+b'\n\n========================================\n'+warning.encode("utf-8"))
#     fileno+=1

  if in_style!=0: warning+="in_style=%d\n"%(in_style)
  if in_script!=0: warning+="in_script=%d\n"%(in_script)
#  if warning: text=("!!! "+warning+" !!!").encode()+text
#  if warning: print(warning)

#  return (b' '.join(text.split())).replace(b'<BR>',b'\n')
  text=b' '.join(text.split())  # remove redundant spaces
  return b'\n'.join([ t.strip() for t in text.split(b'<BR>') ])



def html2text5(data):
  in_style=0
  in_script=0
  in_title=0
  text=""
  dom = html5lib.parse(data,namespaceHTMLElements=False)
  walker = html5lib.treewalkers.getTreeWalker("etree")
  for i in walker(dom):
    t=i["type"]
# {'type': 'StartTag', 'name': 'p', 'namespace': None, 'data': OrderedDict([((None, 'style'), "font-size: 14px; line-height: 1.2; text-align: justify; word-break: break-word; font-family: Arial, 'Helvetica Neue', Helvetica, sans-serif; mso-line-height-alt: 17px; margin: 0;")])}
    if t=="StartTag" and i["name"]=="style": in_style+=1
    if t=="EndTag" and i["name"]=="style": in_style-=1
    if t=="StartTag" and i["name"]=="script": in_script+=1
    if t=="EndTag" and i["name"]=="script": in_script-=1
    if t=="StartTag" and i["name"]=="title": in_title+=1
    if t=="EndTag" and i["name"]=="title": in_title-=1
    if in_style<=0 and in_script<=0 and in_title<=0:
      if (t=="StartTag" or t=="EmptyTag") and i["name"] in ["p","br","tr"]: text+="<BR>"
      elif (t=="StartTag" or t=="EndTag") and not i["name"] in ["span","a","b","i","u","em","strong","abbr"]: text+=" "
      if t=="Characters" or t=="SpaceCharacters": text+=i["data"]
  text=' '.join(text.split())  # remove redundant spaces
  return '\n'.join([ t.strip() for t in text.split('<BR>') ])


def is_utf8(s):
#    s=[c for c in s if c>=128] # only non-ascii bytes
#    if len(s)<2: return False
    lengths=[ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,   0, 0, 0, 0, 0, 0, 0, 0,   2, 2, 2, 2,   3, 3, 4, 0 ]
    ok=0
    bad=0
    e=0
    for a in s:
      l=lengths[a>>3]
#      print(a,l,e)
      if l==0:  # non-first utf8 byte!
        if e>0: # we need 'e' extra bytes, it's ok then
          e-=1
          ok+=1
        else:
          bad+=1
      else:
        bad+=e  # ha e>0, akkor hianyzik 'e' darab extra byte meg, es ujra start-byte (vagy ascii) jott!!
        e=l-1

    if e>0: bad+=e # hianyzik par byte...
#    print(ok,bad)
    return ok>4*bad # ha bad==0 akkor ok==1 is eleg!

#    l=len(s)
#    n=sum(c>=192 for c in s) # n# of utf8 characters
#    m=sum(c>=128 for c in s) # n# of utf8 bytes
#    return n>=5 and m>=2*n


def decode_payload(data,ctyp="text/html",charset=None):
    data5=None

    ldata=data.lower()
    if ctyp=="text/html" or ctyp=="text/xml" or ((ctyp!="text/plain" or b'</head>' in ldata) and b'<' in ldata and (ldata.find(b'<body')>=0 or ldata.find(b'<img ')>=0 or ldata.find(b'<style')>=0 or ldata.find(b'<br>')>=0 or ldata.find(b'<center>')>=0 or ldata.find(b'<a href')>=0)):
#        origdata=str(charset).encode()+b'\n'+data
#        data5=html2text5(data)        # html5lib version
        p=ldata.find(b'<body')
        if p>0:
            charset=parse_htmlhead(data[:p],charset) # parse charset override from <head>
            data=html2text(data[p:]) # skip html header, start at <body>
        else:
            data=html2text(data)     # binary version

    if not charset:
      charset="iso8859-2"
    elif charset in charset_mapping:
      charset=charset_mapping[charset]

    if charset=="utf-8" or is_utf8(data):
        # Try UTF-8:
        try:
            data=data.decode("utf-8", 'strict')
        except UnicodeDecodeError as e:
            print('BAD_UTF8, CHARSET='+charset) #, repr(e))
            data=data.decode(charset, 'mixed')  # exceptiont dob ha nincs ilyen charset!
    else:
        try:
            data=data.decode(charset, 'mixed')
        except LookupError: # nincs 'charset' nevu kodlap:
            print('BAD_CHARSET='+charset)
            data=data.decode("utf-8", 'mixed') # lehet inkabb latin2 kene eleve?

    data=unescape(data)
    
#    data=''.join([invalid_charrefs.get(ord(c),c) for c in data])

    if data5:
      data2=" ".join(data.split())
      data5=" ".join(data5.split())
      if data2!=data5:
        global fileno
        print(len(data),len(data5),"!!!!!!!")
        open("debug_%d.html"%(fileno),"wb").write(origdata)
        open("debug_%d.txt1"%(fileno),"wt").write(data2)
        open("debug_%d.txt2"%(fileno),"wt").write(data5)
        fileno+=1

    return data # fix &gt; etc

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
#    t=b'<p>Hello<i>World</em>!!! em</p>'
#    print(t)
    import sys

    x="Gárdos Péter filmrendező-író volt Veiszer Alinda vendége, aki többek között beszélt ".encode("utf-8")
    print(is_utf8(x))
    exit(0)


    t=open(sys.argv[1],"rb").read()
#    print(decode_payload(t,ctyp="text/html",charset=None))
    decode_payload(t,ctyp="text/html",charset=None)

#    t1=html2text(t)
#    t2=html2text5(t)
#    print(len(t1),len(t2))
#    open(sys.argv[1]+".txt1","wb").write(t1)
#    open(sys.argv[1]+".txt2","wt").write(t2)
    
#    print(t1)
#    print(t2)


    