//! RTF: parse_rtfhead, rtf_hex_encoding, rtf_fallback_text (a striprtf nelkuli durva kinyero), fix_surrogates

use crate::codec::{decode_name, lookup, Errors};
use crate::util::find;
use regex::Regex;
use std::collections::HashMap;
use std::sync::OnceLock;

/// Python kivetel, ami az eml2str-bol kifut (pl. chr() ValueError)
#[derive(Debug)]
pub struct PyErr(pub &'static str);

/// parse_rtfhead(): \ansicpgNNNN, kulonben charset, vegul cp1252 - mindig ASCII-kompatibilis, letezo kodlap
pub fn parse_rtfhead(data: &[u8], charset: Option<&str>) -> Result<String, PyErr> {
    let head = &data[..data.len().min(4096)];
    let mut ansi = None;
    let mut i = 0;
    while let Some(p) = find(head, b"\\ansicpg", i) {
        let s = p + 8;
        let mut e = s;
        while e < head.len() && e - s < 5 && head[e].is_ascii_digit() {
            e += 1;
        }
        if e > s {
            ansi = Some(format!("cp{}", std::str::from_utf8(&head[s..e]).unwrap()));
            break;
        }
        i = p + 1;
    }
    for cp in [ansi.as_deref(), charset, Some("cp1252")].into_iter().flatten() {
        if cp.contains('\0') {
            return Err(PyErr("ValueError"));
        }
        if !cp.is_empty() && lookup(cp).map_or(false, |c| c.rtf_ok) {
            return Ok(cp.to_string());
        }
    }
    Ok("cp1252".to_string())
}

/// rtf_hex_encoding()
pub fn rtf_hex_encoding(cp: &str) -> String {
    let l = cp.to_lowercase();
    if l == "utf-8" || l == "utf8" { "cp1252".to_string() } else { cp.to_string() }
}

const SKIP_GROUPS: &[&str] = &[
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "objdata", "header", "headerl", "headerr", "headerf",
    "footer", "footerl", "footerr", "footerf", "listtable", "listoverridetable", "rsidtbl", "generator", "themedata",
    "colorschememapping", "datastore", "latentstyles", "xmlnstbl", "fldinst", "shprslt", "sp", "sn", "sv",
];
const TRANSPARENT_GROUPS: &[&str] = &["shpinst", "do"];

fn fcharset_cp(n: i64) -> Option<&'static str> {
    Some(match n {
        0 => "cp1252", 77 => "mac-roman", 128 => "cp932", 129 => "cp949", 130 => "johab", 134 => "gbk", 136 => "big5",
        161 => "cp1253", 162 => "cp1254", 163 => "cp1258", 177 => "cp1255", 178 => "cp1256", 186 => "cp1257",
        204 => "cp1251", 222 => "cp874", 238 => "cp1250", 254 => "cp437", 255 => "cp850",
        _ => return None,
    })
}

fn special_word(w: &str) -> Option<&'static str> {
    Some(match w {
        "par" | "line" | "row" | "sect" | "page" => "\n",
        "tab" | "cell" => "\t",
        "emdash" => "\u{2014}", "endash" => "\u{2013}", "bullet" => "\u{2022}", "lquote" => "\u{2018}",
        "rquote" => "\u{2019}", "ldblquote" => "\u{201c}", "rdblquote" => "\u{201d}",
        "emspace" | "enspace" | "qmspace" => " ",
        _ => return None,
    })
}

fn special_sym(c: char) -> Option<char> {
    Some(match c {
        '\\' => '\\', '{' => '{', '}' => '}', '~' => '\u{a0}', '_' => '-', '\r' | '\n' => '\n',
        _ => return None,
    })
}

