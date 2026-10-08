#!/usr/bin/env python3
# A Python codec-registry, az egybajtos kodtablak es a html.unescape tablainak kiirasa Rust forraskodba (src/tables.rs),
# hogy a Rust port pontosan ugyanugy oldja fel / dekodolja a charset-neveket, mint a Python (+ az eml2str sajat aliasai).
#   python3 gen_tables.py > tables.rs   (a build.rs futtatja forditaskor, az OUT_DIR-be)
import codecs, encodings, encodings.aliases, html, html.entities, os, pkgutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import eml2str  # regisztralja a sajat codec-keresot (codec_aliases)

def norm_c(name):  # a CPython _Py_normalize_encoding()-ja (a codecs.lookup ezt kapja)
    out, punct = [], False
    for c in name:
        if (c.isascii() and c.isalnum()) or c == '.':
            if punct and out: out.append('_')
            out.append(c.lower()); punct = False
        else: punct = True
    return ''.join(out)

PROBE = b'<body +x- ~~ \x1b$B>'
RTFPROBE = b'{\\rtf1 +x-}'

MB = {  # CJK kodlapok -> encoding_rs (ervenyes bemenetre azonos a Pythonnal, hibas byte-oknal elterhet)
    'gb2312': 'GBK', 'gbk': 'GBK', 'gb18030': 'GB18030',
    'big5': 'BIG5', 'big5hkscs': 'BIG5', 'cp950': 'BIG5',
    'shift_jis': 'SHIFT_JIS', 'cp932': 'SHIFT_JIS', 'shift_jis_2004': 'SHIFT_JIS', 'shift_jisx0213': 'SHIFT_JIS',
    'euc_jp': 'EUC_JP', 'euc_jis_2004': 'EUC_JP', 'euc_jisx0213': 'EUC_JP',
    'euc_kr': 'EUC_KR', 'cp949': 'EUC_KR',
    'iso2022_jp': 'ISO_2022_JP', 'iso2022_jp_1': 'ISO_2022_JP', 'iso2022_jp_2': 'ISO_2022_JP',
    'iso2022_jp_2004': 'ISO_2022_JP', 'iso2022_jp_3': 'ISO_2022_JP', 'iso2022_jp_ext': 'ISO_2022_JP',
}
SIMPLE = {'utf-8': 'Utf8', 'utf-8-sig': 'Utf8Sig', 'iso8859-1': 'Latin1', 'ascii': 'Ascii',
          'utf-16': 'Utf16', 'utf-16-le': 'Utf16Le', 'utf-16-be': 'Utf16Be',
          'utf-32': 'Utf32', 'utf-32-le': 'Utf32Le', 'utf-32-be': 'Utf32Be'}

codec_list, codec_idx, charmaps = [], {}, []

def codec_of(ci):
    name = ci.name
    if name in codec_idx: return codec_idx[name]
    try: PROBE.decode(name); ascii_ok = (PROBE.decode(name) == PROBE.decode('ascii'))
    except LookupError: ascii_ok = True
    except UnicodeError: ascii_ok = False
    try: rtf_ok = RTFPROBE.decode(name) == RTFPROBE.decode('ascii')
    except (LookupError, UnicodeError): rtf_ok = False
    modname = getattr(ci.decode, '__module__', '') or ''
    mod = sys.modules.get(modname)
    if not getattr(ci, '_is_text_encoding', True): kind = 'NotText'
    elif name in SIMPLE: kind = SIMPLE[name]
    elif mod is not None and hasattr(mod, 'decoding_table') and isinstance(mod.decoding_table, str) and len(mod.decoding_table) == 256:
        kind = 'Charmap(%d)' % len(charmaps); charmaps.append([ord(c) for c in mod.decoding_table])
    elif name == 'utf-7': kind = 'Utf7'
    elif name.replace('-', '_') in MB: kind = 'Mb(&encoding_rs::%s_INIT)' % MB[name.replace('-', '_')]
    elif name in ('undefined', 'idna'): kind = 'Undefined'  # az idna is UnicodeError-t dob minden nem-strict hibakezelore
    elif name == 'charmap': kind = 'Latin1'  # mapping nelkul a charmap codec latin-1
    else: kind = 'Unsupported'  # hz, johab, iso2022_kr, punycode, unicode_escape...: utf-8 + mixed-del kozelitjuk
    codec_idx[name] = len(codec_list)
    codec_list.append((name, kind, ascii_ok, rtf_ok))
    return codec_idx[name]

