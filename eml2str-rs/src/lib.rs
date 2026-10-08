//! Az eml2str.py Rust portja: `eml2str(msg, ds2=True)` -> (subject, szoveg), a Pythonnal byte-ra azonos kimenettel.
//!
//! Nem portolt (az eml2str()-bol nem erheto el, vagy nalunk nincs telepitve): TNEF (tnef_mini), striprtf (helyette
//! a beepitett durva RTF kinyero fut, mint a Pythonban striprtf nelkul), docx, get_mimedata, readfolder, decode_from.

#[cfg(feature = "python")]
mod python;
pub mod codec;
pub mod html;
pub mod mime;
pub mod rtf;
/// a Python codec-tablai: a build.rs generalja forditaskor a gen_tables.py-val
#[allow(dead_code)]
mod tables {
    include!(concat!(env!("OUT_DIR"), "/tables.rs"));
}
mod utf7;
mod util;

use codec::{ascii_compatible, charset_name, fix_chars, safe_decode, Errors};
use regex::Regex;
use rtf::PyErr;
use std::sync::OnceLock;
use util::*;

/// BOM-ok (a utf-32-le elobb, mint a vele azonosan kezdodo utf-16-le)
const BOMS: &[(&[u8], &str)] = &[
    (b"\xef\xbb\xbf", "utf-8"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
];

/// parse_ics(): DESCRIPTION vagy X-ALT-DESC (html) mezo
fn parse_ics(data: &[u8]) -> Result<Vec<u8>, PyErr> {
    let mut ics: Vec<Vec<u8>> = Vec::new();
    let mut hdr: Vec<u8> = Vec::new();
    for line in data.split(|&b| b == b'\n') {
        if line.first() == Some(&b' ') || line.first() == Some(&b'\t') {
            hdr.extend_from_slice(brstrip(&line[1..]));
            continue;
        }
        if !hdr.is_empty() {
            ics.push(std::mem::take(&mut hdr));
        }
        hdr = brstrip(line).to_vec();
    }
    if !hdr.is_empty() {
        ics.push(hdr);
    }
    fn unesc(t: &[u8]) -> Vec<u8> {
        let t = html::replace(t, b"\\N", b"\\n");
        let t = html::replace(&t, b"\r\n", b"\n");
        let t = html::replace(&t, b"\\n", b"\n");
        let t = html::replace(&t, b"\\,", b",");
        let t = html::replace(&t, b"\\;", b";");
        html::replace(&t, b"\\\\", b"\\")
    }
    for x in &ics {
        let (k, v) = match x.iter().position(|&b| b == b':') {
            Some(c) => (&x[..c], Some(&x[c + 1..])),
            None => (&x[..], None),
        };
        if k.starts_with(b"DESCRIPTION") {
            return Ok(unesc(v.ok_or(PyErr("IndexError"))?));
        }
        if k == b"X-ALT-DESC;FMTTYPE=text/html" {
            return Ok(html::html2text(&unesc(v.ok_or(PyErr("IndexError"))?)));
        }
    }
    Ok(Vec::new())
}

/// decode_payload(data, ctyp, charset) -> dekodolt, megtisztitott szoveg
pub fn decode_payload(data: &[u8], ctyp: &str, charset: Option<&str>) -> Result<String, PyErr> {
    let mut charset: Option<String> = charset.map(str::to_string);
    let mut data: &[u8] = data;
    let mut bom = false;
    for &(b, cs) in BOMS {
        if data.starts_with(b) {
            data = &data[b.len()..];
            charset = Some(cs.to_string());
            bom = true;
            break;
        }
    }
    let owned: Vec<u8>;
    let ldata = blower(data);
    if ctyp == "text/calendar" || ctyp == "application/ics" {
        owned = parse_ics(data)?;
        data = &owned;
    } else if ctyp == "text/html"
        || ctyp == "text/xml"
        || ((ctyp != "text/plain" || contains(&ldata, b"</head>") || contains(&ldata, b"</br>"))
            && contains(&ldata, b"<")
            && (contains(&ldata, b"<body")
                || contains(&ldata, b"<img ")
                || contains(&ldata, b"<style")
                || contains(&ldata, b"<br>")
                || contains(&ldata, b"<center>")
                || contains(&ldata, b"<a href")))
    {
        if let Some(p) = find(&ldata, b"<body", 0) {
            if p > 0 && !bom {
                charset = html::parse_htmlhead(&data[..p], charset);
            }
        }
        let mut conv: Option<Vec<u8>> = None;
        if let Some(cs) = charset.as_deref().filter(|c| !c.is_empty()) {
            let csn = charset_name(cs);
            if csn.contains('\0') {
                return Err(PyErr("ValueError")); // codec-nevben NUL: "embedded null character"
            }
            if !ascii_compatible(&csn) {
                conv = Some(safe_decode(data, Some(&csn), Errors::Ignore).into_bytes());
                charset = Some("utf-8".to_string());
            }
        }
        owned = html::html2text(conv.as_deref().unwrap_or(data));
        data = &owned;
    }

    let mut charset = charset_name(charset.as_deref().filter(|c| !c.is_empty()).unwrap_or("iso8859-1"));
    let is_rtf = ctyp == "application/rtf";
    if is_rtf {
        charset = rtf::parse_rtfhead(data, Some(&charset))?;
    }
    if charset.contains('\0') {
        return Err(PyErr("ValueError"));
    }

    let text = if ascii_compatible(&charset) {
        match std::str::from_utf8(data) {
            Ok(s) => s.to_string(),
            Err(_) => safe_decode(data, Some(&charset), Errors::Mixed),
        }
    } else {
        safe_decode(data, Some(&charset), Errors::Mixed)
    };

    let text = if is_rtf { rtf::rtf_to_text(&text, &rtf::rtf_hex_encoding(&charset))? } else { html::unescape(&text) };
    Ok(fix_chars(text))
}

fn re_hdr() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"=\?([^?]*?)\?([qQbB])\?(.*?)\?=").unwrap())
}

