# eml2str-rs

Az `eml2str.py` Rust portja: levélből a subject és a törzsszöveg kinyerése a DeepSpam-hez. Ugyanazt adja, mint a Python
`eml2str(msg, True)`, a hibás és szándékosan rongált leveleken is, a kivételeket is beleértve. Kivételt a CJK kódlapú
részek jelentenek, lásd az ismert eltéréseknél.

## Állapot

- **Valódi levelek** (13 150 levél, 6,8 GB) és **Junk.mbox** (2281 levél): a kimenet bájtra azonos a Pythonéval
  (önálló programként és Python-modulként is).
- **Junk-all.mbox** (30 270 spam, 1 GB): bájtra azonos, kivéve 23 CJK kódlapú levelet (lásd az ismert eltéréseket).
- **Differenciális fuzz** (`gen_fuzz.py`, összesen kb. 90 000 levél): valódi levelek mutációi, plusz szintetikus levelek
  RTF, ICS, UTF-16/32, CJK, iso-2022, utf-7, hibás base64/QP, encoded-word fejlécek, HTML-entitások, trükkös tagok
  (`<id="x>`, `a=b=">"`, `<!x a="b>c">`…) és egymásba ágyazott multipart részekkel. A levelek kb. 1,5%-a tér el:
  ezek mind CJK kódlapú részt tartalmaznak, egyetlen kivétel az ismert utf-7 surrogate-eset.
- **Kimerítő tesztek** a `html2text` trükkös részeire (tagvég, comment, `style`, `opacity`): több százezer generált
  HTML-darabon azonos.
- **Átnézés 2026-10-13/14** (kódolvasás + újabb differenciális tesztek): 1456 kézzel írt éleset (base64/QP padding,
  `opacity`, meta charset, NUL a charset-névben, BOM-ok, 27 charset × 14 bájtsor, ICS, multipart-trükkök, hibás
  fejlécek, véletlen szemét), 80 000 fuzz-levél két új seeddel és 30 000 tisztán véletlen "levél": a Rust nem
  panic-el, a Python-modul 8 szálon is az egyszálúval azonos kimenetet ad, az eltérések mind a CJK-kategóriába esnek
  (beleértve az RTF `\ansicpg936` és a Subject gb2312/gbk encoded-word eseteit). Ekkor került be a 10 szintes
  MIME-mélységlimit, a johab fallback (`flush_hex`) és a Pythonból generált Unicode-számjegy tábla (lásd lent).
- **Sebesség** ezen a gépen (egy szálon, a Python oldalon is a mostani, optimalizált `eml2str.py`-vel):

  | | valódi levelek (6,8 GB) | Junk-all (1 GB) |
  |---|---|---|
  | CPython 3.9 | 26,1 s | 19,0 s |
  | CPython 3.14 | 21,2 s | 15,0 s |
  | PyPy 3.12 | 14,8 s | 16,4 s |
  | Rust | **3,4 s** | **2,5 s** |

  A Rust a CPythonnál kb. 6–8×, a PyPy-nál kb. 4–7× gyorsabb. Több szálon (a modul elengedi a GIL-t) tovább skálázódik.

## Fordítás

```bash
cargo build --release
```

A fordításhoz Python kell: a `build.rs` a `gen_tables.py`-val generálja a codec-táblákat (`OUT_DIR/tables.rs`),
abból a Pythonból, amelyiket a `PYO3_PYTHON` (vagy `PYTHON`) változó megad, ennek hiányában a `python3`-ból. A
generátor a szülőkönyvtárban lévő `eml2str.py`-t is beolvassa (az ottani aliasok és felülírások miatt), ezért az
`eml2str-rs/` könyvtár az `eml2str.py` mellett legyen.

A `make distclean` megfelelője a `cargo clean`: törli a `target/` könyvtárat, a forrásfába a fordítás semmit nem ír.

## Python-modul (eml2str_rs)

A Rust változat Pythonból is hívható, a tiszta Python `eml2str` helyett. Ugyanaz a függvény, ugyanaz a visszatérési
érték, ugyanazok a kivételtípusok:

```python
from eml2str_rs import eml2str
subject, text = eml2str(msg_bytes, True)   # ds2=False (alapértelmezés): csak a text
```

Fordítás és bemásolás a `ds2-lite` könyvtárba (`eml2str_rs.abi3.so`, egyetlen fájl minden CPython >= 3.9-hez):

```bash
./build_python.sh            # vagy: ./build_python.sh /cel/konyvtar
```

Ha több Python is van a gépen, a `PYO3_PYTHON=python3.x` változóval választható, melyikkel forduljon. Az abi3 miatt
a modul minden verzióval betöltődik, de a codec-táblák a fordító Python viselkedését követik (a 3.9 és a 3.14 között
is van különbség), ezért azzal a Pythonnal fordítsd, amelyik futtatni fogja. Linuxon ugyanez a szkript
`libeml2str.so`-ból készíti a modult.

