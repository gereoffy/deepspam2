# DeepSpam modell Rustban

A `model/` Python kódjának CPU-s Rust változata. A meglévő `spm6.model`,
`unicodes6x.map` és `deepspam_weights.npz` fájlokat közvetlenül használja;
nincs modellkonverzió, újratanítás, Python, C++ SentencePiece vagy NN framework
a futó programban. A Python modell és a GPU-s telepítés változatlanul használható.

A következő parancsok a projekt gyökérkönyvtárából futnak:

```sh
cargo build --release --locked --manifest-path model-rs/Cargo.toml
printf '%s\n' 'März Straße Árvíztűrő tükörfúrógép' | model-rs/target/release/deepspam-model score
```

Az alapértelmezett modellkönyvtár `model`; a `--model-dir DIR` és `--weights FILE`
kapcsolóval változtatható. Az abszolút súlyfájlnév is használható.

## Könyvtári API

```rust
use deepspam_model::{DeepSpam, Workspace};

let model = DeepSpam::load("model")?;
let mut workspace = Workspace::default();
let result = model.predict_mail("Subject", "Body text", &mut workspace)?;
println!("{}%", result.percent);
```

A modell változatlan és szálbiztos, `Arc<DeepSpam>`-ként megosztható. Minden
egyidejű számításhoz saját `Workspace` kell. A pufferek hívások között
újrahasználhatók; az embedding 256 MiB-os táblájából egy megosztott példány elég.

## Megvalósítás

- `preprocess.rs`: cirill hasonmásbetűk, NFKC, saját karaktertérkép, Python-féle
  whitespace-kezelés, a Python sorrendjében. A subject és body elválasztója `|\n`;
  üres subject esetén csak a body kerül feldolgozásra.
- `lib.rs`: `sentencepiece-rust` 0.1.1, közvetlen `.model` betöltéssel.
  A teljes szöveg tokenizálása megelőzi a vágást. A tokenizer ritkán választhat
  másik optimális szegmentálást, mint a Python vagy a korábbi C++ implementáció.
  Üres bemenetre a crate üres listát ad, a saját Python tokenizáló dummy szóközt.
- `nn.rs`: `float32` embedding, négy valid Conv1D, ReLU, global max pooling,
  összefűzés, dense + ReLU, dense. Az `ndarray` alapértelmezett Rust
  `matrixmultiply` hátterét használja, külső BLAS nélkül. A konvolúciós ablakok
  átmeneti munkapufferbe kerülnek, majd mátrixszorzás fut rajtuk.
- A kimenet a két sigmoid normalizált százaléka, a Python képletével.
- Az `ndarray-npy` a jelenlegi, tömörítetlen NPZ-ben tárolt `float32` tömböket
  olvassa. A dimenziókat és a tokenazonosítókat ellenőrzi.

Szándékosan megmaradt a `DeepSpam.__call__()` kétszeri előfeldolgozása és az,
hogy a minimumhossz ellenőrzése a 256 tokenes feltöltés **után** fut. Azonos
első/második előfeldolgozás esetén nem tokenizálunk kétszer. A napló a Python
`tokenized()` egyszeri előfeldolgozásához tartozó teljes tokenlistát kapja.

A `unicode-normalization` saját Unicode-adatverziót használ; a támogatott
karaktertérképen és a vizsgált leveleken az előfeldolgozás a Pythonnal egyezik.

## Diagnosztikai CLI

Minden parancs soronként olvas a standard bemenetről:

| Parancs | Kimenet |
|---|---|
| `preprocess` | Előfeldolgozott szöveg; nem tölt NN-súlyokat |
| `tokenize` | Szóközzel elválasztott tokenek; nem tölt NN-súlyokat |
| `score` | Százalék a teljes feldolgozási lánccal |
| `score-ids` | Bemenet: egész token-ID-k. Kimenet: százalék, logit0, logit1, tabulátorral elválasztva |

## Ellenőrzés

```sh
cargo test --locked --manifest-path model-rs/Cargo.toml
python3 model-rs/tools/compare_model.py --corpus deepspam2.res.xz --samples 1000
```

A Python/NumPy csak az összehasonlító fejlesztői eszközhöz kell. Az NN-ellenőrzés
azonos, a naplóból visszaállított token-ID-ket ad mindkét implementációnak, így
független a tokenizáló döntéseitől. A külön előfeldolgozási és teljes láncot
ellenőrző teszt ezután fut. A `--cases sampled.jsonl` korábban elmentett,
`text`, `pieces`, `score` mezőket tartalmazó mintát is fogad.

2026-11-14: 1000 véletlen valódi tokenlistán a legnagyobb NumPy–Rust
logiteltérés 0,00000287; a legnagyobb százalékeltérés **0,000046 százalékpont**.
1031 előfeldolgozási esetben nem volt eltérés. A teljes előfeldolgozás–SPM–NN
lánc további 1000 bemenetén mindegyik tokenlista egyezett, és a százalékeltérés
ott is legfeljebb 0,000046 volt. A kis determinisztikus NPZ-n futó
regressziós tesztek független skaláris konvolúcióval is ellenőrzik a rétegeket,
a padding nullázását, a puffer-újrahasználatot és a százalékképletet.

A régi `.res.xz` egész százaléka nem pontos lebegőpontos referencia: a mintában
999/1000 sor a `+0.1` eltolás utáni csonkolással egyezik. Egy sor a mentett
tokenek közvetlen NN-számításával mindkét implementációban eltér; visszaállított
szövegként, újratokenizálva mindkettő a naplóhoz illő eredményt ad. A port
numerikus referenciája ezért az aktuális Python NN azonos tokenbemenettel.
