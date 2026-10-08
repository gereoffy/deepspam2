
import io
import codecs
import encodings
import re
import zipfile
from itertools import islice

from binascii import a2b_qp,a2b_base64
from urllib.parse import unquote_to_bytes

from html import unescape  #  https://docs.python.org/3/library/html.html

try:
  from striprtf import rtf_to_text
  rtf_support=True
except ImportError:
  rtf_support=False

try:
  from tnef_mini import parse_tnef_body
  tnef_support=True
except ImportError:
  tnef_support=False

# Karakterkeszlet-nevek, amiket a Python nem ismer, de levelekben / HTML-ben / RTF-ben elofordulnak.
# Egy codec-keresot regisztralunk rajuk, igy barmelyik decode() / codecs.lookup() felismeri oket (a striprtf-ben
# is), nem kell minden dekodolas elott kulon lekepezni. A Python a keresonek csak az altala nem ismert neveket adja
# at, normalizalva (kisbetu, a nem alfanumerikus reszek '_'-ra cserelve, pl. 'X-Mac-CE' -> 'x_mac_ce').
codec_aliases = {
    'cp-850':              'cp850',
    '_iso-2022-jp$esc':    'iso-2022-jp',
    'windows-874':         'cp874',
    'x-mac-ce':            'maccentraleurope',
    'iso-8859-8-i':        'iso-8859-8',
    'unicode-1-1-utf-8':   'utf-8',

    # source: /usr/local/lib/python3.10/dist-packages/webencodings/labels.py
    'iso-88-2':            'iso-8859-2',
    'iso88592':            'iso-8859-2',
    'iso88593':            'iso-8859-3',
    'iso88594':            'iso-8859-4',
    'iso88595':            'iso-8859-5',
    'csiso88596e':         'iso-8859-6',
    'csiso88596i':         'iso-8859-6',
    'iso-8859-6-e':        'iso-8859-6',
    'iso-8859-6-i':        'iso-8859-6',
    'iso88596':            'iso-8859-6',
    'iso88597':            'iso-8859-7',
    'sun_eu_greek':        'iso-8859-7',
    'csiso88598e':         'iso-8859-8',
    'iso-8859-8-e':        'iso-8859-8',
    'iso88598':            'iso-8859-8',
    'visual':              'iso-8859-8',
    'csiso88598i':         'iso-8859-8',  # iso-8859-8-i: a logikai irasirany jelolese, a dekodolas ugyanaz
    'logical':             'iso-8859-8',
    'iso885910':           'iso-8859-10',
    'dos-874':             'iso-8859-11',
    'iso885911':           'iso-8859-11',
    'iso885913':           'iso-8859-13',
    'iso885914':           'iso-8859-14',
    'csisolatin9':         'iso-8859-15',
    'iso885915':           'iso-8859-15',
    'koi':                 'koi8-r',
    'koi8':                'koi8-r',
    'csmacintosh':         'macintosh',
    'mac':                 'macintosh',
    'x-mac-roman':         'macintosh',
    'x-cp1250':            'windows-1250',
    'x-cp1251':            'windows-1251',
    'iso88591':            'windows-1252',
    'x-cp1252':            'windows-1252',
    'x-cp1253':            'windows-1253',
    'iso88599':            'windows-1254',
    'x-cp1254':            'windows-1254',
    'x-cp1255':            'windows-1255',
    'x-cp1256':            'windows-1256',
    'x-cp1257':            'windows-1257',
    'x-cp1258':            'windows-1258',
    'x-mac-cyrillic':      'mac-cyrillic',
    'x-mac-ukrainian':     'mac-cyrillic',
    'csgb2312':            'gbk',
    'gb_2312':             'gbk',
    'gb_2312-80':          'gbk',
    'x-gbk':               'gbk',
    'cn-big5':             'big5hkscs',
    'x-x-big5':            'big5hkscs',
    'cseucpkdfmtjapanese': 'euc-jp',
    'x-euc-jp':            'euc-jp',
    'windows-31j':         'cp932',
    'x-sjis':              'cp932',
    'cseuckr':             'cp949',
    'csksc56011987':       'cp949',
    'iso-ir-149':          'cp949',
    'ks_c_5601-1989':      'cp949',
    'ksc_5601':            'cp949',
    'windows-949':         'cp949',

    # a striprtf charset_map-jenek nem letezo mac_* codec-nevei (\fcharset77..89); a hebrew / thai kozelites
    'mac_ce':              'mac_latin2',
    'mac_rumanian':        'mac_romanian',
    'mac_ukrainian':       'mac_cyrillic',
    'mac_japanese':        'shift_jis',
    'mac_chinesetrad':     'big5',
    'mac_chinesesimp':     'gbk',
    'mac_korean':          'euc_kr',
    'mac_hebrew':          'cp1255',
    'mac_thai':            'cp874',
}
_codec_aliases = {encodings.normalize_encoding(k).lower(): v for k, v in codec_aliases.items()}

def _codec_alias_search(name):
    target = _codec_aliases.get(name)
    if target:
        try: return codecs.lookup(target)
        except LookupError: pass
    return None

codecs.register(_codec_alias_search)

# Szandekos felulirasok: ezeket a neveket a Python is ismeri, de mashogy dekodolna (a WHATWG / bongeszok szerint
# pl. a latin1 / us-ascii valojaban windows-1252). A codec-kereso ezeket nem kapja meg, es globalisan sem szabad
# atirni oket (az email modul, a tokenizerek stb. a pontos latin-1-re epitenek), ezert csak a sajat dekodolasainknal
# alkalmazzuk, a charset_name() fuggvenyen keresztul.
charset_overrides = {
    'utf-16':              'utf-16le',
    'tis-620':             'iso-8859-11',
    'ansi_x3.4-1968':      'windows-1252',
    'ascii':               'windows-1252',
    'cp819':               'windows-1252',
    'csisolatin1':         'windows-1252',
    'ibm819':              'windows-1252',
    'iso-8859-1':          'windows-1252',
    'iso-ir-100':          'windows-1252',
    'iso8859-1':           'windows-1252',
    'iso_8859-1':          'windows-1252',
    'iso_8859-1:1987':     'windows-1252',
    'l1':                  'windows-1252',
    'latin1':              'windows-1252',
    'us-ascii':            'windows-1252',
    'csisolatin5':         'windows-1254',
    'iso-8859-9':          'windows-1254',
    'iso-ir-148':          'windows-1254',
    'iso8859-9':           'windows-1254',
    'iso_8859-9':          'windows-1254',
    'iso_8859-9:1989':     'windows-1254',
    'l5':                  'windows-1254',
    'latin5':              'windows-1254',
    'chinese':             'gbk',
    'csiso58gb231280':     'gbk',
    'gb2312':              'gbk',
    'iso-ir-58':           'gbk',
    # WHATWG: a big5 valojaban Big5-HKSCS, a shift_jis windows-31j (cp932), az euc-kr windows-949 (cp949), ezek bovebbek
    'big5':                'big5hkscs',
    'big5-tw':             'big5hkscs',
    'csbig5':              'big5hkscs',
    'csshiftjis':          'cp932',
    'shift-jis':           'cp932',
    'shift_jis':           'cp932',
    'sjis':                'cp932',
    'euc-kr':              'cp949',
    'euc_kr':              'cp949',
    'euckr':               'cp949',
    'korean':              'cp949',
    'ks_c_5601':           'cp949',
    'ks_c_5601-1987':      'cp949',
    'ksc5601':             'cp949',
}