- A `deepspam4.py` magától a Rust modult használja, ha megtalálja, különben a tiszta Pythont. Induláskor kiírja,
  melyiket. Kényszeríteni a `DEEPSPAM_EML2STR=python` vagy `=rust` változóval lehet.
- A feldolgozás alatt a modul elengedi a GIL-t, így több szálon (pl. `ThreadPoolExecutor`, asyncio
  `run_in_executor`) párhuzamosan is futhat.
- PyPy-hoz nem kell, és nem is működik vele (az abi3 modul CPython-specifikus).

## Benchmark (python3 / pypy3 / rust)

Mindhárom ugyanúgy vágja szét az mboxot (a `From ` soroknál), és ugyanabban a formátumban írja ki az eredményt.
A mért idő csak az `eml2str()` hívásoké, az mbox beolvasása nincs benne.

```bash
python3 ../bench_py.py nagy.mbox py.out
pypy3   ../bench_py.py nagy.mbox pypy.out
EML2STR=eml2str_rs python3 ../bench_py.py nagy.mbox mod.out   # a Rust Python-modulon keresztül
./target/release/eml2str-bench nagy.mbox rs.out            # --repeat N: N-szer futtatja, átlagidő
python3 ../compare_out.py py.out rs.out -v 5               # eltérések száma, az első 5 részletesen
```

Az `EML2STR` változóval a `bench_py.py` tetszőleges, `eml2str()` függvényt adó modult mér (alapértelmezés: `eml2str`).

Megjegyzések:

- A Python driver az `eml2str` debug print-jeit (`BoundaryNotFound` stb.) `/dev/null`-ba irányítja, hogy ne mérjenek bele.
- A Rust idejében benne van a táblák egyszeri inicializálása (kb. 1-2 ms). Rövid mappánál ez is számít, ilyenkor
  érdemes `--repeat`-tel mérni.
- Mindhárom egy szálon fut. A Rust verzió szálbiztos, több szálon gyakorlatilag lineárisan skálázna, de az
  összehasonlításhoz az egy magra jutó áteresztés a releváns.

## Ismert eltérések a Pythontól

A MIME-fa mélysége mindkét változatban 10 szintre van korlátozva (`MAX_MIME_DEPTH` / `MAX_DEPTH`): az ennél mélyebb
multipart / message részek nem bomlanak tovább, a tartalmuk kimarad. (Korlát nélkül a Python egy ~1000 szint mélyen
egymásba ágyazott levélen `RecursionError`-t, sőt fatális `Cannot recover from stack overflow` hibát adott.)

| Eset | Python | Rust |
|---|---|---|
| utf-7 szöveg, benne magában álló surrogate (`+2D3-`) | a str-ben marad a lone surrogate | U+FFFD (a Rust `String` nem tud surrogate-ot tárolni) |
| CJK kódlap (gbk, gb18030, big5, shift_jis, euc-jp, euc-kr, iso-2022-jp...), érvényes bájtsorozat | dekódolja | ugyanaz (encoding_rs) |
| CJK kódlap, hibás bájtsorozat | a CPython CJK-dekóderének hibahatárai | az encoding_rs (WHATWG) hibahatárai, így más bájtokra jut a `mixed` csere |
| ritka CJK változatok (shift_jis_2004, euc-jisx0213, iso-2022-jp-2/2004/3, big5hkscs) | a saját kiterjesztéseikkel | az alap kódlapként (shift_jis, euc-jp, iso-2022-jp, big5) |
| `hz`, `johab`, `iso-2022-kr`, `raw-unicode-escape`, `unicode-escape`, `punycode` mint charset | dekódolja | utf-8 + mixed visszaesés |
| RTF `\fcharsetN` → `johab` (130) a `\'xx` escape-ekhez | johab szerint dekódolja | a dokumentum kódlapja (`\ansicpg` / charset / cp1252) szerint |

A CJK-eltérések szándékosak: a deepspam2 tokenizere a nem latin karaktereket úgyis eldobja, a valódi korpuszban
pedig nem fordult elő CJK charset. Pontos CJK-táblák helyett ezért az encoding_rs crate dekódol (a Firefox
kódlap-könyvtára, a táblái a binárisba fordulnak).

**Fontos:** a port a *mostani* telepítést követi, amelyben nincs `striprtf` és nincs `tnef_mini`:

- RTF-nél a beépített tartalék kinyerő fut (`rtf_fallback_text`), ezt portoltam.
- A TNEF (`winmail.dat`) részeket az `eml2str` kihagyja.

