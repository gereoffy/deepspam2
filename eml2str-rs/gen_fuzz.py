#!/usr/bin/env python3
# Differencialis fuzz-teszthez mbox generalasa: valodi levelek mutacioi + szintetikus levelek a ritka agakra
# (RTF, UTF-16/32, ICS, CJK, entitasok, hibas base64 / QP, encoded-word fejlecek, egymasba agyazott multipart).
#   python3 gen_fuzz.py Junk.mbox fuzz.mbox [N] [seed]
import random, sys, os, codecs, base64, quopri
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from bench_py import split_mbox

src, dst = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
rnd = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else 1)
real = split_mbox(open(src, 'rb').read())

CHARSETS = ['utf-8', 'UTF-8', 'utf8', 'iso-8859-1', 'iso-8859-2', 'latin2', 'latin-1', 'windows-1250', 'windows-1252',
    'windows-1251', 'cp1250', 'us-ascii', 'ascii', 'ibm852', 'cp-850', 'koi8-r', 'x-mac-ce', 'mac', 'gb2312', 'gbk',
    'gb18030', 'big5', 'shift_jis', 'sjis', 'euc-jp', 'euc-kr', 'ks_c_5601-1987', 'iso-2022-jp', 'utf-16', 'utf-16le',
    'utf-16be', 'utf-32', 'utf-7', 'iso-8859-8-i', 'iso-8859-15', 'tis-620', 'windows-874', 'base64', 'undefined',
    'unknown-8bit', 'x-unknown', '', 'utf-8 garbage', 'ISO_8859-2:1987', 'iso8859.2', 'hz-gb-2312', 'johab', 'cp037',
    'iso-2022-jp-2', 'iso-2022-kr', 'big5-hkscs', 'cp949', 'euc-jisx0213', 'shift_jis_2004', 'utf-32be', 'utf-8-sig',
    'idna', 'cp65001', 'macintosh', 'cp437', 'iso-8859-3', 'iso-8859-6', 'iso-8859-11', 'koi8-u', 'ptcp154', 'utf_16']
CTYPES = ['text/plain', 'text/html', 'text/xml', 'text/calendar', 'application/ics', 'application/rtf', 'text/enriched',
    'message/rfc822', 'multipart/mixed', 'multipart/alternative', 'image/png']
CTE = ['7bit', '8bit', 'quoted-printable', 'base64', 'binary', 'utf-8', 'x-uuencode', '']
WORDS = ['Kedves', 'árvíztűrő', 'tükörfúrógép', 'ŐŰőű', 'Õõ', 'Ûû', 'hello', 'world', 'ingyen', 'nyeremény', 'фото',
    '中文', 'テスト', '한국어', 'ελληνικά', 'עברית', '€', '…', ' ', '­', '​', '\U0001F600', 'a&amp;b',
    '&nbsp;', '&#337;', '&#x151;', '&ouml', '&notit;', '&#0;', '&#128;', '&#xD800;', '&#99999999999;', '&amp', '&;',
    '&#x;', '&AElig', '&lt;b&gt;', 'http://example.com/x?a=1&b=2', 'Spam detection software,']