def charset_name(cset):
    # MIME / HTML charset nev -> a dekodolashoz hasznalando nev (a felulirasok alkalmazasa; az aliasokat a codec-kereso intezi)
    return charset_overrides.get(cset.lower(), cset) if cset else cset


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
    0x8c: '\u015a',  # CP1250-bol (cp1252: CAPITAL LIGATURE OE)
    0x8d: '\u0164',  # CP1250-bol :)
    0x8e: '\u017d',  # LATIN CAPITAL LETTER Z WITH CARON
    0x8f: '\u0179',  # CP1250-bol :)
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
    0x9c: '\u015b',  # CP1250-bol (cp1252: SMALL LIGATURE OE)
    0x9d: '\u0165',  # CP1250-bol :)
    0x9e: '\u017e',  # LATIN SMALL LETTER Z WITH CARON
    0x9f: '\u017a',  # CP1250-bol (cp1252: CAPITAL LETTER Y WITH DIAERESIS)
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

def _mixed_factory(cs):
    # mint a mixed, de a felso fel (A0..FF) a megadott kodlap szerint (latin2 / cp1250), a 80..9F marad az invalid_charrefs
    tbl=bytes(range(0xa0,0x100)).decode(cs)
    def handler(e):
        b=e.object[e.start]
        return (tbl[b-0xa0] if b>=0xa0 else invalid_charrefs.get(b,chr(b)), e.start+1)
    return handler
for _cs in ("iso8859-2","cp1250"): codecs.register_error("mixed_"+_cs,_mixed_factory(_cs))

def safe_decode(data,cs,errors="mixed"):
    # dekodolas a cs kodlappal; ha az nem letezik vagy nem hasznalhato (LookupError: unknown-8bit, iso-2022-cn, base64...,
    # UnicodeError: undefined, idna, ami a 'mixed'-et sem tamogatja), akkor utf-8 + mixed (latin1/cp1252 visszaesessel).
    # Latin1/2 kodlapnal, ha utf-8 magyar ekezetek vannak benne (is_utf8_mixed), hibaturo utf-8, ahol az ervenytelen
    # byte-ok a megadott kodlap szerint dekodolodnak (pl. levelezolista footer, idezett utf-8 resz)
    try:
        cs=codecs.lookup(cs or "utf-8").name
        if cs in ["cp1252","iso8859-1","iso8859-2","cp1250"]: # latin1/2 kanonikus nevei (a charset_name utan a latin1/us-ascii mar cp1252)
            try: return data.decode("utf-8","strict")  # gyakran utf-8 a latin1/2-nek jelolt szoveg (rovid fejlecekben is)
            except UnicodeDecodeError: pass
            if is_utf8_mixed(data): return data.decode("utf-8","mixed_"+cs if cs in ("iso8859-2","cp1250") else "mixed")
        return data.decode(cs,errors)
    except (LookupError,UnicodeError): return data.decode("utf-8","mixed")

_ASCII_PROBE=b'<body +x- ~~ \x1b$B>'  # utf-7 (+x-), hz (~~), iso-2022 (ESC $ B), utf-16/32 (paratlan hossz) mind elrontja

def ascii_compatible(cs):
    # az ASCII byte-ok ASCII karaktert jelentenek-e ebben a kodlapban (a html2text byte-okon dolgozik, ehhez kell);
    # ismeretlen kodlap: igen, mert ugyis utf-8 + mixed lesz belole
    try: return _ASCII_PROBE.decode(cs)==_ASCII_PROBE.decode("ascii")
    except LookupError: return True
    except UnicodeError: return False

_FIX_TABLE=dict(invalid_charrefs)  # str.translate tabla: kodpont -> csere ('' = torles)

def fix_chars(s):
    # az invalid_charrefs csere a dekodolt szovegen (C1 -> cp1252 irasjelek, Õ Û õ û -> Ő Ű ő ű, nbsp, shy...)
    # (str.translate: ugyanaz, mint a ''.join([invalid_charrefs.get(ord(c),c) for c in s]), de C-ben fut)
    return s.translate(_FIX_TABLE)

# a utf-32-le elobb kell, mint a vele azonosan kezdodo utf-16-le
BOMS=((codecs.BOM_UTF8,"utf-8"),(codecs.BOM_UTF32_LE,"utf-32-le"),(codecs.BOM_UTF32_BE,"utf-32-be"),
      (codecs.BOM_UTF16_LE,"utf-16-le"),(codecs.BOM_UTF16_BE,"utf-16-be"))


_HU_U8=re.compile(rb'\xc3[\x81\x89\x8d\x93\x96\x9a\x9c\xa1\xa9\xad\xb3\xb6\xba\xbc]|\xc5[\x90\x91\xb0\xb1]')  # utf-8 ÁÉÍÓÖÚÜ áéíóöúü Őő Űű

def is_utf8_mixed(data,n=4):
    # van-e legalabb n db utf-8 kodolt magyar ekezetes betu (csak latin1/2 deklaralt kodlapnal hasznaljuk,
    # mas kodlapoknal tevesen is kijohet: gbk "好。" = C3 A1, euc-kr 처 = C3 B3, cp1251 "Гі" = C3 B3)
    return sum(1 for _ in islice(_HU_U8.finditer(data),n))>=n


