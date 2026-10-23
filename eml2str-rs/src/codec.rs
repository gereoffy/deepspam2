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
    /// mixed_iso8859-2 / mixed_cp1250 / mixed_cp1251: a lo..FF byte-ok a megadott kodlap szerint (kodpontok, 0xFFFE = nem definialt)
    MixedCs(&'static [u32], u8),
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
    /// invalid_charrefs: a mixed hibakezelokhoz (byte -> karakter) es a fix_chars-hoz (kodpont -> csere), 0x100 alatt
    charrefs: [Option<&'static str>; 256],
    /// az invalid_charrefs 0x100 feletti bejegyzesei (lathatatlan karakterek stb.): csak a fix_chars hasznalja
    charrefs_hi: HashMap<u32, &'static str>,
    latin2_hi: [u32; 96],
    cp1250_hi: [u32; 96],
    cp1251_hi: [u32; 128],
}

fn registry() -> &'static Registry {
    static R: OnceLock<Registry> = OnceLock::new();
    R.get_or_init(|| {
        let codecs: Vec<Codec> = tables::CODECS
            .iter()
            .map(|&(name, kind, ascii_ok, rtf_ok)| Codec { name, kind, ascii_ok, rtf_ok })
            .collect();
        let mut charrefs = [None; 256];
        let mut charrefs_hi = HashMap::new();
        for &(k, v) in tables::INVALID_CHARREFS {
            if k < 256 {
                charrefs[k as usize] = Some(v);
            } else {
                charrefs_hi.insert(k, v);
            }
        }
        let hi = |name: &str, out: &mut [u32]| {
            let c = codecs.iter().find(|c| c.name == name).expect(name);
            let Kind::Charmap(t) = c.kind else { panic!("{name}") };
            let lo = 0x100 - out.len();
            for (i, o) in out.iter_mut().enumerate() {
                *o = tables::CHARMAPS[t][lo + i];
            }
        };
        let mut latin2_hi = [0u32; 96];
        let mut cp1250_hi = [0u32; 96];
        let mut cp1251_hi = [0u32; 128];
        hi("iso8859-2", &mut latin2_hi);
        hi("cp1250", &mut cp1250_hi);
        hi("cp1251", &mut cp1251_hi);
        Registry {
            aliases: tables::ALIASES.iter().copied().collect(),
            modules: tables::MODULES.iter().copied().collect(),
            custom: tables::CUSTOM.iter().copied().collect(),
            overrides: tables::CHARSET_OVERRIDES.iter().copied().collect(),
            codecs,
            charrefs,
            charrefs_hi,
            latin2_hi,
            cp1250_hi,
            cp1251_hi,
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
        Errors::MixedCs(tbl, lo) if b >= lo && tbl[(b - lo) as usize] != 0xfffe => push_cp(out, tbl[(b - lo) as usize]),
        _ => match r.charrefs[b as usize] {
            Some(s) => out.push_str(s),
            None => out.push(b as char),
        },
    }
}

pub fn mixed_latin2() -> Errors {
    Errors::MixedCs(&registry().latin2_hi, 0xa0)
}
pub fn mixed_cp1250() -> Errors {
    Errors::MixedCs(&registry().cp1250_hi, 0xa0)
}
pub fn mixed_cp1251() -> Errors {
    Errors::MixedCs(&registry().cp1251_hi, 0x80)
}

/// eml2str._cyrillic_like(): a C0-FF byte-ok tobbsege 3+ hosszu futamban all (cp1251 cirill szavak); latin szovegben az ekezetek
/// elszigeteltek vagy parosak, ervenyes utf-8-ban ket C0-FF byte nem allhat egymas mellett
fn cyrillic_like(data: &[u8]) -> bool {
    let (mut highs, mut runs, mut run) = (0usize, 0usize, 0usize);
    for &b in data.iter().chain(std::iter::once(&0u8)) {
        if b >= 0xc0 {
            run += 1;
        } else {
            highs += run;
            if run >= 3 {
                runs += run;
            }
            run = 0;
        }
    }
    highs > 0 && runs * 2 >= highs
}

/// eml2str.cesu8_pair(): CESU-8 / WTF-8 surrogate-par (ED A0..AF xx ED B0..BF xx) a pos-tol -> a teljes karakter (6 byte)
pub(crate) fn cesu8_pair(data: &[u8], pos: usize) -> Option<char> {
    let d = data.get(pos..pos + 6)?;
    if d[0] == 0xed && (0xa0..=0xaf).contains(&d[1]) && (0x80..=0xbf).contains(&d[2]) && d[3] == 0xed && (0xb0..=0xbf).contains(&d[4]) && (0x80..=0xbf).contains(&d[5]) {
        let hi = 0xd000 | ((d[1] as u32 & 0x3f) << 6) | (d[2] as u32 & 0x3f);
        let lo = 0xd000 | ((d[4] as u32 & 0x3f) << 6) | (d[5] as u32 & 0x3f);
        return char::from_u32(0x10000 + ((hi - 0xd800) << 10) + (lo - 0xdc00));
    }
    None
}

/// a mixed / mixed_* hibakezelo egy hibahelyen (Python: mixed_decoder / _mixed_factory handler): CESU-8 par -> a karakter es
/// 6 byte-tal tovabb, kulonben a hibas byte invalid_charrefs / latin1 szerint es 1 byte-tal tovabb. Visszaadja az uj poziciot.
pub(crate) fn handler_at(out: &mut String, data: &[u8], pos: usize, errors: Errors) -> usize {
    if !matches!(errors, Errors::Ignore) {
        if let Some(c) = cesu8_pair(data, pos) {
            out.push(c);
            return pos + 6;
        }
    }
    handler_push(out, data[pos], errors);
    pos + 1
}

/// eml2str.decode_utf8_cesu(): szigoru utf-8, de a CESU-8 surrogate-parokat elfogadja es osszevonja; None, ha mas hiba van
pub fn decode_utf8_cesu(data: &[u8]) -> Option<String> {
    match std::str::from_utf8(data) {
        Ok(s) => return Some(s.to_string()),
        Err(e) if cesu8_pair(data, e.valid_up_to()).is_none() => return None,
        Err(_) => {}
    }
    let mut out = String::with_capacity(data.len());
    let mut rest = data;
    loop {
        match std::str::from_utf8(rest) {
            Ok(s) => {
                out.push_str(s);
                return Some(out);
            }
            Err(e) => {
                let good = e.valid_up_to();
                let c = cesu8_pair(rest, good)?;
                out.push_str(unsafe { std::str::from_utf8_unchecked(&rest[..good]) });
                out.push(c);
                rest = &rest[good + 6..];
            }
        }
    }
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
                match errors {
                    Errors::Ignore => {
                        let n = e.error_len().unwrap_or(rest.len() - good);
                        rest = &rest[good + n..];
                    }
                    _ => {
                        let np = handler_at(&mut out, rest, good, errors);
                        rest = &rest[np..];
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
            _ => i = handler_at(&mut out, data, start, errors),
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
            _ => i = handler_at(&mut out, data, start, errors),
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
                        _ => pos = handler_at(&mut out, data, bad_start, errors),
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
            let mut i = 0;
            while i < data.len() {
                if data[i] < 0x80 {
                    out.push(data[i] as char);
                    i += 1;
                } else {
                    i = handler_at(&mut out, data, i, errors);
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
            let mut i = 0;
            while i < data.len() {
                let c = tbl[data[i] as usize];
                if c == 0xfffe {
                    i = handler_at(&mut out, data, i, errors);
                } else {
                    push_cp(&mut out, c);
                    i += 1;
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
/// hint: a MIME-szintu kodlap, ha a html <meta> utf-8-ra irta felul: cp1251 hint + cirillnek latszo byte-ok eseten az utf-8-kent
/// ervenytelen byte-ok cp1251 szerint dekodolodnak (mixed_cp1251), nem latin1/cp1252-kent
pub fn safe_decode(data: &[u8], cs: Option<&str>, errors: Errors, hint: Option<&str>) -> String {
    let name = match cs {
        Some(s) if !s.is_empty() => s,
        _ => "utf-8",
    };
    let Some(codec) = lookup(name) else { return decode_utf8(data, Errors::Mixed) };
    let mut errors = errors;
    if let Some(h) = hint {
        if codec.name == "utf-8" && matches!(errors, Errors::Mixed) && lookup(h).map_or(false, |c| c.name == "cp1251") && cyrillic_like(data) {
            errors = mixed_cp1251();
        }
    }
    // a cp1251 cimke onmagaban nem eleg (sok latin level jon tevesen windows-1251-kent): csak cirillnek latszo byte-okra hiszunk neki
    if codec.name == "cp1251" && !cyrillic_like(data) {
        return decode_utf8(data, Errors::Mixed);
    }
    // 7 bites, shift-szekvencias kodlap (eml2str._SHIFT_CODECS), de a shift-jelolo elo sem fordul: a kodlap csak ASCII-t adhatna,
    // a 8 bites byte-ok mas kodlapbol jonnek -> utf-8 + mixed visszaeses (iso2022_kr es hz: Unsupported, az amugy is visszaesik)
    let shift = match codec.kind {
        Kind::Mb(enc) if enc == encoding_rs::ISO_2022_JP => Some(0x1bu8),
        Kind::Utf7 => Some(b'+'),
        _ => None,
    };
    if let Some(m) = shift {
        if !data.contains(&m) {
            return decode_utf8(data, Errors::Mixed);
        }
    }
    if matches!(codec.name, "cp1252" | "iso8859-1" | "iso8859-2" | "cp1250") {
        if let Some(s) = decode_utf8_cesu(data) {
            return s; // gyakran utf-8 a latin1/2-nek jelolt szoveg; CESU-8 parokkal is
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

/// eml2str.fix_mojibake(): a MOJI tabla alakjai (magyar / nemet ekezetes betuk es nehany irasjel hibasan dekodolt utf-8 alakja,
/// "Ã¡rvÃ­ztÅ±rÅ‘" -> "árvíztűrő") egy menetben, balrol jobbra, a hosszabb alak elobb (a tabla igy van rendezve)
fn fix_mojibake(s: String) -> String {
    static LEADS: OnceLock<Vec<char>> = OnceLock::new();
    let leads = LEADS.get_or_init(|| {
        let mut v: Vec<char> = tables::MOJI.iter().filter_map(|&(k, _)| k.chars().next()).collect();
        v.sort_unstable();
        v.dedup();
        v
    });
    // gyorsut: egyik alak elso karaktere sincs a szovegben
    if !s.chars().any(|c| leads.contains(&c)) {
        return s;
    }
    let mut out = String::with_capacity(s.len());
    let mut i = 0;
    while i < s.len() {
        let rest = &s[i..];
        let c = rest.chars().next().unwrap();
        if leads.contains(&c) {
            if let Some(&(k, t)) = tables::MOJI.iter().find(|&&(k, _)| rest.starts_with(k)) {
                out.push(t);
                i += k.len();
                continue;
            }
        }
        out.push(c);
        i += c.len_utf8();
    }
    out
}

/// eml2str.fix_chars(): fix_mojibake + invalid_charrefs csere a dekodolt szovegen
pub fn fix_chars(s: String) -> String {
    let s = fix_mojibake(s);
    let r = registry();
    let repl = |c: char| -> Option<&'static str> {
        let u = c as u32;
        if u < 256 { r.charrefs[u as usize] } else if u < 0x34f { None } else { r.charrefs_hi.get(&u).copied() }
    };
    // gyors ut: nincs csereolando karakter
    if !s.chars().any(|c| repl(c).is_some()) {
        return s;
    }
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match repl(c) {
            Some(v) => out.push_str(v),
            None => out.push(c),
        }
    }
    out
}
