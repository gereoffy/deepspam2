//! html.unescape (Python stdlib), html2text, parse_htmlhead

use crate::codec::{decode_utf8, Errors};
use crate::tables;
use crate::util::*;
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

struct HtmlTables {
    html5: HashMap<&'static str, &'static str>,
    invalid_charrefs: HashMap<u32, &'static str>,
    invalid_codepoints: HashSet<u32>,
}

fn tbl() -> &'static HtmlTables {
    static T: OnceLock<HtmlTables> = OnceLock::new();
    T.get_or_init(|| HtmlTables {
        html5: tables::HTML5.iter().copied().collect(),
        invalid_charrefs: tables::HTML_INVALID_CHARREFS.iter().copied().collect(),
        invalid_codepoints: tables::HTML_INVALID_CODEPOINTS.iter().copied().collect(),
    })
}

/// html.unescape() - a Python 3.9 implementacio pontos megfeleloje
pub fn unescape(s: &str) -> String {
    if !s.contains('&') {
        return s.to_string();
    }
    let t = tbl();
    let b = s.as_bytes();
    let mut out = String::with_capacity(s.len());
    let mut last = 0; // az utolso, mar kiirt pozicio utan
    let mut i = 0;
    while let Some(amp) = find(b, b"&", i) {
        let j = amp + 1;
        // _charref = &(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\f <&#;]{1,32};?)
        let mut end = None; // a match vege (byte index)
        let mut repl = String::new();
        if j < b.len() && b[j] == b'#' {
            let (hex, ds) = if j + 1 < b.len() && b[j + 1].is_ascii_digit() {
                (false, j + 1)
            } else if j + 2 < b.len() && (b[j + 1] == b'x' || b[j + 1] == b'X') && b[j + 2].is_ascii_hexdigit() {
                (true, j + 2)
            } else {
                (false, usize::MAX)
            };
            if ds != usize::MAX {
                let mut k = ds;
                while k < b.len() && (if hex { b[k].is_ascii_hexdigit() } else { b[k].is_ascii_digit() }) {
                    k += 1;
                }
                let digits = &s[ds..k];
                let e = if k < b.len() && b[k] == b';' { k + 1 } else { k };
                end = Some(e);
                // int(...) - tulcsordulas: biztosan > 0x10FFFF
                let num: u64 = {
                    let d = digits.trim_start_matches('0');
                    if d.len() > 10 { u64::MAX } else if d.is_empty() { 0 } else { u64::from_str_radix(d, if hex { 16 } else { 10 }).unwrap_or(u64::MAX) }
                };
                if num <= u32::MAX as u64 && t.invalid_charrefs.contains_key(&(num as u32)) {
                    repl.push_str(t.invalid_charrefs[&(num as u32)]);
                } else if (0xd800..=0xdfff).contains(&num) || num > 0x10ffff {
                    repl.push('\u{fffd}');
                } else if t.invalid_codepoints.contains(&(num as u32)) {
                } else {
                    repl.push(char::from_u32(num as u32).unwrap());
                }
            }
        } else {
            // nevesitett: [^\t\n\f <&#;]{1,32};?
            let mut k = j;
            let mut n = 0;
            for (ci, c) in s[j..].char_indices() {
                if n == 32 || matches!(c, '\t' | '\n' | '\x0c' | ' ' | '<' | '&' | '#' | ';') {
                    k = j + ci;
                    break;
                }
                n += 1;
                k = j + ci + c.len_utf8();
            }
            if n > 0 {
                let e = if k < b.len() && b[k] == b';' { k + 1 } else { k };
                end = Some(e);
                let name = &s[j..e];
                if let Some(v) = t.html5.get(name) {
                    repl.push_str(v);
                } else {
                    // a leghosszabb illeszkedo nev (x = len-1 .. 2)
                    let idx: Vec<usize> = name.char_indices().map(|(i, _)| i).collect();
                    let mut found = false;
                    for x in (2..idx.len()).rev() {
                        if let Some(v) = t.html5.get(&name[..idx[x]]) {
                            repl.push_str(v);
                            repl.push_str(&name[idx[x]..]);
                            found = true;
                            break;
                        }
                    }
                    if !found {
                        repl.push('&');
                        repl.push_str(name);
                    }
                }
            }
        }
        match end {
            Some(e) => {
                out.push_str(&s[last..amp]);
                out.push_str(&repl);
                last = e;
                i = e;
            }
            None => i = amp + 1,
        }
    }
    out.push_str(&s[last..]);
    out
}