# Mely tag-ek mely attributumaban keressuk az URL-t.
# Bovitheto pl. 'meta' + 'content' (refresh redirect), 'srcset' stb. igeny szerint.
LINK_ATTRS = {
    'a':      'href',
    'area':   'href',
    'base':   'href',
    'link':   'href',
#    'img':    'src',
    'iframe': 'src',
    'frame':  'src',
    'form':   'action',
}

ATTR_RE_CACHE = {}

# Kiszedi egy attributum erteket egy RAW (eredeti case-u!) tag-bol.
def html_extract_attr(rawtag, attrname):
    if attrname not in ATTR_RE_CACHE:
        # (?<![\w-]) -> ne talaljon pl. "xhref"-et vagy "data-href"-et
        ATTR_RE_CACHE[attrname] = re.compile(
            rb'(?<![\w-])' + attrname.encode('ascii') +
            rb'\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))',
            re.IGNORECASE)
    m=ATTR_RE_CACHE[attrname].search(rawtag)
    if not m: return None
    val = m.group(1) or m.group(2) or m.group(3) or b''
    return unescape(val.decode("utf-8","mixed")).strip()


#  <meta content="text/html; charset=utf-8" http-equiv="Content-Type"/>
#  <meta content="utf-8" name="charset"/>
#  <meta charset="utf-8"/>

def parse_rtfhead(data,charset=None):
  # az RTF sajat kodlapja (\ansicpgNNNN a fejlecben), ha az nincs vagy nem hasznalhato, akkor charset,
  # vegul cp1252. Mindig letezo es ASCII-kompatibilis kodlapot ad (pl. utf-16 nem jo: az RTF 7 bites, a
  # kodlap csak a nyers 8 bites byte-okhoz, es a striprtf-nek a \fcharset nelkuli / ismeretlen fcharset-u fontokhoz kell)
  m=re.search(rb'\\ansicpg(\d{1,5})',data[:4096])
  for cp in ("cp"+m.group(1).decode() if m else None,charset,"cp1252"):
    try:
      if cp and b'{\\rtf1 +x-}'.decode(cp)=='{\\rtf1 +x-}': return cp  # a +x- az utf-7 miatt
    except (LookupError,UnicodeError): pass
  return "cp1252"

def rtf_hex_encoding(cp):
  # a parse_rtfhead() kodlapjabol a striprtf-nek atadando kodlap a \'xx escape-ekhez: ezek az RTF szerint
  # egybajtos ANSI kodlapban vannak, ezert a MIME / TNEF charset-bol jovo utf-8 helyett cp1252 (a striprtf
  # default-ja). Az RTF-ben explicit \ansicpg65001 a parse_rtfhead()-tol "cp65001"-kent jon, az marad.
  return "cp1252" if cp.lower() in ("utf-8","utf8") else cp

# a durva RTF szoveg-kinyero tokenjei: \szo[szam], \'xx, \X (escape / szimbolum), { }, sima szoveg, sorvege
rtf_token_re=re.compile(r"\\([a-zA-Z]{1,32})(-?\d{1,10})? ?|\\'([0-9a-fA-F]{2})|\\(.)|([{}])|([^\\{}\r\n]+)|[\r\n]+",re.S)
# csoportok, amiknek a tartalma nem szoveg (a \* -gal jelolteken kivul)
rtf_skip_groups={'fonttbl','colortbl','stylesheet','info','pict','object','objdata','header','headerl','headerr',
    'headerf','footer','footerl','footerr','footerf','listtable','listoverridetable','rsidtbl','generator',
    'themedata','colorschememapping','datastore','latentstyles','xmlnstbl','fldinst','shprslt','sp','sn','sv'}
# \* -os csoportok, amiknek a szovege a dokumentum resze: szovegdobozok ({\shp{\*\shpinst ...{\shptxt ...}}})
# es regi rajzobjektumok ({\*\do ...{\dptxbxtext ...}}); a \shprslt masolatot (ugyanaz a szoveg) kihagyjuk
rtf_transparent_groups={'shpinst','do'}
# \fcharsetN -> kodlap a fontonkenti \'xx dekodolashoz (a tobbi, pl. 1 = default, 2 = symbol: a dokumentum kodlapja)
rtf_fcharset_cp={0:'cp1252',77:'mac-roman',128:'cp932',129:'cp949',130:'johab',134:'gbk',136:'big5',161:'cp1253',
    162:'cp1254',163:'cp1258',177:'cp1255',178:'cp1256',186:'cp1257',204:'cp1251',222:'cp874',238:'cp1250',
    254:'cp437',255:'cp850'}
rtf_font_re=re.compile(r"\\f(\d+)(?![0-9])")
# nevesitett irasjelek es szokozok (ha eldobnank, a szomszedos szavak osszetapadnanak)
rtf_special_words={'par':'\n','line':'\n','row':'\n','sect':'\n','page':'\n','tab':'\t','cell':'\t',
    'emdash':'\u2014','endash':'\u2013','bullet':'\u2022','lquote':'\u2018','rquote':'\u2019',
    'ldblquote':'\u201c','rdblquote':'\u201d','emspace':' ','enspace':' ','qmspace':' '}
rtf_special_syms={'\\':'\\','{':'{','}':'}','~':'\xa0','_':'-','\r':'\n','\n':'\n'}  # a \- (felteteles kotojel) eldobando

def rtf_font_codepages(text):
  # {\fonttbl{\f0\froman\fcharset238 Times New Roman;}...} -> {'0':'cp1250',...}
  m=re.search(r"\{\\fonttbl",text)
  if not m: return {}
  depth=0; end=len(text)
  for b in re.finditer(r"\\[\\{}]|[{}]",text[m.start():m.start()+1000000]):
    if b.group()=='{': depth+=1
    elif b.group()=='}':
      depth-=1
      if depth==0: end=m.start()+b.end(); break
  tbl=text[m.start():end]; fonts={}
  starts=list(rtf_font_re.finditer(tbl))
  for i,f in enumerate(starts):
    seg=tbl[f.end():starts[i+1].start() if i+1<len(starts) else len(tbl)]
    c=re.search(r"\\fcharset(\d+)",seg)
    if c and int(c.group(1)) in rtf_fcharset_cp: fonts[f.group(1)]=rtf_fcharset_cp[int(c.group(1))]
  return fonts

