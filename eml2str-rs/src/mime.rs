//! MIME: parse_eml, parse_ctyp, decode_body + a binascii a2b_base64 / a2b_qp pontos megfeleloje

use crate::rtf::PyErr;
use crate::util::*;

/// binascii.a2b_base64 (CPython 3.9, nem-strict): az ervenytelen karaktereket atugorja, az elso ervenyes
/// padding-sorozat (quad_pos >= 2 utan) lezarja a dekodolast; ha a vegen quad_pos != 0 -> binascii.Error
pub fn a2b_base64(data: &[u8]) -> Result<Vec<u8>, ()> {
    let mut out = Vec::with_capacity(data.len() / 4 * 3 + 3);
    let mut quad_pos = 0;
    let mut leftchar: u32 = 0;
    let mut pads = 0;
    for &c in data {
        if c == b'=' {
            if quad_pos >= 2 {
                pads += 1;
                if quad_pos + pads >= 4 {
                    return Ok(out);
                }
            }
            continue;
        }
        let v = match c {
            b'A'..=b'Z' => c - b'A',
            b'a'..=b'z' => c - b'a' + 26,
            b'0'..=b'9' => c - b'0' + 52,
            b'+' => 62,
            b'/' => 63,
            _ => continue,
        } as u32;
        pads = 0;
        match quad_pos {
            0 => {
                quad_pos = 1;
                leftchar = v;
            }
            1 => {
                quad_pos = 2;
                out.push(((leftchar << 2) | (v >> 4)) as u8);
                leftchar = v & 0x0f;
            }
            2 => {
                quad_pos = 3;
                out.push(((leftchar << 4) | (v >> 2)) as u8);
                leftchar = v & 0x03;
            }
            _ => {
                quad_pos = 0;
                out.push(((leftchar << 6) | v) as u8);
                leftchar = 0;
            }
        }
    }
    if quad_pos != 0 {
        return Err(());
    }
    Ok(out)
}

/// binascii.a2b_qp(data, header)
pub fn a2b_qp(data: &[u8], header: bool) -> Vec<u8> {
    let n = data.len();
    let mut out = Vec::with_capacity(n);
    let mut i = 0;
    while i < n {
        let c = data[i];
        if c == b'=' {
            i += 1;
            if i >= n {
                break;
            }
            if data[i] == b'\n' || data[i] == b'\r' {
                if data[i] != b'\n' {
                    while i < n && data[i] != b'\n' {
                        i += 1;
                    }
                }
                if i < n {
                    i += 1;
                }
            } else if data[i] == b'=' {
                out.push(b'=');
                i += 1;
            } else if i + 1 < n && data[i].is_ascii_hexdigit() && data[i + 1].is_ascii_hexdigit() {
                let h = |b: u8| (b as char).to_digit(16).unwrap() as u8;
                out.push((h(data[i]) << 4) | h(data[i + 1]));
                i += 2;
            } else {
                out.push(b'=');
            }
        } else if header && c == b'_' {
            out.push(b' ');
            i += 1;
        } else {
            out.push(c);
            i += 1;
        }
    }
    out
}

/// decode_body()
fn decode_body(data: &[u8], encoding: &str) -> Vec<u8> {
    if encoding == "base64" {
        let mut d = Vec::with_capacity(data.len() + 3);
        d.extend_from_slice(data);
        d.extend_from_slice(b"===");
        if let Ok(v) = a2b_base64(&d) {
            return v;
        }
    } else if matches!(encoding, "quoted-printable" | "utf8" | "utf-8") {
        // data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        let mut d = Vec::with_capacity(data.len() + data.len() / 32);
        let mut i = 0;
        while i < data.len() {
            if data[i] == b'\r' && i + 1 < data.len() && data[i + 1] == b'\n' {
                i += 1;
                continue;
            }
            if data[i] == b'\n' {
                d.extend_from_slice(b"\r\n");
            } else {
                d.push(data[i]);
            }
            i += 1;
        }
        return a2b_qp(&d, false);
    }
    data.to_vec()
}

