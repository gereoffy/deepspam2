
import codecs
import email
import re

def mixed_decoder(unicode_error):
    position = unicode_error.start
    new_char = unicode_error.object[position:position+1]
    new_char = new_char.decode("iso8859-2","ignore")
#    print(type(new_char))
#    print(len(new_char))
    return new_char, position + 1

codecs.register_error("mixed", mixed_decoder)

# missing in python3... but unescape() of py3's HTMLParser is broken...

name2codepoint={
  "AElig": 198, 
  "Aacute": 193, 
  "Acirc": 194, 
  "Agrave": 192, 
  "Alpha": 913, 
  "Aring": 197, 
  "Atilde": 195, 
  "Auml": 196, 
  "Beta": 914, 
  "Ccedil": 199, 
  "Chi": 935, 
  "Dagger": 8225, 
  "Delta": 916, 
  "ETH": 208, 
  "Eacute": 201, 
  "Ecirc": 202, 
  "Egrave": 200, 
  "Epsilon": 917, 
  "Eta": 919, 
  "Euml": 203, 
  "Gamma": 915, 
  "Iacute": 205, 
  "Icirc": 206, 
  "Igrave": 204, 
  "Iota": 921, 
  "Iuml": 207, 
  "Kappa": 922, 
  "Lambda": 923, 
  "Mu": 924, 
  "Ntilde": 209, 
  "Nu": 925, 
  "OElig": 338, 
  "Oacute": 211, 
  "Ocirc": 212, 
  "Ograve": 210, 
  "Omega": 937, 
  "Omicron": 927, 
  "Oslash": 216, 
  "Otilde": 213, 
  "Ouml": 214, 
  "Phi": 934, 
  "Pi": 928, 
  "Prime": 8243, 
  "Psi": 936, 
  "Rho": 929, 
  "Scaron": 352, 
  "Sigma": 931, 
  "THORN": 222, 
  "Tau": 932, 
  "Theta": 920, 
  "Uacute": 218, 
  "Ucirc": 219, 
  "Ugrave": 217, 
  "Upsilon": 933, 
  "Uuml": 220, 
  "Xi": 926, 
  "Yacute": 221, 
  "Yuml": 376, 
  "Zeta": 918, 
  "aacute": 225, 
  "acirc": 226, 
  "acute": 180, 
  "aelig": 230, 
  "agrave": 224, 
  "alefsym": 8501, 
  "alpha": 945, 
  "amp": 38, 
  "and": 8743, 
  "ang": 8736, 
  "aring": 229, 
  "asymp": 8776, 
  "atilde": 227, 
  "auml": 228, 
  "bdquo": 8222, 
  "beta": 946, 
  "brvbar": 166, 
  "bull": 8226, 
  "cap": 8745, 
  "ccedil": 231, 
  "cedil": 184, 
  "cent": 162, 
  "chi": 967, 
  "circ": 710, 
  "clubs": 9827, 
  "cong": 8773, 
  "copy": 169, 
  "crarr": 8629, 
  "cup": 8746, 
  "curren": 164, 
  "dArr": 8659, 
  "dagger": 8224, 
  "darr": 8595, 
  "deg": 176, 
  "delta": 948, 
  "diams": 9830, 
  "divide": 247, 
  "eacute": 233, 
  "ecirc": 234, 
  "egrave": 232, 
  "empty": 8709, 
  "emsp": 8195, 
  "ensp": 8194, 
  "epsilon": 949, 
  "equiv": 8801, 
  "eta": 951, 
  "eth": 240, 
  "euml": 235, 
  "euro": 8364, 
  "exist": 8707, 
  "fnof": 402, 
  "forall": 8704, 
  "frac12": 189, 
  "frac14": 188, 
  "frac34": 190, 
  "frasl": 8260, 
  "gamma": 947, 
  "ge": 8805, 
  "gt": 62, 
  "hArr": 8660, 
  "harr": 8596, 
  "hearts": 9829, 
  "hellip": 8230, 
  "iacute": 237, 
  "icirc": 238, 
  "iexcl": 161, 
  "igrave": 236, 
  "image": 8465, 
  "infin": 8734, 
  "int": 8747, 
  "iota": 953, 
  "iquest": 191, 
  "isin": 8712, 
  "iuml": 239, 
  "kappa": 954, 
  "lArr": 8656, 
  "lambda": 955, 
  "lang": 9001, 
  "laquo": 171, 
  "larr": 8592, 
  "lceil": 8968, 
  "ldquo": 8220, 
  "le": 8804, 
  "lfloor": 8970, 
  "lowast": 8727, 
  "loz": 9674, 
  "lrm": 8206, 
  "lsaquo": 8249, 
  "lsquo": 8216, 
  "lt": 60, 
  "macr": 175, 
  "mdash": 8212, 
  "micro": 181, 
  "middot": 183, 
  "minus": 8722, 
  "mu": 956, 
  "nabla": 8711, 
  "nbsp": 160, 
  "ndash": 8211, 
  "ne": 8800, 
  "ni": 8715, 
  "not": 172, 
  "notin": 8713, 
  "nsub": 8836, 
  "ntilde": 241, 
  "nu": 957, 
  "oacute": 243, 
  "ocirc": 244, 
  "oelig": 339, 
  "ograve": 242, 
  "oline": 8254, 
  "omega": 969, 
  "omicron": 959, 
  "oplus": 8853, 
  "or": 8744, 
  "ordf": 170, 
  "ordm": 186, 
  "oslash": 248, 
  "otilde": 245, 
  "otimes": 8855, 
  "ouml": 246, 
  "para": 182, 
  "part": 8706, 
  "permil": 8240, 
  "perp": 8869, 
  "phi": 966, 
  "pi": 960, 
  "piv": 982, 
  "plusmn": 177, 
  "pound": 163, 
  "prime": 8242, 
  "prod": 8719, 
  "prop": 8733, 
  "psi": 968, 
  "quot": 34, 
  "rArr": 8658, 
  "radic": 8730, 
  "rang": 9002, 
  "raquo": 187, 
  "rarr": 8594, 
  "rceil": 8969, 
  "rdquo": 8221, 
  "real": 8476, 
  "reg": 174, 
  "rfloor": 8971, 
  "rho": 961, 
  "rlm": 8207, 
  "rsaquo": 8250, 
  "rsquo": 8217, 
  "sbquo": 8218, 
  "scaron": 353, 
  "sdot": 8901, 
  "sect": 167, 
  "shy": 173, 
  "sigma": 963, 
  "sigmaf": 962, 
  "sim": 8764, 
  "spades": 9824, 
  "sub": 8834, 
  "sube": 8838, 
  "sum": 8721, 
  "sup": 8835, 
  "sup1": 185, 
  "sup2": 178, 
  "sup3": 179, 
  "supe": 8839, 
  "szlig": 223, 
  "tau": 964, 
  "there4": 8756, 
  "theta": 952, 
  "thetasym": 977, 
  "thinsp": 8201, 
  "thorn": 254, 
  "tilde": 732, 
  "times": 215, 
  "trade": 8482, 
  "uArr": 8657, 
  "uacute": 250, 
  "uarr": 8593, 
  "ucirc": 251, 
  "ugrave": 249, 
  "uml": 168, 
  "upsih": 978, 
  "upsilon": 965, 
  "uuml": 252, 
  "weierp": 8472, 
  "xi": 958, 
  "yacute": 253, 
  "yen": 165, 
  "yuml": 255, 
  "zeta": 950, 
  "zwj": 8205, 
  "zwnj": 8204
}


