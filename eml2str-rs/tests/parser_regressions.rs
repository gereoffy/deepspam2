use eml2str::{codec, decode_payload, eml2str, html, mime, rtf};

#[test]
fn mixed_utf8_detector_matches_the_python_accent_set_and_threshold() {
    assert!(codec::is_utf8_mixed(b"", 0));
    assert!(codec::is_utf8_mixed(b"ASCII", 0));
    assert!(!codec::is_utf8_mixed(b"", 1));
    for letter in "áéíóöőúüűÁÉÍÓÖŐÚÜŰäÄß".chars() {
        let bytes = letter.to_string().repeat(4).into_bytes();
        assert!(codec::is_utf8_mixed(&bytes, 4), "{letter}");
        assert!(!codec::is_utf8_mixed(&bytes, 5), "{letter}");
        assert!(!codec::is_utf8_mixed(&bytes[..bytes.len() - 1], 4), "{letter}");
    }
    assert!(!codec::is_utf8_mixed("àçñΩЖ".repeat(4).as_bytes(), 1));
}

#[test]
fn german_accents_trigger_mixed_utf8_decoding() {
    for letter in ['ä', 'Ä', 'ß'] {
        let prefix = format!("{} François footer: ", letter.to_string().repeat(4));
        let expected = format!("{prefix}é");
        for charset in ["windows-1252", "windows-1250", "iso-8859-2"] {
            let mut msg = format!("Content-Type: text/plain; charset={charset}\r\n\r\n{prefix}").into_bytes();
            msg.push(0xe9); // latin kodolasu lablec az UTF-8 szoveg utan
            assert_eq!(eml2str(&msg).unwrap().1, expected, "{letter}, {charset}");
        }
    }
}

#[test]
fn malformed_headers_are_ignored() {
    for nl in ["\n", "\r\n"] {
        for bad in [
            " Subject: ignored",
            "\tSubject: ignored",
            "Content-Type",
            "Content-Disposition",
            "Content-Transfer-Encoding",
        ] {
            let msg = format!("{bad}{nl}Content-Type: text/plain{nl}{nl}body");
            assert_eq!(eml2str(msg.as_bytes()).unwrap().1, "body");
        }
        let msg = format!("Subject: folded{nl}\tcontinued{nl}{nl}body");
        assert_eq!(eml2str(msg.as_bytes()).unwrap(), (" folded continued".into(), "body".into()));
    }
}

#[test]
fn empty_headers_preserve_the_body_at_nonzero_offsets() {
    for nl in ["\n", "\r\n"] {
        let data = format!("outside{nl}{nl}{nl}Hello{nl}{nl}restOUTSIDE");
        let start = "outside".len() + 2 * nl.len();
        let end = data.len() - "OUTSIDE".len();
        let tree = mime::parse_eml(data.as_bytes(), 0, start, end).unwrap();
        assert!(tree.headers.is_empty());
        assert_eq!(tree.payload().unwrap(), format!("Hello{nl}{nl}rest").as_bytes());

        let msg = format!("Content-Type: multipart/mixed; boundary=x{nl}{nl}--x{nl}{nl}Hello{nl}--x--{nl}");
        assert_eq!(eml2str(msg.as_bytes()).unwrap().1, "Hello");
    }
}

#[test]
fn mime_parameters_accept_whitespace_and_quoted_escapes() {
    for boundary in ["x", "a\"b", "a\\b"] {
        let quoted = boundary.replace('\\', "\\\\").replace('"', "\\\"");
        let msg = format!(
            "Content-Type: multipart/mixed; boundary \t = \"{quoted}\"\r\n\r\n--{boundary}\r\n\
             Content-Type: text/plain; charset = utf-8\r\n\
             Content-Disposition: inline; filename=\"a\\\"b.txt\"; charset = windows-1250\r\n\r\n\
             Hello\r\n--{boundary}--\r\n"
        );
        let tree = mime::parse_eml(msg.as_bytes(), 0, 0, msg.len()).unwrap();
        assert_eq!(tree.parts.len(), 1);
        assert_eq!(tree.parts[0].charset.as_deref(), Some("windows-1250"));
        assert_eq!(eml2str(msg.as_bytes()).unwrap().1, "Hello");
    }
    let msg = b"Content-Type: text/plain\nContent-Disposition: inline; filename* = UTF-8''name.txt; charset = utf-8\n\nbody";
    let tree = mime::parse_eml(msg, 0, 0, msg.len()).unwrap();
    assert_eq!(tree.charset.as_deref(), Some("utf-8"));
}

#[test]
fn encoded_message_parts_remain_leaves() {
    for (encoding, body) in [
        ("base64", "U3ViamVjdDogaW5uZXINCg0KYm9keQ=="),
        ("quoted-printable", "Subject: inner=0D=0A=0D=0Abody"),
    ] {
        for subtype in ["rfc822", "delivery-status", "global"] {
            let msg = format!("Content-Type: message/{subtype}\r\nContent-Transfer-Encoding: {encoding}\r\n\r\n{body}");
            let tree = mime::parse_eml(msg.as_bytes(), 0, 0, msg.len()).unwrap();
            assert!(tree.parts.is_empty());
            assert_eq!(tree.payload().unwrap(), b"Subject: inner\r\n\r\nbody");
            assert_eq!(eml2str(msg.as_bytes()).unwrap().1, "");
        }
    }
    for encoding in ["", "7bit", "8bit", "binary"] {
        let msg = format!("Content-Type: message/rfc822\nContent-Transfer-Encoding: {encoding}\n\nSubject: inner\n\nbody");
        let tree = mime::parse_eml(msg.as_bytes(), 0, 0, msg.len()).unwrap();
        assert_eq!(tree.parts.len(), 1);
        assert_eq!(eml2str(msg.as_bytes()).unwrap().1, "body");
    }
}