def lookup(n):
    try: return codec_of(codecs.lookup(n))
    except LookupError: return None

aliases, modules, custom = {}, {}, {}
for k, target in encodings.aliases.aliases.items():
    i = lookup(k)
    if i is not None: aliases[k] = i
for m in pkgutil.iter_modules(encodings.__path__):
    if m.name in ('aliases',): continue
    i = lookup(m.name)
    if i is not None: modules[m.name] = i
for k in eml2str._codec_aliases:
    i = lookup(k)
    if i is not None: custom[k] = i

# sajat ellenorzes: a Rust oldali feloldasi szabaly ugyanazt adja-e, mint a codecs.lookup
def rust_rule(n):
    k = norm_c(n)
    if k in aliases: return aliases[k]
    if k.replace('.', '_') in aliases: return aliases[k.replace('.', '_')]
    if k and '.' not in k and k in modules: return modules[k]
    return custom.get(k)
tests = list(aliases) + list(modules) + list(eml2str.codec_aliases) + list(eml2str.charset_overrides.values()) + \
        ['UTF-8', 'Windows-1250', 'iso 8859 2', 'cp-850', 'X-Mac-CE', 'utf.8', 'iso8859.2', 'latin-1', 'ibm852', 'utf8 x', '', 'cp65001']
for n in tests:
    try: exp = codec_idx[codecs.lookup(n).name]
    except LookupError: exp = None
    assert rust_rule(n) == exp, (n, rust_rule(n), exp)

def rs(s): return '"' + ''.join(c if 32 <= ord(c) < 127 and c not in '"\\' else '\\u{%x}' % ord(c) for c in s) + '"'

o = sys.stdout
o.write('// GENERALT FAJL - gen_tables.py, Python %s\nuse crate::codec::Kind;\n\n' % sys.version.split()[0])
o.write('pub static CODECS: &[(&str, Kind, bool, bool)] = &[  // nev, tipus, ascii_compatible, rtf probe ok\n')
for name, kind, a, r in codec_list: o.write('    (%s, Kind::%s, %s, %s),\n' % (rs(name), kind, str(a).lower(), str(r).lower()))
o.write('];\n\n')
for nm, d in (('ALIASES', aliases), ('MODULES', modules), ('CUSTOM', custom)):
    o.write('pub static %s: &[(&str, u16)] = &[\n' % nm)
    for k in sorted(d): o.write('    (%s, %d),\n' % (rs(k), d[k]))
    o.write('];\n\n')
o.write('pub static CHARMAPS: &[[u32; 256]] = &[\n')
for t in charmaps: o.write('    [' + ','.join('0x%x' % c for c in t) + '],\n')
o.write('];\n\n')
o.write('pub static HTML5: &[(&str, &str)] = &[\n')
for k in sorted(html.entities.html5): o.write('    (%s, %s),\n' % (rs(k), rs(html.entities.html5[k])))
o.write('];\n\n')
import html as H
o.write('pub static HTML_INVALID_CHARREFS: &[(u32, &str)] = &[\n')
for k in sorted(H._invalid_charrefs): o.write('    (%d, %s),\n' % (k, rs(H._invalid_charrefs[k])))
o.write('];\n\npub static HTML_INVALID_CODEPOINTS: &[u32] = &[%s];\n\n' % ','.join(str(c) for c in sorted(H._invalid_codepoints)))
o.write('pub static INVALID_CHARREFS: &[(u32, &str)] = &[  // eml2str.invalid_charrefs\n')
for k in sorted(eml2str.invalid_charrefs): o.write('    (%d, %s),\n' % (k, rs(eml2str.invalid_charrefs[k])))
o.write('];\n\npub static CHARSET_OVERRIDES: &[(&str, &str)] = &[\n')
for k in sorted(eml2str.charset_overrides): o.write('    (%s, %s),\n' % (rs(k), rs(eml2str.charset_overrides[k])))
o.write('];\n')
print('codecs: %d  charmaps: %d  aliases: %d  modules: %d  custom: %d' % (len(codec_list), len(charmaps), len(aliases), len(modules), len(custom)), file=sys.stderr)
print([c for c in codec_list if c[1] == 'Unsupported'], file=sys.stderr)