HTML_BITS = ['<br>', '<BR/>', '<p>', '</p>', '<div>', '<DIV style="display:none">rejtett előnézet</div>',
    '<span style="font-size: 0px">x</span>', '<a href="http://a.hu/?x=1&amp;y=2">link</a>', "<a HREF='/rel'>r</a>",
    '<a data-href="no">n</a>', '<a href=noquote>q</a>', '<a href="">e</a>', '<area href=" sp ">', '<iframe src="x.html">',
    '<form action="/post">', '<style>p{color:red}</style>', '<script>if(a<b){x="</div>"}</script>', '<title>T</title>',
    '<!-- comment <b> -->', '<!-- broken', '<![CDATA[ x ]]>', '<svg><text>s</text></svg>', '< 5 >', '<3', 'a < b',
    '<td>', '<tr>', '<img src="i.png">', '<meta charset="iso-8859-2">', '<meta http-equiv="Content-Type" content="text/html; charset=windows-1250">',
    '<body>', '</body>', '<head>', '</head>', '<?xml version="1.0"?>', '<!DOCTYPE html>', '<b>', '</b>', '<x a="1>2">', "<x a='q>",
    '<div style="mso-hide:all">h</div>', '<id="publicly>', '<a x=="y>z">', '<a x=b=">">', '<a ="x>y">', '<a x=\x01"y>z">',
    '<a x=\x0c"y>z">', '<!x a="b>c">', '<?x a="b>c"?>', '</ x>', '</>', '<a/x="y>z">', '<a x="y"z="w>v">', '<a= "=">',
    '<a x = \'y>z\' >', '<br/x="a>b">', '<a\x0bx="y>z">', '<div style="opacity:0">o</div>', '<p style="display: none">pp</p>', '<signedadaptivecard style="display:none">', '\r\n', '\n', '\t']

def rword(): return rnd.choice(WORDS)
def rtext(n): return ' '.join(rword() for _ in range(n))

def enc_text(s, cs):
    try: return s.encode(cs, 'replace' if rnd.random() < 0.7 else 'ignore')
    except (LookupError, UnicodeError, TypeError): return s.encode('utf-8')

def body_html(cs):
    parts = []
    for _ in range(rnd.randint(1, 40)):
        parts.append(rnd.choice(HTML_BITS) if rnd.random() < 0.5 else rtext(rnd.randint(1, 6)))
    return enc_text(''.join(parts), cs)

def body_rtf():
    bits = ['{\\rtf1\\ansi\\ansicpg%s\\deff0' % rnd.choice(['1250', '1252', '1251', '65001', '936', '99999']),
        '{\\fonttbl{\\f0\\froman\\fcharset238 Times;}{\\f1\\fcharset0 Arial;}{\\f2\\fcharset204 X;}{\\f3\\fcharset128 J;}}',
        '{\\colortbl;\\red0;}', '\\f0 ', '\\f1 ', '\\f2 ', '\\plain ', '\\par ', '\\line', '\\tab ', "\\'f5", "\\'e1", "\\'8a", "\\'c3\\'a1", "\\'82\\'a0",
        '\\u337?', '\\u-3?', '\\uc0\\u337 ', '\\uc2\\u337xy', '\\u55357\\u56832?', '\\u55357?', '\\uc-1 ', '\\emdash ', '\\bullet ',
        '{\\*\\generator Riched20;}', '{\\*\\shpinst{\\shptxt dobozszoveg}}', '{\\*\\do{\\dptxbxtext rajz}}', '{\\header fejlec}',
        '\\bin4 {}}x', '\\\\', '\\{', '\\}', '\\~', '\\_', '\\-', '\r\n', 'szoveg ', rtext(2) + ' ', '}', '{', '\\', '\\x12345678901 ',
        '\\abcdefghijklmnopqrstuvwxyzabcdefghij ', '\\u1114112?', '\\u-70000?', "\\'zz"]
    s = bits[0] + ''.join(rnd.choice(bits[1:]) for _ in range(rnd.randint(3, 40))) + '}'
    return enc_text(s, rnd.choice(['utf-8', 'cp1250', 'latin-1']))

def body_ics():
    lines = ['BEGIN:VCALENDAR', 'BEGIN:VEVENT', 'SUMMARY:' + rtext(2)]
    if rnd.random() < 0.6: lines.append('DESCRIPTION;LANGUAGE=hu-HU:' + rtext(5).replace(',', '\\,') + '\\n\\nmasodik\;sor\\\\')
    if rnd.random() < 0.4: lines.append('X-ALT-DESC;FMTTYPE=text/html:<html><body><p>' + rtext(4) + '</p></body></html>')
    if rnd.random() < 0.2: lines.append('DESCRIPTION')
    lines += [' folytatas ' + rword(), '\tmeg ' + rword(), 'END:VEVENT', 'END:VCALENDAR']
    return enc_text('\r\n'.join(lines), 'utf-8')