Ha élesben bármelyik csomag telepítve van, az RTF- vs. TNEF-tartalmú levelekre a Python kimenete el fog térni ettől.

Nem portolt, mert az `eml2str()` nem használja: `get_mimedata`, `readfolder`, `decode_from`, `parse_docx`,
`vocab_split`, `remove_url`, `html_extract_attr` / `LINK_ATTRS` (az `URL:` sorok csak a `html2text(debug=True)` kimenetében vannak).

## Táblák (Python-verziófüggő!)

A charset-kezelés a Python `codecs` viselkedését követi. Ezt a fordításkor generált `tables.rs` biztosítja:
codec-névfeloldás (`codecs.lookup` + az `eml2str` saját aliasai és felülírásai), a Python egybájtos kódtáblái,
HTML5-entitások, `invalid_charrefs`, a mojibake-alakok (`MOJI`, a `fix_chars` előtti `fix_mojibake`-hez), és a Unicode decimális számjegy-blokkok (`ND_ZEROS`, a `unicodedata`-ból): az RTF
`\uN`, `\ucN`, `\binN`, `\fN`, `\fcharsetN` argumentumában a Python `re` `\d`-je és az `int()` minden Nd számjegyet
elfogad, a Rust ugyanezt a táblát használja. A utf-7 dekóder a CPython C-kódját követi, a CJK kódlapokat az
encoding_rs dekódolja.

## Fájlok

| Fájl | Tartalom |
|---|---|
| `src/lib.rs` | `eml2str()`, `decode_payload()`, `hdrdecode4()`, `parse_ics()`, `remove_spamtag()` |
| `src/mime.rs` | `parse_eml()`, `parse_ctyp()`, `decode_body()`, a `binascii` `a2b_base64` / `a2b_qp` pontos megfelelője |
| `src/html.rs` | `html2text()`, `html.unescape()` (Python stdlib), `parse_htmlhead()` (az URL-kinyerés nincs portolva: a Python csak a debug kimenetbe teszi) |
| `src/rtf.rs` | `parse_rtfhead()`, a tartalék RTF-kinyerő (a legkülső `}` után vége, tartományon kívüli `\uN` → U+FFFD, johab fallback), `fix_surrogates()` |
| `src/codec.rs` | `codecs.lookup`, `safe_decode()`, `ascii_compatible()`, a `mixed` hibakezelők (CESU-8 párokkal, `handler_at`), `decode_utf8_cesu()`, UTF-8/16/32, egybájtos kódlapok |
| `src/utf7.rs` | utf-7 dekóder |
| `src/python.rs` | a Python-modul (`eml2str_rs`, a `python` feature-rel) |
| `build.rs`, `gen_tables.py` | a codec-, entitás- és Unicode-számjegy táblák generálása fordításkor |
| `build_python.sh` | a Python-modul fordítása és bemásolása |
| `src/main.rs` | `eml2str-bench` CLI |
| `examples/prof.rs` | fázisonkénti időmérés (`cargo run --release --example prof -- ../Junk.mbox`) |
| `gen_fuzz.py` | fuzz-mbox generátor (`python3 gen_fuzz.py ../Junk.mbox fuzz.mbox 10000 <seed>`) |
| `diag.py` | az eltérő levelek részeinek (ctyp / charset / cte) listázása |

A Rust a Python logikáját követi, a Pythonban is meglévő optimalizálásokkal együtt: a `Content-Transfer-Encoding`
dekódolás csak a ténylegesen felhasznált részekre fut le (`parse_eml(decode='lazy')`), a fejlécvég keresése egy menetben
megy (`header_end()`), a `html2text` tagvég-keresése a HTML5 tokenizer szerinti állapotgép (a Python `TAG_END_RE`
megfelelője, `src/html.rs: tag_end()`).

## Karbantartás

Ha az `eml2str.py`-ben az `eml2str()`-t érintő rész változik (`parse_eml`, `decode_payload`, `html2text`, `hdrdecode4`,
a charset-kezelés…), a Rust oldalt is ugyanígy kell módosítani, utána ellenőrizni:

```bash
./build_python.sh                                     # vagy cargo build --release
python3 ../bench_py.py teszt.mbox py.out
./target/release/eml2str-bench teszt.mbox rs.out
python3 ../compare_out.py py.out rs.out -v 5          # csak a CJK-eltérések maradhatnak
python3 diag.py teszt.mbox py.out rs.out              # az eltérő levelek charsetjei
```

Érdemes egy friss fuzz-korpuszon is lefuttatni (`gen_fuzz.py`), új trükkök esetén a `HTML_BITS` listát bővítve.
A codec-táblák a fordításkor automatikusan frissülnek (az `eml2str.py` aliasai és felülírásai is).
