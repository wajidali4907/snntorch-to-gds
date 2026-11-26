"""Extract w, beta, theta from a trained snnTorch model and build the bit-exact reference.

Writes into runs/<name>/:
  export.json            integer weights + fixed-point params
  ref/stim.hex           input spikes for the first n_verify test samples (one line per step)
  ref/expected_l<l>.hex  expected spikes of every layer (one line per step)
  metrics_export.json    float/int accuracy, snnTorch-vs-int spike match, weight stats
"""
from __future__ import annotations

import json
import math

import numpy as np
import torch

from . import datasets
from .config import Config
from .model import SNN
from .quant import int_forward, weight_to_int


def extract(model: SNN, cfg: Config) -> dict:
    q = cfg.quant
    layers = []
    for fc, lif in zip(model.fcs, model.lifs):
        beta = float(lif.beta)
        k = round(-math.log2(1.0 - beta))
        assert abs(beta - (1 - 2.0 ** -k)) < 1e-6, f"beta={beta} is not 1-2^-k"
        thr = float(lif.threshold)
        w = (fc.weight * fc.mask).detach().cpu().numpy()
        layers.append({"W": weight_to_int(w, fc.bw, fc.f), "k": k,
                       "theta_int": int(round(thr * 2 ** fc.f))})
    ks = {l["k"] for l in layers}
    ths = {l["theta_int"] for l in layers}
    assert len(ks) == 1 and len(ths) == 1, "per-layer k/theta not supported yet"
    return {"bw": q.bw, "f": q.f, "bu": q.bu, "k": ks.pop(), "theta_int": ths.pop(),
            "T": cfg.T, "layers": layers}


def weight_stats(Ws):
    allw = np.concatenate([W.ravel() for W in Ws])
    nz = allw[allw != 0]
    a = np.abs(nz)
    pow2 = np.sum((a & (a - 1)) == 0)
    return {"n_weights": int(allw.size), "zero": int(np.sum(allw == 0)),
            "pow2": int(pow2), "other": int(nz.size - pow2)}


def _hex_lines(bits: np.ndarray) -> list[str]:
    """bits [T, N] -> T hex strings, bit i of the word = channel i."""
    n = bits.shape[1]
    width = (n + 3) // 4
    out = []
    for row in bits:
        v = 0
        for i in np.nonzero(row)[0]:
            v |= 1 << int(i)
        out.append(f"{v:0{width}x}")
    return out


def run_export(cfg: Config):
    out = cfg.run_dir
    n_in, n_out = datasets.n_inputs(cfg.dataset, cfg.bias_step), datasets.N_CLASSES[cfg.dataset]
    model = SNN(cfg, n_in, n_out)
    model.load_state_dict(torch.load(out / "model.pt", map_location="cpu"))
    model.eval()
    ex = extract(model, cfg)
    Ws = [l["W"] for l in ex["layers"]]

    _, (xte, yte) = datasets.load(cfg.dataset, cfg.T, cfg.bias_step)
    x = xte.transpose(1, 0, 2)                       # [T, N, C]
    int_spk, overflow = int_forward(x, Ws, ex["theta_int"], ex["k"], ex["bu"])
    with torch.no_grad():
        sn_spk = [s.numpy().astype(np.uint8) for s in model(torch.from_numpy(x).float())]

    match = [float(np.mean(a == b)) for a, b in zip(int_spk, sn_spk)]
    sample_match = float(np.mean(np.all([(a == b).all(axis=(0, 2)) for a, b in zip(int_spk, sn_spk)], axis=0)))
    acc_int = float(np.mean(int_spk[-1].sum(0).argmax(1) == yte))
    acc_snn = float(np.mean(sn_spk[-1].sum(0).astype(np.int64).argmax(1) == yte))

    # stimuli + expected spikes for RTL replay
    nv = min(cfg.n_verify, len(xte))
    ref = out / "ref"
    ref.mkdir(exist_ok=True)
    stim, exp = [], [[] for _ in Ws]
    for n in range(nv):
        stim += _hex_lines(x[:, n])
        for l, s in enumerate(int_spk):
            exp[l] += _hex_lines(s[:, n])
    (ref / "stim.hex").write_text("\n".join(stim) + "\n")
    for l, e in enumerate(exp):
        (ref / f"expected_l{l}.hex").write_text("\n".join(e) + "\n")
    np.save(ref / "labels.npy", yte[:nv])

    js = dict(ex)
    js["layers"] = [{"W": l["W"].tolist(), "k": l["k"], "theta_int": l["theta_int"]} for l in ex["layers"]]
    (out / "export.json").write_text(json.dumps(js))
    metrics = {"acc_snntorch": acc_snn, "acc_int": acc_int,
               "spike_match_snntorch_vs_int_per_layer": match,
               "sample_match_snntorch_vs_int": sample_match,
               "membrane_overflow": overflow, "n_verify": nv,
               "weights": weight_stats(Ws)}
    (out / "metrics_export.json").write_text(json.dumps(metrics, indent=1))
    print(json.dumps(metrics, indent=1))
    if overflow:
        print("WARNING: membrane overflowed bu bits in the integer model; increase quant.bu")
    return ex, metrics