def rtf_fallback_text(text,encoding="cp1252"):
  # durva RTF -> szoveg, ha a striprtf nincs telepitve vagy kivetelt dob: a nem-szoveg csoportokat kihagyja,
  # a \'xx escape-eket a font \fcharset-je (ha nincs: az encoding) szerint, a \uN-eket unicode-kent dekodolja,
  # a vezerloszavakat eldobja. A lablegyzeteket (a striprtf-fel ellentetben) megtartja.
  fonts=rtf_font_codepages(text)
  out=[]; hexes=[]; skip=False; stack=[]; group_start=False; star=False; ucskip=1; curskip=0
  font=deff=None
  pos=0; n=len(text)
  while pos<n:
    m=rtf_token_re.match(text,pos)
    if not m: break  # pl. a text vegen egy magaban allo backslash
    pos=m.end()
    word,arg,hx,sym,brace,txt=m.groups()
    if hexes and not hx:
      out.append(bytes.fromhex(''.join(hexes)).decode(fonts.get(font,encoding),'ignore')); hexes=[]
    after_star,star=star,False
    if brace=='{':
      stack.append((skip,ucskip,font)); group_start=True; continue
    if brace=='}':
      if stack: skip,ucskip,font=stack.pop()
      group_start=False; continue
    first,group_start=group_start,False
    if word:
      if word=='bin' and arg:
        pos+=max(0,int(arg)); continue  # \binN: N byte binaris adat (barmi lehet benne, kapcsos zarojel is)
      if after_star and word in rtf_transparent_groups:
        skip=stack[-1][0] if stack else False  # a \* visszavonasa: csak akkor rejtett, ha a szulo csoport is az
      elif first and word in rtf_skip_groups: skip=True
      elif word=='f' and arg: font=arg
      elif word=='deff' and arg: deff=font=arg
      elif word=='plain': font=deff
      elif skip: pass
      elif word in rtf_special_words: out.append(rtf_special_words[word])
      elif word=='uc' and arg: ucskip=int(arg)
      elif word=='u' and arg:
        c=int(arg); out.append(chr(c+0x10000 if c<0 else c)); curskip=ucskip
    elif sym:
      if sym=='*' and first: skip=True; star=True; group_start=True  # a kovetkezo szo meg a csoport "elso" szava
      elif not skip and sym in rtf_special_syms: out.append(rtf_special_syms[sym])
    elif hx:
      if curskip: curskip-=1
      elif not skip: hexes.append(hx)
    elif txt and not skip:
      if curskip: txt=txt[curskip:]; curskip=0
      out.append(txt)
  if hexes: out.append(bytes.fromhex(''.join(hexes)).decode(fonts.get(font,encoding),'ignore'))
  return ''.join(out)

def fix_surrogates(s):
  # a \uN parokbol (emoji) kulon chr()-rel keletkezett surrogate-ok osszevonasa, a parositatlanok U+FFFD-re,
  # kulonben a kesobbi .encode("utf-8") kivetelt dob
  try: s.encode("utf-8"); return s
  except UnicodeEncodeError: return s.encode("utf-16-le","surrogatepass").decode("utf-16-le","replace")

def rtf_to_text_safe(text,encoding="cp1252"):
  # striprtf, ha van es nem dob kivetelt (pl. nem letezo codec, lezaratlan csoport...), kulonben a durva kinyero
  if rtf_support:
    try: return fix_surrogates(rtf_to_text(text,encoding=encoding,errors="ignore"))
    except Exception: pass
  return fix_surrogates(rtf_fallback_text(text,encoding))


def parse_htmlhead(data,charset=None):
  for ret in data.split(b'<'):
    tag=ret.split(b'>')[0].lower()
    if tag.startswith(b'meta'):
      p=tag.find(b'charset=')
      if p>=0:
#        print(tag)
        cs=""
        for c in tag[p+8:]:
          if c<=32: continue  # whitespace
          if c==34 or c==39:  # idezojelek
            if cs: break
            continue
          if not c in b'_-0123456789abcdefghijklmnopqrstuvwxyz': break
          cs+=chr(c)
#        print('CHARSET='+cs)
        if cs: return cs
  return charset  # nincs, vagy ures / sablonos (charset="{{cs}}"): marad a MIME charset


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


def html2text(data,debug=False):
  warning=''
  indent=0
  urls=[]
  
  p=data.find(b'<')
  if p<0: # not html!?
      return (data,[data]) if debug else data
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
    rawtag=data[p+1:q-1] # tag without < >
    tag=rawtag.lower()
    tt,ttag=tag_type(tag)     # tag type,name
    in_block= tt>0 and ttag in ['style','script','title','svg','annotation']   # TODO FIXME: svg kell ide?
#    print("TAG:",p,q,tt,ttag,tag) # debug

    # URL kinyerese nyito/selfclosing tagekbol (zaro tag-nek nincs attributuma)
    if tt>=0 and ttag in LINK_ATTRS:
        url=html_extract_attr(rawtag, LINK_ATTRS[ttag])
        if url: urls.append(url)

    if debug:
      if tt<0: indent-=1
      html+=[b'%5d|'%(p)+b' '*max(0,min(64,indent)) + data[p:q].replace(b'\n',b' ')]
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

  if debug and warning: html+=[b' <!> |' + warning.encode("utf-8",errors="ignore")]  # beirjuk a sorok koze inkabb!

  text=b''.join(text)
  text=b' '.join(text.split())  # remove redundant spaces
  text=b'\n'.join([ t.strip() for t in text.split(b'<BR>') ])

  urls=list(dict.fromkeys(urls))  # sorrend-megorzo dedup az URL listan
  for url in urls: text+=b'\nURL: '+url[:128].encode("utf-8")

  if debug: return text, html
  return text


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
    try:
        zipf=zipfile.ZipFile(io.BytesIO(data))
        xml=zipf.open('word/document.xml').read(8*1024*1024)  # zip bomba ellen: a deklaralt merettol fuggetlenul max ennyi byte
        s=b''
        for ret in xml.split(b'<'):
            try:
                tag,txt=ret.split(b'>',1)
                tag1=tag.split()[0]
            except (ValueError,IndexError):  # nincs '>' / ures tag
                continue
            if tag1==b'w:t':
                s+=txt
            elif tag1 in [b'w:tab',b'w:br',b'w:cr',b'w:p']:
                s+=b'\n'
        return s
    except Exception as e:
        return repr(e).encode()

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


