import numpy as np

from .spm_python import SentencePieceProcessor
from .ds2prep import DS2Preprocessor


# ---------------------------------------------------------------------------
# numpy-s alacsonyszintu muveletek (a torch.nn rétegek helyettesitesere)
# ---------------------------------------------------------------------------

def _conv1d(x, weight, bias):
    """
    'valid' padding-u 1D konvolucio (megegyezik torch.nn.Conv1d(padding="valid")-val).

    x:      (batch, in_channels, seq_len)
    weight: (out_channels, in_channels, kernel_size)
    bias:   (out_channels,)
    ->      (batch, out_channels, seq_len - kernel_size + 1)
    """
    kernel_size = weight.shape[2]
    batch, in_channels, seq_len = x.shape
    out_len = seq_len - kernel_size + 1
    if out_len <= 0:
        return np.zeros((batch, weight.shape[0], 0), dtype=x.dtype)

    # csuszo ablakok, masolas nelkul (as_strided helyett sliding_window_view,
    # ami csak numpy>=1.20 ota letezik - as_strided mar 1.7 ota mukodik,
    # es ugyanazt a memoria-view trukkot hasznalja, tehat nincs sebessegveszteseg):
    s_batch, s_chan, s_seq = x.strides
    windows = np.lib.stride_tricks.as_strided(
        x,
        shape=(batch, in_channels, out_len, kernel_size),
        strides=(s_batch, s_chan, s_seq, s_seq),
        writeable=False,
    )
    out = np.einsum('bilk,oik->bol', windows, weight, optimize=True)
    out += bias[None, :, None]
    return out


def _relu(x):
    return np.maximum(x, 0)


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class DeepSpam_model:
    """A CNN sulyainak tarolasa + forward szamitas, tisztan numpy-val.
    A dropout reteget kihagyjuk, mert inference (eval) modban ugyis identitas."""

    def __init__(self, weights, filter_sizes=(2, 3, 4, 5)):
        self.filter_sizes = list(filter_sizes)
        self.conv_w = [weights["convl.%d.weight" % i] for i in range(len(filter_sizes))]
        self.conv_b = [weights["convl.%d.bias" % i] for i in range(len(filter_sizes))]
        self.hid_w = weights["l_hid.weight"]
        self.hid_b = weights["l_hid.bias"]
        self.fc_w = weights["l_fc.weight"]
        self.fc_b = weights["l_fc.bias"]

    def forward(self, x):
        # x: (batch, seq_len, ndim) -> (batch, ndim, seq_len)  [embedding -> conv1d sorrend]
        x = np.transpose(x, (0, 2, 1))

        pooled = []
        for w, b in zip(self.conv_w, self.conv_b):
            c = _relu(_conv1d(x, w, b))            # Conv1D + ReLU
            pooled.append(np.max(c, axis=2))        # GlobalMaxPooling -> (batch, filters)

        x = np.concatenate(pooled, axis=1)          # (batch, len(filter_sizes)*filters)
        x = _relu(x @ self.hid_w.T + self.hid_b)    # linear + ReLU
        x = x @ self.fc_w.T + self.fc_b             # linear -> (batch, num_classes)
        return x

    __call__ = forward


class DeepSpam:

######## Example: ############
# from model import DeepSpam
# ds=DeepSpam()   # load model
# result=ds(text) # use model

  MIN_BLOCK = 8
  MAX_BLOCK = 256

  def __init__(self, path="model/", load="deepspam_weights.npz"):
    # load SPM tokenizer & text preprocessor:
    self.tokenizer = SentencePieceProcessor(model_file=path + 'spm6.model')
    self.preprocess = DS2Preprocessor(path + "unicodes6x.map")  # text cleanup/preprocess

    # load embedding + CNN sulyok egyetlen .npz fajlbol
    # (a convert_weights.py szkripttel keszitheto el a .pt fajlokbol)
    self.load(path + load)

    # print summary:
    all_params = sum(w.size for w in (
        [self.model.hid_w, self.model.hid_b, self.model.fc_w, self.model.fc_b]
        + self.model.conv_w + self.model.conv_b
    ))
    print("MODEL: vocab=%d  embed=%d  params=%d" % (self.num_words, self.num_dim, all_params))

  def __call__(self, text, max_len=MAX_BLOCK, min_len=MIN_BLOCK):
    tokens = self.tokenize(self.preprocess([text]), max_len)  # string to token ids
    if len(tokens[0]) < min_len:
        return -1  # too short

    input_ids = np.asarray(tokens, dtype=np.int64)     # (1, seq_len)
    embedded = self.embedding[input_ids]                # (1, seq_len, ndim) - embedding lookup
    logits = self.model(embedded)                        # run the CNN model
    res = _sigmoid(logits[0])                             # get probs
    res = res[0] * 100.0 / (res[0] + res[1])              # normalize result to percent value
    return float(res)  # 0.0 ... 100.0 %

  # load the .npz saved by convert_weights.py:
  def load(self, path="model/deepspam_weights.npz"):
    weights = np.load(path)
    embedding = weights["embedding"].astype(np.float32).copy()
    embedding[0] *= 0  # token #0 = mask/padding
    self.embedding = embedding
    self.num_words, self.num_dim = embedding.shape
    self.model = DeepSpam_model(weights)

  def tokenized(self,texts):
    return [" ".join(d) for d in self.tokenizer.encode_as_pieces(self.preprocess(texts))]

  # tokenize array of texts (List[str]) to input_ids (List[int]) & optional truncating / padding:
  def tokenize(self, texts, max_len=None):
    data = []
    for d in self.tokenizer.encode(self.preprocess(texts)):
        if max_len:
            d = d[:max_len]  # truncate
            d += [0] * (max_len - len(d))  # add padding
        data.append(d)
    return data