/// Python int() egy (unicode) decimalis szamjegy-sorozatra, elojellel
fn py_int(s: &str) -> Option<i64> {
    let (neg, d) = match s.strip_prefix('-') { Some(r) => (true, r), None => (false, s) };
    let mut v: i64 = 0;
    for c in d.chars() {
        let dv = c.to_digit(10).or_else(|| unicode_digit(c))? as i64;
        v = v.checked_mul(10)?.checked_add(dv)?;
    }
    Some(if neg { -v } else { v })
}

/// nem-ASCII unicode decimalis szamjegyek erteke (a Unicode Nd blokkok 10-es csoportokban vannak)
fn unicode_digit(c: char) -> Option<u32> {
    const ZEROS: &[u32] = &[0x660, 0x6f0, 0x7c0, 0x966, 0x9e6, 0xa66, 0xae6, 0xb66, 0xbe6, 0xc66, 0xce6, 0xd66, 0xde6,
        0xe50, 0xed0, 0xf20, 0x1040, 0x1090, 0x17e0, 0x1810, 0x1946, 0x19d0, 0x1a80, 0x1a90, 0x1b50, 0x1bb0, 0x1c40,
        0x1c50, 0xa620, 0xa8d0, 0xa900, 0xa9d0, 0xa9f0, 0xaa50, 0xabf0, 0xff10];
    let u = c as u32;
    ZEROS.iter().find(|&&z| u >= z && u < z + 10).map(|&z| u - z)
}

fn re_fonttbl() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"\\f(\d+)").unwrap())
}
fn re_fcharset() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"\\fcharset(\d+)").unwrap())
}

/// rtf_font_codepages(): {\fonttbl{\f0...\fcharset238 ...;}...} -> {"0": "cp1250", ...}
fn font_codepages(text: &str) -> HashMap<String, &'static str> {
    let mut fonts = HashMap::new();
    let Some(ms) = text.find("{\\fonttbl") else { return fonts };
    // text[ms:ms+1000000] kodpontokban
    let lim = match text[ms..].char_indices().nth(1_000_000) { Some((i, _)) => ms + i, None => text.len() };
    let b = text.as_bytes();
    let mut depth = 0i64;
    let mut end = text.len();
    let mut i = ms;
    while i < lim {
        match b[i] {
            b'\\' if i + 1 < lim && matches!(b[i + 1], b'\\' | b'{' | b'}') => i += 2,
            b'{' => { depth += 1; i += 1; }
            b'}' => {
                depth -= 1;
                i += 1;
                if depth == 0 { end = i; break; }
            }
            _ => i += 1,
        }
    }
    let tbl = &text[ms..end];
    let starts: Vec<_> = re_fonttbl().captures_iter(tbl).map(|c| (c.get(0).unwrap(), c.get(1).unwrap().as_str())).collect();
    for (k, (m, num)) in starts.iter().enumerate() {
        let seg_end = if k + 1 < starts.len() { starts[k + 1].0.start() } else { tbl.len() };
        let seg = &tbl[m.end()..seg_end.max(m.end())];
        if let Some(c) = re_fcharset().captures(seg) {
            if let Some(cp) = py_int(c.get(1).unwrap().as_str()).and_then(fcharset_cp) {
                fonts.insert(num.to_string(), cp);
            }
        }
    }
    fonts
}

enum Tok<'a> {
    Word(&'a str, Option<&'a str>),
    Hex(u8),
    Sym(char),
    Open,
    Close,
    Text(&'a str),
    Newline,
}