def decode_payload(data,ctyp="text/html",charset=None):

    bom=False
    for b,cs in BOMS:  # BOM eseten az donti el a kodlapot (mint a bongeszokben), magat a BOM-ot levagjuk
        if data.startswith(b): data=data[len(b):]; charset=cs; bom=True; break

    ldata=data.lower()
    if ctyp=="text/calendar" or ctyp=="application/ics":
        data=parse_ics(data)
    elif ctyp=="application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        data=parse_docx(data)
        charset="utf-8"
    elif ctyp=="application/ms-tnef":
#        print("###### Parse TNEF ######")
        tnefobj = parse_tnef_body(data)
        if tnefobj and tnefobj['htmlbody']:
            data=html2text(tnefobj['htmlbody'].encode("utf-8"))   # a tnef_mini mar dekodolta (str)
            charset="utf-8"
        elif tnefobj and tnefobj['rtfbody']:
            try:
                cp=parse_rtfhead(tnefobj['rtfbody'],tnefobj['codepage'])
                rtf_text=tnefobj['rtfbody'].decode(cp,"mixed")
                data=rtf_to_text_safe(rtf_text,rtf_hex_encoding(cp)).encode("utf-8")  # striprtf, vagy ha az nincs / hibazik, a durva kinyero
                charset="utf-8"
            except Exception:
                pass  # marad az eredeti (nyers tnef) data, legalabb nem hasal el
    elif ctyp=="text/html" or ctyp=="text/xml" or ((ctyp!="text/plain" or b'</head>' in ldata or b'</br>' in ldata) and b'<' in ldata and (ldata.find(b'<body')>=0 or ldata.find(b'<img ')>=0 or ldata.find(b'<style')>=0 or ldata.find(b'<br>')>=0 or ldata.find(b'<center>')>=0 or ldata.find(b'<a href')>=0)):
        p=ldata.find(b'<body')
        if p>0 and not bom: charset=parse_htmlhead(data[:p],charset) # parse charset override from <head> (BOM eseten az dont)
        if charset and not ascii_compatible(charset_name(charset)):  # iso-2022-* (japan/koreai, 7 bites, ESC-el), utf-16/32, utf-7, hz: a html parser nem birja :)
            data=safe_decode(data,charset_name(charset),"ignore").encode("utf-8")
            charset="utf-8"
        data=html2text(data)     # binary version!

    charset=charset_name(charset or "iso8859-1")
    if ctyp=="application/rtf":
      charset=parse_rtfhead(data,charset)  # az RTF sajat \ansicpg-je elsobbseget kap a MIME charset-tel szemben

    # elobb strict utf-8 (gyakran utf-8 a szoveg mas charset cimkevel), ha nem az: a deklaralt kodlap mixed modban.
    # Nem ASCII-kompatibilis kodlapnal (utf-16/32, utf-7, iso-2022-jp, hz) nincs utf-8 proba, ott a 7 bites byte-sor tevesen atmenne
    try: data=data.decode("utf-8","strict") if ascii_compatible(charset) else safe_decode(data,charset)
    except UnicodeDecodeError: data=safe_decode(data,charset)  # latin1/2 + utf-8 keverek, ismeretlen kodlap: lasd safe_decode

    # ezt mar a dekodolas utan kell :(
    if ctyp=="application/rtf":
        data=rtf_to_text_safe(data,rtf_hex_encoding(charset)) # remove RTF markup (striprtf, ha hibazik: durva kinyero)
    else:
        data=unescape(data)  # fix &gt; etc

    return fix_chars(data)


def eml2str(msg,ds2=False):
  msg=parse_eml(msg,decode='lazy')  # csak a szovegkent felhasznalt reszek body-ja dekodolodik

  subject=None
  if ds2: # extract subject
    for h in msg["headers"]:
      try:
        hh=h.split(b':',1)
        if hh[0].lower()==b'subject': subject=remove_spamtag(hdrdecode4(hh[1]))
      except Exception: pass

  def walk(eml):
    if eml["parts"]:
        for p in eml["parts"]: yield from walk(p)
    else: yield eml

  text=""
  for p in walk(msg):
    ctyp=p["ctyp"]
    disp=p["disp"]
    charset=p["charset"]
    fnev=p["name"]
#    print((ctyp,charset,disp,fnev))
    if (ctyp.split('/')[0]=="text" and disp!="attachment") or ctyp=="application/ics" or (ctyp=="application/ms-tnef" and tnef_support) or ctyp=="application/rtf":
        data=get_payload(p)
        data=decode_payload(data,ctyp,charset)
#        if not text or len(data)>20: text=data # a kesobbi szoveg vszinu jobb (html>text, delivery hibak utan csatolva az eredeti level, elol a spamassassin fejlece stb)
        if not text or (ctyp in ["text/html","application/ms-tnef"] and len(data)>20) or len(data)>len(text)//2 or text.startswith("Spam detection software,"): text=data
        if ctyp in ["text/html","application/ms-tnef"] and len(text)>200: break
  return (subject,text) if subject else text


def get_mimedata(eml):
    mimeinfo=["RAW message: %d bytes"%(len(eml))]
    mimedata=[eml]
    msg=parse_eml(eml,decode=True)
    def walker(msg,level=0):
#        print(" "*(level*3), msg.is_multipart(), msg.get_content_type(), msg.get_content_charset(), msg.is_attachment(), msg.get_filename())
#        s=" "*(level*3) + "Multi:"+str(msg.is_multipart())+"  "+str(msg.get_content_type())
        ctyp=msg["ctyp"]
        cset=msg["charset"]
        s=" "*(level*3) + str(ctyp) # + str(msg.is_multipart())
        if cset: s+="["+str(cset)+"]"
        #raw=msg.as_bytes()
        raw=msg["raw"] # tupple of start-end position
        raw=eml[raw[0]:raw[1]]
        s+=" (%d) "%(len(raw))
        pay=msg.get("payload",None)
        html=None
        if pay:
            s+="%d"%(len(pay))
            if ctyp.startswith("text/") or ctyp=="application/ics" or (ctyp=="application/ms-tnef" and tnef_support) or ctyp=="application/rtf" or ctyp=="application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                html=decode_payload(pay,ctyp,cset) # ez meg a prettify elott kell, mert az elbassza a whitespacet...
                if ctyp=="text/html" or ctyp=="text/xml":
                    html="\n".join([" ".join(s.split()) for s in html.splitlines() if s]) # remove empty lines and redundant spaces
                    dtext,dhtml=html2text(pay,debug=True)  # html prettify :)
                    pay=b''.join(dhtml)
        mimeinfo.append(s)

        # Attachment file:
        if msg["name"]:
            mimedata.append(raw)
            s=" "*(level*3+3)
            if msg["disp"]: s+=msg["disp"]+": "  # "Attach: " if msg.is_attachment() else "Inline: "
            s+=msg["name"]
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
        if msg["parts"]: #        msg.is_multipart():
            for subpart in msg["parts"]: #msg.get_payload():  # az iter_parts() bugos, csak multipartra jo, message/rfc-re NEM!!!
                walker(subpart,level+1)

