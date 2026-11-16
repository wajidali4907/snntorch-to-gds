#!/usr/bin/env python
"""Collect all paper experiments (scripts/exp_plan.py) into results/paper_summary.md + figures.

Per dataset: 3-seed comparison, λ sweep, log-pow2 term, hidden size, global route.
Unified: one row per dataset (baseline vs. pruning vs. silicon-aware), and figures
results/paper_acc_vs_area.png, results/paper_saving.png.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import exp_plan as P  # noqa: E402

RES = ROOT / "results"


def get(name):
    p = ROOT / "runs" / name / "summary.json"
    if not p.exists():
        return None
    s = json.loads(p.read_text())
    w = s.get("export.weights", {})
    return {"run": name, "acc": 100 * s.get("export.acc_int", np.nan), "match": s.get("sim.spike_match"),
            "area": s.get("pnr_synth.synth_area_um2", np.nan), "zero": w.get("zero"), "pow2": w.get("pow2"),
            "other": w.get("other"), "n_w": w.get("n_weights"),
            "grt_stdcell": s.get("pnr_grt.grt_stdcell_area_um2"), "grt_core": s.get("pnr_grt.grt_core_area_um2"),
            "grt_wns": s.get("pnr_grt.grt_setup_ws_ps")}


def group(ds, variant, seeds=P.SEEDS, label=None):
    rows = [r for s in seeds if (r := get(P.run_name(ds, variant, s)))]
    if not rows:
        return None
    d = pd.DataFrame(rows)
    nz = d.n_w - d.zero
    return {"variant": label or variant, "n": len(d), "acc": d.acc.mean(), "acc_sd": d.acc.std(ddof=0),
            "area": d.area.mean(), "area_sd": d.area.std(ddof=0),
            "zero_%": 100 * (d.zero / d.n_w).mean(), "pow2_%_of_nz": 100 * (d.pow2 / nz).mean(),
            "spike_match": "all" if (d.match == 1.0).all() else f"{(d.match == 1.0).sum()}/{len(d)}"}


def fmt(rows, base_area, base_acc):
    d = pd.DataFrame([r for r in rows if r])
    if d.empty:
        return "_no runs yet_"
    d["Δacc_pts"] = d.acc - base_acc
    d["area_saving_%"] = 100 * (1 - d.area / base_area)
    for c in ["acc", "acc_sd", "Δacc_pts", "area_saving_%", "zero_%", "pow2_%_of_nz"]:
        d[c] = d[c].round(1)
    for c in ["area", "area_sd"]:
        d[c] = d[c].round(0)
    cols = ["variant", "n", "acc", "acc_sd", "Δacc_pts", "area", "area_sd", "area_saving_%", "zero_%",
            "pow2_%_of_nz", "spike_match"]
    return d[cols].to_markdown(index=False)


LABEL = {"qat": "QAT baseline", "prune0.5": "QAT + prune 50%", "l1_3": "silicon-aware L1 λ=3"}


def dataset_section(ds):
    base = group(ds, "qat")
    if not base:
        return [f"## {ds}", "", "_no runs yet_", ""], None
    ba, bc = base["area"], base["acc"]
    out = [f"## {ds}", "", "### Main comparison (mean over seeds; Δ and saving vs. QAT baseline)", ""]
    core = [group(ds, v, label=LABEL[v]) for v in ("qat", "prune0.5", "l1_3")]
    out += [fmt(core, ba, bc), ""]
    lam = [group(ds, f"l1_{l}", (0,), f"L1 λ={l} (seed 0)") for l in ("0.3", "1", "3", "10")]
    out += ["### λ sweep (seed 0)", "", fmt(lam, ba, bc), ""]
    lg = [group(ds, "l1_3", label="L1 λ=3 only")] + \
         [group(ds, f"log{lp}", label=f"L1 λ=3 + log-pow2 λp={lp}") for lp in P.LOG_LAMS]
    out += ["### New log-domain power-of-two term", "", fmt(lg, ba, bc), ""]
    hs = []
    for h in P.HIDDEN[ds] + (128,):
        for v in ("qat", "l1_3"):
            vv = v if h == 128 else f"h{h}_{v}"
            hs.append((h, group(ds, vv, (0,), f"hidden {h}: {LABEL[v]}")))
    hs = [g for _, g in sorted(hs, key=lambda x: x[0])]
    out += ["### Hidden-layer size (seed 0; saving vs. hidden-128 baseline)", "", fmt(hs, ba, bc), ""]
    g = [r for v in ("qat", "l1_3") if (r := get(P.run_name(ds, v, 0))) and r["grt_stdcell"]]
    if len(g) == 2:
        d = pd.DataFrame(g)[["run", "acc", "area", "grt_stdcell", "grt_core", "grt_wns"]]
        d["grt_saving_%"] = [0.0, 100 * (1 - d.grt_stdcell[1] / d.grt_stdcell[0])]
        out += ["### After placement + global route (seed 0)", "", d.round(1).to_markdown(index=False), ""]
    tl = {"qat": "QAT baseline", "prune0.5": "QAT + prune 50%", "l1_1": "silicon-aware L1 λ=1",
          "l1_3": "silicon-aware L1 λ=3"}
    tb = group(ds, "T_qat")
    if tb:
        tr = [group(ds, f"T_{v}", label=f"tuned: {tl[v]}") for v in P.TUNED_VARIANTS]
        out += ["### Main comparison with TUNED baselines (mean over seeds; vs. tuned QAT)", "",
                fmt(tr, tb["area"], tb["acc"]), ""]
    tb2 = group(ds, "T2_qat")
    if tb2:
        tr = [group(ds, f"T2_{v}", label=f"re-tuned: {tl[v]}") for v in P.TUNED_VARIANTS]
        out += ["### Main comparison with MULTI-SEED re-tuned baseline (mean over seeds; vs. re-tuned QAT)", "",
                fmt(tr, tb2["area"], tb2["acc"]), ""]
    best_log = max((x for x in lg[1:] if x), key=lambda x: -x["area"] if x["acc"] >= bc - 1 else -1e9, default=None)
    uni = {"dataset": ds, "baseline_acc": bc, "baseline_area": ba}
    for k, x in [("prune", core[1]), ("L1", core[2]), ("L1+log", best_log)]:
        if x:
            uni[f"{k}_Δacc"] = x["acc"] - bc
            uni[f"{k}_saving_%"] = 100 * (1 - x["area"] / ba)
    if tb:
        uni["tuned_baseline_acc"] = tb["acc"]
        for v in ("prune0.5", "l1_1", "l1_3"):
            x = group(ds, f"T_{v}")
            if x:
                uni[f"tuned_{v}_Δacc"] = x["acc"] - tb["acc"]
                uni[f"tuned_{v}_saving_%"] = 100 * (1 - x["area"] / tb["area"])
    if tb2:
        uni["retuned_baseline_acc"] = tb2["acc"]
        for v in ("prune0.5", "l1_1", "l1_3"):
            x = group(ds, f"T2_{v}")
            if x:
                uni[f"retuned_{v}_Δacc"] = x["acc"] - tb2["acc"]
                uni[f"retuned_{v}_saving_%"] = 100 * (1 - x["area"] / tb2["area"])
    if best_log:
        uni["L1+log_variant"] = best_log["variant"].split("+ ")[-1]
    return out, uni


def figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(13, 4))
    style = {"qat": ("QAT", "k", "o"), "prune": ("prune", "tab:red", "v"), "l1": ("silicon L1", "tab:blue", "s"),
             "log": ("silicon L1 + log-pow2", "tab:green", "D")}
    for ax, ds in zip(axs, P.DATASETS):
        pref = P.DATASETS[ds][1]
        names = [d.name for d in (ROOT / "runs").iterdir()
                 if d.name.startswith(pref + "_") or (ds == "yinyang" and d.name == "yinyang_qat")]
        for n in names:
            r = get(n)
            if not r or "_h" in n:
                continue
            k = ("log" if "_log" in n else "prune" if "prune" in n else "l1" if "_l1_" in n
                 else "qat" if "qat" in n else None)
            if k is None or ("l2" in n or "eq2" in n):
                continue
            lab, c, m = style[k]
            ax.scatter(r["area"], r["acc"], color=c, marker=m, s=30, alpha=0.8, label=lab)
        h, l = ax.get_legend_handles_labels()
        u = dict(zip(l, h))
        ax.legend(u.values(), u.keys(), fontsize=7)
        ax.set_title(ds)
        ax.set_xlabel("synthesized area (µm², ASAP7)")
        ax.grid(alpha=0.3)
    axs[0].set_ylabel("test accuracy (%, bit-exact)")
    fig.tight_layout()
    fig.savefig(RES / "paper_acc_vs_area.png", dpi=150)


def main():
    out = ["# Paper results", "",
           "All accuracies are from the bit-exact integer model (identical to RTL simulation; "
           "`spike_match` = every spike of every layer matched in Verilator). Area = ORFS/Yosys synthesized "
           "cell area, ASAP7, 1 GHz target, fully parallel (P = N_in).", ""]
    unified = []
    for ds in P.DATASETS:
        sec, uni = dataset_section(ds)
        out += sec
        if uni:
            unified.append(uni)
    if unified:
        u = pd.DataFrame(unified).round(1)
        out[4:4] = ["## Unified results (one row per dataset; Δacc in points, saving vs. QAT baseline)", "",
                    u.to_markdown(index=False), ""]
    for f, t in [("pow2_experiment_sp0", "0% zeros"), ("pow2_experiment", "50% zeros"),
                 ("pow2_experiment_sp80", "80% zeros"), ("pow2_experiment_in128", "128-input layer")]:
        p = RES / f"{f}.md"
        if p.exists():
            out += [f"## Controlled power-of-two test ({t})", "", p.read_text()]
    p = RES / "pow2_cost_fit.json"
    if p.exists():
        out += ["## Fitted cost model", "", "```json", p.read_text().strip(), "```"]
    (RES / "paper_summary.md").write_text("\n".join(out) + "\n")
    figures()
    if unified:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        u = pd.DataFrame(unified)
        fig, ax = plt.subplots(figsize=(6, 3.5))
        x = np.arange(len(u))
        for i, (k, c) in enumerate([("prune", "tab:red"), ("L1", "tab:blue"), ("L1+log", "tab:green")]):
            if f"{k}_saving_%" in u:
                ax.bar(x + (i - 1) * 0.27, u[f"{k}_saving_%"].fillna(0), 0.27, color=c, label=k)
                for xi, s, da in zip(x, u[f"{k}_saving_%"], u[f"{k}_Δacc"]):
                    if not np.isnan(s):
                        ax.annotate(f"{da:+.1f}", (xi + (i - 1) * 0.27, s), ha="center", va="bottom", fontsize=6)
        ax.set_xticks(x, u.dataset)
        ax.set_ylabel("area saving vs. QAT (%)")
        ax.set_title("Area saving (labels: Δ accuracy, points)")
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3, axis="y")
        fig.tight_layout()
        fig.savefig(RES / "paper_saving.png", dpi=150)
    print("\n".join(out))


if __name__ == "__main__":
    main()
