# eml2str.py – modul leírás

Önálló (csak standard libet használó) e-mail / MIME feldolgozó modul. Fő célja, hogy egy nyers
`.eml` üzenetből (bytes) **olvasható, tiszta szöveget** állítson elő (pl. spamszűrő / ML
osztályozó bemenetének), de tartalmaz MIME-fa elemzőt, HTML→szöveg konvertert, fejléc-dekódolót,
mbox-olvasót és tokenizálót is.

Az `email` standard csomagot szándékosan **nem** használja: saját, toleráns parser van benne,
ami a hibás/"törött" leveleket is feldolgozza.

## Opcionális függőségek

| Modul | Flag | Mire kell |
|---|---|---|
| `striprtf.rtf_to_text` | `rtf_support` | `application/rtf` részek és TNEF-ben lévő RTF body szöveggé alakítása |
| `tnef_mini.parse_tnef_body` | `tnef_support` | `application/ms-tnef` (Outlook `winmail.dat`) részek feldolgozása |

Ha az import nem sikerül, a flag `False`, és az `eml2str()` / `get_mimedata()` ezeket a részeket kihagyja.

---

## Globális konstansok

| Név | Típus | Leírás |
|---|---|---|
| `charset_mapping` | `dict[str, str]` | Nem szabványos / alias karakterkészlet-nevek leképezése Python codec-nevekre (pl. `latin2` → `iso-8859-2`, `ks_c_5601-1987` → `euc-kr`). Figyelem: a `latin1`/`iso-8859-1`/`us-ascii` szándékosan `windows-1252`-re képződik. |
| `invalid_charrefs` | `dict[int, str]` | Kódpont → helyettesítő karakter. A `0x80–0x9F` tartományt cp1252 szerint értelmezi, a `NUL`/`NBSP` szóközzé, a soft hyphen üressé válik, és a magyar `ő/Ő/ű/Ű` latin1-es "rossz" megfelelőit (`õ, Õ, û, Û`) latin2-es betűkre javítja. |
| `LINK_ATTRS` | `dict[str, str]` | HTML tag → attribútum, amiből URL-t kell kinyerni (`a/href`, `iframe/src`, `form/action`, …). |
| `ATTR_RE_CACHE` | `dict[str, re.Pattern]` | Az `html_extract_attr()` lefordított regex-cache-e. |
| `TAG_RE3`, `TAG_RE4`, `TAG_RE6` | `re.Pattern` | URL, e-mail cím és `.hu` domain felismerő regexek (`remove_url()`). `TAG_RE5` (számok) definiálva, de nincs használva. |
| `STAG_SA` | `re.Pattern` | SpamAssassin `*****SPAM{15.0}*****` jellegű tárgy-tag. |
| `hdr_re` | `re.Pattern` | RFC 2047 encoded-word (`=?charset?Q|B?...?=`) felismerése. |
| `param_re` | `re.Pattern` | RFC 2231 paraméternév-utótag (`*`, `*N`, `*N*`) felismerése (`rfc2231_decode()`). |
| `from_re1`, `from_re2` | `re.Pattern` | `From:` fejléc formátumai: `"Név" <cím>` ill. `cím (Név)`. |

A modul betöltésekor regisztrálódik a **`"mixed"`** nevű codec hibakezelő (`codecs.register_error`),
így bármely `bytes.decode(..., "mixed")` hívás a hibás bájtokat nem dobja el, hanem latin1/cp1252
szerint (az `invalid_charrefs` táblával) karakterré alakítja.

---

## Fő (magas szintű) függvények

### `eml2str(msg, ds2=False)`
A modul fő belépési pontja: nyers e-mailből kinyeri a "legjobb" szöveges törzset.

| Paraméter | Típus | Leírás |
|---|---|---|
| `msg` | `bytes` | A teljes nyers üzenet (fejléc + törzs). |
| `ds2` | `bool` | Ha `True`, a `Subject:` fejlécet is dekódolja (és eltávolítja belőle a spam-tageket). |

**Visszatérés:** `str` – a kinyert szöveg; vagy `ds2=True` és nem üres subject esetén
`tuple[str, str]` = `(subject, text)`.
> Ha `ds2=True`, de nincs (vagy üres) Subject, akkor is csak `str` jön vissza – ez szándékos,
> a deepspam2 így várja.