#        if msg.is_multipart():
#            for subpart in msg.get_payload(): # policy=email.policy.compat32
#                walker(subpart,level+1)
    walker(msg)
    return mimeinfo,mimedata


#TAG_RE1 = re.compile(r'<[^>]+>')
#TAG_RE2 = re.compile(r'\[[^[]+\]')
TAG_RE3 = re.compile(r'https? ?: ?//[-._a-zA-Z0-9/?&=#@]*')
TAG_RE4 = re.compile(r'[-+_$=_.A-Za-z0-9]*@[-.a-z0-9]*\.[a-z][a-z][a-z]*')
TAG_RE5 = re.compile(r'[1-9][-.,:/0-9 ]+[0-9]')
TAG_RE6 = re.compile(r'[a-zA-Z][a-zA-Z][-.0-9a-zA-Z]*\.hu')

#TAG_RE6 = re.compile(r'[-0-9a-z][-0-9a-z][-0-9a-z]*\.[-0-9a-z][-0-9a-z][-0-9a-z]*\.[-0-9a-z][-0-9a-z][-0-9a-z]?')
#TAG_email=re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')

def remove_url(text):
    text=TAG_RE3.sub('<URL>', text)
    text=TAG_RE4.sub('<EMAIL>', text)
    text=TAG_RE6.sub('<DOMAIN>', text)
#    text=TAG_RE5.sub('<NUMBER>', text)
    return text

# *****SPAM{15.0}*****
STAG_SA = re.compile(r'\*\*\*\*\*SPAM[{(][0-9][.0-9]*[)}]\*\*\**')

def remove_spamtag(text):
    text=STAG_SA.sub("", text) # Spamassassin
    text=text.replace("*****SPAM*****","").replace("[SPAM]","").replace("[Spam]","") # External
    text=text.replace("[SpaM]","").replace("[E:spam]","").replace("[E:infected]","") # ESETS
    text=text.replace("[K:Spam]","").replace("[K:Phishing]","").replace("[K:Virus]","").replace("[K:Mass]","") # Kaspersky
    text=text.replace("[Outlook levélszemét-bejelentő]","").replace("[Outlook junk mail report]","") # Outlook
    return text

def vocab_split(preview):
#    preview=remove_url(preview)
    tok=[]
    s=""
    inw=False
    for c in preview:
#        if not c.isalpha(): # if c in '\n\t #".,!?;:_-+/*()[]{}0123456789':
#        if not c.isalnum():
        if not (c.isalnum() or (s and s[-1].isnumeric() and c in ":-/." )): # handle special case of date/phone numbers...
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



# parses "Content-*: value; option2=value2" type headers to dict
def parse_ctyp(data,hdr=b'_',ct=None):
    if ct==None: ct={}
#    print(hdr,data)

    p=data.find(b';')
    if p<0: p=len(data)
    ct[hdr]=data[:p].strip().split(b' ')[0]

    # parse parameters:
    q=p+1
    ijel=None
    eqsn=False
    name=[]
    value=[]
    while q<len(data):
      c=data[q]
      q+=1
      if ijel:  #  quoted string-en belul vagyunk?
#        if c==62 or c==60: warning+="WARN! %c inside %c at %d\n"%(c,ijel,q) # < vagy > idezojelek kozott, de ez amugy okes
        if c==ijel: ijel=None  #  idezet vege
        else: value.append(c)  #  idezojelen belul kell minden whitespace is...
      elif c==59: #  ;
        if name: ct[bytes(name).lower()]=bytes(value).rstrip()
        name=[]
        value=[]
        eqsn=False
      elif eqsn:  #  after the = character -> value
        # " barhol idezojel, de ' csak az ertek elejen (nem szabvanyos, de elofordul), kulonben
        # elrontana az O'Brien.pdf es az RFC 2231 filename*=UTF-8''... ertekeket (ott soha nem idezojel)
        if c==34 or (c==39 and not value and name and name[-1]!=42): ijel=c
        elif value or c>32: value.append(c)  # skip initial WS
      else:     #  before the = character -> name
        if c==61: eqsn=True #  =
        elif name or c>32: name.append(c)
    if name: ct[bytes(name).lower()]=bytes(value).rstrip()
    return ct


# https://www.w3.org/Protocols/rfc1341/5_Content-Transfer-Encoding.html
def decode_body(data,encoding,binary=True):
    try:
        if encoding=='base64': return a2b_base64(data+b'===')  # hianyzo padding potlasa (a tobblet nem zavar)
#        if encoding=='quoted-printable': return a2b_qp(data)
        if encoding in ['quoted-printable','utf8','utf-8']:
            if binary: data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')   # str-nel ugyanez '\r\n' /
            return a2b_qp(data)
    except Exception as e:
        print("PayloadDecodingExc:",repr(e))
#    if not encoding in ['7bit','8bit','binary','utf-8']: print("UnknownEncoding:",encoding)
    if encoding and not encoding in ['7bit','8bit','binary']: print("UnknownEncoding:",encoding) # The values "8bit", "7bit", and "binary" all imply that NO encoding
    return data


def header_end(data,p,pend):
    # a fejlec vege: min(find(b'\n\n')+2, find(b'\r\n\r\n')+4) a data[p:pend]-ben, kulonben pend.
    # Egy menetben, a sorvegeken lepkedve: a ket kulon find() CRLF-es levelnel (ahol nincs \n\n) a resz vegeig
    # keresett, minden MIME-resznel ujra.
    i=data.find(b'\n',p,pend)
    while i>=0:
        if i+1<pend and data[i+1]==10: return i+2,b'\n'
        if i>p and data[i-1]==13 and i+2<pend and data[i+1]==13 and data[i+2]==10: return i+3,b'\r\n'
        i=data.find(b'\n',i+1,pend)
    return pend,b'\n'