HTML_RE = re.compile(r'&([^;]+);')
def html_unescape(mystring):
  return HTML_RE.sub(lambda m: chr(name2codepoint.get(m.group(1),63)), mystring)

def replaceEntities(s):
    x = s.group(0)
    s = s.group(1)
#    print(s) #  '#43'
    if s[0] == "#":
        if s[1] in ['x','X']:
            c = int(s[2:], 16)
        else:
            c = int(s[1:])
#        if c>=128: # ekezetes karakter, nem irasjel
        return chr(c) # python3-ban chr()
    return x # beken hagyjuk

#    r_unescape = re.compile(r"&(#?[xX]?(?:[0-9a-fA-F]+|\w{1,8}));") # ez erre is matchel:   &nbsp;
r_unescape = re.compile(r"&(#[xX]?[0-9a-fA-F]+);") # de nekunk csak az ekezetes betu unikodok kellenek!
def xmldecode(data):
  return r_unescape.sub(replaceEntities, data)

def html2text(data):
  in_style=0
  in_script=0

#  data=HTML_comment.sub("<comment>",data)
  p=data.find("<!--")
  while p>=0:
    q=data.find("-->",p)
    if q<p:
      data=data[:p]
      break
#    data=data[:p]+" HTMLcomment "+data[q+3:]
    data=data[:p]+data[q+3:]
    p=data.find("<!--",p)

  text=""
  for ret in data.split("<"):
    try:
      tag,txt=ret.split(">",1)
    except:
      text+=ret
      continue
