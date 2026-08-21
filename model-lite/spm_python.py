#!/usr/bin/env python3
"""
spm_pure_tokenizer.py
----------------------
Tiszta Python SentencePiece tokenizalo, semmilyen C/C++ kiterjesztest
(sentencepiece, protobuf stb.) nem hasznal. Kizarolag a Python
standard konyvtarra tamaszkodik.

Tamogatja:
  - UNIGRAM tipusu .model fajlokat (pl. mT5, ALBERT, XLNet, XLM-R stilus)

A .model fajl a SentencePiece sajat protobuf formatuma. Mivel nem akarjuk
a `protobuf` csomagot es a generalt sentencepiece_model_pb2-t hasznalni,
ez a script egy minimalis, kezzel irt protobuf "wire format" dekodert
tartalmaz, ami csak a szukseges mezoket olvassa ki.
"""

from __future__ import annotations

import re
import struct
import sys
from typing import Dict, List, Optional, Tuple

META_SYMBOL = "\u2581"  # '▁' - a SentencePiece szokoz-helyettesito jele

# --------------------------------------------------------------------------
# 1) Minimalis protobuf "wire format" dekoder
#    (csak annyit tud, amennyi a .model fajl kiolvasasahoz kell)
# --------------------------------------------------------------------------

def _read_varint(data: bytes, pos: int) -> Tuple[int, int]:
    result = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def _parse_message(data: bytes) -> Dict[int, List]:
    """Egy protobuf uzenetet field_number -> [ertekek] dict-te alakit.
    varint -> int, fixed32(float) -> float, length-delimited -> bytes."""
    fields: Dict[int, List] = {}
    pos, n = 0, len(data)
    while pos < n:
        tag, pos = _read_varint(data, pos)
        field_num, wire_type = tag >> 3, tag & 0x7
        if wire_type == 0:  # varint
            value, pos = _read_varint(data, pos)
        elif wire_type == 1:  # 64-bit
            value = struct.unpack_from("<d", data, pos)[0]
            pos += 8
        elif wire_type == 2:  # length-delimited
            length, pos = _read_varint(data, pos)
            value = data[pos:pos + length]
            pos += length
        elif wire_type == 5:  # 32-bit (float)
            value = struct.unpack_from("<f", data, pos)[0]
            pos += 4
        else:
            raise ValueError(f"Nem tamogatott protobuf wire type: {wire_type}")
        fields.setdefault(field_num, []).append(value)
    return fields


# --------------------------------------------------------------------------
# 2) A .model fajl beolvasasa (ModelProto)
# --------------------------------------------------------------------------

class _Piece:
    __slots__ = ("piece", "score", "type", "id")

    def __init__(self, piece: str, score: float, ptype: int, idx: int):
        self.piece = piece
        self.score = score
        self.type = ptype  # 1=NORMAL 2=UNKNOWN 3=CONTROL 4=USER_DEFINED 5=UNUSED 6=BYTE
        self.id = idx


def _load_model_proto(path: str):
    with open(path, "rb") as f:
        data = f.read()
    top = _parse_message(data)

    pieces: List[_Piece] = []
    for idx, raw in enumerate(top.get(1, [])):
        pf = _parse_message(raw)
        piece_bytes = pf.get(1, [b""])[0]
        piece = piece_bytes.decode("utf-8", errors="replace")
        score = pf.get(2, [0.0])[0]
        ptype = pf.get(3, [1])[0]
        pieces.append(_Piece(piece, float(score), int(ptype), idx))

    model_type = 1  # default UNIGRAM
    byte_fallback = False
    if top.get(2):
        tsf = _parse_message(top[2][0])
        model_type = tsf.get(3, [1])[0]
        byte_fallback = bool(tsf.get(35, [0])[0])

    add_dummy_prefix = True
    remove_extra_ws = True
    escape_ws = True
    if top.get(3):
        nsf = _parse_message(top[3][0])
        add_dummy_prefix = bool(nsf.get(3, [1])[0])
        remove_extra_ws = bool(nsf.get(4, [1])[0])
        escape_ws = bool(nsf.get(5, [1])[0])

    return pieces, {
        "model_type": model_type,          # 1=UNIGRAM 2=BPE 3=WORD 4=CHAR
        "byte_fallback": byte_fallback,
        "add_dummy_prefix": add_dummy_prefix,
        "remove_extra_ws": remove_extra_ws,
        "escape_ws": escape_ws,
    }


# --------------------------------------------------------------------------
# 3) Tokenizalo
# --------------------------------------------------------------------------

