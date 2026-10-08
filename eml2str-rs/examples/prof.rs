// fazisonkenti idomeres: cargo run --release --example prof -- ../Junk.mbox
use std::time::Instant;
fn main() {
    let data = std::fs::read(std::env::args().nth(1).unwrap()).unwrap();
    let mut msgs = Vec::new();
    let mut s = 0;
    for p in memchr::memmem::find_iter(&data, b"\nFrom ") {
        msgs.push(&data[s..p + 1]);
        s = p + 1;
    }
    msgs.push(&data[s..]);
    let msgs: Vec<&[u8]> = msgs.iter().map(|m| &m[memchr::memchr(b'\n', m).unwrap() + 1..]).collect();
    let rep = 10;
    let t = Instant::now();
    let mut leaves = Vec::new();
    for _ in 0..rep {
        leaves.clear();
        for m in &msgs {
            let e = eml2str::mime::parse_eml(m, 0, 0, m.len()).unwrap();
            fn walk(e: eml2str::mime::Eml, out: &mut Vec<(String, Option<String>, Vec<u8>)>) {
                if e.parts.is_empty() {
                    if e.ctyp.starts_with("text/") {
                        out.push((e.ctyp.clone(), e.charset.clone(), e.payload().unwrap_or_default()));
                    }
                } else {
                    for p in e.parts { walk(p, out) }
                }
            }
            walk(e, &mut leaves);
        }
    }
    println!("parse_eml:      {:.3} s", t.elapsed().as_secs_f64() / rep as f64);
    let t = Instant::now();
    for _ in 0..rep {
        for (c, cs, p) in &leaves { let _ = eml2str::decode_payload(p, c, cs.as_deref()); }
    }
    println!("decode_payload: {:.3} s  ({} part, {:.1} MB)", t.elapsed().as_secs_f64() / rep as f64, leaves.len(), leaves.iter().map(|l| l.2.len()).sum::<usize>() as f64 / 1e6);
    let t = Instant::now();
    for _ in 0..rep {
        for (c, _, p) in &leaves { if c == "text/html" { let _ = eml2str::html::html2text(p); } }
    }
    println!("  html2text:    {:.3} s", t.elapsed().as_secs_f64() / rep as f64);
    let t = Instant::now();
    for _ in 0..rep { for m in &msgs { let _ = eml2str::eml2str(m); } }
    println!("eml2str total:  {:.3} s", t.elapsed().as_secs_f64() / rep as f64);
}