# decode='lazy' eseten a body dekodolasa (Content-Transfer-Encoding) csak keresre, a get_payload()-ban tortenik
def get_payload(eml):
    if "payload" not in eml and "_body" in eml:
        data,hsize,pend=eml["_body"]
        eml["payload"]=decode_body(data[hsize:pend], eml["encoding"])
    return eml.get("payload")

def parse_eml(data,debug=False,decode=False,level=0,p=0,pend=-1):
    if pend<0: pend=len(data)
    
    # find header size:
    hsize,newline=header_end(data,p,pend)
    if debug: print("parse_eml:", level, p,hsize, pend,  newline, data[p:p+32],data[hsize:hsize+32],data[pend-32:pend])
#    if level>0 and not data.startswith(b'Content-') and b'Content-' in data: print("BadHeader:",data[:120]) # MIME-Version: es Date: is szokott lenni legelol...

    # process headers
    headers=[]
    hdr=None
    for rawline in data[p:hsize].split(b'\n'):
        line=rawline.rstrip(b'\r')
        if line and line[0] in [9,32]:
            hdr+=b' '+line.lstrip(b'\t ')
            continue
        if hdr: headers.append(hdr)
        hdr=line
        if len(line)==0: break
    if hdr: headers.append(hdr)  # nincs ures sor a fejlec utan (hsize==pend): az utolso fejlec is kell

    # parse Content-*: headers (get type/encoding/charset/filename)
    ct={}
    for hdr in headers:
        h=hdr.split(b':',1)
#        if debug: print(h)
        if h[0].lower()==b'content-type': parse_ctyp(h[1],b'_ct',ct)
        if h[0].lower()==b'content-disposition': parse_ctyp(h[1],b'_cd',ct)
        if h[0].lower()==b'content-transfer-encoding': parse_ctyp(h[1],b'_ce',ct)
#    if debug: print(level,hsize,len(data),ct)

    ctyp=ct.get(b'_ct',b'').decode("us-ascii",errors="ignore").lower()
    cenc=ct.get(b'_ce',b'').decode("us-ascii",errors="ignore").lower()
#    disp=ct.get(b'_cd',b'').decode("us-ascii",errors="ignore").lower()
    disp=ct[b'_cd'].decode("us-ascii",errors="ignore").lower() if b'_cd' in ct else None
#    cset=ct.get(b'charset',b'').decode("us-ascii",errors="ignore").lower()
    cset=ct[b'charset'].decode("us-ascii",errors="ignore").lower() if b'charset' in ct else None
    try:
        name=ct_param(ct,b'filename')
        if name is None: name=ct_param(ct,b'name')
    except Exception as e: name="EXC!"; print("FilenameExc:",repr(e)) # hdrdecode4 may fail for wrong codepage
    eml={"headers":headers, "raw":(p,pend), "size":pend-p, "hsize":hsize-p, "ct":ct, "ctyp":ctyp or 'text/plain', "charset":cset, "encoding":cenc, "disp":disp, "name":name, "parts":[]}

#    if b'name' in ct: print("FNAME:",hdrdecode4(ct[b'name']))
#    if b'filename' in ct: print("FNAME:",hdrdecode4(ct[b'filename']))

#  27140 MULTI: b'multipart/alternative'
#   1388 MULTI: b'multipart/mixed'
#   1701 MULTI: b'multipart/related'
#     23 MULTI: b'multipart/report'
#      1 MULTI: b'multipart/digest'
#      1 MULTI: b'multipart/parallel'
    if b'boundary' in ct and ctyp.startswith('multipart/'):
        # split data by boundary to parts
        bo=b'--'+ct[b'boundary']
        q=p=hsize # data=data[hsize:]
        first=True
        last=False
        while p<pend:
            p=data.find(bo,p,pend)
            _p=p
            if p<0: # process data after the last boundary: (the end-boundary tag is missing too often...)
#                if first: print("BoundaryNotFound:",q,pend,bo) #, data[:100])
                if not last: print("BoundaryNotFound:",q,pend,bo) #, data[:100])
                pp=p=pend
                if data[q:q+8]!=b'Content-' and data[q:pend].strip(): print("PostBoundaryText:",q,p,len(data), data[q:pend])
#                print(_p,p,pp)
            else:
                pp=p  # pp->start of next boundary
                p+=len(bo)
                if pp>0 and data[pp-1]==10:  # backward skip pre-boundary newline...  for compatibility with email lib :(
                    pp-=1
                    if pp>0 and data[pp-1]==13: pp-=1
                else: print("BoundaryNoNewline:",q,pp,pend,bo)
            #if debug: 
            if data[p:p+2]==b'--':
                p+=2 # end boundary
                last=True
            if debug: print(level,"Boundary:",_p,first,last,q,pp,p,pend,data[pp:p],data[p:min(p+10,pend)])
            #  (p->end of next boundary)
            if p>=pend or data[p]<=32 or data[p:p+8]==b'Content-': # boundary string at EOF or followed by newline/whitespace or Content-*
                # found!
                part=data[q:pp]
                if part and len(part.strip())>2: # not empty block
                    if first and b'Content-Type:' in part: # headers before first boundary!
                        q+=part.find(b'Content-')  # workaround buggy emails
                        print("BoundaryFixCont:",q,data[q:q+20],part[:50])
                        first=False
                    if not first or len(part)>=300 or not (b'MIME' in part or b'multipart message' in part.lower() or b' mime format' in part.lower()): # skip empty/useless compatibility text!
                        if first: print("PreBoundaryText:",len(part),part)
                        pe=parse_eml(data,debug,decode,level+1,p=q,pend=pp)
                        eml["parts"].append(pe)
#                    else: print("SkipUseless:",len(part),part)
                while p<pend and data[p]<=32 and data[p]!=10: p+=1 # skip whitespace
                if p<pend and data[p]==10: p+=1 # skip newline
                q=p
                first=False
            elif data[p:p+4]!=b'_alt': print("BoundarySkip:",q,pp,p,data[pp:p],data[p:p+10])

    elif ctyp.startswith('message/'):
        # message/disposition-notification
        # message/rfc822
        pe=parse_eml(data,debug,decode,level+1,p=hsize,pend=pend)
        eml["parts"].append(pe)
    elif decode=='lazy':
        eml["_body"]=(data,hsize,pend)  # csak a get_payload() dekodolja (a csatolmanyokat igy nem kell)
    elif decode:
        # data, decode?
        eml["payload"]=decode_body(data[hsize:pend], cenc)
