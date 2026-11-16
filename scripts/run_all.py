#!/usr/bin/env python
"""Run every paper experiment on every dataset (plan in scripts/exp_plan.py).

  .venv/bin/python scripts/run_all.py            # run everything not done yet, 3 jobs in parallel
  .venv/bin/python scripts/run_all.py --status   # only rewrite EXPERIMENTS.md (to-do list with status)

Each run: train -> export -> rtl -> sim -> synth -> report  (skipped if runs/<name>/summary.json exists).
Order: cost-model checks (CPU) | core 3-seed comparison | λ sweep | log-pow2 term | hidden size | global route.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import exp_plan as P  # noqa: E402

PY = str(ROOT / ".venv" / "bin" / "python")
LOG = ROOT / "runs" / "paper_logs"
_lock = threading.Lock()


def say(msg):
    with _lock:
        print(f"{msg} {time.strftime('%H:%M')}", flush=True)


def done(name, grt=False):
    d = ROOT / "runs" / name
    return (d / "metrics_pnr_grt.json").exists() if grt else (d / "summary.json").exists()


def cp2():
    p = ROOT / "results" / "pow2_cost_fit.json"
    return json.loads(p.read_text())["c_p2_um2_per_nonpow2_weight"] if p.exists() else None


def one(ds, variant, seed, steps=("train", "export", "rtl", "sim", "synth", "report")):
    cfg = P.DATASETS[ds][0]
    name = P.run_name(ds, variant, seed)
    grt = steps == ("grt", "report")
    if done(name, grt):
        return say(f"SKIP {name}")
    ov = [f"name={name}", f"train.seed={seed}"] + P.overrides(variant, cp2(), ds, ROOT)
    with open(LOG / f"{name}.log", "a") as f:
        for s in steps:
            r = subprocess.run([PY, "-m", "snn2gds", s, cfg, *ov], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
            if r.returncode:
                return say(f"FAIL {name} at {s}")
    say(f"DONE {name}{' (grt)' if grt else ''}")


def tune_one(ds, h, seed=0):
    name = P.tune_name(ds, h, seed)
    if (ROOT / "runs" / name / "train_log.json").exists():
        return say(f"SKIP {name}")
    with open(LOG / f"{name}.log", "a") as f:
        r = subprocess.run([PY, "-m", "snn2gds", "train", P.DATASETS[ds][0], f"name={name}", f"train.seed={seed}",
                            *P.tune_overrides(h)], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    say(f"FAIL {name}" if r.returncode else f"DONE {name}")


def val_score(ds, h, seed=0):
    """Mean validation accuracy over the last 5 epochs (less noisy than the last epoch)."""
    p = ROOT / "runs" / P.tune_name(ds, h, seed) / "train_log.json"
    if not p.exists():
        return None
    log = json.loads(p.read_text())
    return sum(e["val_acc"] for e in log[-5:]) / len(log[-5:])


def tune(jobs):
    say("== Baseline tuning (QAT, validation split)")
    runs = [(ds, h) for ds in P.DATASETS for h in P.tune_grid(ds)]
    with ThreadPoolExecutor(jobs) as pool:
        list(pool.map(lambda r: tune_one(*r), runs))
    best = {}
    for ds in P.DATASETS:
        scored = [(val_score(ds, h), h) for h in P.tune_grid(ds)]
        scored = [x for x in scored if x[0] is not None]
        sc, h = max(scored, key=lambda x: x[0])
        default = next(v for v, g in scored if g["lr"] == 0.002 and g["epochs"] == P._BASE[ds][0]
                       and g["init_gain"] == P._BASE[ds][1])
        best[ds] = {**h, "val_acc": sc, "default_val_acc": default}
        say(f"TUNED {ds}: {h} val {sc:.3f} (default {default:.3f})")
    (ROOT / P.TUNED_FILE).write_text(json.dumps(best, indent=1))


def retune(jobs):
    say("== Multi-seed re-tune (" + ", ".join(P.RETUNE_DS) + ")")
    runs = [(ds, h, s) for ds in P.RETUNE_DS for h in P.tune_grid(ds) for s in P.RETUNE_SEEDS]
    with ThreadPoolExecutor(jobs) as pool:
        list(pool.map(lambda r: tune_one(*r), runs))
    best = {}
    for ds in P.RETUNE_DS:
        scored = []
        for h in P.tune_grid(ds):
            v = [val_score(ds, h, s) for s in P.RETUNE_SEEDS]
            if None not in v:
                m = sum(v) / len(v)
                sd = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5
                scored.append((m, sd, v, h))
        m, sd, v, h = max(scored, key=lambda x: x[0])
        best[ds] = {**h, "val_acc": m, "val_sd": sd, "val_per_seed": v,
                    "grid": [{**g, "val_mean": a, "val_sd": b} for a, b, _, g in sorted(scored, key=lambda x: -x[0])]}
        say(f"RETUNED {ds}: {h} val {m:.3f} ± {sd:.3f} per seed {[round(x, 3) for x in v]}")
    (ROOT / P.TUNED2_FILE).write_text(json.dumps(best, indent=1))


def cost_model_checks():
    """Does the cost model fitted on 32-input layers hold for 128-input layers (hidden -> output)?"""
    say("== cost-model check (128-input layer)")
    if not (ROOT / "results" / "pow2_experiment_in128.md").exists():
        subprocess.run([PY, "scripts/pow2_experiment.py", "--n-in", "128", "--n-out", "8", "--sparsity", "0.5",
                        "--tag", "_in128", "--jobs", "2"], cwd=ROOT,
                       stdout=open(LOG / "A_in128.log", "w"), stderr=subprocess.STDOUT)
    say("== cost-model check done")


def write_status():
    lines = ["# Experiment to-do list", "",
             "Auto-generated by `scripts/run_all.py --status` from `scripts/exp_plan.py`. "
             "Run everything with `.venv/bin/python scripts/run_all.py`; results in `results/paper_summary.md`.", "",
             "## 0. Cost model (synthesis only, no training)", ""]
    for tag, txt in [("_sp0", "pow2 test, 0% zeros"), ("", "pow2 test, 50% zeros"), ("_sp80", "pow2 test, 80% zeros"),
                     ("_in128", "pow2 test, 128-input layer (does the fit transfer?)")]:
        x = "x" if (ROOT / "results" / f"pow2_experiment{tag}.md").exists() else " "
        lines.append(f"- [{x}] {txt} → `results/pow2_experiment{tag}.md`")
    x = "x" if (ROOT / "results" / "pow2_cost_fit.json").exists() else " "
    lines += [f"- [{x}] fit cost model (c_nz, c_p2) → `results/pow2_cost_fit.json`", ""]
    tuned = json.loads((ROOT / P.TUNED_FILE).read_text()) if (ROOT / P.TUNED_FILE).exists() else {}
    lines += ["## Baseline tuning (QAT, seed 0, 20% of train held out; picks lr, epochs, init_gain by validation)", ""]
    for ds in P.DATASETS:
        grid = P.tune_grid(ds)
        k = sum((ROOT / "runs" / P.tune_name(ds, h) / "train_log.json").exists() for h in grid)
        pick = f" → chosen: lr {tuned[ds]['lr']}, epochs {tuned[ds]['epochs']}, init_gain {tuned[ds]['init_gain']}" \
               f" (val {100 * tuned[ds]['val_acc']:.1f}% vs default {100 * tuned[ds]['default_val_acc']:.1f}%)" \
               if ds in tuned else ""
        lines.append(f"- [{'x' if k == len(grid) else ' '}] **{ds}**: {k}/{len(grid)} grid points "
                     f"(lr {list(P.TUNE_LR)} × 2 epoch settings × 3 init gains){pick}")
    t2 = json.loads((ROOT / P.TUNED2_FILE).read_text()) if (ROOT / P.TUNED2_FILE).exists() else {}
    for ds in P.RETUNE_DS:
        grid = P.tune_grid(ds)
        k = sum((ROOT / "runs" / P.tune_name(ds, h, s) / "train_log.json").exists()
                for h in grid for s in P.RETUNE_SEEDS)
        pick = f" → chosen: lr {t2[ds]['lr']}, epochs {t2[ds]['epochs']}, init_gain {t2[ds]['init_gain']}" \
               f" (val {100 * t2[ds]['val_acc']:.1f} ± {100 * t2[ds]['val_sd']:.1f}%)" if ds in t2 else ""
        lines.append(f"- [{'x' if k == len(grid) * len(P.RETUNE_SEEDS) else ' '}] **{ds} multi-seed re-tune**: "
                     f"{k}/{len(grid) * len(P.RETUNE_SEEDS)} (grid × seeds {list(P.RETUNE_SEEDS)}){pick}")
    lines.append("")
    n_all = n_done = 0
    for i, (_, title, runs) in enumerate(P.plan(), 1):
        lines += [f"## {i}. {title}", ""]
        for ds in P.DATASETS:
            items = [(v, s) for d, v, s in runs if d == ds]
            if not items:
                continue
            cells = []
            for v, s in items:
                n = P.run_name(ds, v, s)
                ok = done(n)
                n_all += 1
                n_done += ok
                cells.append(f"[{'x' if ok else ' '}] `{n}`")
            lines.append(f"- **{ds}**: " + ", ".join(cells))
        lines.append("")
    lines += [f"## {len(P.plan()) + 1}. Placement + global route (does the saving survive layout?)", ""]
    for ds, v, s in P.GRT:
        n = P.run_name(ds, v, s)
        lines.append(f"- [{'x' if done(n, True) else ' '}] `{n}`")
    lines += ["", "## Not run (text / future work)", "",
              "- [ ] SRAM-based alternative (needs a memory macro generator): discussion only",
              "- [ ] Full detailed route + GDS: needs > 16 GB RAM",
              "- [ ] Precision paragraph and supported-operator table: writing only",
              "", f"**Training runs done: {n_done} / {n_all}**"]
    (ROOT / "EXPERIMENTS.md").write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    LOG.mkdir(parents=True, exist_ok=True)
    write_status()
    if a.status:
        return
    t = threading.Thread(target=cost_model_checks)
    t.start()
    for key, title, runs in P.plan():
        if key == "tuned":
            tune(a.jobs)
            write_status()
        if key == "tuned2":
            retune(a.jobs)
            write_status()
        say(f"== {title}")
        with ThreadPoolExecutor(a.jobs) as pool:
            list(pool.map(lambda r: one(*r), runs))
        write_status()
    t.join()
    say("== global route")
    for r in P.GRT:            # one at a time: placement/routing needs several GB each
        one(*r, steps=("grt", "report"))
    write_status()
    subprocess.run([PY, "scripts/summarize_paper.py"], cwd=ROOT, stdout=open(LOG / "summary.log", "w"))
    say("ALL DONE")


if __name__ == "__main__":
    main()
