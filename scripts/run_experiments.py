#!/usr/bin/env python
"""Section 5 experiments: train each dataset three ways, push every model through the flow,
and plot test accuracy vs. cell area.

  .venv/bin/python scripts/run_experiments.py configs/yinyang.yaml            # synth area (fast)
  .venv/bin/python scripts/run_experiments.py configs/yinyang.yaml --pnr      # + full place & route
  .venv/bin/python scripts/run_experiments.py configs/braille.yaml --calib runs/calib/calibration.json

Each point is a run under runs/<dataset>_<method>_<param>/, the table goes to results/<dataset>.csv.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

PRUNE = [0.5, 0.7, 0.9]
LAMBDAS = [0.01, 0.03, 0.1, 0.3]


def step(s, cfg, ov):
    cmd = [PY, "-m", "snn2gds", s, cfg, *[f"{k}={v}" for k, v in ov.items()]]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--pnr", action="store_true", help="also run full place & route")
    ap.add_argument("--calib", help="calibration.json from snn2gds.calibrate (c0, c1)")
    ap.add_argument("--skip-existing", action="store_true")
    a = ap.parse_args()

    import yaml
    base = yaml.safe_load(Path(a.config).read_text())
    ds = base["dataset"]
    c = {}
    if a.calib:
        cal = json.loads(Path(a.calib).read_text())
        c = {"train.c0": cal["c0"], "train.c1": cal["c1"]}

    runs = [({"name": f"{ds}_qat", "train.method": "qat"})]
    runs += [{"name": f"{ds}_prune{p}", "train.method": "qat_prune", "train.prune_frac": p} for p in PRUNE]
    runs += [{"name": f"{ds}_silicon{l}", "train.method": "qat_silicon", "train.lam": l, **c} for l in LAMBDAS]

    rows = []
    for ov in runs:
        rd = ROOT / "runs" / ov["name"]
        if not (a.skip_existing and (rd / "summary.json").exists()):
            for s in ["train", "export", "rtl", "sim", "synth"] + (["pnr"] if a.pnr else []) + ["report"]:
                step(s, a.config, ov)
        rows.append(json.loads((rd / "summary.json").read_text()))

    df = pd.DataFrame(rows)
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    df.to_csv(out / f"{ds}.csv", index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    area_col = "pnr_finish.stdcell_area_um2" if a.pnr and "pnr_finish.stdcell_area_um2" in df else "pnr_synth.synth_area_um2"
    fig, ax = plt.subplots(figsize=(5, 3.5))
    for m, g in df.groupby("method"):
        ax.plot(g[area_col], g["export.acc_int"], "o-", label=m)
    ax.set_xlabel("cell area (um$^2$, ASAP7)")
    ax.set_ylabel("test accuracy (bit-exact model)")
    ax.set_title(ds)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / f"{ds}_acc_vs_area.png", dpi=150)
    print(df[["name", "export.acc_int", "sim.spike_match", area_col]].to_string(index=False))


if __name__ == "__main__":
    main()
