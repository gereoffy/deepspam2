#!/bin/sh
# A Python-modul (eml2str_rs) forditasa es bemasolasa a deepspam2 konyvtarba (a deepspam4.py / eml2str.py melle).
# abi3: egyetlen .so minden CPython >= 3.9 verziohoz (3.14-hez is). A PyPy-hoz nem kell (az ugyis a tiszta Pythont futtatja).
#   ./build_python.sh [cel-konyvtar]
set -e
cd "$(dirname "$0")"
DEST="${1:-..}"
# macOS: a Python-szimbolumokat az interpreter adja futaskor (-undefined dynamic_lookup); Linuxon nem kell
if [ "$(uname)" = Darwin ]; then
  cargo rustc --release --lib --features python --crate-type cdylib -- -C link-arg=-undefined -C link-arg=dynamic_lookup
else
  cargo rustc --release --lib --features python --crate-type cdylib
fi
cp target/release/libeml2str.dylib "$DEST/eml2str_rs.abi3.so" 2>/dev/null || cp target/release/libeml2str.so "$DEST/eml2str_rs.abi3.so"
echo "kesz: $DEST/eml2str_rs.abi3.so"
