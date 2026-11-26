#!/usr/bin/env python
"""Fit a per-weight area model from the controlled power-of-two experiments (runs/p2exp*).

  area = base + c_nz * (#non-zero weights) + c_p2 * sum sin^2(pi*log2|w|)

c_nz is the cost of any non-zero weight; c_p2 is the extra cost of a weight that is far
(in log scale) from a power of two. c_p2 is what `train.p2_mode=log train.c1=<c_p2>` uses.
Writes results/pow2_cost_fit.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from snn2gds.train import pow2_log_dist  # noqa: E402


def main():
    rows = []
    for d in sorted((ROOT / "runs").glob("p2exp*")):
        m, e = d / "metrics_pnr_synth.json", d / "export.json"
        if not (m.exists() and e.exists()):
            continue
        if "in128" in d.name:   # the published fit uses only the 45 layers of size 16x32
            continue
        W = np.array(json.loads(e.read_text())["layers"][0]["W"])
        rows.append({"run": d.name, "n_nz": int((W != 0).sum()),
                     "p2dist": float(pow2_log_dist(torch.from_numpy(W).double()).sum()),
                     "area": json.loads(m.read_text())["synth_area_um2"]})
    X = np.array([[1, r["n_nz"], r["p2dist"]] for r in rows], float)
    y = np.array([r["area"] for r in rows])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    r2 = 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)
    res = {"base_um2": coef[0], "c_nz_um2_per_nonzero_weight": coef[1],
           "c_p2_um2_per_nonpow2_weight": coef[2], "r2": float(r2), "n_runs": len(rows),
           "max_abs_err_um2": float(np.abs(y - pred).max()),
           "note": "layer 16x32, 8-bit, ASAP7 ORFS synth, clock 1000 ps; pow2 distance = sin^2(pi*log2|w|)"}
    (ROOT / "results" / "pow2_cost_fit.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
