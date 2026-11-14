//! Milter framing and message assembly, independent of model inference.
use std::io::{self, ErrorKind};
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};

pub enum Action {
    Reply(Vec<u8>),
    Scan(Vec<u8>),
    None,
    Quit,
}

pub struct Session {
    message: Vec<u8>,
    max_message: usize,
}

impl Session {
    pub fn new(max_message: usize) -> Self {
        Self {
            message: Vec::new(),
            max_message,
        }
    }
    fn append(&mut self, bytes: &[u8]) -> io::Result<()> {
        if bytes.len() > self.max_message.saturating_sub(self.message.len()) {
            return Err(invalid("message size limit exceeded"));
        }
        self.message.extend_from_slice(bytes);
        Ok(())
    }
    pub fn command(&mut self, packet: &[u8]) -> io::Result<Action> {
        let (&cmd, data) = packet
            .split_first()
            .ok_or_else(|| invalid("empty packet"))?;
        match cmd {
            b'O' => {
                if data.len() != 12 {
                    return Err(invalid("invalid option negotiation"));
                }
                let offered =
                    |offset| u32::from_be_bytes(data[offset..offset + 4].try_into().unwrap());
                if offered(0) < 2 || offered(4) & 1 == 0 {
                    return Err(invalid("peer must support milter v2 and adding headers"));
                }
                let mut reply = vec![b'O'];
                for value in [2_u32, 1, offered(8) & 0x0f] {
                    reply.extend_from_slice(&value.to_be_bytes());
                }
                Ok(Action::Reply(reply))
            }
            b'D' => Ok(Action::None),
            b'Q' => Ok(Action::Quit),
            b'A' | b'K' => {
                self.message.clear();
                Ok(Action::None)
            }
            b'M' => {
                self.message.clear();
                Ok(Action::Reply(vec![b'c']))
            }
            b'L' => {
                let end = data
                    .iter()
                    .position(|&b| b == 0)
                    .ok_or_else(|| invalid("unterminated header name"))?;
                let value = &data[end + 1..];
                let value_end = value
                    .iter()
                    .position(|&b| b == 0)
                    .ok_or_else(|| invalid("unterminated header value"))?;
                self.append(&data[..end])?;
                self.append(b": ")?;
                self.append(&value[..value_end])?;
                self.append(b"\n")?;
                Ok(Action::Reply(vec![b'c']))
            }
            b'N' => {
                self.append(b"\n")?;
                Ok(Action::Reply(vec![b'c']))
            }
            b'B' => {
                self.append(data)?;
                Ok(Action::Reply(vec![b'c']))
            }
            b'E' => Ok(Action::Scan(std::mem::take(&mut self.message))),
            b'C' | b'H' | b'R' | b'T' | b'U' => Ok(Action::Reply(vec![b'c'])),
            _ => Err(invalid("unsupported milter command")),
        }
    }
}

fn invalid(message: &'static str) -> io::Error {
    io::Error::new(ErrorKind::InvalidData, message)
}

pub async fn read_packet<R: AsyncRead + Unpin>(
    reader: &mut R,
    limit: usize,
) -> io::Result<Option<Vec<u8>>> {
    let mut header = [0_u8; 4];
    if reader.read(&mut header[..1]).await? == 0 {
        return Ok(None);
    }
    reader.read_exact(&mut header[1..]).await?;
    let length = u32::from_be_bytes(header) as usize;
    if length == 0 || length > limit {
        return Err(invalid("invalid milter frame length"));
    }
    let mut packet = vec![0; length];
    reader.read_exact(&mut packet).await?;
    Ok(Some(packet))
}

pub async fn write_packet<W: AsyncWrite + Unpin>(writer: &mut W, bytes: &[u8]) -> io::Result<()> {
    let length = u32::try_from(bytes.len()).map_err(|_| invalid("response too large"))?;
    writer.write_all(&length.to_be_bytes()).await?;
    writer.write_all(bytes).await?;
    writer.flush().await
}

/// Keep deepspam4.py's 0.1 offset, strict thresholds and integer truncation.
pub fn verdict(score: f64) -> String {
    if score < 0.0 {
        return "toosmall".to_owned();
    }
    let score = score + 0.1;
    let label = if score < 2.0 {
        "ham"
    } else if score < 10.0 {
        "maybeham"
    } else if score < 20.0 {
        "20ham"
    } else if score > 98.0 {
        "spam"
    } else if score > 90.0 {
        "maybespam"
    } else if score > 80.0 {
        "80spam"
    } else {
        "dunno"
    };
    format!("{label} {}%", score as i32)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn captures_chunks_resets_after_eom_and_abort() {
        let mut s = Session::new(100);
        s.command(b"LSubject\0one\0").unwrap();
        s.command(b"N").unwrap();
        s.command(b"Babc").unwrap();
        s.command(b"Bdef").unwrap();
        match s.command(b"E").unwrap() {
            Action::Scan(x) => assert_eq!(x, b"Subject: one\n\nabcdef"),
            _ => panic!(),
        }
        s.command(b"Bjunk").unwrap();
        s.command(b"A").unwrap();
        s.command(b"Bnew").unwrap();
        match s.command(b"E").unwrap() {
            Action::Scan(x) => assert_eq!(x, b"new"),
            _ => panic!(),
        }
    }
    #[test]
    fn negotiation_intersects_offered_flags() {
        let mut packet = vec![b'O'];
        for x in [6_u32, 1, 5] {
            packet.extend_from_slice(&x.to_be_bytes());
        }
        match Session::new(100).command(&packet).unwrap() {
            Action::Reply(x) => assert_eq!(&x[1..], &[0, 0, 0, 2, 0, 0, 0, 1, 0, 0, 0, 5]),
            _ => panic!(),
        }
        packet[8] = 0;
        assert!(Session::new(100).command(&packet).is_err());
    }
    #[test]
    fn malformed_frames_and_message_limits() {
        let mut s = Session::new(3);
        assert!(s.command(b"Lbad").is_err());
        assert!(s.command(b"B1234").is_err());
        assert!(s.command(b"O").is_err());
        assert!(s.command(b"").is_err());
    }
    #[test]
    fn python_thresholds() {
        for (value, expected) in [
            (-1.0, "toosmall"),
            (0.0, "ham 0%"),
            (1.9, "maybeham 2%"),
            (9.9, "20ham 10%"),
            (19.9, "dunno 20%"),
            (80.0, "80spam 80%"),
            (90.0, "maybespam 90%"),
            (98.0, "spam 98%"),
            (100.0, "spam 100%"),
        ] {
            assert_eq!(verdict(value), expected);
        }
    }
    #[tokio::test]
    async fn fragmented_stream_and_truncated_frames() {
        let (mut writer, mut reader) = tokio::io::duplex(32);
        let send = tokio::spawn(async move {
            for byte in [0, 0, 0, 2, b'B', b'x', 0, 0] {
                writer.write_all(&[byte]).await.unwrap();
            }
        });
        assert_eq!(
            read_packet(&mut reader, 100).await.unwrap(),
            Some(b"Bx".to_vec())
        );
        assert_eq!(
            read_packet(&mut reader, 100).await.unwrap_err().kind(),
            ErrorKind::UnexpectedEof
        );
        send.await.unwrap();
        assert!(read_packet(&mut &b"\0\0\x01\0"[..], 10).await.is_err());
    }
}
