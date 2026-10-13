# mailer4 – használati útmutató

Konzolos (text mode) mbox-olvasó és -válogató, spam-datasetek előkészítéséhez.
Ezt a leírást a forráskód ([mailer4.py](mailer4.py), [ttykeymap.py](ttykeymap.py), [eml2str.py](eml2str.py)) alapján utólag állítottam össze.

## Indítás

```bash
python3 mailer4.py valami.mbox
```

- Paraméter nélkül a `test.mbox` fájlt nyitja meg.
- Ha a fájl első sora nem `From `-mal kezdődik (tehát nem mbox), a program szó nélkül kilép.
- Induláskor a kurzor a **legutolsó** levélen áll.
- Kilépés: `q`.

## Alapelv: minden a látható levelekre vonatkozik

A szűrők (`D`, `?`, `H`, `A`, `E` – lásd lent) határozzák meg, mely levelek látszanak a listában. **Szándékosan (by design) szinte minden művelet csak a listában éppen látható levelekre hat**, a valamiért rejtettekre nem: mozgás, keresés, csoportos kijelölés (`+` `-` `*`), csoportos törlés (`d`), export (`t`, `[`).

Ebből következik, hogy a csoportos műveletek (`d`, `t`, `[`) **nem a kijelölt, hanem az összes látható** levélre hatnak – ha csak a kijelöltekre akarod, előbb `?`-lel válts „csak kijelöltek” nézetre.

