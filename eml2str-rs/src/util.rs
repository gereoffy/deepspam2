//! Python bytes / str segedfuggvenyek pontos szemantikaval

use memchr::memmem;

/// bytes.find(needle, start) -> None ha nincs (Python -1)
#[inline]
pub fn find(hay: &[u8], needle: &[u8], start: usize) -> Option<usize> {
    if start > hay.len() {
        return None;
    }
    if needle.len() == 1 {
        return memchr::memchr(needle[0], &hay[start..]).map(|i| i + start);
    }
    memmem::find(&hay[start..], needle).map(|i| i + start)
}

#[inline]
pub fn contains(hay: &[u8], needle: &[u8]) -> bool {
    if hay.len() < 64 {
        // rovid haystack-nel (tag-ek) olcsobb, mint egy memmem Finder felepitese
        return needle.is_empty() || hay.windows(needle.len()).any(|w| w == needle);
    }
    memmem::find(hay, needle).is_some()
}

/// bytes.isspace() karakterkeszlete: space \t \n \r \x0b \x0c
#[inline]
pub fn is_bws(b: u8) -> bool {
    matches!(b, b' ' | b'\t' | b'\n' | b'\r' | 0x0b | 0x0c)
}

/// bytes.strip()
pub fn bstrip(s: &[u8]) -> &[u8] {
    let mut a = 0;
    let mut b = s.len();
    while a < b && is_bws(s[a]) {
        a += 1;
    }
    while b > a && is_bws(s[b - 1]) {
        b -= 1;
    }
    &s[a..b]
}

/// bytes.rstrip()
pub fn brstrip(s: &[u8]) -> &[u8] {
    let mut b = s.len();
    while b > 0 && is_bws(s[b - 1]) {
        b -= 1;
    }
    &s[..b]
}

/// bytes.lower()
pub fn blower(s: &[u8]) -> Vec<u8> {
    s.to_ascii_lowercase()
}

/// b' '.join(data.split())
pub fn bjoin_ws(s: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(s.len());
    for w in s.split(|&b| is_bws(b)).filter(|w| !w.is_empty()) {
        if !out.is_empty() {
            out.push(b' ');
        }
        out.extend_from_slice(w);
    }
    out
}

/// str.isspace() egy karakterre (Python definicio: \x1c-\x1f is whitespace)
#[inline]
pub fn py_isspace(c: char) -> bool {
    matches!(c, '\t' | '\n' | '\x0b' | '\x0c' | '\r' | '\x1c' | '\x1d' | '\x1e' | '\x1f' | ' ' | '\u{85}' | '\u{a0}'
        | '\u{1680}' | '\u{2000}'..='\u{200a}' | '\u{2028}' | '\u{2029}' | '\u{202f}' | '\u{205f}' | '\u{3000}')
}

/// str.strip()
pub fn py_strip(s: &str) -> &str {
    s.trim_matches(py_isspace)
}

/// len(str) - kodpontok szama
#[inline]
pub fn py_len(s: &str) -> usize {
    s.chars().count()
}

/// s[:n] kodpontokban
pub fn py_prefix(s: &str, n: usize) -> &str {
    match s.char_indices().nth(n) {
        Some((i, _)) => &s[..i],
        None => s,
    }
}
