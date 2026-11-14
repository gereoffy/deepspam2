//! DeepSpam's Python model/ port. No Python, PyTorch or C++ runtime is needed.
pub mod nn;
pub mod preprocess;

pub use nn::{Cnn, Workspace};
pub use preprocess::Preprocessor;
use sentencepiece_rust::SentencePieceProcessor;
use std::{fmt, path::Path};

pub const MAX_BLOCK: usize = 256;
pub const MIN_BLOCK: usize = 8;
pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug)]
pub struct Error(String);
impl Error {
    pub(crate) fn invalid(message: impl Into<String>) -> Self {
        Self(message.into())
    }
}
impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}
impl std::error::Error for Error {}
impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Self(e.to_string())
    }
}
impl From<ndarray_npy::ReadNpzError> for Error {
    fn from(e: ndarray_npy::ReadNpzError) -> Self {
        Self(e.to_string())
    }
}
impl From<sentencepiece_rust::Error> for Error {
    fn from(e: sentencepiece_rust::Error) -> Self {
        Self(e.to_string())
    }
}

pub struct TextProcessor {
    pub preprocess: Preprocessor,
    tokenizer: SentencePieceProcessor,
}
impl TextProcessor {
    pub fn load(dir: impl AsRef<Path>) -> Result<Self> {
        let dir = dir.as_ref();
        Ok(Self {
            preprocess: Preprocessor::load(dir.join("unicodes6x.map"))?,
            tokenizer: SentencePieceProcessor::open(dir.join("spm6.model"))?,
        })
    }
    pub fn vocab_size(&self) -> usize {
        self.tokenizer.piece_size()
    }
    /// Input is already preprocessed. Complete tokenization precedes truncation.
    pub fn encode_normalized(&self, text: &str) -> Result<Vec<i32>> {
        Ok(self.tokenizer.encode(text)?)
    }
    pub fn tokenize(&self, text: &str) -> Result<Vec<i32>> {
        self.encode_normalized(&self.preprocess.process(text))
    }
    pub fn piece_id(&self, piece: &str) -> Option<i32> {
        self.tokenizer.vocab().piece_to_id(piece.as_bytes())
    }
    pub fn pieces(&self, ids: &[i32]) -> Result<String> {
        let mut output = String::new();
        for (i, &id) in ids.iter().enumerate() {
            let piece = self
                .tokenizer
                .id_to_piece(id)
                .ok_or_else(|| Error::invalid(format!("invalid token id: {id}")))?;
            if i != 0 {
                output.push(' ');
            }
            output.push_str(piece);
        }
        Ok(output)
    }
}

pub struct DeepSpam {
    pub text: TextProcessor,
    pub network: Cnn,
}
pub struct Prediction {
    pub percent: f64,
    /// The single-preprocessing token list used for deepspam2.res logging.
    pub log_tokens: Vec<i32>,
}
impl DeepSpam {
    pub fn load(dir: impl AsRef<Path>) -> Result<Self> {
        Self::load_with_weights(dir, "deepspam_weights.npz")
    }
    pub fn load_with_weights(dir: impl AsRef<Path>, weights: impl AsRef<Path>) -> Result<Self> {
        let dir = dir.as_ref();
        let text = TextProcessor::load(dir)?;
        let network = Cnn::load(dir.join(weights))?;
        if text.vocab_size() != network.vocab_size() {
            return Err(Error::invalid(
                "SentencePiece vocabulary and embedding size differ",
            ));
        }
        Ok(Self { text, network })
    }
    pub fn predict(&self, text: &str, workspace: &mut Workspace) -> Result<Prediction> {
        self.predict_normalized(self.text.preprocess.process(text), workspace)
    }
    pub fn predict_mail(
        &self,
        subject: &str,
        body: &str,
        workspace: &mut Workspace,
    ) -> Result<Prediction> {
        self.predict_normalized(self.text.preprocess.process_mail(subject, body), workspace)
    }
    fn predict_normalized(
        &self,
        normalized: String,
        workspace: &mut Workspace,
    ) -> Result<Prediction> {
        let log_tokens = self.text.encode_normalized(&normalized)?;
        // Preserve Python __call__ -> tokenize's second preprocessing pass.
        let twice = self.text.preprocess.process(&normalized);
        let percent = if twice == normalized {
            self.network.score_tokens(&log_tokens, workspace)?
        } else {
            self.network
                .score_tokens(&self.text.encode_normalized(&twice)?, workspace)?
        };
        Ok(Prediction {
            percent,
            log_tokens,
        })
    }
}