#      print(ret.encode("utf-8"))
#      break
#    print("TAG: '%s'"%(tag))
    try:
      tag1=tag.split()[0].lower()
    except:
      print("TAG parse error: '%s'"%(tag))
      tag1=""
    if tag1=="style":
      in_style+=1
    if tag1=="/style":
      in_style-=1
    if tag1=="script":
      in_script+=1
    if tag1=="/script":
      in_script-=1
#    print(tag1)
#    print(text)
    if in_style<=0 and in_script<=0:
#      if tag1 in ["p","span","div"]:
#        print(tag.lower())
      if tag1=="p" or tag1=="br" or tag1=="td" or tag1=="div" or tag1=="li":
        text+="\n"
      text+=txt

  text=" ".join(text.split()) # remove redundant whitespace
  return text



def eml2str(msg):
  msg = email.message_from_bytes(msg)
  text=""
  #pp = msg.get_payload()
  for p in msg.walk():
#    print p.get_content_type()
    charset=p.get_content_charset("utf-8")
#    print("charset='%s'"%charset)
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
    ctyp=p.get_content_type().lower()
    fnev=str(p.get_filename())
    disp=p.get_content_disposition()
#    print((ctyp,disp,fnev))
    if ctyp.split('/')[0]=="text" and disp!="attachment":
#      print(ctyp)
#      if ctyp.find("rfc")>=0:
#        continue
      try:
        data=p.get_payload(decode=True)
        try:
          data=data.decode(charset, 'mixed')
        except:
          data=data.decode("utf-8", 'mixed')
        data=xmldecode(data) # plaintextre is rafer...
#        print(data)
        ldata=data.lower()
        if ctyp=="text/html" or ctyp=="text/xml" or data.find('<')>=0 and (ldata.find("<body")>=0 or ldata.find("<img")>=0 or ldata.find("<style")>=0 or ldata.find("<center")>=0 or ldata.find("<a href")>=0):
#          print(data.encode("iso8859-2"))
#          print("parsing html...")
          p=ldata.find("<body")
          if p>0: data=data[p:] # skip html header
          data=html2text(data)
#        elif ctyp=="text/plain":
        if len(data)>len(text):
            text=html_unescape(data) # fix &gt; etc
#        print(text)
      except:
        print(traceback.format_exc())
  return text


if __name__ == "__main__":
    s='&nbsp;&nbsp; Elküldve: 2023. május 31. 13:06:16 (UTC&#43;01:00) Belgrád, Budapest, Ljubljana, Pozsony, Prága<br>'
    print(s)
    print(xmldecode(s))
    print(html_unescape(s))
    
    print(eml2str(open("test.eml","rb").read()))