def cte_encode(b, cte):
    if cte == 'base64':
        e = base64.encodebytes(b)
        r = rnd.random()
        if r < 0.1: e = e[:-rnd.randint(1, 5)]  # csonka
        elif r < 0.2: e = e.replace(b'\n', b'\n!@#\n')  # szemet
        elif r < 0.3: e = e + b'==' + base64.encodebytes(b'utana')  # padding kozepen
        return e
    if cte in ('quoted-printable', 'utf-8'):
        e = quopri.encodestring(b)
        if rnd.random() < 0.2: e = e.replace(b'=', b'==', 1) + b'=\r\nX=4' + b'=g=' + b'='
        return e
    return b

def enc_word(s):
    cs = rnd.choice(CHARSETS[:20] + ['UTF-8*hu', 'utf-8', 'gb2312'])
    b = enc_text(s, cs.split('*')[0] or 'utf-8')
    if rnd.random() < 0.5:
        p = base64.b64encode(b).decode()
        if rnd.random() < 0.15: p = p[:-1]
        if rnd.random() < 0.1: p = p[:1]
        return '=?%s?%s?%s?=' % (cs, rnd.choice('bB'), p)
    q = ''.join(c if c.isalnum() else '=%02X' % ord(c) if ord(c) < 128 else c for c in b.decode('latin-1')) if True else ''
    if rnd.random() < 0.2: q = q.replace('=', '==', 1)
    return '=?%s?%s?%s?=' % (cs, rnd.choice('qQ'), q.replace(' ', '_'))

def subject():
    r = rnd.random()
    if r < 0.4: s = ' '.join(enc_word(rtext(rnd.randint(1, 4))) for _ in range(rnd.randint(1, 3)))
    elif r < 0.6: s = rtext(3) + ' ' + enc_word(rtext(2)) + ' ' + rtext(1)
    elif r < 0.7: s = '*****SPAM{15.3}***** ' + rtext(3) + ' [SPAM] [K:Phishing]'
    else: s = rtext(rnd.randint(1, 6))
    return s.encode('utf-8') if rnd.random() < 0.8 else enc_text(s, 'latin-1')

