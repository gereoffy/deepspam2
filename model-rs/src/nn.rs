use crate::{Error, Result, MAX_BLOCK, MIN_BLOCK};
use ndarray::{linalg::general_mat_mul, Array1, Array2, Array3, ArrayView2, ArrayViewMut2};
use ndarray_npy::NpzReader;
use std::{fs::File, path::Path};

struct Conv {
    weights: Array2<f32>, // (filters, embedding dimension * kernel), channel first
    bias: Array1<f32>,
    kernel: usize,
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::{array, Array};
    use ndarray_npy::NpzWriter;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn tiny_model() -> Cnn {
        let path = std::env::temp_dir().join(format!(
            "deepspam-{}-{}.npz",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let mut npz = NpzWriter::new(File::create(&path).unwrap());
        npz.add_array(
            "embedding",
            &array![[42_f32, 42.], [1., -2.], [-3., 4.], [2., 1.]],
        )
        .unwrap();
        for i in 0..4 {
            let kernel = i + 2;
            let w = Array::from_shape_fn((2, 2, kernel), |(o, c, k)| {
                ((o * 7 + c * 3 + k + i) % 9) as f32 * 0.15 - 0.6
            });
            npz.add_array(format!("convl.{i}.weight"), &w).unwrap();
            npz.add_array(format!("convl.{i}.bias"), &array![-0.5_f32, 0.3])
                .unwrap();
        }
        npz.add_array(
            "l_hid.weight",
            &Array::from_shape_fn((3, 8), |(r, c)| (r * 3 + c) as f32 * 0.05 - 0.3),
        )
        .unwrap();
        npz.add_array("l_hid.bias", &array![0.1_f32, -0.2, 0.4])
            .unwrap();
        npz.add_array(
            "l_fc.weight",
            &array![[0.5_f32, -0.2, 0.1], [-0.1, 0.3, -0.5]],
        )
        .unwrap();
        npz.add_array("l_fc.bias", &array![0.4_f32, -0.7]).unwrap();
        npz.finish().unwrap();
        let model = Cnn::load(&path).unwrap();
        std::fs::remove_file(path).unwrap();
        model
    }

    /// Independent, scalar f64 convolution over (token, channel, offset).
    fn scalar(model: &Cnn, ids: &[i32]) -> [f64; 2] {
        let mut pools = Vec::new();
        for conv in &model.convs {
            for out in 0..conv.bias.len() {
                let mut best = 0_f64;
                for start in 0..=ids.len() - conv.kernel {
                    let mut sum = conv.bias[out] as f64;
                    for ch in 0..model.embedding_dim() {
                        for k in 0..conv.kernel {
                            sum += model.embedding[[ids[start + k] as usize, ch]] as f64
                                * conv.weights[[out, ch * conv.kernel + k]] as f64;
                        }
                    }
                    best = best.max(sum);
                }
                pools.push(best);
            }
        }
        let hidden: Vec<_> = model
            .hidden_w
            .outer_iter()
            .zip(&model.hidden_b)
            .map(|(w, &b)| {
                (w.iter()
                    .zip(&pools)
                    .map(|(&w, &x)| w as f64 * x)
                    .sum::<f64>()
                    + b as f64)
                    .max(0.)
            })
            .collect();
        std::array::from_fn(|i| {
            model
                .fc_w
                .row(i)
                .iter()
                .zip(&hidden)
                .map(|(&w, &x)| w as f64 * x)
                .sum::<f64>()
                + model.fc_b[i] as f64
        })
    }

    #[test]
    fn npz_convolution_layout_pooling_dense_and_workspace_reuse() {
        let model = tiny_model();
        assert_eq!(model.embedding.row(0).to_vec(), vec![0., 0.]);
        let mut ws = Workspace::default();
        for ids in [
            vec![1, 2, 3, 0, 1, 2, 0, 0],
            vec![0; 12],
            vec![3, 2, 1, 3, 2],
        ] {
            let expected = scalar(&model, &ids);
            let actual = model.logits(&ids, &mut ws).unwrap();
            for i in 0..2 {
                assert!(
                    (actual[i] as f64 - expected[i]).abs() < 1e-5,
                    "{actual:?} != {expected:?}"
                );
            }
        }
    }
    #[test]
    fn padding_minimum_length_and_invalid_ids() {
        let model = tiny_model();
        let mut ws = Workspace::default();
        let short = [1, 2, 3];
        let mut padded = short.to_vec();
        padded.resize(MAX_BLOCK, 0);
        let expected = Cnn::percent(model.logits(&padded, &mut ws).unwrap()).unwrap();
        assert_eq!(model.score_tokens(&short, &mut ws).unwrap(), expected);
        assert_eq!(
            model
                .score_tokens_with_options(&[], None, 8, &mut ws)
                .unwrap(),
            -1.0
        );
        assert!(model.score_tokens(&[-1], &mut ws).is_err());
        assert!(model.score_tokens(&[4], &mut ws).is_err());
        assert!(model.logits(&[1], &mut ws).is_err());
    }
    #[test]
    fn output_is_two_normalized_sigmoids() {
        let actual = Cnn::percent([2., 1.]).unwrap();
        let a = 1_f64 / (1. + (-2_f64).exp());
        let b = 1_f64 / (1. + (-1_f64).exp());
        assert!((actual - a * 100. / (a + b)).abs() < 1e-5);
        assert!((actual - 100. / (1. + (-1_f64).exp())).abs() > 10.);
    }
}

/// Immutable weights can be shared by every inference thread.
pub struct Cnn {
    embedding: Array2<f32>,
    convs: Vec<Conv>,
    hidden_w: Array2<f32>,
    hidden_b: Array1<f32>,
    fc_w: Array2<f32>,
    fc_b: Array1<f32>,
}

/// Scratch allocations belong to a worker, never to the shared model.
#[derive(Default)]
pub struct Workspace {
    ids: Vec<i32>,
    embedded: Vec<f32>,
    windows: Vec<f32>,
    conv: Vec<f32>,
    pooled: Vec<f32>,
    hidden: Vec<f32>,
}

impl Cnn {
    pub fn load(path: impl AsRef<Path>) -> Result<Self> {
        let mut npz = NpzReader::new(File::open(path)?)?;
        let mut embedding: Array2<f32> = npz.by_name("embedding")?;
        let (vocab, dim) = embedding.dim();
        if vocab == 0 || dim == 0 {
            return Err(Error::invalid("empty embedding"));
        }
        embedding.row_mut(0).fill(0.0);
        let mut convs = Vec::new();
        for i in 0..4 {
            let w: Array3<f32> = npz.by_name(&format!("convl.{i}.weight"))?;
            let bias: Array1<f32> = npz.by_name(&format!("convl.{i}.bias"))?;
            let (filters, channels, kernel) = w.dim();
            if filters == 0
                || channels != dim
                || kernel == 0
                || kernel > MAX_BLOCK
                || bias.len() != filters
            {
                return Err(Error::invalid(format!("invalid convolution {i} shape")));
            }
            let w = w.as_standard_layout().into_owned();
            let weights = w
                .into_shape_with_order((filters, dim * kernel))
                .map_err(|e| Error::invalid(e.to_string()))?;
            convs.push(Conv {
                weights,
                bias,
                kernel,
            });
        }
        let hidden_w: Array2<f32> = npz.by_name("l_hid.weight")?;
        let hidden_b: Array1<f32> = npz.by_name("l_hid.bias")?;
        let fc_w: Array2<f32> = npz.by_name("l_fc.weight")?;
        let fc_b: Array1<f32> = npz.by_name("l_fc.bias")?;
        let pooled = convs.iter().map(|c| c.bias.len()).sum::<usize>();
        if hidden_w.ncols() != pooled
            || hidden_w.nrows() == 0
            || hidden_b.len() != hidden_w.nrows()
            || fc_w.dim() != (2, hidden_w.nrows())
            || fc_b.len() != 2
        {
            return Err(Error::invalid("invalid dense layer shapes"));
        }
        Ok(Self {
            embedding,
            convs,
            hidden_w,
            hidden_b,
            fc_w,
            fc_b,
        })
    }

    pub fn vocab_size(&self) -> usize {
        self.embedding.nrows()
    }
    pub fn embedding_dim(&self) -> usize {
        self.embedding.ncols()
    }
    pub fn parameter_count(&self) -> usize {
        self.convs
            .iter()
            .map(|c| c.weights.len() + c.bias.len())
            .sum::<usize>()
            + self.hidden_w.len()
            + self.hidden_b.len()
            + self.fc_w.len()
            + self.fc_b.len()
    }

    pub fn score_tokens(&self, ids: &[i32], ws: &mut Workspace) -> Result<f64> {
        self.score_tokens_with_options(ids, Some(MAX_BLOCK), MIN_BLOCK, ws)
    }

    /// As in Python, the minimum-length check follows padding/truncation.
    pub fn score_tokens_with_options(
        &self,
        ids: &[i32],
        max_len: Option<usize>,
        min_len: usize,
        ws: &mut Workspace,
    ) -> Result<f64> {
        ws.ids.clear();
        let length = max_len.filter(|&n| n > 0).unwrap_or(ids.len());
        ws.ids.extend_from_slice(&ids[..ids.len().min(length)]);
        ws.ids.resize(length, 0);
        if length < min_len {
            return Ok(-1.0);
        }
        let logits = self.forward_workspace(ws)?;
        Self::percent(logits)
    }

    /// Evaluate an already padded input, primarily for differential tests.
    pub fn logits(&self, ids: &[i32], ws: &mut Workspace) -> Result<[f32; 2]> {
        ws.ids.clear();
        ws.ids.extend_from_slice(ids);
        self.forward_workspace(ws)
    }

    pub fn percent(logits: [f32; 2]) -> Result<f64> {
        let a = 1.0_f32 / (1.0 + (-logits[0]).exp());
        let b = 1.0_f32 / (1.0 + (-logits[1]).exp());
        // Two sigmoids, normalized to a percentage. This is not softmax.
        let score = a * 100.0 / (a + b);
        if !score.is_finite() {
            return Err(Error::invalid("non-finite model result"));
        }
        Ok(f64::from(score))
    }

    fn forward_workspace(&self, ws: &mut Workspace) -> Result<[f32; 2]> {
        let length = ws.ids.len();
        let dim = self.embedding_dim();
        if self.convs.iter().any(|c| c.kernel > length) {
            return Err(Error::invalid("input shorter than a convolution kernel"));
        }
        ws.embedded.resize(length * dim, 0.0);
        for (token, row) in ws.ids.iter().zip(ws.embedded.chunks_exact_mut(dim)) {
            if *token < 0 || *token as usize >= self.vocab_size() {
                return Err(Error::invalid(format!("invalid token id: {token}")));
            }
            let source = self.embedding.row(*token as usize);
            for (target, &value) in row.iter_mut().zip(source) {
                *target = value;
            }
        }
        ws.pooled.clear();
        for conv in &self.convs {
            let rows = length - conv.kernel + 1;
            let cols = dim * conv.kernel;
            let filters = conv.bias.len();
            ws.windows.resize(rows * cols, 0.0);
            for (pos, window) in ws.windows.chunks_exact_mut(cols).enumerate() {
                for channel in 0..dim {
                    for offset in 0..conv.kernel {
                        window[channel * conv.kernel + offset] =
                            ws.embedded[(pos + offset) * dim + channel];
                    }
                }
            }
            ws.conv.resize(rows * filters, 0.0);
            general_mat_mul(
                1.0,
                &ArrayView2::from_shape((rows, cols), &ws.windows).unwrap(),
                &conv.weights.t(),
                0.0,
                &mut ArrayViewMut2::from_shape((rows, filters), &mut ws.conv).unwrap(),
            );
            let start = ws.pooled.len();
            ws.pooled.resize(start + filters, 0.0);
            for row in ws.conv.chunks_exact(filters) {
                for (i, &value) in row.iter().enumerate() {
                    ws.pooled[start + i] = ws.pooled[start + i].max(value + conv.bias[i]);
                }
            }
        }
        ws.hidden.resize(self.hidden_b.len(), 0.0);
        general_mat_mul(
            1.0,
            &ArrayView2::from_shape((1, ws.pooled.len()), &ws.pooled).unwrap(),
            &self.hidden_w.t(),
            0.0,
            &mut ArrayViewMut2::from_shape((1, ws.hidden.len()), &mut ws.hidden).unwrap(),
        );
        for (value, bias) in ws.hidden.iter_mut().zip(&self.hidden_b) {
            *value = (*value + bias).max(0.0);
        }
        let mut logits = [0.0; 2];
        general_mat_mul(
            1.0,
            &ArrayView2::from_shape((1, ws.hidden.len()), &ws.hidden).unwrap(),
            &self.fc_w.t(),
            0.0,
            &mut ArrayViewMut2::from_shape((1, 2), &mut logits).unwrap(),
        );
        for (value, bias) in logits.iter_mut().zip(&self.fc_b) {
            *value += bias;
        }
        Ok(logits)
    }
}
