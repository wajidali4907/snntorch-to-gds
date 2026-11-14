"""Fit c0, c1 of the silicon-aware loss (Eq. 2) from measured synthesis area.

Builds small single-layer designs whose integer weights come from controlled
mixtures (zero / power-of-two / arbitrary, at different magnitudes), synthesizes
each with ORFS (ASAP7), and least-squares fits

    area = a0 + c0 * sum|w| + c1 * sum (w - p2(w))^2          (w in integer units)

Results: runs/calib/calibration.json  ->  pass to training with
    train.c0=<c0> train.c1=<c1>   (or use `python -m snn2gds.calibrate --print-args`)
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch

from . import pnr, rtlgen
from .config import Config, QuantCfg
from .quant import nearest_pow2


def features(W: np.ndarray) -> tuple[float, float]:
    w = torch.from_numpy(W.astype(np.float64))
    return float(w.abs().sum()), float(((w - nearest_pow2(w)) ** 2).sum())


def _sample_weights(rng, n_out, n_in, p_zero, p_pow2, mag_bits, bw):
    hi = 2 ** (bw - 1) - 1
    W = np.zeros((n_out, n_in), np.int64)
    u = rng.random((n_out, n_in))
    sign = rng.choice([-1, 1], size=(n_out, n_in))
    pw = 2 ** rng.integers(0, mag_bits, size=(n_out, n_in))
    other = rng.integers(1, min(2 ** mag_bits, hi) + 1, size=(n_out, n_in))
    other = np.where((other & (other - 1)) == 0, np.minimum(other + 1, hi), other)  # force non-pow2
    W = np.where(u < p_zero, 0, np.where(u < p_zero + p_pow2, sign * pw, sign * other))
    return W


def build_cases(n_cases=16, n_in=32, n_out=16, bw=8, seed=0):
    rng = np.random.default_rng(seed)
    cases = []
    for c in range(n_cases):
        p_zero = rng.uniform(0, 0.8)
        p_pow2 = rng.uniform(0, 1 - p_zero)
        mag = int(rng.integers(2, bw))
        cases.append(_sample_weights(rng, n_out, n_in, p_zero, p_pow2, mag, bw))
    return cases


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=16)
    ap.add_argument("--n-in", type=int, default=32)
    ap.add_argument("--n-out", type=int, default=16)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--refit", action="store_true", help="re-fit from existing runs/calib_case*/ results")
    a = ap.parse_args(argv)
    q = QuantCfg()
    root = Path("runs") / "calib"
    cases = build_cases(a.cases, a.n_in, a.n_out, q.bw)

    def one(i):
        cfg = Config(name=f"calib_case{i:02d}", dataset="yinyang", T=16, n_verify=1, quant=q)
        out = cfg.run_dir
        out.mkdir(parents=True, exist_ok=True)
        th = int(round(q.theta * 2 ** q.f))
        ex = {"bw": q.bw, "f": q.f, "bu": q.bu, "k": q.k, "theta_int": th, "T": cfg.T,
              "layers": [{"W": cases[i].tolist(), "k": q.k, "theta_int": th}]}
        (out / "export.json").write_text(json.dumps(ex))
        (out / "metrics_export.json").write_text(json.dumps({"n_verify": 1}))
        rtlgen.generate(cfg)
        m = pnr.run(cfg, "synth", jobs=2)
        return m["synth_area_um2"]

    if a.refit:   # reuse areas from a previous run
        areas = [json.loads((Path("runs") / f"calib_case{i:02d}" / "metrics_pnr_synth.json").read_text())["synth_area_um2"]
                 for i in range(len(cases))]
    else:
        with ThreadPoolExecutor(a.jobs) as pool:
            areas = list(pool.map(one, range(len(cases))))
    F = np.array([features(W) for W in cases])
    A = np.c_[np.ones(len(F)), F]
    coef, *_ = np.linalg.lstsq(A, np.array(areas), rcond=None)
    pred = A @ coef
    r2 = 1 - np.sum((areas - pred) ** 2) / np.sum((areas - np.mean(areas)) ** 2)
    res = {"a0": coef[0], "c0": coef[1], "c1": coef[2], "r2": float(r2),
           "units": "um^2 per integer-weight unit (ASAP7, ORFS synth)",
           "cases": [{"sum_abs": f[0], "sum_pow2_dist2": f[1], "area": a} for f, a in zip(F.tolist(), areas)]}
    # diagnostic: area per non-zero weight class (not differentiable, but shows the true per-weight cost)
    def counts(W):
        a = np.abs(W[W != 0])
        n_pow2 = int(np.sum((a & (a - 1)) == 0))
        return n_pow2, int(a.size - n_pow2)
    Cn = np.array([counts(W) for W in cases], float)
    coef_n, *_ = np.linalg.lstsq(np.c_[np.ones(len(Cn)), Cn], np.array(areas), rcond=None)
    pred_n = np.c_[np.ones(len(Cn)), Cn] @ coef_n
    res["count_fit"] = {"base": coef_n[0], "per_pow2_weight": coef_n[1], "per_other_weight": coef_n[2],
                        "r2": float(1 - np.sum((areas - pred_n) ** 2) / np.sum((areas - np.mean(areas)) ** 2))}
    for cs, (n2, no) in zip(res["cases"], Cn.tolist()):
        cs["n_pow2"], cs["n_other"] = n2, no
    if coef[2] <= 0:
        print("WARNING: c1 <= 0: (w - p2(w))^2 does not track area for these cases; see count_fit")
    root.mkdir(parents=True, exist_ok=True)
    (root / "calibration.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("a0", "c0", "c1", "r2", "count_fit")}, indent=1))
    print(f"use: train.c0={coef[1]:.6g} train.c1={coef[2]:.6g}")


if __name__ == "__main__":
    main()
