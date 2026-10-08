# eml2str-rs

Az `eml2str.py` Rust portja: levélből a subject és a törzsszöveg kinyerése a DeepSpam-hez. Ugyanazt adja, mint a Python
`eml2str(msg, True)`, a hibás és szándékosan rongált leveleken is, a kivételeket is beleértve. Kivételt a CJK kódlapú
részek jelentenek, lásd az ismert eltéréseknél.

## Állapot

git hash-object eml2str.py -> 485b031f73e7d702b9070ecb205f21dd60ac1d49    (29291d4 2026-10-08 commit)

- **Junk.mbox** (2281 levél, 104,7 MB): a kimenet bájtra azonos a Pythonéval (`cmp`).
- **Valódi korpusz** (13 150 levél, 6,8 GB): bájtra azonos (önálló programként és Python-modulként is).
- **Differenciális fuzz** (`gen_fuzz.py`, 59 000 levél): valódi levelek mutációi, plusz szintetikus levelek RTF, ICS,
  UTF-16/32, CJK, iso-2022, utf-7, hibás base64/QP, encoded-word fejlécek, HTML-entitások és egymásba ágyazott
  multipart részekkel. A levelek kb. 1,5%-a tér el. Ezek mind CJK kódlapú részt tartalmaznak; egyetlen kivétel az
  ismert utf-7 surrogate-eset.
- **Sebesség** ezen a gépen (egy szálon): Python 3.9 **2,6 s**, Rust **0,16 s** a Junk.mbox-on, kb. **16×**.

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
./target/release/eml2str-bench nagy.mbox rs.out            # --repeat N: N-szer futtatja, átlagidő
python3 ../compare_out.py py.out rs.out -v 5               # eltérések száma, az első 5 részletesen
```

Megjegyzések:

- A Python driver az `eml2str` debug print-jeit (`BoundaryNotFound` stb.) `/dev/null`-ba irányítja, hogy ne mérjenek bele.
- A Rust idejében benne van a táblák egyszeri inicializálása (kb. 1-2 ms). Rövid mappánál ez is számít, ilyenkor
  érdemes `--repeat`-tel mérni.
- Mindhárom egy szálon fut. A Rust verzió szálbiztos, több szálon gyakorlatilag lineárisan skálázna, de az
  összehasonlításhoz az egy magra jutó áteresztés a releváns.

## Ismert eltérések a Pythontól

| Eset | Python | Rust |
|---|---|---|
| utf-7 szöveg, benne magában álló surrogate (`+2D3-`) | a str-ben marad a lone surrogate | U+FFFD (a Rust `String` nem tud surrogate-ot tárolni) |
| nagyon mélyen (kb. 1000 szint) egymásba ágyazott MIME | `RecursionError` a hívási mélységtől függő ponton | `RecursionError` fix 990 szintnél |
| CJK kódlap (gbk, gb18030, big5, shift_jis, euc-jp, euc-kr, iso-2022-jp...), érvényes bájtsorozat | dekódolja | ugyanaz (encoding_rs) |
| CJK kódlap, hibás bájtsorozat | a CPython CJK-dekóderének hibahatárai | az encoding_rs (WHATWG) hibahatárai, így más bájtokra jut a `mixed` csere |
| ritka CJK változatok (shift_jis_2004, euc-jisx0213, iso-2022-jp-2/2004/3, big5hkscs) | a saját kiterjesztéseikkel | az alap kódlapként (shift_jis, euc-jp, iso-2022-jp, big5) |
| `hz`, `johab`, `iso-2022-kr`, `raw-unicode-escape`, `unicode-escape`, `punycode` mint charset | dekódolja | utf-8 + mixed visszaesés |

A CJK-eltérések szándékosak: a deepspam2 tokenizere a nem latin karaktereket úgyis eldobja, a valódi korpuszban
pedig nem fordult elő CJK charset. Pontos CJK-táblák helyett ezért az encoding_rs crate dekódol (a Firefox
kódlap-könyvtára, a táblái a binárisba fordulnak).

**Fontos:** a port a *mostani* telepítést követi, amelyben nincs `striprtf` és nincs `tnef_mini`:

- RTF-nél a beépített tartalék kinyerő fut (`rtf_fallback_text`), ezt portoltam.
- A TNEF (`winmail.dat`) részeket az `eml2str` kihagyja.

Ha élesben bármelyik csomag telepítve van, az RTF- vs. TNEF-tartalmú levelekre a Python kimenete el fog térni ettől.

Nem portolt, mert az `eml2str()` nem használja: `get_mimedata`, `readfolder`, `decode_from`, `parse_docx`,
`vocab_split`, `remove_url`.

## Táblák (Python-verziófüggő!)

A charset-kezelés a Python `codecs` viselkedését követi. Ezt a fordításkor generált `tables.rs` biztosítja:
codec-névfeloldás (`codecs.lookup` + az `eml2str` saját aliasai és felülírásai), a Python egybájtos kódtáblái,
HTML5-entitások, `invalid_charrefs`. A utf-7 dekóder a CPython C-kódját követi, a CJK kódlapokat az encoding_rs
dekódolja.

## Fájlok

| Fájl | Tartalom |
|---|---|
| `src/lib.rs` | `eml2str()`, `decode_payload()`, `hdrdecode4()`, `parse_ics()`, `remove_spamtag()` |
| `src/mime.rs` | `parse_eml()`, `parse_ctyp()`, `decode_body()`, a `binascii` `a2b_base64` / `a2b_qp` pontos megfelelője |
| `src/html.rs` | `html2text()`, `html.unescape()` (Python stdlib), `parse_htmlhead()`, `html_extract_attr()` |
| `src/rtf.rs` | `parse_rtfhead()`, a tartalék RTF-kinyerő, `fix_surrogates()` |
| `src/codec.rs` | `codecs.lookup`, `safe_decode()`, `ascii_compatible()`, a `mixed` hibakezelők, UTF-8/16/32, egybájtos kódlapok |
| `src/utf7.rs` | utf-7 dekóder |
| `src/python.rs` | a Python-modul (`eml2str_rs`, a `python` feature-rel) |
| `build.rs`, `gen_tables.py` | a codec-táblák generálása fordításkor |
| `build_python.sh` | a Python-modul fordítása és bemásolása |
| `src/main.rs` | `eml2str-bench` CLI |
| `examples/prof.rs` | fázisonkénti időmérés (`cargo run --release --example prof -- ../Junk.mbox`) |
| `gen_fuzz.py` | fuzz-mbox generátor (`python3 gen_fuzz.py ../Junk.mbox fuzz.mbox 10000 <seed>`) |
| `diag.py` | az eltérő levelek részeinek (ctyp / charset / cte) listázása |

