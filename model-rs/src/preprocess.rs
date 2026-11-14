use crate::{Error, Result};
use std::{collections::HashMap, fs, path::Path};
use unicode_normalization::UnicodeNormalization;

/// The order is significant: Cyrillic lookalikes, NFKC, the map, whitespace.
pub struct Preprocessor {
    map: HashMap<char, String>,
}

impl Preprocessor {
    pub fn load(path: impl AsRef<Path>) -> Result<Self> {
        let contents = fs::read_to_string(path)?;
        let mut map = HashMap::new();
        // Keep the value verbatim, as Python's line.split("\t")[2] does.
        for (index, line) in contents.split_inclusive('\n').enumerate() {
            let line = line.replace("\r\n", "\n");
            let mut fields = line.split('\t');
            fields.next();
            let key = fields
                .next()
                .ok_or_else(|| Error::invalid(format!("map line {}: missing key", index + 1)))?;
            let value = fields
                .next()
                .ok_or_else(|| Error::invalid(format!("map line {}: missing value", index + 1)))?;
            let mut chars = key.chars();
            let key = chars
                .next()
                .filter(|_| chars.next().is_none())
                .ok_or_else(|| {
                    Error::invalid(format!("map line {}: key must be one character", index + 1))
                })?;
            map.insert(key, value.to_owned());
        }
        for cp in [
            0, 173, 847, 8203, 8204, 8205, 8206, 8207, 8232, 8233, 8234, 8235, 8236, 8237, 8238,
            8288, 8289, 8290, 8291, 65038, 65039, 65279,
        ] {
            map.insert(char::from_u32(cp).unwrap(), String::new());
        }
        map.insert('\n', "\n".to_owned());
        Ok(Self { map })
    }

    pub fn process(&self, text: &str) -> String {
        let mut output = String::with_capacity(text.len());
        let mut space = false;
        for ch in text.chars().map(cyrillic_lookalike).nfkc() {
            if let Some(value) = self.map.get(&ch) {
                for ch in value.chars() {
                    if python_whitespace(ch) {
                        space = !output.is_empty();
                    } else {
                        if space {
                            output.push(' ');
                            space = false;
                        }
                        output.push(ch);
                    }
                }
            }
        }
        output
    }

    /// Equivalent to DS2Preprocessor's "|\n".join((subject, body)).
    /// An empty subject is the plain-string eml2str(ds2=True) case.
    pub fn process_mail(&self, subject: &str, body: &str) -> String {
        if subject.is_empty() {
            self.process(body)
        } else {
            self.process(&format!("{subject}|\n{body}"))
        }
    }
}

fn python_whitespace(ch: char) -> bool {
    ch.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&ch)
}

fn cyrillic_lookalike(ch: char) -> char {
    match ch as u32 {
        1029 => 'S',
        1030 => 'I',
        1032 => 'J',
        1040 => 'A',
        1042 => 'B',
        1045 => 'E',
        1050 => 'K',
        1052 => 'M',
        1053 => 'H',
        1054 => 'O',
        1056 => 'P',
        1057 => 'C',
        1058 => 'T',
        1061 => 'X',
        1072 => 'a',
        1077 => 'e',
        1086 => 'o',
        1088 => 'p',
        1089 => 'c',
        1091 => 'y',
        1093 => 'x',
        1109 => 's',
        1110 => 'i',
        1112 => 'j',
        _ => ch,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preprocessing_order_and_python_whitespace() {
        let map = [
            ('A', "a"),
            ('a', "a"),
            ('e', "e"),
            ('o', "o"),
            ('|', "|"),
            (' ', " "),
            ('\n', "\n"),
            ('\u{1c}', "\u{1c}"),
            ('é', "e"),
            ('\u{200b}', ""),
        ]
        .into_iter()
        .map(|(k, v)| (k, v.to_owned()))
        .collect();
        let p = Preprocessor { map };
        assert_eq!(
            p.process(" \u{410}Ａe\u{301}\u{200b} \u{43e}\u{1c}a\n"),
            "aae o a"
        );
        assert_eq!(p.process_mail("A", "o\n a"), "a| o a");
        assert_eq!(p.process_mail("", "o"), "o");
    }
}