class SentencePieceProcessor:
    def __init__(self, model_file: str):
        pieces, spec = _load_model_proto(model_file)
        print(spec) # {'model_type': 1, 'byte_fallback': False, 'add_dummy_prefix': True, 'remove_extra_ws': True, 'escape_ws': True}
        if spec["model_type"] != 1:
            raise ValueError("Nem tamogatott model tipus: %d"%(spec["model_type"]))

        self.spec = spec
        self.id2piece = [p.piece for p in pieces]
        self.piece2id: Dict[str, int] = {p.piece: p.id for p in pieces}
        self.scores: Dict[str, float] = {p.piece: p.score for p in pieces}

        self.unk_id = next((p.id for p in pieces if p.type == 2), 0)
        self.max_piece_len = max((len(p.piece) for p in pieces), default=1)

        # byte-fallback darabok: "<0x41>" stilusu tokenek
        self._byte_piece_id: Dict[int, int] = {}
        for p in pieces:
            if p.type == 6 and len(p.piece) == 6 and p.piece.startswith("<0x"):
                try:
                    b = int(p.piece[3:5], 16)
                    self._byte_piece_id[b] = p.id
                except ValueError:
                    pass

    # ---- normalizalas -----------------------------------------------
    def _normalize(self, text: str) -> str:
#        text = unicodedata.normalize("NFKC", text)
        if self.spec["remove_extra_ws"]:
            text = re.sub(r"\s+", " ", text).strip()
        if self.spec["add_dummy_prefix"]:
            text = " " + text
        if self.spec["escape_ws"]:
            text = text.replace(" ", META_SYMBOL)
        return text

    # ---- byte fallback segedfuggveny ---------------------------------
    def _char_byte_fallback(self, ch: str) -> Optional[Tuple[float, List[int]]]:
        if not self.spec["byte_fallback"]:
            return None
        ids = []
        total = 0.0
        for b in ch.encode("utf-8"):
            pid = self._byte_piece_id.get(b)
            if pid is None:
                return None
            ids.append(pid)
            total += self.scores.get(self.id2piece[pid], -1.0)
        return total, ids

    # ---- UNIGRAM: Viterbi legjobb-ut szegmentalas ---------------------
    def _encode_unigram(self, text: str) -> List[int]:
        n = len(text)
        NEG_INF = float("-inf")
        UNK_SCORE = -10.0
        dp = [NEG_INF] * (n + 1)
        dp[0] = 0.0
        back: List[Optional[Tuple[int, List[int]]]] = [None] * (n + 1)

        for i in range(1, n + 1):
            start = max(0, i - self.max_piece_len)
            best_score, best = NEG_INF, None
            for j in range(start, i):
                piece = text[j:i]
                sc = self.scores.get(piece)
                if sc is not None:
                    cand = dp[j] + sc
                    if cand > best_score:
                        best_score, best = cand, (j, [self.piece2id[piece]])
            # 1 karakteres fallback (unk vagy byte-fallback)
            j = i - 1
            ch = text[j:i]
            fb = self._char_byte_fallback(ch)
            if fb is not None:
                cand = dp[j] + fb[0]
                if cand > best_score:
                    best_score, best = cand, (j, fb[1])
            elif ch not in self.scores:
                cand = dp[j] + UNK_SCORE
                if cand > best_score:
                    best_score, best = cand, (j, [self.unk_id])
            dp[i], back[i] = best_score, best

        ids: List[int] = []
        i = n
        while i > 0:
            j, piece_ids = back[i]
            ids = piece_ids + ids
            i = j
        return ids

    # ---- publikus API ---------------------------------------------------
    def encode(self, input: str | Sequence[str], out_type=int):
        if type(input)!=list: input=[input]
        out=[]
        for text in input:
            norm = self._normalize(text)
            ids = self._encode_unigram(norm)
            if out_type is int: out.append(ids)
            else: out.append([self.id2piece[i] for i in ids])
        return out

    def encode_as_pieces(self, input: str | Sequence[str]):
        return self.encode(input, out_type=str)

    def decode(self, ids: List[int]) -> str:
        pieces = [self.id2piece[i] for i in ids if 0 <= i < len(self.id2piece)]
        text = "".join(pieces)
        text = text.replace(META_SYMBOL, " ")
        return text.strip()

    def score_of(self, pieces: List[str]) -> float:
        """Egy adott darabsorozat teljes (unigram) pontszama - hasznos
        annak eldontesehez, hogy ket eltero szegmentalas gyakorlatilag
        holtversenyben van-e (pl. tie-break miatt eltero bontas)."""
        total = 0.0
        for p in pieces:
            sc = self.scores.get(p, -10.0)
            total = total + sc
        return total


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print("Hasznalat: python3 spm_pure_tokenizer.py <model.model> <input.txt>")
        sys.exit(1)
    model_file, input_path = sys.argv[1], sys.argv[2]
    tok = SentencePieceProcessor(model_file)
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    ids = tok.encode(text)
    pieces = tok.encode(text, out_type=str)
    print("Darabok:", pieces)
    print("ID-k   :", ids)


if __name__ == "__main__":
    main()
