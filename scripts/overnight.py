#!/usr/bin/env python3
"""Overnight queue for the new baseline protocol. Every stage is resumable (finished runs are skipped).

  A  wait for scripts/explore_yinyang_readout.sh; pick the best training-loss / bias variant on Yin-Yang
  B  check that variant against the old spike-count loss on all three datasets and network sizes
  C  tuning grid (3 learning rates x 3 gains x sizes, 3 seeds) with the chosen variant
     -> per dataset: best lr / gain for the published network size (sizes are fixed, see SIZES)
  D  final runs on the full training set (float, qat, prune 50%, L1 lambda 1 and 3; 3 seeds): train + export
  E  rtl -> sim -> synth -> report for the final runs (seed 0 first)

All choices in A-C use a 20% validation split of the training data; the test set is first used in D.
Report: results/overnight/REPORT.md      Usage: scripts/overnight.py [--dry] [--from B|C|D|E]
"""
import os
import json
import statistics as st
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv/bin/python")
RUNS, OUT, LOGS = ROOT / "runs", ROOT / "results/overnight", ROOT / "runs/overnight_logs"
DRY = "--dry" in sys.argv
START = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else "A"

DS = {"yinyang": "yy", "braille": "braille", "ntidigits": "ntidigits"}
GAIN = {"yinyang": 6.0, "braille": 2.0, "ntidigits": 1.0}            # centre of the init-gain grid (g/2, g, 2g)
# Network sizes are fixed to the published ones (no size search):
#   Yin-Yang 120 hidden (Goeltz et al. 2021; Taylor et al. 2023), Braille 256-256 (Meszaros et al. 2025),
#   N-TIDIGITS 256-256 (Sun et al. 2022).
SIZES = {"yinyang": [[120]], "braille": [[256, 256]], "ntidigits": [[256, 256]]}
N_IO = {"yinyang": (4, 3), "braille": (24, 27), "ntidigits": (64, 11)}
LRS = (0.001, 0.002, 0.005)
SEEDS = (0, 1, 2)
COMMON = ["train.epochs=100", "train.batch_size=64"]
VAL = ["train.val_frac=0.2"]
C0 = 0.0734
VARIANTS = {  # stage A names (yyx_<key>_s<seed>) -> config overrides
    "count": ["train.loss=count"],
    "count_b0": ["train.loss=count", "bias_step=0"],
    "memstep": ["train.loss=mem_step"],
    "memstep_b0": ["train.loss=mem_step", "bias_step=0"],
    "memstep_b40": ["train.loss=mem_step", "bias_step=40"],
    "memmax_b0": ["train.loss=mem_max", "bias_step=0"],
    "memmean_b0": ["train.loss=mem_mean", "bias_step=0"],
}
METHODS = {"float": ["train.qat=false"], "qat": [],
           "prune0.5": ["train.method=qat_prune", "train.prune_frac=0.5"],
           "l1_1": ["train.method=qat_silicon", "train.lam=1", f"train.c0={C0}", "train.c1=0"],
           "l1_3": ["train.method=qat_silicon", "train.lam=3", f"train.c0={C0}", "train.c1=0"]}
TIMEOUT = {"train": 3 * 3600, "export": 3600, "rtl": 1800, "sim": 2 * 3600, "synth": 4 * 3600, "report": 600}


def log(msg):
    line = f"[{time.strftime('%H:%M')}] {msg}"
    print(line, flush=True)
    if not DRY:
        OUT.mkdir(parents=True, exist_ok=True)
        with open(OUT / "REPORT.md", "a") as f:
            f.write(msg + "\n")


def htag(h):
    return "x".join(map(str, h))


def n_weights(ds, h):
    s = [N_IO[ds][0], *h, N_IO[ds][1]]
    return sum(a * b for a, b in zip(s[:-1], s[1:]))


def done(name, steps):
    d = RUNS / name
    if "report" in steps:
        return (d / "summary.json").exists() and (d / "metrics_pnr_synth.json").exists()
    if "export" in steps:
        return (d / "metrics_export.json").exists()
    return (d / "train_log.json").exists()


def _cap_memory():
    """Synthesis only: cap the address space at 11 GB so a too-large design fails by itself instead of
    running the whole machine out of memory (which stopped the queue at 03:00 on 2026-11-19)."""
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (11 * 2 ** 30, 11 * 2 ** 30))


