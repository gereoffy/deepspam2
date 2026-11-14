#!/usr/bin/env python3
"""In-process batch=1 benchmark of the unchanged Python model, including PyPy.

Inputs: reconstructed texts and logged token-ID sequences, one per line.
Decompression, input parsing, model loading, warmup and score output are excluded
from the timed stages. BLAS is restricted to one thread before importing NumPy.
"""
import os
for variable in ("OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ[variable] = "1"

import argparse
import contextlib
import io
import json
from pathlib import Path
import platform
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("ids", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=200)
    args = parser.parse_args()
    if args.repeats <= 0 or args.warmup < 0:
        parser.error("repeats must be positive; warmup cannot be negative")
    import numpy as np
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from model import DeepSpam
    texts = args.inputs.read_text().split("\n")
    ids = args.ids.read_text().split("\n")
    if texts and texts[-1] == "": texts.pop()
    if ids and ids[-1] == "": ids.pop()
    ids = [[int(i) for i in row.split()] for row in ids]
    assert texts and len(texts) == len(ids)
    args.output.mkdir(parents=True, exist_ok=True)
    runtime = platform.python_implementation().lower()
    config = io.StringIO()
    with contextlib.redirect_stdout(config): np.show_config()
    (args.output / (runtime + "-numpy-config.txt")).write_text(config.getvalue())
    print(json.dumps({"runtime":runtime,"stage":"environment","python":sys.version,
                      "numpy":np.__version__,"architecture":platform.machine(),"blas_threads":1}),flush=True)
    start = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):
        model = DeepSpam(str(args.model_dir) + "/")
    print(json.dumps({"runtime":runtime,"stage":"load","seconds":time.perf_counter()-start,
                      "warmup_cases":args.warmup}),flush=True)

    def predict_nn(index):
        # Same per-call list truncation, padding, array creation and embedding
        # lookup as Python DeepSpam.__call__ after tokenization.
        row = ids[index][:256]
        row += [0] * (256-len(row))
        embedded = model.embedding[np.asarray([row],dtype=np.int64)]
        logits = model.model(embedded)[0]
        result = 1.0 / (1.0 + np.exp(-logits))
        return float(result[0]*100.0/(result[0]+result[1]))

    def predict_full(index):
        return model(texts[index])

    for stage,predict in (("nn",predict_nn),("full",predict_full)):
        for i in range(args.warmup): predict(i % len(texts))
        for iteration in range(args.repeats):
            scores = []
            start = time.perf_counter()
            for i in range(len(texts)): scores.append(predict(i))
            seconds = time.perf_counter()-start
            print(json.dumps({"runtime":runtime,"stage":stage,"pass":iteration,
                              "cases":len(texts),"seconds":seconds,"checksum":sum(scores)}),flush=True)
            if iteration == 0:
                (args.output / (stage+"-"+runtime+".scores")).write_text("".join("%.12f\n"%x for x in scores))


if __name__ == "__main__":
    main()