enum Strip {
    Text(String),
    Enc(Vec<u8>, String),
}

/// hdrdecode4(): RFC 2047 encoded-word-ok dekodolasa (Err: a Python ValueError-t dobna - NUL a charset nevben)
pub fn hdrdecode4(h: &[u8]) -> Result<String, PyErr> {
    let s = codec::decode_utf8(h, Errors::Mixed);
    let mut strips: Vec<Strip> = Vec::new();
    let push_text = |strips: &mut Vec<Strip>, t: &str| {
        if !t.is_empty() && !t.chars().all(py_isspace) {
            strips.push(Strip::Text(t.to_string()));
        }
    };
    let mut last = 0;
    for c in re_hdr().captures_iter(&s) {
        let m = c.get(0).unwrap();
        push_text(&mut strips, &s[last..m.start()]);
        last = m.end();
        let cset = c[1].to_lowercase();
        let cset = cset.split('*').next().unwrap().to_string();
        let cfmt = c[2].to_lowercase();
        let cenc = &c[3];
        let dec = if cfmt == "q" {
            Ok(mime::a2b_qp(cenc.replace("==", "=").as_bytes(), true))
        } else {
            let mut d = cenc.as_bytes().to_vec();
            d.extend_from_slice(b"===");
            mime::a2b_base64(&d)
        };
        match dec {
            Ok(cdec) => match strips.last_mut() {
                Some(Strip::Enc(b, cs)) if *cs == cset => b.extend_from_slice(&cdec),
                _ => strips.push(Strip::Enc(cdec, cset)),
            },
            Err(_) => strips.push(Strip::Text(cenc.to_string())),
        }
    }
    push_text(&mut strips, &s[last..]);
    let mut out = String::new();
    for x in strips {
        match x {
            Strip::Text(t) => out.push_str(&t),
            Strip::Enc(b, cs) => {
                let csn = charset_name(&cs);
                if csn.contains('\0') {
                    return Err(PyErr("ValueError"));
                }
                out.push_str(&safe_decode(&b, Some(&csn), Errors::Mixed))
            }
        }
    }
    Ok(fix_chars(out))
}

fn re_stag() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"\*\*\*\*\*SPAM[{(][0-9][.0-9]*[)}]\*\*\**").unwrap())
}

/// remove_spamtag()
pub fn remove_spamtag(text: &str) -> String {
    let mut t = re_stag().replace_all(text, "").into_owned();
    for tag in [
        "*****SPAM*****", "[SPAM]", "[Spam]", "[SpaM]", "[E:spam]", "[E:infected]", "[K:Spam]", "[K:Phishing]",
        "[K:Virus]", "[K:Mass]", "[Outlook levélszemét-bejelentő]", "[Outlook junk mail report]",
    ] {
        if t.contains(tag) {
            t = t.replace(tag, "");
        }
    }
    t
}

fn leaves<'a, 'b>(e: &'a mime::Eml<'b>, out: &mut Vec<&'a mime::Eml<'b>>) {
    if e.parts.is_empty() {
        out.push(e);
    } else {
        for p in &e.parts {
            leaves(p, out);
        }
    }
}

/// eml2str(msg, ds2=True) -> (subject, text); a subject ures, ha nincs (a Python ilyenkor csak a text-et adja vissza).
/// Err: a Python verzio ezen a levelen kivetelt dobna (a hiba Python-tipusneve).
pub fn eml2str(msg: &[u8]) -> Result<(String, String), &'static str> {
    let eml = mime::parse_eml(msg, 0, 0, msg.len()).map_err(|e| e.0)?;

    let mut subject = String::new();
    for h in &eml.headers {
        if let Some(c) = h.iter().position(|&b| b == b':') {
            if h[..c].eq_ignore_ascii_case(b"subject") {
                if let Ok(s) = hdrdecode4(&h[c + 1..]) {
                    subject = remove_spamtag(&s);
                }
            }
        }
    }

    let mut parts = Vec::new();
    leaves(&eml, &mut parts);
    let mut text = String::new();
    let mut text_len = 0usize;
    for p in parts {
        let ctyp = p.ctyp.as_str();
        let major = ctyp.split('/').next().unwrap();
        if (major == "text" && p.disp.as_deref() != Some("attachment")) || ctyp == "application/ics" || ctyp == "application/rtf" {
            let payload = p.payload().unwrap_or_default();
            let data = decode_payload(&payload, ctyp, p.charset.as_deref()).map_err(|e| e.0)?;
            let dlen = py_len(&data);
            let htmlish = ctyp == "text/html" || ctyp == "application/ms-tnef";
            if text.is_empty() || (htmlish && dlen > 20) || dlen > text_len / 2 || text.starts_with("Spam detection software,") {
                text = data;
                text_len = dlen;
            }
            if htmlish && text_len > 200 {
                break;
            }
        }
    }
    Ok((subject, text))
}
