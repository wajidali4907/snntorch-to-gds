#!/usr/bin/env python
"""Tabulate accuracy vs. area for a set of runs against a baseline, and plot it.

  .venv/bin/python scripts/compare.py yinyang_qat 'yy_*'  -> results/compare_yinyang.{csv,md,png}
"""
from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def row(name):
    p = ROOT / "runs" / name / "summary.json"
    if not p.exists():
        return None
    s = json.loads(p.read_text())
    w = s.get("export.weights", {})
    cfg = __import__("yaml").safe_load((ROOT / "runs" / name / "config.yaml").read_text())
    label = s["method"]
    if label == "qat_silicon":
        t = cfg["train"]
        if t["c1"] == 0:
            label += " (zero term only)"
        elif t.get("lam_p2", -1) >= 0:
            label += f" (λ0={t['lam']}, sweep λ1{', p2 incl. 0' if t.get('p2_zero') else ''})"
        else:
            label += " (full Eq. 2, λ1=λ0)"
    return {"run": name, "method": s["method"], "variant": label, "lam": s["lam"], "lam_p2": cfg["train"].get("lam_p2", -1), "p2_zero": cfg["train"].get("p2_zero", False), "prune": s["prune_frac"],
            "acc": s.get("export.acc_int"), "spike_match": s.get("sim.spike_match"),
            "zero": w.get("zero"), "pow2": w.get("pow2"), "other": w.get("other"),
            "area": s.get("pnr_synth.synth_area_um2"), "cells": s.get("pnr_synth.synth_cells")}


def main():
    base, pats = sys.argv[1], sys.argv[2:]
    names = sorted({d.name for d in (ROOT / "runs").iterdir() for p in pats if fnmatch.fnmatch(d.name, p)})
    names = [base] + [n for n in names if n != base and n != "yy_smoke"]
    df = pd.DataFrame([r for n in names if (r := row(n))])
    b = df.iloc[0]
    df["d_acc_pts"] = (df["acc"] - b["acc"]) * 100
    df["area_saving_%"] = (1 - df["area"] / b["area"]) * 100
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    tag = base.split("_")[0]
    df.to_csv(out / f"compare_{tag}.csv", index=False)
    fmt = df.copy()
    fmt["acc"] = (fmt["acc"] * 100).round(1)
    for c in ["area", "d_acc_pts", "area_saving_%"]:
        fmt[c] = fmt[c].round(1)
    md = fmt.drop(columns=["cells"]).to_markdown(index=False)
    (out / f"compare_{tag}.md").write_text(md + "\n")
    print(md)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4))
    for m, g in df.groupby("variant"):
        g = g.sort_values("area")
        ax.plot(g["area"], g["acc"] * 100, "o-" if len(g) > 1 else "*", ms=8, label=m)
        for _, r in g.iterrows():
            ax.annotate(r["run"], (r["area"], r["acc"] * 100), fontsize=6, xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("synthesized cell area (µm², ASAP7)")
    ax.set_ylabel("test accuracy (%)")
    ax.set_title(f"{tag}: accuracy vs. area")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / f"compare_{tag}.png", dpi=150)


if __name__ == "__main__":
    main()