#        if not ctyp and len(eml["payload"].strip())<3: eml["payload"]=data[p:pend] # no headers, no body...

    return eml


def readfolder(f,do_eml,keephdrs=['from','subject','x-deepspam','x-grey-ng']):
  eml=None
  in_hdr=0
  fpos=f.tell()
  for rawline in f:

    if in_hdr:
        fpos+=len(rawline)

        line=rawline.rstrip(b'\r\n') # The chars argument is a string specifying the set of characters to be removed. 
        if len(line)==0: # empty line -> end of the header
            in_hdr=0
            eml["_hsize"]=fpos-eml["_fpos"]
        elif line[0] in [9,32]: # starts with tab/space -> header continuation
            hdr+=line # keep whitespace?
            continue

        if hdr:
            try:
                hdrname,hdrbody = hdr.split(b':',1)
                hdrname=hdrname.decode("us-ascii").lower()
                if hdrname in keephdrs: # csak ezek kellenek
                    eml[hdrname]=hdrbody.lstrip().decode("utf-8", 'mixed')
            except Exception as e:
                print("INVALID:",hdr,"\n   EXC:", repr(e))

        hdr=line
        continue

    # in body:
    if rawline[0:5]==b'From ':
        if eml: do_eml(eml,fpos)
        in_hdr=1
        hdr=b''
        eml={"_fpos":fpos,"_from":rawline.rstrip(b'\r\n').decode("us-ascii", errors="ignore")}

    elif not eml: # and (rawline[:10]==b'X-Grey-ng:' or rawline[:9]==b'Received:'):
        in_hdr=1
        hdr=rawline.rstrip(b'\r\n')
        eml={"_fpos":fpos}

    elif rawline.startswith(b'Content-Disposition: attachment'):
        eml['_attach']=True

    fpos+=len(rawline)

  if eml: do_eml(eml,fpos)
  return fpos # folder file size




hdr_re=re.compile(r'=\?([^?]*?)\?([qQbB])\?(.*?)\?=') # non-greedy matching   =? ... ? [bBqQ] ? ... ?=

def hdrdecode4(h):
    if type(h)!=str: h=h.decode("utf-8","mixed") # handle bytes input
    parts = hdr_re.split(h)
#    print(type(parts),parts)
    strips=[]
    while parts:
        textpart=parts.pop(0)
        if textpart and not textpart.isspace(): strips.append([textpart,None]) # ignore spaces between encoded parts!
        if parts:
            cset=parts.pop(0).lower().split('*')[0] # RFC 2231 nyelvjelolo levagasa:  =?UTF-8*hu?Q?...?=
            cfmt=parts.pop(0).lower() # csak q es b lehet!
            cenc=parts.pop(0)
#            print((cset,cfmt,cenc))
            try:
                # bytes-kent, mert az encoded-word-on beluli nyers 8 bites resz str-kent ValueError-t dobna
                if cfmt=='q': cdec=a2b_qp(cenc.replace("==","=").encode("utf-8"), header=True) # lehets=C3==A9ges
                else: cdec=a2b_base64(cenc.encode("utf-8")+b"===")
                # EVIL workaround: some utf8 strings are splitted in the middle of an utf8 character...
                if strips and strips[-1][1]==cset: #    try to concatenate these parts before decoding!
                    strips[-1][0]+=cdec
                else:
                    strips.append([cdec,cset])
            except Exception as e:
                print(repr(e),cfmt,repr(cenc))
                strips.append([cenc,None])  # ne vesszen el, nyersen marad
    return fix_chars("".join(x[0] if x[1] is None else safe_decode(x[0],charset_name(x[1])) for x in strips))


# RFC 2231 parameter value continuations/encoding:  filename*=UTF-8''sz%C3%A1mla.pdf
#   filename*0*=UTF-8''hossz%C3%BA; filename*1*=_n%C3%A9v.pdf; filename*2=".pdf"
param_re=re.compile(rb'^\*(?:(\d+)(\*)?)?$')

def rfc2231_decode(ct,key):
    parts=[]
    for k,v in ct.items():
        if k.startswith(key+b'*'):
            m=param_re.match(k[len(key):])
            if m: parts.append((int(m.group(1) or 0), m.group(1) is None or m.group(2) is not None, v))
    if not parts: return None
    parts.sort()
    raw=b''
    cset='us-ascii'
    for i,(n,encoded,v) in enumerate(parts):
        if encoded:
            if i==0 and v.count(b"'")>=2:
                cs,lang,v=v.split(b"'",2)
                cset=cs.decode("us-ascii","ignore").lower() or 'us-ascii'
            v=unquote_to_bytes(v)
        raw+=v
    return fix_chars(safe_decode(raw,charset_name(cset)))

# decoded parameter value from parse_ctyp() dict: RFC 2231 (key*=...) preferred, then RFC 2047 (key=...)
def ct_param(ct,key):
    v=rfc2231_decode(ct,key)
    if v is None and key in ct: v=hdrdecode4(ct[key])
    return v


from_re1=re.compile(r'^(?:(\"((?:\\.|[^\"])*?)\"\s*)|(.*?))\s*<([^>]*?)>$') # ("val\" ami"|vala mi) <emailcim>   -> \2|\3 <\4>
from_re2=re.compile(r'^(.*?)([^<>\")\s]*@[-.a-zA-Z0-9]*)\s*(\(.*\))?') # \1 emailcim (\3)   -> \3|\1 <\2>

# split From: header to Address and Name part (does not decode)
def parse_from(h):
    m=from_re1.match(h)
    if m:  # match!   new style:  name <address>
        return m.group(4),(m.group(2) or m.group(3) or "")
    m=from_re2.match(h)
    if m:  # match!   old style:  address (name)
        return m.group(2),(m.group(3) or m.group(1) or "")
#    print("BADdress:",h)
    return "",h  # no address found...

# split From: header to Address and Name part (and decode it)
def decode_from(h):
    a,n=parse_from(h.strip())
    n=hdrdecode4(n)
    if not a and '@' in n: a,n=parse_from(n.strip()) # workaround(=ugly hack) for base64-encoded email addresses...
#   print("%50s | %s"%(a,n))
    return a,n

    