def part(depth=0):
    ct = rnd.choice(CTYPES if depth < 3 else CTYPES[:7])
    cs = rnd.choice(CHARSETS)
    hdr = []
    if ct.startswith('multipart/'):
        bnd = rnd.choice(['b1', '----=_Part_%d' % rnd.randint(0, 999), 'x y', '"quoted;b"', ''])
        bv = bnd.strip('"')
        hdr.append(b'Content-Type: ' + ct.encode() + b'; boundary=' + bnd.encode())
        body = b''
        if rnd.random() < 0.3: body += b'This is a multi-part message in MIME format.\r\n'
        for _ in range(rnd.randint(0, 4)):
            body += b'\r\n--' + bv.encode() + rnd.choice([b'\r\n', b'\n', b' \r\n', b'_alt\r\n', b'']) + part(depth + 1)
        if rnd.random() < 0.7: body += b'\r\n--' + bv.encode() + b'--\r\n'
        return b'\r\n'.join(hdr) + b'\r\n\r\n' + body
    if ct == 'message/rfc822':
        return b'Content-Type: message/rfc822\r\n\r\n' + message(depth + 1)
    if ct == 'application/rtf': b = body_rtf()
    elif ct in ('text/calendar', 'application/ics'): b = body_ics()
    elif ct == 'image/png': b = os.urandom(rnd.randint(0, 200))
    elif rnd.random() < 0.15:  # veletlen byte-ok: a dekoderek hibaagainak terhelese
        b = bytes(rnd.choice([rnd.randrange(256), rnd.randrange(0x80, 256), rnd.randrange(0x20, 0x7f), 0x7e, 0x2b, 0x1b, 0x24, 0x28, 0x42, 0x0e, 0x0f, 0xa4, 0xd4, 0x8f, 0x30, 0x81, 0x00, 0xd8, 0xdc])
                  for _ in range(rnd.randint(0, 300)))
        if ct == 'text/html': b = b'<html><body>' + b + b'</body></html>'
    else: b = body_html(cs) if rnd.random() < 0.6 else enc_text(rtext(rnd.randint(1, 60)), cs)
    if rnd.random() < 0.1: b = rnd.choice([codecs.BOM_UTF8, codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE, codecs.BOM_UTF32_LE]) + b
    if rnd.random() < 0.1 and cs.startswith('utf-16'): b = b + b'\x00'  # paratlan hossz
    cte = rnd.choice(CTE)
    params = '; charset=%s' % (rnd.choice(['"%s"', "'%s'", '%s', ' %s ', '%s;format=flowed']) % cs) if rnd.random() < 0.85 else ''
    hdr.append(('Content-Type: %s%s' % (ct, params)).encode())
    if cte: hdr.append(b'Content-Transfer-Encoding: ' + cte.encode())
    if rnd.random() < 0.15: hdr.append(rnd.choice([b'Content-Disposition: attachment; filename="a.txt"', b'Content-Disposition: inline',
                                                    b"Content-Disposition: attachment; filename*=UTF-8''sz%C3%A1mla.txt"]))
    return b'\r\n'.join(hdr) + b'\r\n\r\n' + cte_encode(b, cte)

def message(depth=0):
    h = [b'From: x@y.hu', b'Subject: ' + subject(), b'MIME-Version: 1.0']
    if rnd.random() < 0.1: h.append(b'Subject: ' + subject())
    if rnd.random() < 0.1: h.append(b'X-Long: a\r\n\tfolded\r\n continued')
    return b'\r\n'.join(h) + b'\r\n' + part(depth)

def mutate(m):
    m = bytearray(m)
    for _ in range(rnd.randint(1, 8)):
        r = rnd.random()
        if not m: break
        i = rnd.randrange(len(m))
        if r < 0.3: m[i] = rnd.randrange(256)
        elif r < 0.5: m[i:i] = rnd.choice([b'<', b'>', b'&', b'=', b'"', b"'", b'\r\n', b'\n\n', b'\xc3', b'\xf5', b'=?', b'?=', b'--', b';', b'<br>', b'&amp;', b'=\r\n'])
        elif r < 0.65: del m[i:i + rnd.randint(1, 200)]
        elif r < 0.8:
            j = rnd.randrange(len(m)); m[i:i] = m[j:j + rnd.randint(1, 300)]
        else:  # charset / cte / ctype csere
            s = bytes(m)
            for key, pool in ((b'charset=', CHARSETS), (b'Content-Transfer-Encoding: ', CTE), (b'Content-Type: ', CTYPES)):
                p = s.find(key, i) if rnd.random() < 0.5 else s.find(key)
                if p >= 0 and rnd.random() < 0.5:
                    e = p + len(key)
                    q = e
                    while q < len(s) and s[q:q + 1] not in (b';', b'\r', b'\n'): q += 1
                    m[e:q] = rnd.choice(pool).encode(); break
    return bytes(m)

out = open(dst, 'wb')
for k in range(N):
    if rnd.random() < 0.5:
        msg = mutate(rnd.choice(real))
    else:
        msg = message()
        if rnd.random() < 0.3: msg = mutate(msg)
    if rnd.random() < 0.2: msg = msg.replace(b'\r\n', b'\n')
    msg = msg.replace(b'\nFrom ', b'\nFrom_')
    if msg.startswith(b'From '): msg = b'X' + msg
    out.write(b'From - fuzz %d\n' % k + msg + (b'' if msg.endswith(b'\n') else b'\n'))
out.close()