A kivételeket – amelyek a rejtett levelekre is hatnak vagy rájuk is tekintettel vannak – a leírásban ⚠️ jelöli, és a végén össze is vannak gyűjtve: [Kivételek](#kivételek-az-alapelv-alól).

### Opcionális függőségek (ha hiányoznak, a program csendben nélkülük fut)

| Mi | Honnan tölti | Mire kell |
|---|---|---|
| DeepSpam modell | `/home/mailer4/model.py` + `/home/mailer4/model/`, `device="cuda"` | spam-valószínűség oszlop, `d` keresés, tokenizer preview |
| GeoIP | `pylibloc` (`LocDB`) | ország/szolgáltató kiírása a fejlécben |
| Szótár (vocab) | `/home/vocab/vocab.txt` (`szó darabszám` soronként) | vocab-preview kiemelés, `v` keresés, vocab alapú dedup |
| Viewer | `mcedit` (Midnight Commander) | MIME részek megnézése Enterrel |

A GeoIP az `X-Grey-ng` fejlécből veszi az `ip=` értéket; ha nincs ilyen fejléc, `???` jelenik meg.

### Mellékfájlok (az mbox mellé, `<mbox>.xxx` néven)

| Fájl | Tartalom | Mikor íródik |
|---|---|---|
| `.meta` | fejléc-index (pickle): pozíció, méret, From, Subject, … | induláskor, ha új levelek jöttek **és** >10 000 levél van |
| `.flag` | jelölők (kijelölt / törölt / extra) levelenként | kilépéskor, ill. Enteres viewer-indítás előtt |
| `.dedup` | duplikáció-információ | `h` (dedup) futtatása után |
| `.text` | kinyert szöveges tartalom (preview) soronként | `P` után, ha ≥2000 levél van |
| `.tag_SPAM` / `.tag_PHIS` / `.tag_HAM` | dataset-export (`mbox:index:subject\|szöveg`) | `t` paranccsal |

Fontos:
- A `.meta` inkrementális: ha az mbox **végéhez** új levelek kerülnek, induláskor csak azokat olvassa be. Ha viszont az mbox-ot átírod (levelet törölsz belőle, átrendezed), töröld a `.meta`, `.flag`, `.dedup`, `.text` fájlokat, mert ezek levél-sorszám/pozíció alapúak és elcsúsznak.
- A „törlés” csak jelölés (`.flag`), **az mbox fájlhoz a program soha nem nyúl**.
- A `.text` betöltésekor (ha van DeepSpam) induláskor batch-ben kiszámolja minden levél spam-értékét.

## A képernyő

### Fejléc (1. sor)

```
  [eadHS+] 90749/90749 [172x37]  P:2108154475 S:6723 D:99.87%  dup:3 (90120) 0.973  preview:vocab  EU/Netherlands/Delis LLC
```

- `[eadHS+]` – aktív szűrők; **nagybetű = szűrő bekapcsolva** (részletesen lent a Szűrők résznél)
- `90749/90749` – aktuális levél sorszáma / összes levél
- `[172x37]` – lista mérete
- `P:` – a levél bájtpozíciója az mbox-ban, `S:` – teljes mérete
- `D:` – DeepSpam érték (`n/a`, ha nincs modell; üres, ha még nincs kiszámolva; `short`, ha túl rövid a szöveg)
- `dup:N` – hány példány van ebből a levélből (⚠️ a rejtetteket is beleszámolva); `!` = ez az eredeti, `(1234)` = ez másolat, az eredeti sorszáma 1234; utána a hasonlósági arány az eredetihez képest
- `preview:` – aktuális preview mód
- végén: GeoIP (kontinens/ország/szolgáltató) vagy az IP vagy az `X-Grey-ng` első szava

### Levéllista sorai

```
 99.87%  D* Feladó Neve  <cim@domain>        6723+ Tárgy szövege
```

- színes spam-% (csak ha van DeepSpam): zöld → sárga → narancs → piros (≥99,9%)
- `D` = törlésre jelölt, `*` = extra jelölés
- feladó (formátuma `f`-fel váltható)
- body mérete bájtban, `+` = van csatolmány
- tárgy (spamtagek eltávolítása `T`-vel kapcsolható)

Kiemelések: **inverz** = kurzor, **félkövér** = kijelölt (selected), **halvány** = duplikátum.

## Billentyűk

### Mozgás

| Billentyű | Funkció |
|---|---|
| `↑` / `↓` | előző / következő levél |
| `PgUp` / `PgDn` | egy képernyőnyit fel / le |
| `Home` / `End` | első / utolsó levél |
| `←` / `→` | Feladó és Tárgy oszlop vízszintes görgetése (5 karakterenként) |
| `l` | ugrás adott sorszámú levélre (beírod a számot) – ⚠️ abszolút sorszám, rejtett levélre is ráugrik |
| `q` | kilépés (jelölők mentése) |

### Jelölés egyenként (a kurzor utána a következő levélre lép)

| Billentyű | Funkció |
|---|---|
| `Insert` | kijelölés (selected) be/ki |
| `Delete` | törlésjelölés be/ki |
| `e` | „extra” jelölés be/ki (`*` a sorban) |

### Szűrők (mi látszik a listában)

| Billentyű | Fejléc | Funkció |
|---|---|---|
| `D` | `d` → `D+` → `D` | 3 állás: törölt jelöltek **elrejtve** (alap) → **mind** látszik → **csak a törölt** jelöltek |
| `?` | `S+` → `S` → `s` | 3 állás: **mind** (alap) → **csak kijelöltek** → **csak nem kijelöltek** |
| `H` | `H` / `h` | duplikátumok elrejtése be/ki (**alapból BE**: csak az eredetiek látszanak) |
| `A` | `A` / `a` | csak a csatolmányos levelek |
| `E` | `E` / `e` | csak az „extra” jelöltek |

### Megjelenítés

| Billentyű | Funkció |
|---|---|
| `f` | feladó formátuma körbe: csak cím → csak név → `Név <cím>` (alap) |
| `T` | spamtagek (`*****SPAM*****`, `[SPAM]`, `[K:Spam]`, `[E:spam]`, Outlook stb.) eltávolítása a tárgyból be/ki (alapból a tárgy változatlan) |
| `p` | preview panel (alul 8 sor) módjai körbe: |
|  | • `off` – nincs preview |
|  | • `vocab` – levél szövege; a szótárban szereplő szavak félkövérek (ha nincs vocab, sima szöveg) |
|  | • `sanitized` / `diff` – URL-ek, e-mail címek, `.hu` domainek kicserélve (`<URL>`, `<EMAIL>`, `<DOMAIN>`); **duplikátumnál színes diff az eredetihez képest**: piros = csak az eredetiben, zöld = csak ebben, fehér = közös |
|  | • `non-latin` – a nem latin (U+017F feletti) karakterek félkövérek |
|  | • `tokenizer` – a DeepSpam tokenizált bemenete (csak ha van modell) |
| `P` | ⚠️ **minden** levél (a rejtettek is) szövegének kinyerése (preview generálás, progress-szel); ≥2000 levélnél elmenti a `.text` fájlba, így legközelebb gyors az indulás és a DeepSpam is rögtön lefut |
| `Enter` | a levél MIME-szerkezete menüben (RAW üzenet, részek, csatolmányok, HTML-ből kinyert szöveg); a kiválasztott rész `/tmp/mailer4.tmp`-be kerül és `mcedit`-ben megnyílik; kilépés után vissza a listába |

### Keresés

| Billentyű | Funkció |
|---|---|
| `s` | új keresés megadása, majd keresés **visszafelé** |
| `n` | új keresés megadása, majd keresés **előre** |
| `S` | előző találat (ugyanazzal a feltétellel) |
| `N` | következő találat |

### Csoportos kijelölés feltétel alapján

A feltétel szintaxisa ugyanaz, mint a keresésé (lásd lent).

| Billentyű | Funkció |
|---|---|
| `+` | a feltételnek megfelelőek kijelölése (hozzáadás). Ha a `?` szűrő „csak kijelöltek” (`S`) állásban van, akkor **szűkít**: a kijelöltek közül csak a feltételnek megfelelők maradnak kijelölve (ÉS kapcsolat) |
| `-` | a feltételnek megfelelőek kijelölésének levétele |
| `*` | a feltételnek megfelelők kijelölésének invertálása. Speciális eset: „csak kijelöltek” (`S`) állásban a `*` a látható levelek kijelölését törli és visszavált „mind” nézetre (a más szűrő – pl. `D`, `H` – miatt rejtett kijelöltek kijelölve maradnak) |

Üres feltétel (csak Enter) = minden látható levél illeszkedik, tehát pl. `+` Enter = mind kijelölése, `*` Enter = kijelölés invertálása.

### Csoportos műveletek

Tipikus használat: előbb kijelölöd, amit kell, aztán `?`-lel „csak kijelöltek” nézetre váltasz, és úgy adod ki a parancsot (lásd [Alapelv](#alapelv-minden-a-látható-levelekre-vonatkozik)).

| Billentyű | Funkció |
|---|---|
| `d` | az összes látható levél törlésre jelölése – megerősítés **nagy `Y`**-nal |
| `t` | dataset-export: menüből `SPAM` / `PHIS` / `HAM`, a látható leveleket a `<mbox>.tag_XXX` fájlba írja (`mbox:sorszám:tárgy\|szöveg` soronként). **A meglévő fájlt felülírja!** |
| `[` | a látható levelek kimentése nyers formában egy új mbox fájlba (fájlnevet kér) |

### Duplikátumszűrés

`h` – menüből választható összehasonlítási módszer, utána végignézi a leveleket, az eredményt a `.dedup` fájlba menti. ⚠️ **Kivétel az alapelv alól:** a szűrőket figyelmen kívül hagyja, csak a törlésre jelölteket hagyja ki, minden mást (rejtett, nem kijelölt, csatolmány nélküli stb. levelet is) vizsgál.

1. **Exact match** – a kinyert szöveg pontosan egyezik
2. **Sanitized match** – URL/e-mail/domain kicserélve, kisbetűsítve
3. **Vocab words only** – csak a szótárban szereplő szavak alapján
4. **Vocab words (5:100)** – szótárszavak közül az 5.–100.
5. **First 100 words** – az első 100 szó
6. **Words 10:100** – a 10.–100. szó
7. **SequenceMatcher** – fuzzy összehasonlítás, ≥95% hasonlóság (token-szinten) esetén duplikátum. Először a pontos (sanitized) egyezéseket csoportosítja, majd az egyedi levelek között keres közeli másolatot; prefix-szűrés miatt csak a szóba jöhető párokat hasonlítja össze, de az eredmény ugyanaz, mintha mindenkit mindenkivel összevetne. Még így is ez a leglassabb mód.

A 2–7. módok is a sanitized (URL-mentes, kisbetűs) szövegből indulnak ki. Az első előfordulás az „eredeti”, a többi ennek másolata. Utána a `H` szűrővel lehet rejteni/mutatni a másolatokat, a preview `diff` módja pedig megmutatja az eltérést az eredetitől.

## Keresési / kijelölési feltétel szintaxisa

### 1. Egyszerű szöveg

```
viagra
```

Kis/nagybetű-független keresés a feladóban és a tárgyban (ugyanaz, mint `SF:viagra`).

### 2. Szöveges keresés: `mezők:érték`

A `:` előtti betűk mondják meg, hol keressen (több is kombinálható, VAGY kapcsolattal):

| Betű | Hol |
|---|---|
| `s` / `S` | Subject (eredeti tárgy) |
| `f` / `F` | From (abban a formában, ahogy éppen `f`-fel be van állítva) |
| `p` / `P` | Preview (a levél kinyert szövege – ha még nincs meg, kinyeri, lassú lehet) |
| `g` / `G` | Grey/GeoIP szöveg (ami a fejléc végén látszik) |
| `h` | a levél teljes nyers fejléce |

Kisbetű = kis/nagybetű-érzékeny, nagybetű = érzéketlen. Ha **minden** mezőbetű nagybetű, a keresett értéket kisbetűsíti (pl. `SFP:Bitcoin` = „bitcoin” bárhol a tárgyban, feladóban, szövegben, betűmérettől függetlenül).

Példák:

```
s:[SPAM]
F:@gmail.com
P:unsubscribe
G:russia
h:X-Mailer: PHPMailer
```

### 3. Numerikus feltétel: `mező<op>szám`

Operátorok: `<`, `<=`, `=`, `>=`, `>`

| Betű | Érték |
|---|---|
| `d` | DeepSpam % (kell a modell, és a levélnek legyen kiszámolt értéke) |
| `s` | body mérete bájtban |
| `w` | szavak száma a szövegben |
| `v` | szótárbeli szavak száma |
| `l` | latin betűk száma (≤ U+017F) |
| `L` | nem latin karakterek száma |
| `j` | CJK (kínai/japán/koreai) karakterek száma |
| `h` | duplikáció-szám (lásd megjegyzés lent; ⚠️ a rejtett példányokat is számolja) |

Példák:

```
d>=99
s<200
w<10
j>50
```

## Tipikus munkafolyamat (dataset-készítés)

1. `python3 mailer4.py spam.mbox`
2. `P` – szövegek kinyerése (és DeepSpam értékek), ez a `.text`-be mentődik
3. `h` → pl. *Sanitized match* – duplikátumok szűrése (a `H` alapból rejti őket)
4. Szemét kiszórása: pl. `+` → `w<5` (túl rövidek), `+` → `j>20` (CJK), aztán `?` (csak kijelöltek) → átnézés → `d` → `Y`, majd `*` (kijelölések törlése, vissza mind nézetre). Megjegyzés: a `d` után a törölt levelek eltűnnek a listából, ezért a `*` rájuk már nem hat, kijelölve maradnak (a `D` szűrővel visszahozva látszik)
5. Végső válogatás jelöléssel, aztán `?`-lel a megfelelő nézet, és `t` → `SPAM`/`PHIS`/`HAM` export, vagy `[` mbox export
6. `q` – kilépés, jelölők mentése

## Beviteli ablakok, menük

- **Szövegbeviteli ablak** (keresés, sorszám, fájlnév): `←` `→` `Home` `End` `Del`, `Enter` = OK, `Esc` = mégse. Az első leütött karakter **felülírja** az előző értéket (ha csak módosítani akarod, előbb nyomj egy nyilat).
- **Menü** (dedup, tag, MIME, hibaüzenet): `↑` `↓` `Home`/`PgUp` `End`/`PgDn`, `Enter` vagy `F3` = választás, `Esc` vagy `q` = mégse.
- Ha futás közben kivétel történik, a traceback egy menüablakban jelenik meg; `Enter`-rel vissza lehet térni.

## Kivételek az alapelv alól

Ami **nem** csak a látható levelekre hat, vagy a rejtettekre is tekintettel van:

| Mi | Viselkedés |
|---|---|
| `h` dedup | minden levelet vizsgál, csak a törlésre jelölteket hagyja ki. A törölt jelölt levelek régi dedup-értéke megmarad (nem nullázódik). |
| `H` szűrő + más szűrő | mivel a dedup a rejtett levelekre is kiterjed, egy másolat akkor is rejtve marad, ha az eredetije egy másik szűrő miatt nem látszik. Pl. `?` „csak kijelöltek” nézetben egy kijelölt másolat, amelynek az eredetije nincs kijelölve, **egyáltalán nem jelenik meg**; a csoport tehát akár teljesen eltűnhet a listából. Ilyenkor `H`-val kapcsold ki a duplikátum-rejtést. |
| `P` preview generálás | minden levél szövegét kinyeri (törölteket, rejtetteket is) és menti a `.text`-be |
| DeepSpam induláskor | a `.text` alapján minden levélre kiszámolja |
| `dup:N` a fejlécben, `h<op>szám` keresés | a duplikátumcsoport méretébe a rejtett példányok is beleszámítanak; a fejlécben mutatott eredeti sorszáma lehet rejtett levél is |
| `l` (ugrás sorszámra) | abszolút sorszám, rejtett levélre is ráugrik (a kurzor ilyenkor nem látszik a listában, de a fejléc azt a levelet mutatja; a nyilakkal onnan lehet tovább lépni) |
| `.flag` mentés | természetesen minden levél jelölőjét menti |

Ami szándék szerint **igen**, csak a láthatókra hat (a teljesség kedvéért): mozgás, keresés (`s` `n` `S` `N`), `+` `-` `*` (a `*` speciális esete is!), `d`, `t`, `[`. Az egyenkénti jelölés (`Ins`, `Del`, `e`) és az `Enter` a kurzor alatti levélre hat.

## Ismert furcsaságok (a kód alapján)

- **Backspace** a beviteli mezőben valószínűleg nem működik a legtöbb terminálban: a 0x7F kódot a keymap `s+bs`-nek nevezi, a mező pedig csak a `bs`-t (0x08, Ctrl+H) kezeli. Használható helyette `←` + `Del`, vagy `Ctrl+H`.
- Ha egy sima keresőszövegben betűk után `:` vagy `<`/`=`/`>` jön (pl. `http://...`), akkor azt mezőmegadásnak értelmezi (`http` → `h`,`t`,`p` mezők).
- A `h<op>szám` numerikus keresés eredeti (alap) levélnél negatív számot használ (`-1` = egyedi, `-3` = 2 másolata van), másolatnál pozitívat (a csoport méretét), tehát pl. `h>1` csak a másolatokat találja meg, az eredetiket nem.
- `d` feltétel DeepSpam nélkül, vagy még ki nem számolt értékű levélen hibát dob.
- A `.flag` csak kilépéskor (vagy Enteres viewer-indításkor) mentődik – program-összeomlásnál a jelölések elveszhetnek.
- A DeepSpam útvonalak (`/home/mailer4`, `/home/vocab`) és a `cuda` eszköz bele vannak égetve a kódba.
