#!/usr/bin/env python
"""Controlled test of the Eq. 2 power-of-two term (suggested in the proposal review).

Two (or more) single layers that differ ONLY in how many non-zero weights are powers of two:
same shape, bit width, sparsity, positions, signs, clock target and P (fully parallel).
Start from non-power-of-two magnitudes, then replace a fraction of the non-zero weights by
their nearest power of two (magnitude-matched). Synthesize each with ORFS (ASAP7) and compare
measured area with what Eq. 2 predicts.

  .venv/bin/python scripts/pow2_experiment.py            -> results/pow2_experiment.{json,md,png}
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from snn2gds import pnr, rtlgen  # noqa: E402
from snn2gds.calibrate import features  # noqa: E402
from snn2gds.config import Config, QuantCfg  # noqa: E402


def is_pow2(a):
    return (a > 0) & ((a & (a - 1)) == 0)


def base_layer(rng, n_out, n_in, sparsity, lo, hi):
    """Non-power-of-two magnitudes in [lo, hi], random signs, exactly `sparsity` zeros."""
    vals = rng.integers(lo, hi + 1, size=n_out * n_in * 4)
    vals = vals[~is_pow2(vals)][: n_out * n_in]
    W = (vals * rng.choice([-1, 1], size=vals.size)).reshape(n_out, n_in)
    zero = rng.permutation(W.size)[: int(round(sparsity * W.size))]
    W.flat[zero] = 0
    return W


def with_pow2_fraction(W, frac, order):
    """Replace the first `frac` of the non-zero weights (in a fixed random order) by their nearest power of two."""
    W = W.copy()
    nz = order[W.flat[order] != 0]
    pick = nz[: int(round(frac * nz.size))]
    a = np.abs(W.flat[pick])
    p = (2 ** np.round(np.log2(a))).astype(np.int64)
    W.flat[pick] = np.sign(W.flat[pick]) * np.minimum(p, 64)
    return W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fracs", default="0,0.25,0.5,0.75,1.0")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--sparsity", type=float, default=0.5)
    ap.add_argument("--n-in", type=int, default=32)
    ap.add_argument("--n-out", type=int, default=16)
    ap.add_argument("--lo", type=int, default=3)
    ap.add_argument("--hi", type=int, default=63)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--tag", default="", help="suffix for run dirs and result files, e.g. _sp0")
    a = ap.parse_args()
    fracs = [float(x) for x in a.fracs.split(",")]
    seeds = [int(x) for x in a.seeds.split(",")]
    q = QuantCfg()
    th = int(round(q.theta * 2 ** q.f))

    cases = []
    for s in seeds:
        rng = np.random.default_rng(1000 + s)
        W0 = base_layer(rng, a.n_out, a.n_in, a.sparsity, a.lo, a.hi)
        order = rng.permutation(W0.size)
        for f in fracs:
            cases.append({"seed": s, "frac": f, "W": with_pow2_fraction(W0, f, order)})

    def one(c):
        name = f"p2exp{a.tag}_s{c['seed']}_f{int(c['frac'] * 100):03d}"
        cfg = Config(name=name, dataset="yinyang", T=16, n_verify=1, quant=q)
        out = cfg.run_dir
        out.mkdir(parents=True, exist_ok=True)
        ex = {"bw": q.bw, "f": q.f, "bu": q.bu, "k": q.k, "theta_int": th, "T": cfg.T,
              "layers": [{"W": c["W"].tolist(), "k": q.k, "theta_int": th}]}
        (out / "export.json").write_text(json.dumps(ex))
        (out / "metrics_export.json").write_text(json.dumps({"n_verify": 1}))
        rtlgen.generate(cfg)
        m = pnr.run(cfg, "synth", jobs=2)
        print(f"{name}: {m['synth_area_um2']:.1f} um^2", flush=True)
        return m["synth_area_um2"], cfg.hw.clk_period_ps

    with ThreadPoolExecutor(a.jobs) as pool:
        res = list(pool.map(one, cases))

    calib = json.loads((ROOT / "runs" / "calib" / "calibration.json").read_text())
    c0, c1, a0 = calib["c0"], calib["c1"], calib["a0"]
    cf = calib["count_fit"]
    rows = []
    for c, (area, clk) in zip(cases, res):
        W = c["W"]
        sa, sd = features(W)
        aw = np.abs(W[W != 0])
        n2, no = int(is_pow2(aw).sum()), int((~is_pow2(aw)).sum())
        rows.append({"seed": c["seed"], "pow2_frac": c["frac"], "zeros": int((W == 0).sum()),
                     "n_pow2": n2, "n_other": no, "sum_abs": sa, "sum_pow2_dist2": sd,
                     "area_um2": area, "clk_ps": clk,
                     "eq2_calibrated": a0 + c0 * sa + c1 * sd,     # c1 as fitted (negative)
                     "eq2_c1_eq_c0": a0 + c0 * sa + c0 * sd,      # c1 = c0, as used in the Eq. 2 training runs
                     "count_model": cf["base"] + cf["per_pow2_weight"] * n2 + cf["per_other_weight"] * no})

    import pandas as pd
    df = pd.DataFrame(rows)
    base = df[df.pow2_frac == 0].set_index("seed")["area_um2"]
    df["measured_change_%"] = [100 * (r.area_um2 / base[r.seed] - 1) for r in df.itertuples()]
    for col in ["eq2_calibrated", "eq2_c1_eq_c0", "count_model"]:
        b = df[df.pow2_frac == 0].set_index("seed")[col]
        df[col + "_change_%"] = [100 * (getattr(r, col) / b[r.seed] - 1) for r in df.itertuples()]
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    df.to_csv(out / f"pow2_experiment{a.tag}.csv", index=False)
    g = df.groupby("pow2_frac").agg(
        area_mean=("area_um2", "mean"), area_std=("area_um2", "std"),
        measured=("measured_change_%", "mean"), measured_std=("measured_change_%", "std"),
        eq2_calibrated=("eq2_calibrated_change_%", "mean"), eq2_c1_eq_c0=("eq2_c1_eq_c0_change_%", "mean"),
        count_model=("count_model_change_%", "mean")).round(2).reset_index()
    md = (f"Layer {a.n_out}x{a.n_in}, 8-bit, {int(a.sparsity * 100)}% zeros, |w| in [{a.lo},{a.hi}], "
          f"clock {res[0][1]} ps, P = fully parallel, seeds {seeds}. Change % is relative to pow2_frac = 0.\n\n"
          + g.to_markdown(index=False))
    (out / f"pow2_experiment{a.tag}.md").write_text(md + "\n")
    print(md)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4))
    x = g.pow2_frac * 100
    ax.errorbar(x, g.measured, yerr=g.measured_std, fmt="o-", color="k", capsize=3, label="measured (ORFS synth)")
    ax.plot(x, g.eq2_c1_eq_c0, "s--", label="Eq. 2, c1 = c0 (as trained)")
    ax.plot(x, g.eq2_calibrated, "^--", label="Eq. 2, fitted c1 (negative)")
    ax.plot(x, g.count_model, "d:", label="per-weight count model")
    ax.axhline(0, color="grey", lw=0.5)
    ax.set_xlabel("% of non-zero weights that are powers of two")
    ax.set_ylabel("area change vs. 0% (%)")
    ax.set_title(f"Same layer, sparsity {int(a.sparsity * 100)}%: does Eq. 2 predict area?")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / f"pow2_experiment{a.tag}.png", dpi=150)


if __name__ == "__main__":
    main()