Működés: `parse_eml(decode=True)`-val MIME-fát épít, bejárja a leveleket (leaf part-okat), és a
nem-csatolmány `text/*`, `application/ics`, TNEF és RTF részeket `decode_payload()`-dal dekódolja.
Heurisztika a választáshoz: a HTML / TNEF rész előnyt élvez (>20 karakter), egy későbbi rész
felülírja az eddigit, ha legalább fele olyan hosszú, és a SpamAssassin riport ("Spam detection
software,…") mindig felülíródik. Ha találunk 200 karakternél hosszabb HTML/TNEF szöveget, leáll.

### `get_mimedata(eml)`
Debug / megjelenítő célú MIME-fa kibontás (pl. GUI-s levélnézőhöz).

| Paraméter | Típus | Leírás |
|---|---|---|
| `eml` | `bytes` | Nyers üzenet. |

**Visszatérés:** `tuple[list[str], list[bytes]]` = `(mimeinfo, mimedata)`
A két lista mindig egyforma hosszú, és index szerint összetartozik (`mimeinfo[i]` ↔ `mimedata[i]`).
Az első pár: `"RAW message: N bytes"` ↔ a teljes nyers levél. Utána MIME részenként:

| Feltétel | `mimeinfo` sor | `mimedata` blokk |
|---|---|---|
| ha nincs fájlnév | típussor: behúzás + típus + `[charset]` + `(nyers méret)` + payload méret | a dekódolt payload (vagy ha nincs, a nyers rész) |
| ha van fájlnév | típussor | a nyers rész (fejléccel együtt) |
| | `disposition: fájlnév` sor | a dekódolt payload (vagy a nyers rész) |
| ha van kinyert szöveg, és eltér a payloadtól | `Extracted text: <karakter>/<bájt>` | a kinyert szöveg UTF-8 bájtokként |

HTML / XML résznél a payload blokk a `html2text(debug=True)` által "prettify"-olt, annotált HTML.

### `parse_eml(data, debug=False, decode=False, level=0, p=0, pend=-1)`
Saját, rekurzív MIME parser. A `data`-t nem másolja, csak pozíciókkal (`p`, `pend`) dolgozik.

| Paraméter | Típus | Leírás |
|---|---|---|
| `data` | `bytes` | A teljes nyers üzenet. |
| `debug` | `bool` | Részletes kiírás stdout-ra. |
| `decode` | `bool` | Ha `True`, a leaf részeknél a transfer-encodingot (base64/QP) is dekódolja → `"payload"` kulcs. |
| `level` | `int` | Rekurziós mélység (belső használatra). |
| `p`, `pend` | `int` | Az aktuális rész kezdő/záró pozíciója `data`-ban (`pend=-1` → `len(data)`). |

**Visszatérés:** `dict` az alábbi kulcsokkal:

| Kulcs | Típus | Tartalom |
|---|---|---|
| `headers` | `list[bytes]` | Összefűzött (unfolded) fejlécsorok. |
| `raw` | `tuple[int, int]` | A rész `(start, end)` pozíciója a `data`-ban. |
| `size` | `int` | A rész teljes mérete. |
| `hsize` | `int` | A fejléc mérete (az üres sorral együtt). |
| `ct` | `dict[bytes, bytes]` | `parse_ctyp()` eredménye: `b'_ct'`, `b'_cd'`, `b'_ce'` + paraméterek (`b'charset'`, `b'boundary'`, `b'name'`, `b'filename'`…). |
| `ctyp` | `str` | Content-Type kisbetűvel, alapértelmezés `'text/plain'`. |
| `charset` | `str \| None` | Charset kisbetűvel. |
| `encoding` | `str` | Content-Transfer-Encoding kisbetűvel (lehet `''`). |
| `disp` | `str \| None` | Content-Disposition (`attachment`, `inline`…). |
| `name` | `str \| None` | Dekódolt fájlnév (`filename`, ennek hiányában `name`, mindkettő `ct_param()`-mal, tehát RFC 2231 és RFC 2047 szerint is); dekódolási hibánál `"EXC!"`. |
| `parts` | `list[dict]` | Alrészek (`multipart/*` és `message/*` esetén), ugyanilyen szerkezettel. |
| `payload` | `bytes` | Csak `decode=True` és leaf rész esetén: a transfer-decoded törzs. |

Toleráns a hibás levelekkel szemben (hiányzó záró boundary, boundary előtti fejlécek, CRLF/LF
keverés stb.); a rendellenességeket `print()`-tel jelzi (`BoundaryNotFound:`, `PreBoundaryText:`…).

### `readfolder(f, do_eml, keephdrs=['from','subject','x-deepspam','x-grey-ng'])`
mbox formátumú (`From ` sorokkal elválasztott) postafiók-fájl gyors, soronkénti végigolvasása,
teljes parse nélkül.

| Paraméter | Típus | Leírás |
|---|---|---|
| `f` | bináris fájlobjektum | Pl. `open(path, 'rb')`; a `f.tell()`-től kezdi. |
| `do_eml` | `Callable[[dict, int], Any]` | Callback, levelenként hívódik: `do_eml(eml, fpos_end)`, ahol `fpos_end` a levél végének fájlpozíciója. |
| `keephdrs` | `list[str]` | Mely fejléceket (kisbetűs névvel) tegye bele a dict-be. |

A callbacknek átadott `eml` dict kulcsai: `_fpos` (a levél kezdete), `_from` (a `From ` elválasztó
sor), `_hsize` (fejlécméret), `_attach` (`True`, ha van `Content-Disposition: attachment` sor), valamint
a `keephdrs` szerinti fejlécek nyers (nem RFC2047-dekódolt) `str` értékkel.

**Visszatérés:** `int` – az utolsó pozíció (= a folder fájl mérete).

---

## Dekódolás / tartalomkonverzió

### `decode_payload(data, ctyp="text/html", charset=None)`
Egy (már transfer-decoded) MIME rész bájtjait alakítja végleges, tiszta Unicode szöveggé.

| Paraméter | Típus | Leírás |
|---|---|---|
| `data` | `bytes` | A rész payloadja. |
| `ctyp` | `str` | Content-Type. |
| `charset` | `str \| None` | Deklarált karakterkészlet. |

**Visszatérés:** `str`

Lépések:
1. Típus szerinti előfeldolgozás: `text/calendar`/`application/ics` → `parse_ics()`; DOCX → `parse_docx()`;
   TNEF → `parse_tnef_body()` (HTML body → `html2text()`, különben RTF → `rtf_to_text()`);
   HTML (vagy HTML-nek *látszó* text/plain) → charset felülírás a `<head>`-ből (`parse_htmlhead()`),
   ISO-2022-* előzetes dekódolás, majd `html2text()`.
2. Charset feloldás: alapértelmezés `iso8859-1`, aliasok a `charset_mapping` szerint.
3. Dekódolás: ha `utf-8` vagy `is_utf8()` szerint annak tűnik → szigorú UTF-8, hiba esetén a
   deklarált charset `"mixed"` hibakezelővel; ismeretlen codec esetén UTF-8 `"mixed"`-del.
4. RTF esetén `rtf_to_text()`, egyébként HTML entitások feloldása (`html.unescape`).
5. Végül minden karakter átfut az `invalid_charrefs` táblán.

> A `tnef_support` / `rtf_support` flaget itt nem ellenőrzi, ez a hívó (`eml2str()`,
> `get_mimedata()`) feladata.

### `decode_body(data, encoding)`
Content-Transfer-Encoding dekódolás.

| Paraméter | Típus | Leírás |
|---|---|---|
| `data` | `bytes` | Kódolt törzs. |
| `encoding` | `str` | `base64`, `quoted-printable` (vagy a hibás `utf8`/`utf-8`, amit QP-ként kezel), `7bit`/`8bit`/`binary`. |

**Visszatérés:** `bytes` – dekódolt adat; hiba vagy ismeretlen kódolás esetén az eredeti `data`
(és egy `print()` üzenet).

### `html2text(data, debug=False)`
Saját, gyors, toleráns HTML → szöveg konverter (bájt szinten dolgozik, a karakterkódolás ekkor még nincs feloldva).

| Paraméter | Típus | Leírás |
|---|---|---|
| `data` | `bytes` | HTML forrás. |
| `debug` | `bool` | Ha `True`, egy tagenként tördelt, behúzott, pozíciókkal és warningokkal annotált HTML listát is visszaad. |

**Visszatérés:**
- `debug=False`: `bytes` – a szöveg.
- `debug=True`: `tuple[bytes, list[bytes]]` = `(text, html_lines)`.
- Ha a bemenetben nincs `<`: változatlanul adja vissza (`debug` esetén `(data, [data])`).

Jellemzők:
- `<style>`, `<script>`, `<title>`, `<svg>`, `<annotation>` blokkok és HTML kommentek kihagyása, CDATA kezelése.
- Rejtett szöveg felismerése (`display:none`, `font-size:0/1px`, `max-height:0`, `mso-hide:all`, `opacity:0`)
  → kimarad; kivétel a levél eleji rejtett "preheader", ami `[...]` közé téve bekerül.
  MS Teams `signedadaptivecard` rejtett base64 adat kihagyva.
- `div`, `p`, `br`, `tr` → sortörés; inline elemek (`span`, `a`, `b`, …) között nincs extra szóköz.
- Felesleges whitespace összevonása, soronkénti strip.
- A `LINK_ATTRS` szerinti linkek (sorrendtartó deduplikálással) a szöveg végére kerülnek
  `URL: <max. 128 karakter>` sorokként.
- A HTML entitásokat itt **nem** oldja fel (azt a `decode_payload()` teszi dekódolás után).

### `parse_htmlhead(data, charset=None)`
A HTML `<head>` részből kiszedi a `<meta ... charset=...>` értéket.

- `data`: `bytes` (a `<body` előtti rész), `charset`: `str | None` – alapérték, ha nincs meta.
- **Visszatérés:** `str | None` – kisbetűs charset név (vagy a bemenő alapérték).

### `html_extract_attr(rawtag, attrname)`
Egy tag belsejéből (`<` és `>` nélkül, eredeti kis-nagybetűkkel) kiveszi egy attribútum értékét
(idézőjeles, aposztrófos vagy idézőjel nélküli formában is; `data-href`-et nem találja meg `href`-ként).

- `rawtag`: `bytes`, `attrname`: `str`
- **Visszatérés:** `str | None` – UTF-8 (`mixed`) dekódolt, entitás-feloldott, strip-elt érték.

### `tag_type(tag)`
Egy (kisbetűsített, `<>` nélküli) tagból meghatározza a nevét és típusát.

- `tag`: `bytes`
- **Visszatérés:** `tuple[int, str]` = `(típus, név)`, ahol típus: `1` = nyitó, `-1` = záró,
  `0` = önzáró / void elem (`br`, `img`, `meta`, …) vagy speciális (`!` = doctype/komment, `?` = XML PI).
  A névben csak az `a–z` betűket veszi figyelembe (pl. `h1`…`h6` → `h`). Ez szándékos: a számra
  nincs szükség, és így egyszerűbb a tagnév-ellenőrzés.

### `parse_ics(data)`
iCalendar (`.ics`) tartalomból kiszedi a leírást.

- `data`: `bytes`
- **Visszatérés:** `bytes` – az első `DESCRIPTION*` mező (escape-ek feloldva), vagy ha előbb
  `X-ALT-DESC;FMTTYPE=text/html` jön, annak `html2text()` változata; ha egyik sincs, `b''`.

### `parse_docx(data)`
Word `.docx` (ZIP) fájlból a `word/document.xml` szövegét veszi ki (`w:t` elemek; `w:p`, `w:br`,
`w:tab`, `w:cr` → újsor).

- `data`: `bytes`
- **Visszatérés:** `bytes` (UTF-8); hiba esetén a kivétel `repr()`-je bájtként.

### `is_utf8(s)`
Heurisztikus UTF-8 detektor: megszámolja a helyes és hibás többbájtos szekvenciákat.

- `s`: `bytes`
- **Visszatérés:** `bool` – `True`, ha a helyes folytató bájtok száma > 4 × a hibák száma.
  (Tisztán ASCII bemenetre `False`.)

### `mixed_decoder(unicode_error)`
A `"mixed"` codec hibakezelő implementációja (közvetlenül nem kell hívni).

- `unicode_error`: `UnicodeDecodeError`
- **Visszatérés:** `tuple[str, int]` – a hibás bájt helyettesítő karaktere (`invalid_charrefs`
  vagy latin1) és a folytatási pozíció.

---

## Fejlécek

### `hdrdecode4(h)`
RFC 2047 encoded-word-ös fejléc (pl. `=?UTF-8?B?...?=`, `=?iso-8859-2?Q?...?=`) dekódolása.

- `h`: `str | bytes` (bytes esetén UTF-8 `mixed`-del dekódolja előbb)
- **Visszatérés:** `str`

Kezeli az encoded-word-ök közti whitespace elhagyását, a hibás `==` QP-t, a padding nélküli base64-et,
és összefűzi az azonos charsetű szomszédos darabokat dekódolás előtt (a karakter közepén kettévágott
UTF-8 szekvenciák miatt).

### `parse_ctyp(data, hdr=b'_', ct=None)`
`Content-*: érték; param1=érték1; param2="érték 2"` típusú fejlécérték feldolgozása.

| Paraméter | Típus | Leírás |
|---|---|---|
| `data` | `bytes` | A fejléc értéke (a `:` utáni rész). |
| `hdr` | `bytes` | Kulcs, amely alá a fő érték kerül (pl. `b'_ct'`, `b'_cd'`, `b'_ce'`). |
| `ct` | `dict \| None` | Meglévő dict, amibe ír (több fejléc gyűjthető egybe); `None` → új dict. |

**Visszatérés:** `dict[bytes, bytes]` – a fő érték a `hdr` kulcs alatt, a paraméterek kisbetűs
névvel (idézőjelek levéve, idézőjelen belüli whitespace megtartva). A paraméterértékek nyersek:
az RFC 2047 / RFC 2231 dekódolás a `ct_param()` dolga.

Idézőjelek: a `"` az érték bármely pontján idézetet nyit. Az aposztróf (`'`) csak az érték
**elején** számít idézőjelnek (nem szabványos, de előfordul: `filename='x.pdf'`), és az RFC 2231
paramétereknél (`név*=`, `név*N*=`) ott sem. Így az `O'Brien.pdf` és a `filename*=UTF-8''...`
értékek épen maradnak.

### `ct_param(ct, key)`
Egy paraméter dekódolt értéke a `parse_ctyp()` dict-jéből.

- `ct`: `dict[bytes, bytes]`, `key`: `bytes` (pl. `b'filename'`, `b'name'`)
- **Visszatérés:** `str | None`. Ha van RFC 2231 alak (`key*`, `key*0*`, `key*1`…), az élvez
  elsőbbséget (`rfc2231_decode()`), különben a sima `key` érték `hdrdecode4()`-gyel. Ha egyik
  sincs: `None`.

### `rfc2231_decode(ct, key)`
RFC 2231 paraméter dekódolása: folytatósorok (`key*0`, `key*1`… sorrendben összefűzve), a
`charset'nyelv'` előtag és a `%XX` kódolás a `*`-gal jelölt darabokban. Ismeretlen charset esetén
UTF-8, a hibás bájtok a `"mixed"` hibakezelővel.

- `ct`: `dict[bytes, bytes]`, `key`: `bytes`
- **Visszatérés:** `str | None` (`None`, ha nincs ilyen RFC 2231 paraméter).

### `parse_from(h)`
`From:` fejléc szétbontása cím és név részre, **dekódolás nélkül**.

- `h`: `str`
- **Visszatérés:** `tuple[str, str]` = `(cím, név)`. Formák: `"Név" <cím>`, `Név <cím>`, `cím (Név)`
  (utóbbinál a név a zárójelekkel együtt jön vissza). Ha nincs felismerhető cím: `("", h)`.

### `decode_from(h)`
Mint a `parse_from()`, de a nevet `hdrdecode4()`-gyel dekódolja is; ha a cím csak a dekódolt névben
volt (base64-be kódolt cím), újra parse-olja.

- `h`: `str`
- **Visszatérés:** `tuple[str, str]` = `(cím, dekódolt név)`

---

## Szövegtisztítás / tokenizálás

### `remove_spamtag(text)`
A tárgysorból eltávolítja a spamszűrők által beszúrt jelöléseket (SpamAssassin, ESET, Kaspersky,
Outlook, `[SPAM]` stb.).

- `text`: `str` → **Visszatérés:** `str`

### `remove_url(text)`
URL-ek, e-mail címek és `.hu` domainek lecserélése `<URL>`, `<EMAIL>`, `<DOMAIN>` placeholderre
(normalizálás pl. ML tanításhoz).

- `text`: `str` → **Visszatérés:** `str`

### `vocab_split(preview)`
Szöveg tokenizálása szó / nem-szó darabokra úgy, hogy a darabok összefűzése visszaadja az eredetit.

- `preview`: `str`
- **Visszatérés:** `list[str]` – felváltva elválasztó (írásjel/whitespace) és szó (alfanumerikus)
  tokenek; az első elem lehet üres string. Számok után a `: - / .` karakterek a tokenen belül
  maradnak (dátumok, telefonszámok, időpontok egyben maradnak).

---

## Tipikus használat

```python
from eml2str import eml2str, get_mimedata, decode_from, hdrdecode4

raw = open("level.eml", "rb").read()

text = eml2str(raw)                     # csak a törzs szövege
res = eml2str(raw, ds2=True)            # (subject, text), ha van subject
info, blocks = get_mimedata(raw)        # MIME-fa debug nézethez

addr, name = decode_from('=?UTF-8?B?S292w6FjcyBKw6Fub3M=?= <kj@example.hu>')
```
