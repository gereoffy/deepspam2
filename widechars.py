#! /usr/bin/python3

# based on https://github.com/jquast/wcwidth   (Python library that measures the width of unicode strings rendered to a terminal)

WIDE_EASTASIAN = (
        # Source: EastAsianWidth-15.0.0.txt
        # Date: 2022-05-24, 17:40:20 GMT [KW, LI]
        #
        (0x01100, 0x0115f,),  # Hangul Choseong Kiyeok  ..Hangul Choseong Filler
        (0x0231a, 0x0231b,),  # Watch                   ..Hourglass
        (0x02329, 0x0232a,),  # Left-pointing Angle Brac..Right-pointing Angle Bra
        (0x023e9, 0x023ec,),  # Black Right-pointing Dou..Black Down-pointing Doub
        (0x023f0, 0x023f0,),  # Alarm Clock
        (0x023f3, 0x023f3,),  # Hourglass With Flowing Sand
        (0x025fd, 0x025fe,),  # White Medium Small Squar..Black Medium Small Squar
        (0x02614, 0x02615,),  # Umbrella With Rain Drops..Hot Beverage
        (0x02648, 0x02653,),  # Aries                   ..Pisces
        (0x0267f, 0x0267f,),  # Wheelchair Symbol
        (0x02693, 0x02693,),  # Anchor
        (0x026a1, 0x026a1,),  # High Voltage Sign
        (0x026aa, 0x026ab,),  # Medium White Circle     ..Medium Black Circle
        (0x026bd, 0x026be,),  # Soccer Ball             ..Baseball
        (0x026c4, 0x026c5,),  # Snowman Without Snow    ..Sun Behind Cloud
        (0x026ce, 0x026ce,),  # Ophiuchus
        (0x026d4, 0x026d4,),  # No Entry
        (0x026ea, 0x026ea,),  # Church
        (0x026f2, 0x026f3,),  # Fountain                ..Flag In Hole
        (0x026f5, 0x026f5,),  # Sailboat
        (0x026fa, 0x026fa,),  # Tent
        (0x026fd, 0x026fd,),  # Fuel Pump
        (0x02705, 0x02705,),  # White Heavy Check Mark
        (0x0270a, 0x0270b,),  # Raised Fist             ..Raised Hand
        (0x02728, 0x02728,),  # Sparkles
        (0x0274c, 0x0274c,),  # Cross Mark
        (0x0274e, 0x0274e,),  # Negative Squared Cross Mark
        (0x02753, 0x02755,),  # Black Question Mark Orna..White Exclamation Mark O
        (0x02757, 0x02757,),  # Heavy Exclamation Mark Symbol
#        (0x2764, 0x2764,),    # Heavy black heart   --Arpi
        (0x02795, 0x02797,),  # Heavy Plus Sign         ..Heavy Division Sign
        (0x027b0, 0x027b0,),  # Curly Loop
        (0x027bf, 0x027bf,),  # Double Curly Loop
        (0x02b1b, 0x02b1c,),  # Black Large Square      ..White Large Square
        (0x02b50, 0x02b50,),  # White Medium Star
        (0x02b55, 0x02b55,),  # Heavy Large Circle
        (0x02e80, 0x02e99,),  # Cjk Radical Repeat      ..Cjk Radical Rap
        (0x02e9b, 0x02ef3,),  # Cjk Radical Choke       ..Cjk Radical C-simplified
        (0x02f00, 0x02fd5,),  # Kangxi Radical One      ..Kangxi Radical Flute
        (0x02ff0, 0x02ffb,),  # Ideographic Description ..Ideographic Description
        (0x03000, 0x0303e,),  # Ideographic Space       ..Ideographic Variation In
        (0x03041, 0x03096,),  # Hiragana Letter Small A ..Hiragana Letter Small Ke
        (0x03099, 0x030ff,),  # Combining Katakana-hirag..Katakana Digraph Koto
        (0x03105, 0x0312f,),  # Bopomofo Letter B       ..Bopomofo Letter Nn
        (0x03131, 0x0318e,),  # Hangul Letter Kiyeok    ..Hangul Letter Araeae
        (0x03190, 0x031e3,),  # Ideographic Annotation L..Cjk Stroke Q
        (0x031f0, 0x0321e,),  # Katakana Letter Small Ku..Parenthesized Korean Cha
        (0x03220, 0x03247,),  # Parenthesized Ideograph ..Circled Ideograph Koto
        (0x03250, 0x04dbf,),  # Partnership Sign        ..Cjk Unified Ideograph-4d
        (0x04e00, 0x0a48c,),  # Cjk Unified Ideograph-4e..Yi Syllable Yyr
        (0x0a490, 0x0a4c6,),  # Yi Radical Qot          ..Yi Radical Ke
        (0x0a960, 0x0a97c,),  # Hangul Choseong Tikeut-m..Hangul Choseong Ssangyeo
        (0x0ac00, 0x0d7a3,),  # Hangul Syllable Ga      ..Hangul Syllable Hih
        (0x0f900, 0x0faff,),  # Cjk Compatibility Ideogr..(nil)
        (0x0fe10, 0x0fe19,),  # Presentation Form For Ve..Presentation Form For Ve
        (0x0fe30, 0x0fe52,),  # Presentation Form For Ve..Small Full Stop
        (0x0fe54, 0x0fe66,),  # Small Semicolon         ..Small Equals Sign
        (0x0fe68, 0x0fe6b,),  # Small Reverse Solidus   ..Small Commercial At
        (0x0ff01, 0x0ff60,),  # Fullwidth Exclamation Ma..Fullwidth Right White Pa
        (0x0ffe0, 0x0ffe6,),  # Fullwidth Cent Sign     ..Fullwidth Won Sign
        (0x16fe0, 0x16fe4,),  # Tangut Iteration Mark   ..Khitan Small Script Fill
        (0x16ff0, 0x16ff1,),  # Vietnamese Alternate Rea..Vietnamese Alternate Rea
        (0x17000, 0x187f7,),  # (nil)
        (0x18800, 0x18cd5,),  # Tangut Component-001    ..Khitan Small Script Char
        (0x18d00, 0x18d08,),  # (nil)
        (0x1aff0, 0x1aff3,),  # Katakana Letter Minnan T..Katakana Letter Minnan T
        (0x1aff5, 0x1affb,),  # Katakana Letter Minnan T..Katakana Letter Minnan N
        (0x1affd, 0x1affe,),  # Katakana Letter Minnan N..Katakana Letter Minnan N
        (0x1b000, 0x1b122,),  # Katakana Letter Archaic ..Katakana Letter Archaic
        (0x1b132, 0x1b132,),  # (nil)
        (0x1b150, 0x1b152,),  # Hiragana Letter Small Wi..Hiragana Letter Small Wo
        (0x1b155, 0x1b155,),  # (nil)
        (0x1b164, 0x1b167,),  # Katakana Letter Small Wi..Katakana Letter Small N
        (0x1b170, 0x1b2fb,),  # Nushu Character-1b170   ..Nushu Character-1b2fb
        (0x1f004, 0x1f004,),  # Mahjong Tile Red Dragon
        (0x1f0cf, 0x1f0cf,),  # Playing Card Black Joker
        (0x1f18e, 0x1f18e,),  # Negative Squared Ab
        (0x1f191, 0x1f19a,),  # Squared Cl              ..Squared Vs
        (0x1f200, 0x1f202,),  # Square Hiragana Hoka    ..Squared Katakana Sa
        (0x1f210, 0x1f23b,),  # Squared Cjk Unified Ideo..Squared Cjk Unified Ideo
        (0x1f240, 0x1f248,),  # Tortoise Shell Bracketed..Tortoise Shell Bracketed
        (0x1f250, 0x1f251,),  # Circled Ideograph Advant..Circled Ideograph Accept
        (0x1f260, 0x1f265,),  # Rounded Symbol For Fu   ..Rounded Symbol For Cai
        (0x1f300, 0x1f320,),  # Cyclone                 ..Shooting Star
        (0x1f32d, 0x1f335,),  # Hot Dog                 ..Cactus
        (0x1f337, 0x1f37c,),  # Tulip                   ..Baby Bottle
        (0x1f37e, 0x1f393,),  # Bottle With Popping Cork..Graduation Cap
        (0x1f3a0, 0x1f3ca,),  # Carousel Horse          ..Swimmer
        (0x1f3cf, 0x1f3d3,),  # Cricket Bat And Ball    ..Table Tennis Paddle And
        (0x1f3e0, 0x1f3f0,),  # House Building          ..European Castle
        (0x1f3f4, 0x1f3f4,),  # Waving Black Flag
        (0x1f3f8, 0x1f43e,),  # Badminton Racquet And Sh..Paw Prints
        (0x1f440, 0x1f440,),  # Eyes
        (0x1f442, 0x1f4fc,),  # Ear                     ..Videocassette
        (0x1f4ff, 0x1f53d,),  # Prayer Beads            ..Down-pointing Small Red
        (0x1f54b, 0x1f54e,),  # Kaaba                   ..Menorah With Nine Branch
        (0x1f550, 0x1f567,),  # Clock Face One Oclock   ..Clock Face Twelve-thirty
        (0x1f57a, 0x1f57a,),  # Man Dancing
        (0x1f595, 0x1f596,),  # Reversed Hand With Middl..Raised Hand With Part Be
        (0x1f5a4, 0x1f5a4,),  # Black Heart
        (0x1f5fb, 0x1f64f,),  # Mount Fuji              ..Person With Folded Hands
        (0x1f680, 0x1f6c5,),  # Rocket                  ..Left Luggage
        (0x1f6cc, 0x1f6cc,),  # Sleeping Accommodation
        (0x1f6d0, 0x1f6d2,),  # Place Of Worship        ..Shopping Trolley
        (0x1f6d5, 0x1f6d7,),  # Hindu Temple            ..Elevator
        (0x1f6dc, 0x1f6df,),  # (nil)                   ..Ring Buoy
        (0x1f6eb, 0x1f6ec,),  # Airplane Departure      ..Airplane Arriving
        (0x1f6f4, 0x1f6fc,),  # Scooter                 ..Roller Skate
        (0x1f7e0, 0x1f7eb,),  # Large Orange Circle     ..Large Brown Square
        (0x1f7f0, 0x1f7f0,),  # Heavy Equals Sign
        (0x1f90c, 0x1f93a,),  # Pinched Fingers         ..Fencer
        (0x1f93c, 0x1f945,),  # Wrestlers               ..Goal Net
        (0x1f947, 0x1f9ff,),  # First Place Medal       ..Nazar Amulet
        (0x1fa70, 0x1fa7c,),  # Ballet Shoes            ..Crutch
        (0x1fa80, 0x1fa88,),  # Yo-yo                   ..(nil)
        (0x1fa90, 0x1fabd,),  # Ringed Planet           ..(nil)
        (0x1fabf, 0x1fac5,),  # (nil)                   ..Person With Crown
        (0x1face, 0x1fadb,),  # (nil)
        (0x1fae0, 0x1fae8,),  # Melting Face            ..(nil)
        (0x1faf0, 0x1faf8,),  # Hand With Index Finger A..(nil)
        (0x20000, 0x2fffd,),  # Cjk Unified Ideograph-20..(nil)
        (0x30000, 0x3fffd,),  # Cjk Unified Ideograph-30..(nil)
    )


