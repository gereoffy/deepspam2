//! Charset-kezeles a Python `codecs` viselkedesenek megfeleloen: nevfeloldas (`codecs.lookup` + az eml2str sajat
//! aliasai), dekodolas `mixed` / `ignore` hibakezelovel, `safe_decode`, `ascii_compatible`, `fix_chars`.

use crate::tables;
use std::collections::HashMap;
use std::sync::OnceLock;

#[derive(Clone, Copy, Debug)]
pub enum Kind {
    Utf8,
    Utf8Sig,
    Latin1,
    Ascii,
    Utf16,
    Utf16Le,
    Utf16Be,
    Utf32,
    Utf32Le,
    Utf32Be,
    /// egybajtos kodtabla (index a tables::CHARMAPS-ben), 0xFFFE = nem definialt byte
    Charmap(usize),
    Utf7,
    /// CJK kodlap (gbk, big5, shift_jis, euc-jp, euc-kr, iso-2022-jp...) encoding_rs-sel. Ervenyes bemenetre a
    /// Pythonnal azonos; hibas byte-sorozatnal a hiba helye / hossza elterhet (WHATWG vs CPython dekoder)
    Mb(&'static encoding_rs::Encoding),
    /// nem szoveg-kodolas (base64, rot13...): a Python LookupError-t dob
    NotText,
    /// 'undefined': mindig UnicodeError
    Undefined,
    /// hz, johab, iso2022_kr, raw-unicode-escape...: nincs implementalva, UnicodeError-kent kezeljuk (-> utf-8 + mixed)
    Unsupported,
}

pub struct Codec {
    pub name: &'static str,
    pub kind: Kind,
    pub ascii_ok: bool,
    pub rtf_ok: bool,
}

/// A dekodolas hibakezeloje (Python `errors=` parameter)
#[derive(Clone, Copy)]
pub enum Errors {
    /// eml2str.mixed_decoder: a hibas byte -> invalid_charrefs / latin1
    Mixed,
    /// mixed_iso8859-2 / mixed_cp1250: a felso fel (A0..FF) a megadott kodlap szerint
    MixedCs(&'static [char; 96]),
    Ignore,
}

/// A dekodolas sikertelen (Python UnicodeError vagy LookupError)
#[derive(Debug)]
pub struct DecodeError;

struct Registry {
    codecs: Vec<Codec>,
    aliases: HashMap<&'static str, u16>,
    modules: HashMap<&'static str, u16>,
    custom: HashMap<&'static str, u16>,
    overrides: HashMap<&'static str, &'static str>,
    charrefs: [Option<&'static str>; 256],
    latin2_hi: [char; 96],
    cp1250_hi: [char; 96],
}

fn registry() -> &'static Registry {
    static R: OnceLock<Registry> = OnceLock::new();
    R.get_or_init(|| {
        let codecs: Vec<Codec> = tables::CODECS
            .iter()
            .map(|&(name, kind, ascii_ok, rtf_ok)| Codec { name, kind, ascii_ok, rtf_ok })
            .collect();
        let mut charrefs = [None; 256];
        for &(k, v) in tables::INVALID_CHARREFS {
            charrefs[k as usize] = Some(v);
        }
        let hi = |name: &str| -> [char; 96] {
            let c = codecs.iter().find(|c| c.name == name).expect(name);
            let Kind::Charmap(t) = c.kind else { panic!("{name}") };
            let mut out = ['\0'; 96];
            for (i, o) in out.iter_mut().enumerate() {
                *o = char::from_u32(tables::CHARMAPS[t][0xa0 + i]).unwrap();
            }
            out
        };
        let latin2_hi = hi("iso8859-2");
        let cp1250_hi = hi("cp1250");
        Registry {
            aliases: tables::ALIASES.iter().copied().collect(),
            modules: tables::MODULES.iter().copied().collect(),
            custom: tables::CUSTOM.iter().copied().collect(),
            overrides: tables::CHARSET_OVERRIDES.iter().copied().collect(),
            codecs,
            charrefs,
            latin2_hi,
            cp1250_hi,
        }
    })
}

/// CPython _Py_normalize_encoding(): kisbetu, a nem alfanumerikus (es nem '.') reszek egy '_'-ra, szelekrol levagva
fn normalize(name: &str) -> String {
    let mut out = String::with_capacity(name.len());
    let mut punct = false;
    for b in name.bytes() {
        if b.is_ascii_alphanumeric() || b == b'.' {
            if punct && !out.is_empty() {
                out.push('_');
            }
            out.push(b.to_ascii_lowercase() as char);
            punct = false;
        } else {
            punct = true;
        }
    }
    out
}

/// codecs.lookup(name) - None: LookupError
pub fn lookup(name: &str) -> Option<&'static Codec> {
    let r = registry();
    let k = normalize(name);
    let idx = r
        .aliases
        .get(k.as_str())
        .or_else(|| if k.contains('.') { r.aliases.get(k.replace('.', "_").as_str()) } else { None })
        .or_else(|| if !k.is_empty() && !k.contains('.') { r.modules.get(k.as_str()) } else { None })
        .or_else(|| r.custom.get(k.as_str()))?;
    Some(&r.codecs[*idx as usize])
}

/// eml2str.charset_name()
pub fn charset_name(cset: &str) -> String {
    let r = registry();
    match r.overrides.get(cset.to_lowercase().as_str()) {
        Some(v) => v.to_string(),
        None => cset.to_string(),
    }
}

/// eml2str.ascii_compatible()
pub fn ascii_compatible(cs: &str) -> bool {
    lookup(cs).map_or(true, |c| c.ascii_ok)
}

/// a mixed hibakezelo kimenete egy byte-ra
#[inline]
pub(crate) fn handler_push(out: &mut String, b: u8, errors: Errors) {
    let r = registry();
    match errors {
        Errors::Ignore => {}
        Errors::MixedCs(tbl) if b >= 0xa0 => out.push(tbl[(b - 0xa0) as usize]),
        _ => match r.charrefs[b as usize] {
            Some(s) => out.push_str(s),
            None => out.push(b as char),
        },
    }
}

pub fn mixed_latin2() -> Errors {
    Errors::MixedCs(&registry().latin2_hi)
}
pub fn mixed_cp1250() -> Errors {
    Errors::MixedCs(&registry().cp1250_hi)
}

/// data.decode("utf-8", errors) - a hibas szekvencia elso byte-ja a handler-hez, folytatas a kovetkezo byte-tol
/// (ignore eseten a teljes hibas szekvencia atugrasa, mint a Pythonban)
pub fn decode_utf8(data: &[u8], errors: Errors) -> String {
    let mut out = String::with_capacity(data.len() + 16);
    let mut rest = data;
    loop {
        match std::str::from_utf8(rest) {
            Ok(s) => {
                out.push_str(s);
                return out;
            }
            Err(e) => {
                let good = e.valid_up_to();
                out.push_str(unsafe { std::str::from_utf8_unchecked(&rest[..good]) });
                let b = rest[good];
                match errors {
                    Errors::Ignore => {
                        let n = e.error_len().unwrap_or(rest.len() - good);
                        rest = &rest[good + n..];
                    }
                    _ => {
                        handler_push(&mut out, b, errors);
                        rest = &rest[good + 1..];
                    }
                }
            }
        }
    }
}

#[inline]
fn push_cp(out: &mut String, cp: u32) {
    out.push(char::from_u32(cp).unwrap_or('\u{fffd}'));
}

/// CPython UTF-16 dekoder hibahatarai (start / end), a handler a start+1-tol folytat (ignore: end-tol)
fn decode_utf16(data: &[u8], le: bool, errors: Errors) -> String {
    let n = data.len();
    let mut out = String::with_capacity(n / 2 + 4);
    let unit = |i: usize| -> u16 {
        if le { u16::from_le_bytes([data[i], data[i + 1]]) } else { u16::from_be_bytes([data[i], data[i + 1]]) }
    };
    let mut i = 0;
    while i < n {
        let (start, end);
        if i + 1 >= n {
            // truncated data
            start = i;
            end = n;
        } else {
            let u = unit(i);
            if !(0xd800..0xe000).contains(&u) {
                push_cp(&mut out, u as u32);
                i += 2;
                continue;
            }
            if u >= 0xdc00 {
                // illegal encoding (magaban allo low surrogate)
                start = i;
                end = i + 2;
            } else if i + 3 >= n {
                // unexpected end of data
                start = i;
                end = n;
            } else {
                let u2 = unit(i + 2);
                if (0xdc00..0xe000).contains(&u2) {
                    push_cp(&mut out, 0x10000 + (((u as u32) - 0xd800) << 10) + ((u2 as u32) - 0xdc00));
                    i += 4;
                    continue;
                }
                // illegal UTF-16 surrogate
                start = i;
                end = i + 2;
            }
        }
        match errors {
            Errors::Ignore => i = end,
            _ => {
                handler_push(&mut out, data[start], errors);
                i = start + 1;
            }
        }
    }
    out
}

fn decode_utf32(data: &[u8], le: bool, errors: Errors) -> String {
    let n = data.len();
    let mut out = String::with_capacity(n / 4 + 4);
    let mut i = 0;
    while i < n {
        let (start, end);
        if i + 4 > n {
            start = i;
            end = n;
        } else {
            let b = [data[i], data[i + 1], data[i + 2], data[i + 3]];
            let cp = if le { u32::from_le_bytes(b) } else { u32::from_be_bytes(b) };
            if let Some(c) = char::from_u32(cp) {
                out.push(c);
                i += 4;
                continue;
            }
            start = i;
            end = i + 4;
        }
        match errors {
            Errors::Ignore => i = end,
            _ => {
                handler_push(&mut out, data[start], errors);
                i = start + 1;
            }
        }
    }
    out
}

/// CJK kodlap encoding_rs-sel; hibanal (mint a Python 'mixed' kezelonel) a hibas szekvencia elso byte-ja a
/// handler-hez, es a dekodolas a kovetkezo byte-tol ujraindul ('ignore': a hibas szekvencia atugrasa)
fn decode_mb(data: &[u8], enc: &'static encoding_rs::Encoding, errors: Errors) -> String {
    use encoding_rs::DecoderResult;
    let mut out = String::with_capacity(data.len() * 3 / 2 + 16);
    let mut pos = 0;
    while pos < data.len() {
        let mut dec = enc.new_decoder_without_bom_handling();
        let src = &data[pos..];
        let mut read_total = 0;
        loop {
            let need = dec.max_utf8_buffer_length_without_replacement(src.len() - read_total).unwrap_or(1 << 20);
            out.reserve(need);
            let (res, read) = dec.decode_to_string_without_replacement(&src[read_total..], &mut out, true);
            read_total += read;
            match res {
                DecoderResult::InputEmpty => {
                    pos = data.len();
                    break;
                }
                DecoderResult::OutputFull => continue,
                DecoderResult::Malformed(bad, extra) => {
                    let bad_start = pos + read_total - extra as usize - bad as usize;
                    match errors {
                        Errors::Ignore => pos = bad_start + (bad as usize).max(1),
                        _ => {
                            handler_push(&mut out, data[bad_start], errors);
                            pos = bad_start + 1;
                        }
                    }
                    break;
                }
            }
        }
    }
    out
}

/// data.decode(codec, errors)
pub fn decode(data: &[u8], codec: &Codec, errors: Errors) -> Result<String, DecodeError> {
    Ok(match codec.kind {
        Kind::Utf8 => decode_utf8(data, errors),
        Kind::Utf8Sig => decode_utf8(data.strip_prefix(b"\xef\xbb\xbf").unwrap_or(data), errors),
        Kind::Latin1 => data.iter().map(|&b| b as char).collect(),
        Kind::Ascii => {
            let mut out = String::with_capacity(data.len());
            for &b in data {
                if b < 0x80 {
                    out.push(b as char)
                } else {
                    handler_push(&mut out, b, errors)
                }
            }
            out
        }
        Kind::Utf16 => {
            if let Some(d) = data.strip_prefix(b"\xff\xfe") {
                decode_utf16(d, true, errors)
            } else if let Some(d) = data.strip_prefix(b"\xfe\xff") {
                decode_utf16(d, false, errors)
            } else {
                decode_utf16(data, true, errors)
            }
        }
        Kind::Utf16Le => decode_utf16(data, true, errors),
        Kind::Utf16Be => decode_utf16(data, false, errors),
        Kind::Utf32 => {
            if let Some(d) = data.strip_prefix(b"\xff\xfe\x00\x00") {
                decode_utf32(d, true, errors)
            } else if let Some(d) = data.strip_prefix(b"\x00\x00\xfe\xff") {
                decode_utf32(d, false, errors)
            } else {
                decode_utf32(data, true, errors)
            }
        }
        Kind::Utf32Le => decode_utf32(data, true, errors),
        Kind::Utf32Be => decode_utf32(data, false, errors),
        Kind::Charmap(t) => {
            let tbl = &tables::CHARMAPS[t];
            let mut out = String::with_capacity(data.len() + data.len() / 2);
            for &b in data {
                let c = tbl[b as usize];
                if c == 0xfffe {
                    handler_push(&mut out, b, errors)
                } else {
                    push_cp(&mut out, c)
                }
            }
            out
        }
        Kind::Mb(enc) => decode_mb(data, enc, errors),
        Kind::Utf7 => crate::utf7::decode_utf7(data, errors),
        Kind::NotText | Kind::Undefined | Kind::Unsupported => return Err(DecodeError),
    })
}

/// decode a codec nevevel (LookupError -> Err)
pub fn decode_name(data: &[u8], name: &str, errors: Errors) -> Result<String, DecodeError> {
    decode(data, lookup(name).ok_or(DecodeError)?, errors)
}

/// eml2str.is_utf8_mixed(): legalabb n db utf-8 kodolt magyar ekezetes betu
pub fn is_utf8_mixed(data: &[u8], n: usize) -> bool {
    let mut cnt = 0;
    let mut i = 0;
    while i + 1 < data.len() {
        let hit = match data[i] {
            0xc3 => matches!(data[i + 1], 0x81 | 0x89 | 0x8d | 0x93 | 0x96 | 0x9a | 0x9c | 0xa1 | 0xa9 | 0xad | 0xb3 | 0xb6 | 0xba | 0xbc),
            0xc5 => matches!(data[i + 1], 0x90 | 0x91 | 0xb0 | 0xb1),
            _ => false,
        };
        if hit {
            cnt += 1;
            if cnt >= n {
                return true;
            }
            i += 2;
        } else {
            i += 1;
        }
    }
    false
}

/// eml2str.safe_decode()
pub fn safe_decode(data: &[u8], cs: Option<&str>, errors: Errors) -> String {
    let name = match cs {
        Some(s) if !s.is_empty() => s,
        _ => "utf-8",
    };
    let Some(codec) = lookup(name) else { return decode_utf8(data, Errors::Mixed) };
    if matches!(codec.name, "cp1252" | "iso8859-1" | "iso8859-2" | "cp1250") {
        if let Ok(s) = std::str::from_utf8(data) {
            return s.to_string();
        }
        if is_utf8_mixed(data, 4) {
            let h = match codec.name {
                "iso8859-2" => mixed_latin2(),
                "cp1250" => mixed_cp1250(),
                _ => Errors::Mixed,
            };
            return decode_utf8(data, h);
        }
    }
    decode(data, codec, errors).unwrap_or_else(|_| decode_utf8(data, Errors::Mixed))
}

/// eml2str.fix_chars(): invalid_charrefs csere a dekodolt szovegen
pub fn fix_chars(s: String) -> String {
    let r = registry();
    // gyors ut: nincs csereolando karakter
    if !s.chars().any(|c| (c as u32) < 256 && r.charrefs[c as usize].is_some()) {
        return s;
    }
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match if (c as u32) < 256 { r.charrefs[c as usize] } else { None } {
            Some(v) => out.push_str(v),
            None => out.push(c),
        }
    }
    out
}