/// a parse_ctyp() altal kitoltott dict (beszurasi sorrendben, a kesobbi azonos kulcs felulirja az erteket)
#[derive(Default)]
pub struct Ct(Vec<(Vec<u8>, Vec<u8>)>);
impl Ct {
    fn set(&mut self, k: Vec<u8>, v: Vec<u8>) {
        match self.0.iter_mut().find(|(kk, _)| *kk == k) {
            Some(e) => e.1 = v,
            None => self.0.push((k, v)),
        }
    }
    pub fn get(&self, k: &[u8]) -> Option<&[u8]> {
        self.0.iter().find(|(kk, _)| kk == k).map(|(_, v)| v.as_slice())
    }
}

/// parse_ctyp(): "Content-*: value; name=value; ..." -> ct
fn parse_ctyp(data: &[u8], hdr: &[u8], ct: &mut Ct) {
    let p = find(data, b";", 0).unwrap_or(data.len());
    let v = bstrip(&data[..p]);
    let v = match v.iter().position(|&b| b == b' ') {
        Some(i) => &v[..i],
        None => v,
    };
    ct.set(hdr.to_vec(), v.to_vec());

    let mut q = p + 1;
    let mut ijel = 0u8;
    let mut eqsn = false;
    let mut name: Vec<u8> = Vec::new();
    let mut value: Vec<u8> = Vec::new();
    while q < data.len() {
        let c = data[q];
        q += 1;
        if ijel != 0 {
            if c == ijel {
                ijel = 0;
            } else {
                value.push(c);
            }
        } else if c == 59 {
            if !name.is_empty() {
                ct.set(blower(&name), brstrip(&value).to_vec());
            }
            name.clear();
            value.clear();
            eqsn = false;
        } else if eqsn {
            if c == 34 || (c == 39 && value.is_empty() && !name.is_empty() && *name.last().unwrap() != 42) {
                ijel = c;
            } else if !value.is_empty() || c > 32 {
                value.push(c);
            }
        } else if c == 61 {
            eqsn = true;
        } else if !name.is_empty() || c > 32 {
            name.push(c);
        }
    }
    if !name.is_empty() {
        ct.set(blower(&name), brstrip(&value).to_vec());
    }
}

pub struct Eml<'a> {
    pub headers: Vec<Vec<u8>>,
    pub ctyp: String,
    pub charset: Option<String>,
    pub disp: Option<String>,
    /// a nyers (Content-Transfer-Encoding szerint meg nem dekodolt) body - lasd payload()
    body: Option<&'a [u8]>,
    cenc: String,
    pub parts: Vec<Eml<'a>>,
}

impl Eml<'_> {
    /// a dekodolt payload (a Python parse_eml(decode=True) "payload"-ja). Csak a ténylegesen hasznalt reszekre
    /// fut le (a decode_body nem dobhat kivetelt, igy az eredmeny ugyanaz, mintha mindet elore dekodolnank).
    pub fn payload(&self) -> Option<Vec<u8>> {
        self.body.map(|b| decode_body(b, &self.cenc))
    }
}

/// .decode("us-ascii", errors="ignore").lower()
fn ascii_lower(b: &[u8]) -> String {
    b.iter().filter(|c| c.is_ascii()).map(|c| c.to_ascii_lowercase() as char).collect()
}

/// hsize: min(find(b'\n\n')+2, find(b'\r\n\r\n')+4) a data[p0:pend]-ben, kulonben pend - egyetlen menetben
/// (a Python ket kulon keresest csinal, CRLF-es levelnel a \n\n keresese a resz vegeig fut)
fn header_end(data: &[u8], p0: usize, pend: usize) -> usize {
    let d = &data[..pend];
    for i in memchr::memchr_iter(b'\n', &d[p0..]).map(|i| i + p0) {
        if i + 1 < pend && d[i + 1] == b'\n' {
            return i + 2;
        }
        if i > p0 && d[i - 1] == b'\r' && i + 2 < pend && d[i + 1] == b'\r' && d[i + 2] == b'\n' {
            return i + 3;
        }
    }
    pend
}

/// a Python rekurzios limit (1000) kozelitese
const MAX_DEPTH: usize = 990;