const LINK_ATTRS: &[(&[u8], &[u8])] = &[
    (b"a", b"href"),
    (b"area", b"href"),
    (b"base", b"href"),
    (b"link", b"href"),
    (b"iframe", b"src"),
    (b"frame", b"src"),
    (b"form", b"action"),
];

#[inline]
fn is_bword(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b == b'_'
}

/// html_extract_attr(): (?<![\w-])ATTR\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))  IGNORECASE, search
pub fn html_extract_attr(rawtag: &[u8], attr: &[u8]) -> Option<String> {
    let n = rawtag.len();
    let al = attr.len();
    let mut i = 0;
    while i + al <= n {
        if rawtag[i..i + al].eq_ignore_ascii_case(attr) && (i == 0 || !(is_bword(rawtag[i - 1]) || rawtag[i - 1] == b'-')) {
            let mut k = i + al;
            while k < n && is_bws(rawtag[k]) {
                k += 1;
            }
            if k < n && rawtag[k] == b'=' {
                k += 1;
                while k < n && is_bws(rawtag[k]) {
                    k += 1;
                }
                let mut val: Option<&[u8]> = None;
                if k < n && (rawtag[k] == b'"' || rawtag[k] == b'\'') {
                    if let Some(e) = find(rawtag, &[rawtag[k]], k + 1) {
                        val = Some(&rawtag[k + 1..e]);
                    }
                }
                if val.is_none() {
                    let mut e = k;
                    while e < n && !is_bws(rawtag[e]) && rawtag[e] != b'>' {
                        e += 1;
                    }
                    if e > k {
                        val = Some(&rawtag[k..e]);
                    }
                }
                if let Some(v) = val {
                    return Some(py_strip(&unescape(&decode_utf8(v, Errors::Mixed))).to_string());
                }
            }
        }
        i += 1;
    }
    None
}

/// parse_htmlhead(): <meta ... charset=XXX> a <body> elotti reszben
pub fn parse_htmlhead(data: &[u8], charset: Option<String>) -> Option<String> {
    for ret in data.split(|&b| b == b'<') {
        let tag = match ret.iter().position(|&b| b == b'>') {
            Some(p) => &ret[..p],
            None => ret,
        };
        if tag.len() < 4 || !tag[..4].eq_ignore_ascii_case(b"meta") {
            continue;
        }
        let tag = blower(tag);
        if let Some(p) = find(&tag, b"charset=", 0) {
            let mut cs = String::new();
            for &c in &tag[p + 8..] {
                if c <= 32 {
                    continue;
                }
                if c == 34 || c == 39 {
                    if !cs.is_empty() {
                        break;
                    }
                    continue;
                }
                if !(c == b'_' || c == b'-' || c.is_ascii_digit() || c.is_ascii_lowercase()) {
                    break;
                }
                cs.push(c as char);
            }
            if !cs.is_empty() {
                return Some(cs);
            }
        }
    }
    charset
}

/// tag_type(): (-1=endtag 0=selfclosing 1=nyito, nev)
fn tag_type(tag: &[u8]) -> (i32, &[u8]) {
    if tag.first() == Some(&b'!') {
        return (0, b"!");
    }
    if tag.first() == Some(&b'?') {
        return (0, b"?");
    }
    let mut closing = false;
    let mut ns = 0;
    let mut ne = 0; // a nev: tag[ns..ne]
    let mut started = false;
    for (i, &c) in tag.iter().enumerate() {
        if c == 47 {
            if started {
                break;
            }
            closing = true;
            continue;
        }
        if c <= 32 {
            if !started {
                continue;
            }
            break;
        }
        if !(97..=122).contains(&c) {
            break;
        }
        if !started {
            started = true;
            ns = i;
        }
        ne = i + 1;
    }
    // a Python a nevet karakterenkent gyujti: a nev nem feltetlenul folytonos? de: a nev kozben barmilyen mas
    // karakter break-et okoz, igy folytonos
    let name = &tag[ns..ne];
    if matches!(name, b"br" | b"area" | b"base" | b"meta" | b"col" | b"embed" | b"hr" | b"img" | b"input" | b"link" | b"param" | b"source" | b"track" | b"wbr") {
        return (0, name);
    }
    if closing {
        return (-1, name);
    }
    if tag.last() == Some(&b'/') {
        return (0, name);
    }
    (1, name)
}