/// rtf_token_re.match(text, pos): (token, uj pozicio) - None, ha nincs illeszkedes
fn next_token(text: &str, pos: usize) -> Option<(Tok<'_>, usize)> {
    let b = text.as_bytes();
    let c = b[pos];
    match c {
        b'\\' => {
            let p1 = pos + 1;
            if p1 >= b.len() {
                return None;
            }
            if b[p1].is_ascii_alphabetic() {
                let mut e = p1;
                while e < b.len() && e - p1 < 32 && b[e].is_ascii_alphabetic() {
                    e += 1;
                }
                let word = &text[p1..e];
                // (-?\d{1,10})?  - \d unicode decimalis
                let mut arg = None;
                let mut k = e;
                if k < b.len() && b[k] == b'-' {
                    k += 1;
                }
                let ds = k;
                let mut nd = 0;
                for (ci, ch) in text[ds..].char_indices() {
                    if nd == 10 || !(ch.is_ascii_digit() || unicode_digit(ch).is_some()) {
                        k = ds + ci;
                        break;
                    }
                    nd += 1;
                    k = ds + ci + ch.len_utf8();
                }
                let mut e2 = e;
                if nd > 0 {
                    arg = Some(&text[e..k]);
                    e2 = k;
                }
                if e2 < b.len() && b[e2] == b' ' {
                    e2 += 1;
                }
                Some((Tok::Word(word, arg), e2))
            } else if b[p1] == b'\'' && p1 + 2 < b.len() && b[p1 + 1].is_ascii_hexdigit() && b[p1 + 2].is_ascii_hexdigit() {
                let h = u8::from_str_radix(&text[p1 + 1..p1 + 3], 16).unwrap();
                Some((Tok::Hex(h), p1 + 3))
            } else {
                let ch = text[p1..].chars().next().unwrap();
                Some((Tok::Sym(ch), p1 + ch.len_utf8()))
            }
        }
        b'{' => Some((Tok::Open, pos + 1)),
        b'}' => Some((Tok::Close, pos + 1)),
        b'\r' | b'\n' => {
            let mut e = pos;
            while e < b.len() && (b[e] == b'\r' || b[e] == b'\n') {
                e += 1;
            }
            Some((Tok::Newline, e))
        }
        _ => {
            let mut e = pos;
            while e < b.len() && !matches!(b[e], b'\\' | b'{' | b'}' | b'\r' | b'\n') {
                e += 1;
            }
            Some((Tok::Text(&text[pos..e]), e))
        }
    }
}

/// Python str, amiben lehetnek magukban allo surrogate-ok (a \uN-ekbol)
struct PyStr(Vec<u32>);
impl PyStr {
    fn push_str(&mut self, s: &str) {
        self.0.extend(s.chars().map(|c| c as u32));
    }
    /// fix_surrogates(): parok osszevonasa, a parositatlanok U+FFFD-re
    fn into_string(self) -> String {
        let v = self.0;
        let mut out = String::with_capacity(v.len());
        let mut i = 0;
        while i < v.len() {
            let c = v[i];
            if (0xd800..0xdc00).contains(&c) && i + 1 < v.len() && (0xdc00..0xe000).contains(&v[i + 1]) {
                out.push(char::from_u32(0x10000 + ((c - 0xd800) << 10) + (v[i + 1] - 0xdc00)).unwrap());
                i += 2;
                continue;
            }
            out.push(char::from_u32(c).unwrap_or('\u{fffd}'));
            i += 1;
        }
        out
    }
}

fn flush_hex(out: &mut PyStr, hexes: &mut Vec<u8>, fonts: &HashMap<String, &'static str>, font: &Option<String>, encoding: &str) -> Result<(), PyErr> {
    let cp = font.as_ref().and_then(|f| fonts.get(f).copied()).unwrap_or(encoding);
    // a Pythonban itt nincs try: pl. az idna codec UnicodeError-ja kifut az eml2str()-bol
    let s = decode_name(hexes, cp, Errors::Ignore).map_err(|_| PyErr("UnicodeError"))?;
    out.push_str(&s);
    hexes.clear();
    Ok(())
}

/// Python slice txt[k:] (k lehet negativ is) kodpontokban
fn py_slice_from(s: &str, k: i64) -> &str {
    let n = s.chars().count() as i64;
    let start = if k < 0 { (n + k).max(0) } else { k.min(n) };
    match s.char_indices().nth(start as usize) {
        Some((i, _)) => &s[i..],
        None => "",
    }
}

