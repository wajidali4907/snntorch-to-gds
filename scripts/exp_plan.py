"""Single source of truth for the paper experiments: every run, on every dataset.

Used by scripts/run_all.py (runs them), scripts/summarize_paper.py (tables/figures)
and to write EXPERIMENTS.md (to-do list with status).
"""
from __future__ import annotations

DATASETS = {   # name -> (config, run-name prefix)
    "yinyang": ("configs/yinyang.yaml", "yy"),
    "braille": ("configs/braille.yaml", "braille"),
    "ntidigits": ("configs/ntidigits.yaml", "ntidigits"),
}
C0 = 0.0734           # um^2 per |w| unit (runs/calib/calibration.json)
SEEDS = (0, 1, 2)
LOG_LAMS = ("0.3", "1", "3")
HIDDEN = {"yinyang": (32, 64, 256), "braille": (64, 256), "ntidigits": (64, 256)}

# ---- baseline tuning (QAT, seed 0, 20% of TRAIN held out as validation; test set untouched)
VAL_FRAC = 0.2
_BASE = {"yinyang": (30, 6.0), "braille": (50, 0.5), "ntidigits": (50, 1.0)}   # (epochs, init_gain) in configs/
TUNE_LR = (0.001, 0.002, 0.005)


def tune_grid(ds):
    ep, g = _BASE[ds]
    return [{"lr": lr, "epochs": e, "init_gain": gg}
            for lr in TUNE_LR for e in (ep, 2 * ep) for gg in (g / 2, g, 2 * g)]


def tune_name(ds, h, seed=0):
    return f"{DATASETS[ds][1]}_tune_lr{h['lr']}_ep{h['epochs']}_g{h['init_gain']}" + (f"_s{seed}" if seed else "")


def tune_overrides(h):
    return [f"train.lr={h['lr']}", f"train.epochs={h['epochs']}", f"train.init_gain={h['init_gain']}",
            f"train.val_frac={VAL_FRAC}"]


TUNED_FILE = "results/tuned.json"     # written by scripts/run_all.py after the tuning grid
TUNED_VARIANTS = ("qat", "prune0.5", "l1_1", "l1_3")

# ---- re-tune (Yin-Yang): the seed-0 pick (lr 0.005, gain 12) was unstable on seeds 1-2 (baseline sd 4 pts).
# Same grid, but every point trained with 3 seeds; pick by the MEAN validation accuracy over seeds.
RETUNE_DS = ("yinyang",)
RETUNE_SEEDS = (0, 1, 2)
TUNED2_FILE = "results/tuned_multiseed.json"


def tuned_overrides(ds, root, file=TUNED_FILE):
    import json
    from pathlib import Path
    h = json.loads((Path(root) / file).read_text())[ds]
    return [f"train.lr={h['lr']}", f"train.epochs={h['epochs']}", f"train.init_gain={h['init_gain']}"]


def overrides(variant: str, cp2: float | None = None, ds: str | None = None, root=".") -> list[str]:
    """Config overrides for a variant name. "T_<variant>" = <variant> with the tuned baseline settings."""
    if variant.startswith("T2_"):
        return tuned_overrides(ds, root, TUNED2_FILE) + overrides(variant[3:], cp2)
    if variant.startswith("T_"):
        return tuned_overrides(ds, root) + overrides(variant[2:], cp2)
    if variant == "qat":
        return []
    if variant.startswith("prune"):
        return ["train.method=qat_prune", f"train.prune_frac={variant[5:]}"]
    if variant.startswith("l1_"):
        return ["train.method=qat_silicon", f"train.lam={variant[3:]}", f"train.c0={C0}", "train.c1=0"]
    if variant.startswith("log"):
        assert cp2 is not None, "log variants need the fitted c_p2 (results/pow2_cost_fit.json)"
        return ["train.method=qat_silicon", "train.lam=3", f"train.c0={C0}", f"train.c1={cp2}",
                f"train.lam_p2={variant[3:]}", "train.p2_mode=log"]
    if variant.startswith("h"):
        h, rest = variant[1:].split("_", 1)
        return [f"hidden={h}"] + overrides(rest, cp2)
    raise ValueError(variant)


def run_name(ds: str, variant: str, seed: int = 0) -> str:
    p = DATASETS[ds][1]
    if variant.startswith("log") or variant.startswith(("T_", "T2_")):
        return f"{p}_{variant}_s{seed}"
    if ds == "yinyang" and seed == 0:          # names of the first Yin-Yang sweep
        return "yinyang_qat" if variant == "qat" else f"yy_{variant}"
    if seed == 0:
        return f"{p}_{variant}"
    return f"{p}_{variant}_s{seed}"


# (group, title, [(ds, variant, seed), ...]) in priority order
def plan() -> list[tuple[str, str, list[tuple[str, str, int]]]]:
    G = []
    G.append(("core", "Baseline vs. pruning vs. silicon-aware (L1, λ=3), 3 seeds",
              [(ds, v, s) for s in SEEDS for ds in DATASETS for v in ("qat", "prune0.5", "l1_3")]))
    G.append(("lam", "Silicon-aware λ sweep (accuracy-vs-area curve), seed 0",
              [(ds, f"l1_{l}", 0) for ds in DATASETS for l in ("1", "10")]))
    G.append(("log", "New log-domain power-of-two term on top of L1 (calibrated c_p2)",
              [(ds, f"log{lp}", 0) for ds in DATASETS for lp in LOG_LAMS]
              + [(ds, "log1", s) for s in (1, 2) for ds in DATASETS]
              + [("yinyang", f"log{lp}", s) for s in (1, 2) for lp in ("0.3", "3")]))
    G.append(("hidden", "Hidden-layer size: qat vs. L1 λ=3, seed 0",
              [(ds, f"h{h}_{v}", 0) for ds in DATASETS for h in HIDDEN[ds] for v in ("qat", "l1_3")]))
    G.append(("tuned", "Main comparison again with TUNED baselines (settings from the tuning grid), 3 seeds",
              [(ds, f"T_{v}", s) for s in SEEDS for ds in DATASETS for v in TUNED_VARIANTS]))
    G.append(("tuned2", "Yin-Yang again with the MULTI-SEED re-tune (pick by mean val acc over 3 seeds), 3 seeds",
              [(ds, f"T2_{v}", s) for s in SEEDS for ds in RETUNE_DS for v in TUNED_VARIANTS]))
    return G


GRT = [(ds, v, 0) for ds in DATASETS for v in ("qat", "l1_3")]   # placement + global route
