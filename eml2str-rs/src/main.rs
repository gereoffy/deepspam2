//! eml2str benchmark / osszehasonlito kimenet - a bench_py.py Rust parja.
//!   eml2str-bench Junk.mbox [out.bin] [--repeat N]
//! Kimenet levelenkent: <index> <subject hossz> <text hossz>\n<subject><text>\n  (kivetelnel a text "EXC:<Python tipusnev>")

use std::io::Write;
use std::time::Instant;

fn find(hay: &[u8], needle: &[u8], start: usize) -> Option<usize> {
    memchr::memmem::find(&hay[start..], needle).map(|i| i + start)
}

/// mbox szetvagasa a "From " soroknal (a From sor nem resze a levelnek) - azonos a bench_py.py split_mbox()-aval
fn split_mbox(data: &[u8]) -> Vec<&[u8]> {
    let mut msgs = Vec::new();
    let mut pos = if data.starts_with(b"From ") { Some(0) } else { find(data, b"\nFrom ", 0) };
    while let Some(mut p) = pos {
        if data.get(p) == Some(&b'\n') {
            p += 1;
        }
        let Some(nl) = find(data, b"\n", p) else { break };
        let start = nl + 1;
        let nxt = find(data, b"\nFrom ", start);
        msgs.push(&data[start..nxt.map_or(data.len(), |n| n + 1)]);
        pos = nxt;
    }
    msgs
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mut files = Vec::new();
    let mut repeat = 1usize;
    let mut i = 1;
    while i < args.len() {
        if args[i] == "--repeat" {
            repeat = args[i + 1].parse().expect("--repeat N");
            i += 2;
            continue;
        }
        files.push(args[i].clone());
        i += 1;
    }
    if files.is_empty() {
        eprintln!("hasznalat: eml2str-bench <mbox> [out.bin] [--repeat N]");
        std::process::exit(1);
    }
    let data = std::fs::read(&files[0]).expect("mbox olvasas");
    let msgs = split_mbox(&data);
    let nbytes: usize = msgs.iter().map(|m| m.len()).sum();

    let mut results = Vec::with_capacity(msgs.len());
    let t0 = Instant::now();
    for r in 0..repeat {
        results.clear();
        for m in &msgs {
            let res = std::panic::catch_unwind(|| eml2str::eml2str(m)).unwrap_or(Err("RustPanic"));
            if r + 1 == repeat {
                results.push(res);
            }
        }
    }
    let t = t0.elapsed().as_secs_f64() / repeat as f64;

    if let Some(out) = files.get(1) {
        let mut f = std::io::BufWriter::new(std::fs::File::create(out).expect("kimenet"));
        for (i, r) in results.iter().enumerate() {
            let exc;
            let (s, t) = match r {
                Ok((s, t)) => (s.as_str(), t.as_str()),
                Err(e) => {
                    exc = format!("EXC:{}", e);
                    ("", exc.as_str())
                }
            };
            write!(f, "{} {} {}\n", i, s.len(), t.len()).unwrap();
            f.write_all(s.as_bytes()).unwrap();
            f.write_all(t.as_bytes()).unwrap();
            f.write_all(b"\n").unwrap();
        }
    }
    println!(
        "rust: {} level, {:.1} MB, {:.3} s  ({:.3} ms/level, {:.1} MB/s)",
        msgs.len(),
        nbytes as f64 / 1e6,
        t,
        1000.0 * t / msgs.len().max(1) as f64,
        nbytes as f64 / 1e6 / t
    );
}
