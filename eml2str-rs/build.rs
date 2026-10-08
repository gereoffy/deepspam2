//! A codec-tablak (tables.rs) generalasa forditaskor a gen_tables.py-val, abbol a Pythonbol, amelyikhez a modul
//! keszul: a charset-nevek feloldasa, a kodtablak es a HTML-entitasok igy pontosan az o viselkedeset kovetik.
//! Python: $PYO3_PYTHON, ha nincs, $PYTHON, kulonben python3.

use std::path::PathBuf;
use std::process::Command;

fn main() {
    let python = std::env::var("PYO3_PYTHON").or_else(|_| std::env::var("PYTHON")).unwrap_or_else(|_| "python3".into());
    let dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    let out = PathBuf::from(std::env::var("OUT_DIR").unwrap()).join("tables.rs");
    println!("cargo:rerun-if-changed=gen_tables.py");
    println!("cargo:rerun-if-changed=../eml2str.py");
    println!("cargo:rerun-if-env-changed=PYO3_PYTHON");
    println!("cargo:rerun-if-env-changed=PYTHON");
    let res = Command::new(&python)
        .arg(dir.join("gen_tables.py"))
        .output()
        .unwrap_or_else(|e| panic!("a gen_tables.py nem indithato ({python}): {e}"));
    if !res.status.success() {
        panic!("gen_tables.py hiba ({python}):\n{}", String::from_utf8_lossy(&res.stderr));
    }
    std::fs::write(&out, &res.stdout).expect("tables.rs irasa");
}