#[test]
fn initial_literal_less_than_is_preserved() {
    for (input, expected) in [
        ("2 < 3", "2 < 3"),
        ("2 < 3 and 5 > 4 <b>hello</b>", "2 < 3 and 5 > 4 hello"),
        ("<3 <b>hello</b>", "<3 hello"),
        ("<", "<"),
        ("<b>hello</b>", "hello"),
        ("<!-- comment --><p>hello</p>", "hello"),
    ] {
        assert_eq!(html::html2text(input.as_bytes()), expected.as_bytes());
    }
}

#[test]
fn meta_charset_accepts_ascii_whitespace() {
    for ws in ["", " ", "\t", "\r\n ", "\u{b}\u{c}"] {
        let meta = format!("<meta charset{ws}=\"windows-1250\">");
        assert_eq!(html::parse_htmlhead(meta.as_bytes(), None).as_deref(), Some("windows-1250"));
        let mut body = format!("<head>{meta}</head><body>").into_bytes();
        body.extend_from_slice(b"\xe8</body>");
        assert_eq!(decode_payload(&body, "text/html", None).unwrap(), "č");
    }
    let head = b"<meta charsetX=bad content=\"text/html; charset = windows-1250\">";
    assert_eq!(html::parse_htmlhead(head, None).as_deref(), Some("windows-1250"));
    assert_eq!(html::parse_htmlhead(b"<meta charset = {{cs}}>", Some("utf-8".into())).as_deref(), Some("utf-8"));
}

#[test]
fn text_rtf_uses_the_rtf_decoder() {
    let rtf = br"{\rtf1\ansi\ansicpg1250 \'e1rv\'edzt\'fbr\'f5}";
    for ctyp in ["text/rtf", "application/rtf"] {
        assert_eq!(decode_payload(rtf, ctyp, Some("windows-1252")).unwrap(), "árvíztűrő");
        let mut msg = format!("Content-Type: {ctyp}; charset=windows-1252\n\n").into_bytes();
        msg.extend_from_slice(rtf);
        assert_eq!(eml2str(&msg).unwrap().1, "árvíztűrő");
    }
}

#[test]
fn malformed_calendar_fields_are_skipped() {
    for data in [
        "DESCRIPTION\nDESCRIPTION:valid",
        "X-ALT-DESC;FMTTYPE=text/html\nDESCRIPTION:valid",
        "DESCRIPTION\nX-ALT-DESC;FMTTYPE=text/html:<b>valid</b>",
    ] {
        assert_eq!(decode_payload(data.as_bytes(), "text/calendar", None).unwrap(), "valid");
    }
    assert_eq!(decode_payload(b"DESCRIPTION", "text/calendar", None).unwrap(), "");
}

#[test]
fn calendar_escapes_are_decoded_once() {
    for (value, expected) in [
        (r"one\nnext", "one\nnext"),
        (r"one\Nnext", "one\nnext"),
        (r"one\\nnext", r"one\nnext"),
        (r"one\\Nnext", r"one\Nnext"),
        (r"C:\\new\\notes.txt", r"C:\new\notes.txt"),
        (r"one\,two\;three", "one,two;three"),
        (r"unknown\t", r"unknown\t"),
    ] {
        let data = format!("DESCRIPTION:{value}");
        assert_eq!(decode_payload(data.as_bytes(), "application/ics", None).unwrap(), expected);
    }
}

#[test]
fn rtf_fallback_counts_tokens_and_stops_at_groups() {
    for (input, expected) in [
        (r"{\rtf1\uc1\u945\~TEXT}", "αTEXT"),
        ("{\\rtf1\\uc2\\u945 a\r\nbC}", "αC"),
        (r"{\rtf1\uc2\u945 a\b bC}", "αbC"),
        (r"{\rtf1\uc1\u945\tab TEXT}", "αTEXT"),
        (r"{\rtf1\uc1\u945\bin3 {}\TEXT}", "αTEXT"),
        (r"{\rtf1\uc2\u945\bin2 őűxTEXT}", "αTEXT"),
        (r"{\rtf1\uc2\u945 a{\b TEXT}TAIL}", "αTEXTTAIL"),
        (r"{\rtf1{\uc2\u945 a}TEXT}", "αTEXT"),
        (r"{\rtf1\uc2\u945ő\'fbTEXT}", "αTEXT"),
        (r"{\rtf1\uc-2\u945TEXT}", "αTEXT"),
        (r"{\rtf1\uc1\u-10179?\u-8704?TEXT}", "😀TEXT"),
        (r"{\rtf1\uc1{\uc2\u945ab}\u946?TEXT}", "αβTEXT"),
    ] {
        assert_eq!(rtf::rtf_to_text(input, "cp1252").unwrap(), expected, "{input}");
    }
}