def _bisearch(ucs, table):
    """
    Auxiliary function for binary search in interval table.

    :arg int ucs: Ordinal value of unicode character.
    :arg list table: List of starting and ending ranges of ordinal values,
        in form of ``[(start, end), ...]``.
    :rtype: int
    :returns: 1 if ordinal value ucs is found within lookup table, else 0.
    """
    lbound = 0
    ubound = len(table) - 1

    if ucs < table[0][0] or ucs > table[ubound][1]:
        return 0
    while ubound >= lbound:
        mid = (lbound + ubound) // 2
        if ucs > table[mid][1]:
            lbound = mid + 1
        elif ucs < table[mid][0]:
            ubound = mid - 1
        else:
            return 1

    return 0


# NOTE: created by hand, there isn't anything identifiable other than
# general Cf category code to identify these, and some characters in Cf
# category code are of non-zero width.
# Also includes some Cc, Mn, Zl, and Zp characters
ZERO_WIDTH_CF = set([
    0,       # Null (Cc)
    0xAD,    # Soft hyphen
    0x034F,  # Combining grapheme joiner (Mn)  # https://www.compart.com/en/unicode/U+034F
    0x200B,  # Zero width space
    0x200C,  # Zero width non-joiner
    0x200D,  # Zero width joiner
    0x200E,  # Left-to-right mark
    0x200F,  # Right-to-left mark
    0x2028,  # Line separator (Zl)
    0x2029,  # Paragraph separator (Zp)
    0x202A,  # Left-to-right embedding
    0x202B,  # Right-to-left embedding
    0x202C,  # Pop directional formatting
    0x202D,  # Left-to-right override
    0x202E,  # Right-to-left override
    0x2060,  # Word joiner
    0x2061,  # Function application
    0x2062,  # Invisible times
    0x2063,  # Invisible separator
             # https://unicode.org/emoji/charts/emoji-variants.html
    0xFE0E,  # Variation selector:  The character U+FE0E VARIATION SELECTOR-15 (VS15), used to request a text presentation for an emoji character.
    0xFE0F,  # Variation selector:  The character U+FE0F VARIATION SELECTOR-16 (VS16), used to request an emoji presentation for an emoji character.
    0xFEFF   # BOM, ZWNBSP, ZERO WIDTH NO-BREAK SPACE. Unicode Hexadecimal: 0xFEFF. Unicode Decimal: 65279
])