def run_job(job):
    name, ds, ov, steps = job
    if done(name, steps):
        return name, "skip"
    for s in steps:
        if s == "train" and (RUNS / name / "train_log.json").exists():
            continue
        if s == "export" and (RUNS / name / "metrics_export.json").exists():
            continue
        cmd = [PY, "-m", "snn2gds", s, f"configs/{ds}.yaml", f"name={name}", *ov]
        try:
            with open(LOGS / f"{name}.log", "a") as lf:
                r = subprocess.run(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, timeout=TIMEOUT[s],
                                   preexec_fn=_cap_memory if s == "synth" else None)
            if r.returncode != 0:
                return name, f"FAIL at {s}"
        except subprocess.TimeoutExpired:
            return name, f"TIMEOUT at {s}"
    return name, "ok"


def run_many(jobs, parallel, title):
    todo = [j for j in jobs if not done(j[0], j[3])]
    log(f"\n### {title}: {len(jobs)} runs, {len(todo)} to do, {parallel} in parallel")
    if DRY:
        for j in todo[:3]:
            print("   e.g.", j[0], " ".join(j[2]), j[3])
        return
    LOGS.mkdir(parents=True, exist_ok=True)
    t0, bad = time.time(), []
    with ThreadPoolExecutor(parallel) as ex:
        for name, status in ex.map(run_job, todo):
            if status not in ("ok", "skip"):
                bad.append(f"{name}: {status}")
                print(f"   {name}: {status}", flush=True)
    log(f"finished in {(time.time() - t0) / 60:.0f} min" + (f"; problems: {'; '.join(bad)}" if bad else ""))


def val(name):
    """Mean validation accuracy (%) over the last 5 epochs of a run, or None."""
    f = RUNS / name / "train_log.json"
    if not f.exists():
        return None
    lg = json.loads(f.read_text())
    v = [e["val_acc"] for e in lg[-5:] if "val_acc" in e]
    return 100 * sum(v) / len(v) if v else None


def stats(names):
    v = [x for x in map(val, names) if x is not None]
    if not v:
        return None, None, 0
    return sum(v) / len(v), (st.stdev(v) if len(v) > 1 else 0.0), len(v)


def pname(ds, vkey, h, lr, g, seed):
    return f"{DS[ds]}P_{vkey}_h{htag(h)}_lr{lr}_g{g}_s{seed}"


def pjob(ds, vkey, h, lr, g, seed):
    ov = COMMON + VAL + VARIANTS[vkey] + [f"hidden={json.dumps(h)}", f"train.lr={lr}", f"train.init_gain={g}",
                                         f"train.seed={seed}"]
    return (pname(ds, vkey, h, lr, g, seed), ds, ov, ["train"])


def save(name, obj):
    if not DRY:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(json.dumps(obj, indent=1))


def load(name, default=None):
    f = OUT / name
    return json.loads(f.read_text()) if f.exists() else default


# ----------------------------------------------------------------------------------------------- A
def stage_a():
    log("\n## Stage A: Yin-Yang, which training loss / bias input? (validation accuracy, 3 seeds)")
    while not DRY and subprocess.run(["pgrep", "-f", "explore_yinyang_readout"], capture_output=True).stdout.strip():
        time.sleep(60)
    rows = {}
    log("\n| variant | mean val % | sd | n |\n|---|---|---|---|")
    for k in VARIANTS:
        m, sd, n = stats([f"yyx_{k}_s{s}" for s in SEEDS])
        if m is not None:
            rows[k] = m
            log(f"| {k} | {m:.1f} | {sd:.1f} | {n} |")
    best = max(rows, key=rows.get) if rows else "memstep_b0"
    log(f"\nBest on Yin-Yang: **{best}**")
    save("stageA.json", {"best": best, "table": rows})
    return best


