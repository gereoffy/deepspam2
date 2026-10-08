//! utf-7 dekoder a CPython PyUnicode_DecodeUTF7Stateful alapjan - a hibak helye es kezelese is a Pythonnal azonos
//! (a 'mixed' / 'ignore' hibakezelo miatt fontos).

use crate::codec::{handler_push, Errors};

#[inline]
fn is_b64(c: u8) -> bool {
    c.is_ascii_alphanumeric() || c == b'+' || c == b'/'
}
#[inline]
fn from_b64(c: u8) -> u32 {
    (match c {
        b'A'..=b'Z' => c - b'A',
        b'a'..=b'z' => c - b'a' + 26,
        b'0'..=b'9' => c - b'0' + 52,
        b'+' => 62,
        _ => 63,
    }) as u32
}

/// utf-7 - a CPython PyUnicode_DecodeUTF7Stateful alapjan (hibanal a mar kiirt shift-resz megmarad, a handler a
/// '+' pozicioja utan folytat). A magukban allo surrogate-okat (Python str-ben lehetnek) U+FFFD-re cserelju.
pub fn decode_utf7(data: &[u8], errors: Errors) -> String {
    let n = data.len();
    let mut out = String::with_capacity(n);
    let push = |out: &mut String, c: u32| out.push(char::from_u32(c).unwrap_or('\u{fffd}'));
    let mut s = 0usize;
    let mut in_shift = false;
    let mut b64buf: u32 = 0;
    let mut b64bits: u32 = 0;
    let mut surrogate: u32 = 0;
    let mut startinpos = 0usize;
    loop {
        while s < n {
            let ch = data[s];
            let mut err_end: Option<usize> = None;
            if in_shift {
                if is_b64(ch) {
                    b64buf = (b64buf << 6) | from_b64(ch);
                    b64bits += 6;
                    s += 1;
                    if b64bits >= 16 {
                        let out_ch = (b64buf >> (b64bits - 16)) & 0xffff;
                        b64bits -= 16;
                        b64buf &= (1u32 << b64bits) - 1;
                        if surrogate != 0 {
                            if (0xdc00..0xe000).contains(&out_ch) {
                                push(&mut out, 0x10000 + ((surrogate - 0xd800) << 10) + (out_ch - 0xdc00));
                                surrogate = 0;
                                continue;
                            }
                            push(&mut out, surrogate);
                            surrogate = 0;
                        }
                        if (0xd800..0xdc00).contains(&out_ch) {
                            surrogate = out_ch;
                        } else {
                            push(&mut out, out_ch);
                        }
                    }
                } else {
                    in_shift = false;
                    if b64bits > 0 && (b64bits >= 6 || b64buf != 0) {
                        // partial character / non-zero padding bits in shift sequence
                        s += 1;
                        err_end = Some(s);
                    } else {
                        if surrogate != 0 && ch <= 127 && ch != b'+' {
                            push(&mut out, surrogate);
                        }
                        surrogate = 0;
                        if ch == b'-' {
                            s += 1;
                        }
                    }
                }
            } else if ch == b'+' {
                startinpos = s;
                s += 1;
                if s < n && data[s] == b'-' {
                    s += 1;
                    out.push('+');
                } else if s < n && !is_b64(data[s]) {
                    s += 1;
                    err_end = Some(s); // ill-formed sequence
                } else {
                    in_shift = true;
                    surrogate = 0;
                    b64bits = 0;
                    b64buf = 0;
                }
            } else if ch <= 127 {
                s += 1;
                out.push(ch as char);
            } else {
                startinpos = s;
                s += 1;
                err_end = Some(s); // unexpected special character
            }
            if let Some(e) = err_end {
                s = match errors {
                    Errors::Ignore => e,
                    _ => {
                        handler_push(&mut out, data[startinpos], errors);
                        startinpos + 1
                    }
                };
            }
        }
        // a string vege: lezaratlan shift-szekvencia
        if in_shift {
            in_shift = false;
            if surrogate != 0 || b64bits >= 6 || (b64bits > 0 && b64buf != 0) {
                s = match errors {
                    Errors::Ignore => n,
                    _ => {
                        handler_push(&mut out, data[startinpos], errors);
                        startinpos + 1
                    }
                };
                if s < n {
                    continue;
                }
            }
        }
        break;
    }
    out
}
