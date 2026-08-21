#!/usr/bin/env python3
"""
Konvertalja a DeepSpam pytorch sulyait (.pt fajlok) egyetlen numpy .npz
fajlba, hogy a modell futtatasahoz (inference) mar ne kelljen a pytorch
fuggoseg - csak numpy.

Ezt a szkriptet csak EGYSZER kell lefuttatni (ott, ahol van pytorch),
utana a "model/deepspam_weights.npz" fajlt hasznalja a tiszta numpy-s
__init__.py.

Hasznalat:
    python convert_weights.py [model_dir]     # alapertelmezes: model/

Bemenet (model_dir-ben):
    embeddings6.pt   - torch.Tensor, alak: (num_words, num_dim)
    deepspam.pt       - torch modell state_dict (Conv1d + Linear sulyok)

Kimenet:
    <model_dir>/deepspam_weights.npz
        kulcsok: "embedding", "convl.0.weight", "convl.0.bias", ...,
                 "l_hid.weight", "l_hid.bias", "l_fc.weight", "l_fc.bias"
"""
import sys
import numpy as np
import torch


def convert(model_dir="model/"):
    if not model_dir.endswith("/"):
        model_dir += "/"

    print("Betoltes: %sembeddings6.pt" % model_dir)
    embedding = torch.load(model_dir + "embeddings6.pt", map_location="cpu")
    embedding = embedding.detach().cpu().numpy().astype(np.float32)

    print("Betoltes: %sdeepspam.pt" % model_dir)
    state_dict = torch.load(model_dir + "deepspam.pt", map_location="cpu")

    weights = {"embedding": embedding}
    for k, v in state_dict.items():
        weights[k] = v.detach().cpu().numpy().astype(np.float32)

    out_path = model_dir + "deepspam_weights.npz"
    np.savez(out_path, **weights)

    print("Elmentve: %s" % out_path)
    print("Kulcsok:", sorted(weights.keys()))
    print("embedding alak:", embedding.shape)


if __name__ == "__main__":
    model_dir = sys.argv[1] if len(sys.argv) > 1 else "model/"
    convert(model_dir)