# ----------------------------------------------------------------------------------------------- B
def stage_b(best):
    log("\n## Stage B: chosen variant vs. spike-count loss on all datasets and sizes (default lr, gain)")
    cands = ["count"] + ([best] if best != "count" else [])
    jobs = [pjob(ds, v, h, 0.002, GAIN[ds], s) for ds in DS for h in SIZES[ds] for v in cands for s in SEEDS]
    run_many(jobs, 6, "variant check")
    tot, lines = {v: 0.0 for v in cands}, []
    log("\n| dataset | size | " + " | ".join(cands) + " |\n|---|---|" + "---|" * len(cands))
    for ds in DS:
        bestsz = {v: -1.0 for v in cands}
        for h in SIZES[ds]:
            cells = []
            for v in cands:
                m, sd, n = stats([pname(ds, v, h, 0.002, GAIN[ds], s) for s in SEEDS])
                cells.append("-" if m is None else f"{m:.1f} ± {sd:.1f}")
                if m is not None:
                    bestsz[v] = max(bestsz[v], m)
            log(f"| {ds} | {htag(h)} | " + " | ".join(cells) + " |")
        for v in cands:
            tot[v] += bestsz[v]
        lines.append((ds, bestsz))
    final = max(tot, key=tot.get)
    for ds, b in lines:
        if best in b and b[best] < b["count"] - 1.0:
            log(f"\nNOTE: on {ds} the variant {best} is {b['count'] - b[best]:.1f} points BELOW spike-count loss.")
    log(f"\nVariant used for the protocol (highest summed validation accuracy): **{final}**")
    save("stageB.json", {"final": final, "totals": tot})
    return final


# ----------------------------------------------------------------------------------------------- C
def stage_c(final):
    log(f"\n## Stage C: tuning grid with variant {final} (3 lr x 3 gains x sizes, 3 seeds, validation)")
    # to fit in one night: only tune the sizes that are within 3 points of the best size at default settings
    sizes = {}
    for ds in DS:
        sc = {htag(h): stats([pname(ds, final, h, 0.002, GAIN[ds], s) for s in SEEDS])[0] for h in SIZES[ds]}
        top = max([v for v in sc.values() if v is not None], default=None)
        sizes[ds] = [h for h in SIZES[ds] if top is None or (sc[htag(h)] is not None and sc[htag(h)] >= top - 3.0)]
        log(f"{ds}: sizes tuned = {[htag(h) for h in sizes[ds]]} (default-setting val: "
            + ", ".join(f"{k} {v:.1f}" if v is not None else f"{k} -" for k, v in sc.items()) + ")")
    grid = {ds: [(h, lr, g) for h in sizes[ds] for lr in LRS for g in (GAIN[ds] / 2, GAIN[ds], GAIN[ds] * 2)]
            for ds in DS}
    jobs = [pjob(ds, final, h, lr, g, s) for ds in DS for (h, lr, g) in grid[ds] for s in SEEDS]
    probe = None
    if False:     # disabled: synthesis of a 256-256 net needs > 4.4 GB and ran the machine out of memory
                  # next to training (2026-11-19 03:00). Kept for reference: one full-flow probe of the largest network, to learn synthesis time and memory
        ov = COMMON + VARIANTS[final] + ["hidden=[256,256]"]
        probe = ThreadPoolExecutor(1).submit(
            run_job, ("probe_ntidigits_256x256", "ntidigits", ov, ["train", "export", "rtl", "sim", "synth", "report"]))
    run_many(jobs, 5, "tuning grid")
    if probe is not None and probe.done():
        log(f"synthesis probe (ntidigits 256-256, untuned): {probe.result()[1]}")
    proto = {"variant": final, "variant_overrides": VARIANTS[final], "datasets": {}}
    for ds in DS:
        per_size = {}
        for (h, lr, g) in grid[ds]:
            m, sd, n = stats([pname(ds, final, h, lr, g, s) for s in SEEDS])
            if m is None or n < len(SEEDS):
                continue
            if htag(h) not in per_size or m > per_size[htag(h)]["val"]:
                per_size[htag(h)] = {"hidden": h, "lr": lr, "gain": g, "val": m, "sd": sd,
                                     "weights": n_weights(ds, h)}
        if not per_size:
            log(f"\n{ds}: no complete grid point, skipped")
            continue
        top = max(p["val"] for p in per_size.values())
        ok = [p for p in per_size.values() if p["val"] >= top - 1.0]
        pick = min(ok, key=lambda p: p["weights"])
        proto["datasets"][ds] = pick
        log(f"\n**{ds}** (best setting per size; pick = smallest within 1 point of the best)\n")
        log("| size | weights | lr | gain | val % | sd | picked |\n|---|---|---|---|---|---|---|")
        for p in sorted(per_size.values(), key=lambda p: p["weights"]):
            log(f"| {htag(p['hidden'])} | {p['weights']} | {p['lr']} | {p['gain']} | {p['val']:.1f} | {p['sd']:.1f} | "
                f"{'yes' if p is pick else ''} |")
    save("protocol.json", proto)
    return proto


