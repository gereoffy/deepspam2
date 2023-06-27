
import io
import codecs
import re
import zipfile
import email
import email.policy

from html import unescape  #  https://docs.python.org/3/library/html.html
#from html.entities import name2codepoint

#import html5lib # for testing
# from bs4 import BeautifulSoup

try:
  from striprtf import rtf_to_text
  rtf_support=True
except:
  rtf_support=False

try:
  from tnefparse import TNEF
  tnef_support=1  # TNEF/HTML support
#  if rtf_support:
#    try:
#      import compressed_rtf
#      tnef_support=2  # TNEF/RTF support
#    except:
#      pass
except:
  tnef_support=0


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


# based on:  /usr/lib/python3.10/html/__init__.py
invalid_charrefs = {
    0x00: ' ',        # REPLACEMENT CHARACTER
    0x80: '\u20ac',  # EURO SIGN
    0x81: '',        # <control>
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
    0x8d: '',        # <control>
    0x8e: '\u017d',  # LATIN CAPITAL LETTER Z WITH CARON
    0x8f: '',        # <control>
    0x90: '',        # <control>
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
    0x9d: '',        # <control>
    0x9e: '\u017e',  # LATIN SMALL LETTER Z WITH CARON
    0x9f: '\u0178',  # LATIN CAPITAL LETTER Y WITH DIAERESIS
    0xA0: ' ',       # &nbsp Unicode Character 'NO-BREAK SPACE' (U+00A0)
    0xAD: '',        # &shy SOFT HYPHEN  https://stackoverflow.com/questions/34835786/what-is-shy-and-how-do-i-get-rid-of-it
    # csak ezek ternek el a magyar abc-ben a latin1 es latin2 kozott, inkabb a latin2-eset hasznaljuk ezekbol:
    0xD5: '\u0150',  # O~ => O"
    0xDB: '\u0170',  # U^ => U"
    0xF5: '\u0151',  # o~ => o"
    0xFB: '\u0171',  # u^ => u"
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


# a tag-bol kiparsoljuk a tag nevet, es hogy milyen:  -1=endtag 0=selfclosing 1=nyito
def tag_type(tag):
    if tag[:1]==b'!': return 0,'!' # special
    if tag[:1]==b'?': return 0,'?' # special
    name=''
    closing=False
    for c in tag:
        if c==47:  # /
            if name: break # <br/>
            closing=True   # a tag neve elott van a /
            continue
        if c<=32:  # whitespace
            if not name: continue # a tag neve elotti whitespace
            break # done
        if c<97 or c>122: break  # fixme: szamokat is le kene kezelni!
        name+=chr(c)
#    print(name)
    if name in ['br','area','base','meta','col','embed','hr','img','input','link','param','source','track','wbr']: return 0,name # self-closing tags
    if closing: return -1,name
    if tag[-1:]==b'/': return 0,name
    return 1,name


fileno=1000

def html2text(data,debug=False):
  global fileno
  warning=''
  indent=0
  
  p=data.find(b'<')
  if p<0: return data # not html!?
  text=[data[:p]] if p>0 else []  # initial text before 1st tag
  tlen=0 #len(data[:p].strip())

  if debug:
      html=[] if data[p:p+9]==b'<!DOCTYPE' else [b'<!DOCTYPE HTML>\n']
      html+=[data[:p]]

  while p<len(data):  #for ret in data.split(b'<'):

    # FIND end of tag!
    q=p+1

    if data[p:p+4]==b'<!--':  # comment "tag" - ennek csak --> lehet a vege, addig ignoralni kell mindent!
      q=data.find(b'-->',p)
#      warning+="COMMENT block found: %d-%d\n"%(p,q)
      if q<0:
        q=p+1 # broken...
        warning+="WARN! missing comment end-tag at %d-\n"%(p)

    ijel=None
    eqsn=False
    while q<len(data):
      c=data[q]
      q+=1
      if ijel:  #  quoted string-en belul vagyunk?
#        if c==62 or c==60: warning+="WARN! %c inside %c at %d\n"%(c,ijel,q) # < vagy > idezojelek kozott, de ez amugy okes
        if c==ijel: ijel=None  #  idezet vege
        continue
      if eqsn:  #  = jel utan vagyunk?
        if c==34 or c==39: ijel=c   # idezojelek = utan oke
        if c>32: eqsn=False         # nem whitespace (9,10,13,32)
      else:
        if c==34 or c==39: # idezojelek = jel nelkul:
            if data[p+1]!=33: warning+="WARN! %c without = at %d\n"%(c,q)  # <! utan oke (a doctype-ban pl. lehet), egyebkent warning
      if c==61: eqsn=True #  =
      if c==62: break     #  >
    # 
    tag=data[p+1:q-1].lower() # tag without < >
    tt,ttag=tag_type(tag)     # tag type,name
    in_block= tt>0 and ttag in ['style','script','title','svg','annotation']   # TODO FIXME: svg kell ide?
#    print("TAG:",p,q,tt,ttag,tag) # debug

    if debug:
      if tt<0: indent-=1
      html+=[b'%5d|'%(p)+b' '*max(0,min(48,indent)) + data[p:q].replace(b'\n',b' ')]
      if tt>0: indent+=1

    # FIND next tag:
    p=data.find(b'<',q)
    while True:
#      print(p,in_block,data[p:p+10])
      if p<0 or p+2>=len(data):
        p=len(data) # EOF
        break
      if in_block: # mas parser altal kezelt (js, css, svg stb) blokk veget keressuk, ebben csak a cdata-val kell foglalkozni az endtag-en kivul:
        endtag=bytes('</'+ttag,'ascii')            # ez igy nem szep, es elvileg lefuthat foloslegesen tobbszor is, de gyakorlatilag ez nem jellemzo
        if data[p:p+len(endtag)].lower()==endtag:  #  </ttag>
#          warning+="%s block found: %d-%d\n"%(ttag,q,p)
          break
        if data[p:p+9]==b'<![CDATA[':  # https://stackoverflow.com/questions/2784183/what-does-cdata-in-xml-mean
          pp=data.find(b']]>',p)
          warning+="CDATA block found in %s: %d-%d\n"%(ttag,p,pp)
          if pp>0: p=pp #+3    nem szabad a kovetkezo < jelre mutatnia a p-nek, mert a loop vegen van egy find p+1 es akkor pont atugorja!!!
          else: warning+="WARN! missing CDATA end-tag at %d- (in %s)\n"%(p,ttag)
        #else: warning+="WARN! skip <%c at %d in %s\n"%(c,p,ttag)   # igazabol itt lehet barmi, megengedett...
      else:
        c=data[p+1]
        if c==47 or c==33 or 97<=c<=122 or 65<=c<=90 or c==63: break  #  </ or <! or <tag [a-z,A-Z] or <?xml
        warning+="WARN! skip <%c at %d\n"%(c,p)  # hibas tag formatum!
      p=data.find(b'<',p+1) # skip this < and find next one

    if debug:
      html+=[data[q:p].rstrip()+b'\n']
      if warning: html+=[b' <!> |' + warning.encode("utf-8",errors="ignore")]  # beirjuk a sorok koze inkabb!
      warning=""

    if in_block:
#      print("Skipping %s block at %d-%d, size=%d"%(ttag,q,p,p-q))  # debug
      if p>=len(data): warning+="WARN! non-closed tag %s at %d-\n"%(ttag,q)  # EOF, tehat nincs meg az endtag!
      continue

    txt=data[q:p]
#    print(q,p,tt,ttag,txt) # debug

    if b'style' in tag: # detect hidden text!
        tag=tag.replace(b': ',b':')
        if b'display:none' in tag or b'font-size:0p' in tag or b'font-size:1p' in tag or b'max-height:0p' in tag or b'mso-hide:all' in tag or b'opacity:0' in tag:
            if b'signedadaptivecard' in tag: continue # ms teams hidden base64 data!!!
#            if b'display:none' in tag and len(text.strip())==0:
            if b'display:none' in tag and tlen==0:
                if len(txt.strip())>=3: text+=[b'['+txt+b'] '] # preview header  https://responsivehtmlemail.com/html-email-preheader-text/
#            else:
#                if len(txt.strip())>=3: text+=[b'{{'+txt+b'}}'] # hidden text
            continue

    if tag==b'div' or (tt>=0 and ttag in ['p','br','tr']):
        text+=[b'<BR>']  # https://www.w3schools.com/html/html_blocks.asp
    else:
        if not ttag in ['span','a','b','i','u','em','strong','abbr','font']: text+=[b' '] # not inline elements
    text+=[txt]
    tlen+=len(txt.strip())

#  if warning: text=("!!! "+warning+" !!!").encode()+text
#  if debug and warning: print(warning)
  if debug and warning: html+=[b' <!> |' + warning.encode("utf-8",errors="ignore")]  # beirjuk a sorok koze inkabb!
#  if warning:
#     open("debug_%d.html"%(fileno),"wb").write(data+b'\n\n========================================\n'+warning.encode("utf-8"))
#     fileno+=1

  text=b''.join(text)
  text=b' '.join(text.split())  # remove redundant spaces
  text=b'\n'.join([ t.strip() for t in text.split(b'<BR>') ])
  if debug: return text, html
  return text


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




def parse_ics(data):
    ics=[]
    hdr=b''
    for line in data.split(b'\n'):
        if line[:1]==b' ' or line[:1]==b'\t':
            hdr+=line[1:].rstrip()
            continue
        if hdr: ics.append(hdr.split(b':',1))
        hdr=line.rstrip()
    if hdr: ics.append(hdr.split(b':',1))

    def unescape(text):
        return text.replace(b'\\N', b'\\n')\
                   .replace(b'\r\n', b'\n')\
                   .replace(b'\\n', b'\n')\
                   .replace(b'\\,', b',')\
                   .replace(b'\\;', b';')\
                   .replace(b'\\\\', b'\\')

    for x in ics:
#        print(x)
        if x[0][:11]==b'DESCRIPTION': return unescape(x[1])  # DESCRIPTION;LANGUAGE=hu-HU:Kedves Endre\,\n\n\nSzeretettel
        if x[0]==b'X-ALT-DESC;FMTTYPE=text/html': return html2text(unescape(x[1]))
    return b'' #  FIXME


def parse_docx(data):   # if ctyp=="application/vnd.openxmlformats-officedocument.wordprocessingml.document" or fnev.endswith(".docx"):
#    try:
        zipf=zipfile.ZipFile(io.BytesIO(data))
        xml=zipf.read('word/document.xml') #.decode("utf-8")
        s=b''
        for ret in xml.split(b'<'):
            try:
                tag,txt=ret.split(b'>',1)
                tag1=tag.split()[0]
            except:
                continue
            if tag1==b'w:t':
                s+=txt
            elif tag1 in [b'w:tab',b'w:br',b'w:cr',b'w:p']:
                s+=b'\n'
        return s


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
    if ctyp=="text/calendar" or ctyp=="application/ics":
        data=parse_ics(data)
    elif ctyp=="application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        data=parse_docx(data)
        charset="utf-8"
    elif ctyp=="application/ms-tnef":
#        print("###### Parse TNEF ######")
        tnefobj = TNEF(data)
        if tnefobj.htmlbody:
            charset="utf-8"
            data=html2text(tnefobj.htmlbody.encode(charset))
#         elif tnef_support>1 and tnefobj.rtfbody:
#            s = rtf_to_text(tnefobj.rtfbody.decode(tnefcp,"ignore"))
    elif ctyp=="text/html" or ctyp=="text/xml" or ((ctyp!="text/plain" or b'</head>' in ldata or b'</br>' in ldata) and b'<' in ldata and (ldata.find(b'<body')>=0 or ldata.find(b'<img ')>=0 or ldata.find(b'<style')>=0 or ldata.find(b'<br>')>=0 or ldata.find(b'<center>')>=0 or ldata.find(b'<a href')>=0)):
#        origdata=str(charset).encode()+b'\n'+data
#        data5=html2text5(data)        # html5lib version
        p=ldata.find(b'<body')
        if p>0: charset=parse_htmlhead(data[:p],charset) # parse charset override from <head>
        if charset and (charset.startswith("iso-2022") or charset.startswith("csiso2022")):  # https://en.wikipedia.org/wiki/ISO/IEC_2022
            data=data.decode(charset,errors="ignore").encode("utf-8")  # japan/koreai, 7 bitbe kodolt tobb byteos karakterkodok, ESC-el stb, a html parser nem birja :)
            charset="utf-8"
        data=html2text(data)     # binary version!

    if not charset:
      charset="iso8859-1"
    elif charset in charset_mapping:
      charset=charset_mapping[charset]

    if charset=="utf-8" or is_utf8(data):
        # Try UTF-8:
        try:
            data=data.decode("utf-8", 'strict')
        except UnicodeDecodeError as e:
#            print('BAD_UTF8, CHARSET='+charset) #, repr(e))
            data=data.decode(charset, 'mixed')  # exceptiont dob ha nincs ilyen charset!
    else:
        try:
            data=data.decode(charset, 'mixed')
        except LookupError: # nincs 'charset' nevu kodlap:
#            print('BAD_CHARSET='+charset)
            data=data.decode("utf-8", 'mixed') # lehet inkabb latin2 kene eleve?

    # ezt mar a dekodolas utan kell :(
    if ctyp=="application/rtf":
        data=rtf_to_text(data) # remove RTF markup
    else:
        data=unescape(data)  # fix &gt; etc

    # nbsp->space, remove SOFT HYPHEN  https://stackoverflow.com/questions/34835786/what-is-shy-and-how-do-i-get-rid-of-it
#    data=data.replace('\u00A0',' ').replace('\u00AD','')
    data=''.join([invalid_charrefs.get(ord(c),c) for c in data])

    if data5:  # compare with html5lib version, and save raw+outputs for debugging if mismatch...
      data2=" ".join(data.split())
      data5=" ".join(data5.split())
      if data2!=data5:
        global fileno
        print(len(data),len(data5),"!!!!!!!")
        open("debug_%d.html"%(fileno),"wb").write(origdata)
        open("debug_%d.txt1"%(fileno),"wt").write(data2)
        open("debug_%d.txt2"%(fileno),"wt").write(data5)
        fileno+=1
    return data


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
    if (ctyp.split('/')[0]=="text" and disp!="attachment") or ctyp=="application/ics" or (ctyp=="application/ms-tnef" and tnef_support) or (ctyp=="application/rtf" and rtf_support):
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
            if ctyp.startswith("text/") or ctyp=="application/ics" or (ctyp=="application/ms-tnef" and tnef_support) or (ctyp=="application/rtf" and rtf_support) or ctyp=="application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                html=decode_payload(pay,ctyp,cset) # ez meg a soup-prettify elott kell, mert az elbassza a whitespacet...
                if ctyp=="text/html" or ctyp=="text/xml":
                    html="\n".join([" ".join(s.split()) for s in html.splitlines() if s]) # remove empty lines and redundant spaces
#                    soup=BeautifulSoup(pay,"html5lib", from_encoding=cset)
#                    pay=soup.prettify(encoding="utf-8")
                    dtext,dhtml=html2text(pay,debug=True)  # html prettify :)
                    pay=b''.join(dhtml)
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
        if not c.isalpha(): # if c in '\n\t #".,!?;:_-+/*()[]{}0123456789':
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

#    print(is_utf8(x))
#    exit(0)

#    t=open("sample.ics","rb").read()
#    x=parse_ics(t)
#    print(x.decode())

#    t=open(sys.argv[1],"rb").read()
    t=open("ALL.html","rb").read()
#    print(decode_payload(t,ctyp="text/html",charset=None))
#    decode_payload(t,ctyp="text/html",charset=None)

    import time
    t0=time.time()

#    t1=html2text(t)
    t1,h1=html2text(t,debug=True)
    h1=b''.join(h1)

    t0=time.time()-t0
#    print("%8.5f ms"%(t0*1000.0),len(t),len(t1))
    print("%8.5f ms"%(t0*1000.0),len(t),len(t1),len(h1))

#    open("ALL.out","wb").write(h1)
    
    
#    t2=html2text5(t)
#    print(len(t1),len(t2))
#    open(sys.argv[1]+".txt1","wb").write(t1)
#    open(sys.argv[1]+".txt2","wt").write(t2)
    
#    print(t1)
#    print(t2)


    