/// a tag vege ('>' utan) q-tol, a HTML5 tokenizer szerint - az eml2str.py TAG_END_RE / html2text ciklusa:
/// whitespace: tab, LF, FF, CR, szokoz; a tag- es attributumnevben levo '=' es idezojel nem nyit semmit; az '=' utan
/// (whitespace utan) "idezett", 'idezett' vagy idezojel nelkuli ertek; lezaratlan idezet / '>' hianya: a data vege
#[inline]
fn tag_end(data: &[u8], mut q: usize) -> usize {
    #[derive(PartialEq)]
    enum St {
        TagName,
        BeforeName,
        Name,
        AfterName,
        BeforeValue,
        Unquoted,
    }
    let n = data.len();
    let mut st = St::TagName;
    while q < n {
        let c = data[q];
        q += 1;
        if c == b'>' {
            return q;
        }
        let ws = matches!(c, b' ' | b'\t' | b'\n' | b'\r' | 0x0c);
        st = match st {
            St::TagName if ws || c == b'/' => St::BeforeName,
            St::BeforeName if !(ws || c == b'/') => St::Name,
            St::Name if c == b'=' => St::BeforeValue,
            St::Name if ws => St::AfterName,
            St::Name if c == b'/' => St::BeforeName,
            St::AfterName if c == b'=' => St::BeforeValue,
            St::AfterName if c == b'/' => St::BeforeName,
            St::AfterName if !ws => St::Name,
            St::BeforeValue if c == b'"' || c == b'\'' => match memchr::memchr(c, &data[q..]) {
                Some(e) => {
                    q += e + 1;
                    St::BeforeName // idezet vege, johet a kovetkezo attributum
                }
                None => return n,
            },
            St::BeforeValue if !ws => St::Unquoted,
            St::Unquoted if ws => St::BeforeName,
            other => other,
        };
    }
    n
}