/// parse_eml(data, decode=True, level, p, pend)
pub fn parse_eml(data: &[u8], level: usize, p0: usize, pend: usize) -> Result<Eml<'_>, PyErr> {
    if level > MAX_DEPTH {
        return Err(PyErr("RecursionError"));
    }
    let hsize = header_end(data, p0, pend);

    let mut headers: Vec<Vec<u8>> = Vec::new();
    let mut hdr: Option<Vec<u8>> = None;
    let hpart = if p0 <= hsize { &data[p0..hsize] } else { &b""[..] };
    for rawline in hpart.split(|&b| b == b'\n') {
        let mut line = rawline;
        while let [rest @ .., b'\r'] = line {
            line = rest;
        }
        if !line.is_empty() && (line[0] == 9 || line[0] == 32) {
            let Some(h) = hdr.as_mut() else { return Err(PyErr("TypeError")) };
            let mut k = 0;
            while k < line.len() && (line[k] == b'\t' || line[k] == b' ') {
                k += 1;
            }
            h.push(b' ');
            h.extend_from_slice(&line[k..]);
            continue;
        }
        if let Some(h) = hdr.take() {
            if !h.is_empty() {
                headers.push(h);
            }
        }
        hdr = Some(line.to_vec());
        if line.is_empty() {
            break;
        }
    }
    if let Some(h) = hdr {
        if !h.is_empty() {
            headers.push(h);
        }
    }

    let mut ct = Ct::default();
    for h in &headers {
        let colon = h.iter().position(|&b| b == b':');
        let name = match colon {
            Some(c) => &h[..c],
            None => &h[..],
        };
        let key: &[u8] = match blower(name).as_slice() {
            b"content-type" => b"_ct",
            b"content-disposition" => b"_cd",
            b"content-transfer-encoding" => b"_ce",
            _ => continue,
        };
        let Some(c) = colon else { return Err(PyErr("IndexError")) };
        parse_ctyp(&h[c + 1..], key, &mut ct);
    }

    let ctyp = ascii_lower(ct.get(b"_ct").unwrap_or(b""));
    let cenc = ascii_lower(ct.get(b"_ce").unwrap_or(b""));
    let disp = ct.get(b"_cd").map(ascii_lower);
    let cset = ct.get(b"charset").map(ascii_lower);
    let mut eml = Eml {
        headers,
        ctyp: if ctyp.is_empty() { "text/plain".to_string() } else { ctyp.clone() },
        charset: cset,
        disp,
        body: None,
        cenc: String::new(),
        parts: Vec::new(),
    };

    let boundary = ct.get(b"boundary");
    if boundary.is_some() && ctyp.starts_with("multipart/") {
        let mut bo = b"--".to_vec();
        bo.extend_from_slice(boundary.unwrap());
        let mut q = hsize;
        let mut p = hsize;
        let mut first = true;
        while p < pend {
            let pp;
            match find(&data[..pend], &bo, p) {
                None => {
                    p = pend;
                    pp = pend;
                }
                Some(x) => {
                    let mut x2 = x;
                    p = x + bo.len();
                    if x2 > 0 && data[x2 - 1] == 10 {
                        x2 -= 1;
                        if x2 > 0 && data[x2 - 1] == 13 {
                            x2 -= 1;
                        }
                    }
                    pp = x2;
                }
            }
            if data.get(p..p + 2) == Some(b"--") {
                p += 2;
            }
            if p >= pend || data[p] <= 32 || data.get(p..p + 8) == Some(b"Content-") {
                let part: &[u8] = if q < pp { &data[q..pp] } else { b"" };
                if !part.is_empty() && bstrip(part).len() > 2 {
                    if first && contains(part, b"Content-Type:") {
                        q += find(part, b"Content-", 0).unwrap();
                        first = false;
                    }
                    if !first
                        || part.len() >= 300
                        || !(contains(part, b"MIME") || contains(&blower(part), b"multipart message") || contains(&blower(part), b" mime format"))
                    {
                        eml.parts.push(parse_eml(data, level + 1, q, pp)?);
                    }
                }
                while p < pend && data[p] <= 32 && data[p] != 10 {
                    p += 1;
                }
                if p < pend && data[p] == 10 {
                    p += 1;
                }
                q = p;
                first = false;
            }
        }
    } else if ctyp.starts_with("message/") {
        eml.parts.push(parse_eml(data, level + 1, hsize, pend)?);
    } else {
        let body = if hsize <= pend { &data[hsize..pend] } else { &b""[..] };
        eml.body = Some(body);
        eml.cenc = cenc;
    }
    Ok(eml)
}
