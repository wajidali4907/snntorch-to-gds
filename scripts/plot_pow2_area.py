"""Paper Fig. 2: measured area vs share of power-of-two weights (16x32 layer)."""
import csv
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
SETS = [("0% zero weights", "pow2_experiment_sp0.csv", "#1f77b4", "o"),
        ("50% zero weights", "pow2_experiment.csv", "#d95f02", "s"),
        ("80% zero weights", "pow2_experiment_sp80.csv", "#2ca02c", "^")]

fig, ax = plt.subplots(figsize=(4.6, 3.3))
for label, name, col, mk in SETS:
    d = defaultdict(list)
    for r in csv.DictReader(open(ROOT / "results" / name)):
        d[float(r["pow2_frac"]) * 100].append(float(r["area_um2"]))
    x = sorted(d)
    m = [np.mean(d[k]) for k in x]
    s = [np.std(d[k]) for k in x]
    ax.errorbar(x, m, yerr=s, color=col, marker=mk, ms=5, lw=1.6, capsize=3, label=label)
    print(label, [round(v) for v in m], [round(v, 1) for v in s])
ax.set_xlabel("Non-zero weights that are powers of two (%)")
ax.set_ylabel(r"Area after synthesis ($\mu$m$^2$)")
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_ylim(0, 1250)
ax.grid(alpha=0.3)
ax.legend(fontsize=8, loc="lower left")
fig.tight_layout()
fig.savefig(ROOT / "paper" / "figs" / "pow2_area.png", dpi=300)