# ----------------------------------------------------------------------------------------------- D / E
def final_jobs(proto, steps, seeds=SEEDS, methods=METHODS):
    jobs = []
    for seed in seeds:
        for m in methods:
            for ds, p in proto["datasets"].items():
                ov = COMMON + proto["variant_overrides"] + [f"hidden={json.dumps(p['hidden'])}", f"train.lr={p['lr']}",
                                                            f"train.init_gain={p['gain']}", f"train.seed={seed}"]
                jobs.append((f"{DS[ds]}F_{m}_s{seed}", ds, ov + METHODS[m], steps))
    return jobs


def final_table(proto):
    log("\n| dataset | method | n | test acc % (float row: float weights; others: bit-exact) | sd | zero % | synth area um2 (n) |\n|---|---|---|---|---|---|---|")
    for ds in proto["datasets"]:
        for m in METHODS:
            acc, zero, area = [], [], []
            for s in SEEDS:
                d = RUNS / f"{DS[ds]}F_{m}_s{s}"
                if (d / "metrics_export.json").exists():
                    e = json.loads((d / "metrics_export.json").read_text())
                    # float row: float weights on the test set (no hardware, so no area); others: bit-exact integer model
                    acc.append(100 * e["acc_snntorch" if m == "float" else "acc_int"])
                    zero.append(100 * e["weights"]["zero"] / e["weights"]["n_weights"])
                if m != "float" and (d / "metrics_pnr_synth.json").exists():
                    area.append(json.loads((d / "metrics_pnr_synth.json").read_text())["synth_area_um2"])
            if acc:
                a = f"{sum(area) / len(area):.0f} ({len(area)})" if area else "-"
                log(f"| {ds} | {m} | {len(acc)} | {sum(acc) / len(acc):.1f} | "
                    f"{(st.stdev(acc) if len(acc) > 1 else 0):.1f} | {sum(zero) / len(zero):.1f} | {a} |")


def stage_d(proto):
    log("\n## Stage D: final runs on the full training set (test accuracy from the bit-exact integer model)")
    run_many(final_jobs(proto, ["train", "export"]), 6, "final training + export")
    final_table(proto)


def stage_e(proto):
    log("\n## Stage E: Verilog, spike-match simulation and synthesis for the final runs")
    flow = ["train", "export", "rtl", "sim", "synth", "report"]
    first = final_jobs(proto, flow, seeds=(0,), methods=("qat", "l1_3"))
    run_many(first, 1, "synthesis, seed 0, qat and l1_3")
    final_table(proto)
    rest = [j for j in final_jobs(proto, flow) if j[0] not in {f[0] for f in first}]
    run_many(rest, 1, "synthesis, everything else")
    final_table(proto)


def main():
    log(f"\n# Overnight queue, started {time.strftime('%Y-%m-%d %H:%M')}" + (" (dry run)" if DRY else ""))
    order = "ABCDE"
    go = lambda s: order.index(s) >= order.index(START)
    best = stage_a() if go("A") else load("stageA.json", {"best": "memstep_b0"})["best"]
    final = stage_b(best) if go("B") else load("stageB.json", {"final": best})["final"]
    proto = stage_c(final) if go("C") else load("protocol.json")
    if not proto or not proto.get("datasets"):
        if DRY:   # show the size of the later stages with placeholder picks
            proto = {"variant_overrides": VARIANTS[final],
                     "datasets": {ds: {"hidden": SIZES[ds][-1], "lr": 0.002, "gain": GAIN[ds]} for ds in DS}}
        else:
            log("no protocol selected; stopping")
            return
    skip = [d for d in os.environ.get("SNN_SKIP", "").split(",") if d]   # e.g. SNN_SKIP=ntidigits
    if skip:
        proto["datasets"] = {k: v for k, v in proto["datasets"].items() if k not in skip}
        log(f"\n**Skipping datasets for now: {', '.join(skip)}**")
    if go("D"):
        stage_d(proto)
    stage_e(proto)
    log(f"\nALL DONE {time.strftime('%H:%M')}")


if __name__ == "__main__":
    main()
