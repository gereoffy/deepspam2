#!/usr/bin/env python3
"""Differential test against model/, using logged token IDs independently of SPM.

Run from the repository root after cargo build --release --manifest-path model-rs/Cargo.toml.
Only this development tool needs Python/NumPy; neither Rust executable does.
"""
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import argparse
import contextlib
import importlib.util
import io
import json
import lzma
from pathlib import Path
import random
import re
import subprocess
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from model import DeepSpam


def run(binary, directory, command, rows):
    result = subprocess.run([str(binary), "--model-dir", str(directory), command],
                            input="\n".join(rows) + "\n", text=True, capture_output=True, check=True)
    return result.stdout.splitlines()


def corpus_cases(path, count):
    rng = random.Random(20261114)
    sample = []
    seen = 0
    with lzma.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            match = re.match(r"^\s*(-?\d+)%: ?(.*)$", line.rstrip("\r\n"))
            if not match:
                continue
            seen += 1
            slot = seen - 1 if seen <= count else rng.randrange(seen)
            if slot < count:
                case = {"pieces": match[2].split(), "score": int(match[1])}
                case["text"] = "".join(case["pieces"]).replace("▁", " ")
                if seen <= count:
                    sample.append(case)
                else:
                    sample[slot] = case
    print("sampled", len(sample), "of", seen, "corpus rows", flush=True)
    return sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "model-rs/target/release/deepspam-model")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "model")
    parser.add_argument("--corpus", type=Path, default=ROOT / "deepspam2.res.xz")
    parser.add_argument("--cases", type=Path, help="Reuse sampled JSONL with text, pieces and score fields")
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--end-to-end-samples", type=int, default=100)
    parser.add_argument("--logit-atol", type=float, default=0.0001)
    parser.add_argument("--score-atol", type=float, default=0.001)
    args = parser.parse_args()
    if args.samples <= 0:
        parser.error("samples must be positive")
    if args.cases:
        cases = [json.loads(line) for line in args.cases.open(encoding="utf-8")]
        cases = random.Random(218).sample(cases, min(args.samples, len(cases)))
    else:
        cases = corpus_cases(args.corpus, args.samples)
    with contextlib.redirect_stdout(io.StringIO()):
        ds = DeepSpam(str(args.model_dir) + "/")

    # Real text plus every mapping key, NFKC sequences, lookalikes and controls.
    texts = [c["text"] for c in cases]
    keys = [c for c in ds.preprocess.unimap if c not in "\r\n"]
    probes = ["".join(keys[i:i+128]) for i in range(0, len(keys), 128)]
    probes += ["ＡＢＣ ﬁ ① e\u0301 Ä ä ß Straße", "АВЕКМНОРСТХ аеорсухѕіј", "a\x1cb\x1dc\x1ed\x1fe", "", "   ", "a\u200bb\ufeffc"]
    preprocessing = texts + probes
    expected_prep = ds.preprocess(preprocessing)
    actual_prep = run(args.binary, args.model_dir, "preprocess", preprocessing)
    prep_diffs = sum(a != b for a,b in zip(actual_prep, expected_prep))
    assert len(actual_prep) == len(expected_prep)
    assert prep_diffs == 0, "preprocessing differences: %d" % prep_diffs

    # The log's token sequence is the same NN input for both implementations.
    ids = [[ds.tokenizer.piece2id.get(piece, ds.tokenizer.unk_id) for piece in c["pieces"]] for c in cases]
    fixed = [row[:256] + [0] * max(0, 256-len(row)) for row in ids]
    raw = run(args.binary, args.model_dir, "score-ids", [" ".join(map(str,row)) for row in ids])
    actual = np.array([[float(v) for v in row.split("\t")] for row in raw])
    assert actual.shape == (len(cases),3)
    start = time.monotonic()
    expected = []
    for row in fixed:
        logits = ds.model(ds.embedding[np.asarray([row],dtype=np.int64)])[0]
        prob = 1.0 / (1.0 + np.exp(-logits))
        percent = prob[0] * 100.0 / (prob[0] + prob[1])
        expected.append([float(percent),float(logits[0]),float(logits[1])])
    expected = np.array(expected)
    delta = np.abs(actual-expected)
    assert np.isfinite(actual).all() and np.isfinite(expected).all()
    assert delta[:,0].max() <= args.score_atol, "score error: %g" % delta[:,0].max()
    assert delta[:,1:].max() <= args.logit_atol, "logit error: %g" % delta[:,1:].max()

    # Exercise the combined preprocessing -> SPM -> CNN path as well.
    end_texts = texts[:args.end_to_end_samples]
    end_actual = list(map(float, run(args.binary,args.model_dir,"score",end_texts)))
    end_expected = [ds(text) for text in end_texts]
    end_diffs = [abs(a-b) for a,b in zip(end_actual,end_expected)]
    # SPM may legitimately choose another equally good path. Report this separately.
    tokenized = run(args.binary,args.model_dir,"tokenize",end_texts)
    py_tokenized = ds.tokenized(end_texts)
    token_matches = [a==b for a,b in zip(tokenized,py_tokenized)]
    for match,error in zip(token_matches,end_diffs):
        if match:
            assert error <= args.score_atol, "end-to-end score error: %g" % error
    report = {
        "nn_cases":len(cases), "preprocess_cases":len(preprocessing), "preprocess_differences":prep_diffs,
        "max_percent_error":float(delta[:,0].max()), "max_logit_error":float(delta[:,1:].max()),
        "mean_percent_error":float(delta[:,0].mean()),
        "logged_integer_matches_python":sum(int(row[0])==c["score"] for row,c in zip(expected,cases)),
        "logged_integer_matches_rust":sum(int(row[0])==c["score"] for row,c in zip(actual,cases)),
        "logged_integer_matches_python_with_0_1_offset":sum(int(row[0]+.1)==c["score"] for row,c in zip(expected,cases)),
        "logged_integer_matches_rust_with_0_1_offset":sum(int(row[0]+.1)==c["score"] for row,c in zip(actual,cases)),
        "end_to_end_cases":len(end_texts), "tokenizer_matches":sum(token_matches),
        "end_to_end_max_percent_error":max(end_diffs,default=0),
        "reference_seconds":round(time.monotonic()-start,3),
    }
    print(json.dumps(report,indent=2),flush=True)


if __name__ == "__main__":
    main()