def wcwidth(wc):
    ucs = ord(wc)
    if ucs in ZERO_WIDTH_CF: return 0

    # C0/C1 control characters
    if ucs < 32 or 0x07F <= ucs < 0x0A0: return -1

    # "Wide AastAsian" (and emojis)
    return 1 + _bisearch(ucs, WIDE_EASTASIAN)

def ucsremove(s): # unicode shit remover
    return "".join(["" if ord(c) in ZERO_WIDTH_CF else c for c in s])

# a dupla szeles karakterek (kinai/japan irasjelek, emojik) beszurunk egy zero-width space-t, igy karakter darabszamra is 2 lesz, de megjelenitve meg nem csuszik el
def wcfixchar(wc):
    ucs = ord(wc)
    if ucs in ZERO_WIDTH_CF or ucs>=0xE0000: return "" # drop zero-width (invisible) chars
    if ucs>=0x1100 and _bisearch(ucs, WIDE_EASTASIAN): return wc+chr(0x200B) # add padding for known wide chars
    if 0x1F000 <= ucs < 0x20000:
        if 0x1F110 <= ucs < 0x1F190:
            ucs=(ucs-0x1F110)&31
            if ucs<26: return chr(65+ucs) # bekarikazott/keretezett ABC...Z betuk
        return "" # drop color shit...  https://en.wikibooks.org/wiki/Unicode/Character_reference/1F000-1FFFF
    return wc

