# DeepSpam milter Rustban

A `deepspam4.py` önálló CPU-s Rust változata. Az `eml2str-rs` parserre és a
`model-rs` modellkönyvtárra épül. A hálózati kiszolgálást Tokio végzi; a parser és
az NN korlátozott számú külön CPU-munkaszálon fut. A súlyok és a tokenizer
megosztottak, a számítási pufferek munkaszálanként újrahasználhatók.

## Fordítás és indítás

A projekt gyökérkönyvtárából:

```sh
cargo build --release --locked --manifest-path deepspam-rs/Cargo.toml
deepspam-rs/target/release/deepspam4 --model-dir model
```

Alapértelmezett cím: **127.0.0.1:1081**, mint a Python változatnál. Más címmel:

```sh
deepspam-rs/target/release/deepspam4 --model-dir model --listen 127.0.0.1:1082 --workers 4
```

Egyetlen levél vizsgálata, szerver és naplóírás nélkül:

```sh
deepspam-rs/target/release/deepspam4 --model-dir model --no-res-log --check Stephanie.eml
```

A futó programnak csak a bináris és a három eredeti modelladatfájl kell.
Az **eml2str fordítása** továbbra is Pythonból generálja a codec-táblákat;
Python futtatókörnyezet a kész milterhez nem kell. Nincs PyTorch, külső BLAS
vagy C++ SentencePiece a milterben.

## Működés és beállítások

A milter ugyanazokat a fejléc/törzs bájtokat állítja össze, mint a Python.
Minden sikeres vizsgálatkor `X-deepspam` fejlécet ad, majd elfogadja a levelet.
Megmaradt a Python `+0.1` eltolása, az egészre csonkolás, a szigorú küszöbök és
a `ham`, `maybeham`, `20ham`, `dunno`, `80spam`, `maybespam`, `spam`, `toosmall`
eredmények. Az NN- és tokenizerkompatibilitás részletei a `model-rs/README.md`-ben.

| Kapcsoló | Alapértelmezés |
|---|---|
| `--listen IP:PORT` | `127.0.0.1:1081` |
| `--model-dir DIR` | `model` |
| `--weights FILE` | `deepspam_weights.npz`, a modellkönyvtárhoz képest; abszolút út is lehet |
| `--workers N` | Az elérhető logikai CPU-k száma; legfeljebb ennyi parser/NN feladat fut egyszerre |
| `--cache-entries N` | `10000`; `0` kikapcsolja a cache-t |
| `--res-log FILE` | `deepspam2.res`, append mód, teljes tokenlista; cache-találatot nem naplóz újra |
| `--no-res-log` | Kikapcsolja a százalék/token naplót |
| `--max-message-bytes N` | `104857600` (100 MiB) |
| `--max-frame-bytes N` | `16777216` (16 MiB) |
| `--check FILE` | Egy levél fejlécértékének kiírása és kilépés |

A Python korlátlan cache-ével szemben itt beállítható méretű FIFO cache van.
Kulcsa továbbra is a parser eredeti subject/törzs kimenete. A két méretkorlát
a hibás vagy túlméretes bemenetek fogadását állítja meg; szükség esetén növelhető.
Hibás protokollcsomagra a kapcsolat lezárul. Feldolgozási hibára a szerver
`tempfail` választ küld, és nem ad osztályozási fejlécet. A naplóírás best effort.

A v2 opcióegyeztetés a másik fél által felkínált flag-eket veszi figyelembe.
Az abort, a több levél egy kapcsolaton, a makrók és a QUIT_NC kezelése külön
állapothoz kötött. SIGINT/SIGTERM lezárja a kiszolgálót; az elkezdett CPU-feladatok
még befejeződnek a folyamat kilépése előtt.

## Python/GPU változat és opcionális parser wrapper

**A meglévő `deepspam4.py`, `model/` és az `eml2str` Python wrapper változatlan.**
A PyTorch/GPU szerverek továbbra is használhatják az opcionális `eml2str_rs` modult:

```sh
cd eml2str-rs
./build_python.sh
```

A wrapper továbbra is a parser `python` Cargo feature-jével fordul. A natív
milter ezt a feature-t nem engedélyezi, nem fordít PyO3-at, és nem használja
vagy helyettesíti a telepített `.so` fájlt. A két változat egymás mellett marad.
A frissen külön lefordított wrapper ellenőrzése: hat levélen azonos Python
kimenet és 240 hívás nyolc szálon azonos eredménnyel.

## Ellenőrzés

```sh
cargo test --locked --manifest-path model-rs/Cargo.toml
cargo test --locked --manifest-path deepspam-rs/Cargo.toml
cargo test --locked --manifest-path eml2str-rs/Cargo.toml
python3 deepspam-rs/tools/test_milter.py
```

Az integrációs teszt ideiglenes localhost portra indítja a kész miltert,
ideiglenes naplót használ, majd leállítja. A fejlécértékeket a változatlan
`deepspam4.py`-ból kivett `do_eml()` és az eredeti Python modell alapján ellenőrzi.
Ehhez a fejlesztői teszthez Python/NumPy is kell.

2026-11-14: 20 osztályozás a Pythonéval azonos fejléccel; opcióegyeztetés,
darabolt frame-ek, makrók, abort, kapcsolatonként több levél, cache, napló,
párhuzamos kliensek és öt hibás bemeneti eset ellenőrizve.