/// html2text() (debug=False valtozat)
pub fn html2text(data: &[u8]) -> Vec<u8> {
    let n = data.len();
    let Some(mut p) = find(data, b"<", 0) else { return data.to_vec() };
    let mut text: Vec<u8> = Vec::with_capacity(n / 2);
    text.extend_from_slice(&data[..p]);
    let mut tlen = 0usize;
    let mut urls: Vec<String> = Vec::new();
    let mut tagbuf: Vec<u8> = Vec::new();

    while p < n {
        let mut q = p + 1;
        if data[p..].starts_with(b"<!--") {
            q = find(data, b"-->", p).unwrap_or(p + 1);
        }
        let c = data.get(p + 1).copied();
        if c == Some(b'!') || c == Some(b'?') || (c == Some(b'/') && !data.get(p + 2).is_some_and(|b| b.is_ascii_alphabetic())) {
            // <!...>, <?...>, </ + nem betu: (bogus) comment, az elso '>'-ig, idezojelektol fuggetlenul
            q = find(data, b">", q).map_or(n, |e| e + 1);
        } else {
            q = tag_end(data, q);
        }
        let rawtag: &[u8] = if q >= 1 && q - 1 > p + 1 { &data[p + 1..q - 1] } else { b"" };
        tagbuf.clear();
        tagbuf.extend(rawtag.iter().map(|b| b.to_ascii_lowercase()));
        let tag = &tagbuf[..];
        let (tt, ttag) = tag_type(tag);
        let ttag = ttag.to_vec();
        let in_block = tt > 0 && matches!(ttag.as_slice(), b"style" | b"script" | b"title" | b"svg" | b"annotation");

        if tt >= 0 {
            if let Some(&(_, attr)) = LINK_ATTRS.iter().find(|(t, _)| *t == ttag.as_slice()) {
                if let Some(url) = html_extract_attr(rawtag, attr) {
                    if !url.is_empty() {
                        urls.push(url);
                    }
                }
            }
        }

        // a kovetkezo tag
        let mut np = find(data, b"<", q);
        loop {
            let Some(x) = np else { break };
            if x + 2 >= n {
                np = None;
                break;
            }
            let mut x = x;
            if in_block {
                let el = 2 + ttag.len();
                let end = (x + el).min(n);
                let cand = &data[x..end];
                if cand.len() == el && cand[0] == b'<' && cand[1] == b'/' && cand[2..].eq_ignore_ascii_case(&ttag) {
                    break;
                }
                if data[x..].starts_with(b"<![CDATA[") {
                    if let Some(pp) = find(data, b"]]>", x) {
                        if pp > 0 {
                            x = pp;
                        }
                    }
                }
            } else {
                let c = data[x + 1];
                if c == 47 || c == 33 || c.is_ascii_alphabetic() || c == 63 {
                    break;
                }
            }
            np = find(data, b"<", x + 1);
        }
        p = np.unwrap_or(n);

        if in_block {
            continue;
        }

        let txt = &data[q.min(p)..p];

        if contains(tag, b"style") {
            // minden whitespace torlese (tag.translate(None, b' \t\n\r\x0b\x0c')): display : none, display:\tnone, es a
            // sortoressel szettort stilus is (a Postfix pl. 990 karakternel CRLF+szokozzel tordel: font-s\n ize:1px)
            let tag2: Vec<u8> = tag.iter().copied().filter(|&b| !is_bws(b)).collect();
            if contains(&tag2, b"display:none")
                || contains(&tag2, b"font-size:0p")
                || contains(&tag2, b"font-size:1p")
                || contains(&tag2, b"max-height:0p")
                || contains(&tag2, b"mso-hide:all")
                || opacity_hidden(&tag2)
            {
                if contains(&tag2, b"signedadaptivecard") {
                    continue;
                }
                if contains(&tag2, b"display:none") && tlen == 0 && bstrip(txt).len() >= 3 {
                    text.push(b'[');
                    text.extend_from_slice(txt);
                    text.extend_from_slice(b"] ");
                }
                continue;
            }
        }

        if tag == b"div" || (tt >= 0 && matches!(ttag.as_slice(), b"p" | b"br" | b"tr")) {
            text.extend_from_slice(b"<BR>");
        } else if !matches!(ttag.as_slice(), b"span" | b"a" | b"b" | b"i" | b"u" | b"em" | b"strong" | b"abbr" | b"font" | b"!" | b"?") {
            // (a comment sem tesz szokozt: vi<!-- x -->agra = viagra)
            text.push(b' ');
        }
        text.extend_from_slice(txt);
        tlen += bstrip(txt).len();
    }

    let joined = bjoin_ws(&text);
    let mut out = Vec::with_capacity(joined.len() + 64);
    let mut first = true;
    let mut rest: &[u8] = &joined;
    loop {
        let (seg, next) = match find(rest, b"<BR>", 0) {
            Some(i) => (&rest[..i], Some(&rest[i + 4..])),
            None => (rest, None),
        };
        if !first {
            out.push(b'\n');
        }
        first = false;
        out.extend_from_slice(bstrip(seg));
        match next {
            Some(r) => rest = r,
            None => break,
        }
    }

    let mut seen = HashSet::new();
    for url in urls {
        if seen.insert(url.clone()) {
            out.extend_from_slice(b"\nURL: ");
            out.extend_from_slice(py_prefix(&url, 128).as_bytes());
        }
    }
    out
}

/// eml2str.opacity_hidden(): az (utolso) `opacity:` erteke < 0.5 (a `%` alak is); az ertek az
/// `opacity:([0-9]*\.?[0-9]+)(%?)` regex szerint
fn opacity_hidden(tag: &[u8]) -> bool {
    let mut last: Option<f64> = None;
    let mut i = 0;
    while let Some(p) = find(tag, b"opacity:", i) {
        let s = p + 8;
        i = s;
        let mut e = s;
        while e < tag.len() && tag[e].is_ascii_digit() {
            e += 1;
        }
        let mut end = e; // a szam vege
        if e < tag.len() && tag[e] == b'.' && e + 1 < tag.len() && tag[e + 1].is_ascii_digit() {
            end = e + 1;
            while end < tag.len() && tag[end].is_ascii_digit() {
                end += 1;
            }
        } else if e == s {
            continue; // nincs szam
        }
        let mut v: f64 = std::str::from_utf8(&tag[s..end]).unwrap().parse().unwrap();
        if tag.get(end) == Some(&b'%') {
            v /= 100.0;
            end += 1;
        }
        last = Some(v);
        i = end;
    }
    last.is_some_and(|v| v < 0.5)
}

/// bytes.replace(a, b)
pub fn replace(s: &[u8], a: &[u8], b: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(s.len());
    let mut i = 0;
    while let Some(p) = find(s, a, i) {
        out.extend_from_slice(&s[i..p]);
        out.extend_from_slice(b);
        i = p + a.len();
    }
    out.extend_from_slice(&s[i..]);
    out
}