def wcfixstr(s):
    if not s: return s # no string, no fun...
#    if not s or max(s)<chr(0x1100): return s # quickpath
    if max(s)<chr(0x024F) and not chr(0) in s and not chr(0xAD) in s: return s # quickpath
    return "".join([wcfixchar(c) for c in s])
#    return "".join([wcfixchar(c) if ord(c)>=0x1100 else c for c in s])
#    return "".join([chr(0x200B)*_bisearch(ord(c),WIDE_EASTASIAN)+c if ord(c)>=0x1100 else c for c in s])


if __name__ == "__main__":

#    t=" \t \n NPO法人グッドシニアライフ  <waigh55@vega.ocn.ne.jp>                      945  *****SPAM(26.9)***** [E:spam]  [K:Spam] 【NPO法人グッドシニアライフ 送信確認】 採用情報"
#    t="❤️ Alice sent you a HOT video! Click Here: http://bit.do/fSv7s?ckuc ❤️      1092  *****SPAM(30.7)***** [E:spam]  [K:Spam]Invitation to Email a Colleague"
    t="この度は、「三菱ＨＣキャピタル」をご利用いただきありがとうございます。 ご利用環境の確認のため、24時間のみ有効URLをお送りいたします。 次のURLをクリックいただくことでお客さまのご利用環境を確認いたします。 https://mitsubishi-hc-capital-card.afcfjs.com/ なお、このURLの有効期限は2022年01月09日 23時までとなっています。 有効期限を過ぎた場合は、もう一度ログインしていただきますと、再度24時間のみ有効なURLをお送りいたします。 なお、お客さまへ最後に通知されたもののみ有効です。 また、三菱ＨＣキャピタルのご利用には、ご利用端末変更の際、もしくは最終ログインから一定期間経過すると、ご利用環境の再確認が必要となります。 お客さまのご利用環境の確認は、不正アクセス対策の一環として行っております。 不正アクセス対策について、くわしくはこちらをご覧ください。 https://mitsubishi-hc-capital-card.jp.mxkyy.com/ このメールは送信専用メールアドレスから配信されております。 このままご返信いただいてもお答えできませんので、「アットユーネット」からのお問い合わせは、以下の「お問い合わせフォーム」よりお願いいたします。 https://mitsubishi-hc-capital-card.jp"
    print(t)
    print(",".join([ str(wcwidth(c)) for c in t]))
    print(",".join([ str(ord(c)) for c in t]))

    print(len(t))
    tt=wcfixstr(t)
    print(tt)
    print(len(tt))

    print(t[:10])
    print(tt[:10])

    tt=""
    for c in t:
        if wcwidth(c)!=2:
            print(wcwidth(c),ord(c),c)
            tt+=c
    print(tt)
    print(len(tt))

#    jo="Meghalt az Életrevalók című filmet ihlető francia üzletember. Philippe Pozzo di Borgo 72 éves volt. \n"
#    print(max(jo)<chr(0x1100))
#    print(max(t)<chr(0x1100))
#    print(max(tt)<chr(0x1100))