/// rtf_fallback_text() + fix_surrogates()
pub fn rtf_to_text(text: &str, encoding: &str) -> Result<String, PyErr> {
    let fonts = font_codepages(text);
    let mut out = PyStr(Vec::with_capacity(text.len() / 2));
    let mut hexes: Vec<u8> = Vec::new();
    let mut skip = false;
    let mut stack: Vec<(bool, i64, Option<String>)> = Vec::new();
    let mut group_start = false;
    let mut star = false;
    let mut ucskip: i64 = 1;
    let mut curskip: i64 = 0;
    let mut font: Option<String> = None;
    let mut deff: Option<String> = None;
    let mut pos = 0usize;
    let n = text.len();
    while pos < n {
        let Some((tok, np)) = next_token(text, pos) else { break };
        pos = np;
        let is_hex = matches!(tok, Tok::Hex(_));
        if !hexes.is_empty() && !is_hex {
            flush_hex(&mut out, &mut hexes, &fonts, &font, encoding)?;
        }
        let after_star = star;
        star = false;
        match tok {
            Tok::Open => {
                stack.push((skip, ucskip, font.clone()));
                group_start = true;
                continue;
            }
            Tok::Close => {
                if let Some((s, u, f)) = stack.pop() {
                    skip = s;
                    ucskip = u;
                    font = f;
                }
                group_start = false;
                continue;
            }
            _ => {}
        }
        let first = group_start;
        group_start = false;
        match tok {
            Tok::Word(word, arg) => {
                if word == "bin" && arg.is_some() {
                    let k = py_int(arg.unwrap()).unwrap_or(0).max(0);
                    // pos += k kodpontban
                    let mut p = pos;
                    for _ in 0..k {
                        match text[p..].chars().next() {
                            Some(c) => p += c.len_utf8(),
                            None => break,
                        }
                    }
                    pos = p;
                    continue;
                }
                if after_star && TRANSPARENT_GROUPS.contains(&word) {
                    skip = stack.last().map_or(false, |s| s.0);
                } else if first && SKIP_GROUPS.contains(&word) {
                    skip = true;
                } else if word == "f" && arg.is_some() {
                    font = arg.map(str::to_string);
                } else if word == "deff" && arg.is_some() {
                    deff = arg.map(str::to_string);
                    font = deff.clone();
                } else if word == "plain" {
                    font = deff.clone();
                } else if skip {
                } else if let Some(s) = special_word(word) {
                    out.push_str(s);
                } else if word == "uc" && arg.is_some() {
                    ucskip = py_int(arg.unwrap()).unwrap_or(0);
                } else if word == "u" && arg.is_some() {
                    let c = py_int(arg.unwrap()).unwrap_or(0);
                    let c = if c < 0 { c + 0x10000 } else { c };
                    if !(0..=0x10ffff).contains(&c) {
                        return Err(PyErr("ValueError"));
                    }
                    out.0.push(c as u32);
                    curskip = ucskip;
                }
            }
            Tok::Sym(sym) => {
                if sym == '*' && first {
                    skip = true;
                    star = true;
                    group_start = true;
                } else if !skip {
                    if let Some(c) = special_sym(sym) {
                        out.0.push(c as u32);
                    }
                }
            }
            Tok::Hex(h) => {
                if curskip != 0 {
                    curskip -= 1;
                } else if !skip {
                    hexes.push(h);
                }
            }
            Tok::Text(txt) => {
                if !skip {
                    let mut t = txt;
                    if curskip != 0 {
                        t = py_slice_from(txt, curskip);
                        curskip = 0;
                    }
                    out.push_str(t);
                }
            }
            _ => {}
        }
    }
    if !hexes.is_empty() {
        flush_hex(&mut out, &mut hexes, &fonts, &font, encoding)?;
    }
    Ok(out.into_string())
}
