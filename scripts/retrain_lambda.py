"""Retrain with a lambda-only loss (no c0, c1, no scale constant):
    L = L_task + (1/N_w) * (lam0 * sum|w| + lam1 * sum d(w))
w is the trained weight (real units, 1/16 of the integer weight); d(w) = sin^2(pi*log2|w_int|).
In the config this is c0 = 1/16 (integer -> real units) and c1 = 1.
The old runs stay in runs/*F_l1_* and are not touched. New run names: <ds>F_r<lam0>[_p<lam1>]_s<seed>.
 1  L1 alone: lam0 in {1, 3, 10, 30}, 3 datasets
 2  L1 + power-of-two: Yin-Yang lam0 in {1, 3} x lam1 in {0.1, 0.3}; Braille, N-TIDIGITS (3, 0.1), (3, 0.3), (30, 0.3)
 3  power-of-two term alone on Yin-Yang: lam1 in {0.1, 0.3, 1}
 4  RTL-to-GDS of Yin-Yang L1 lam0 = 1 and 3, seed 0 (1.5 ns clock), to replace the old layouts
Resumable. Training runs 5 in parallel; synthesis one at a time, seed 0 first."""
import json, os, shutil, subprocess, sys, time
sys.argv = sys.argv[:1]
sys.path.insert(0, "scripts")
import overnight as o


def m(lam0, lam1=0):
    return ["train.method=qat_silicon", "train.c0=0.0625", "train.c1=1", f"train.lam={lam0}",
            f"train.lam_p2={lam1}", "train.p2_mode=log"]


L1 = {f"r{a}": m(a) for a in (1, 3, 10, 30)}
YY = {f"r{a}_p{p}": m(a, p) for a in (1, 3) for p in (0.1, 0.3)}
YY.update({f"r0_p{p}": m(0, p) for p in (0.1, 0.3, 1)})
BIG = {"r3_p0.1": m(3, 0.1), "r3_p0.3": m(3, 0.3), "r30_p0.3": m(30, 0.3)}
o.METHODS.update({**L1, **YY, **BIG})
FLOW = ["train", "export", "rtl", "sim", "synth", "report"]


def jobs(proto, steps, seeds=o.SEEDS, p2=False):
    if not p2:
        return o.final_jobs(proto, steps, seeds=seeds, methods=L1)
    out = []
    for j in o.final_jobs(proto, steps, seeds=seeds, methods={**YY, **BIG}):
        meth = j[0].split("F_", 1)[1].rsplit("_s", 1)[0]
        if meth in (YY if j[1] == "yinyang" else BIG):
            out.append(j)
    return out


def gds(meth):
    src, name = o.RUNS / f"yyF_{meth}_s0", f"yyG_{meth}_s0"
    dst = o.RUNS / name
    if (dst / "metrics_pnr_finish.json").exists():
        return "skip"
    if not (src / "metrics_sim.json").exists():
        return "no spike-checked RTL"
    dst.mkdir(exist_ok=True)
    shutil.copytree(src / "rtl", dst / "rtl", dirs_exist_ok=True)
    for f in ("export.json", "metrics_export.json", "metrics_sim.json"):
        shutil.copy(src / f, dst / f)
    env = {k: v for k, v in os.environ.items() if k != "DISPLAY"}
    with open(o.LOGS / f"{name}.log", "a") as lf:
        r = subprocess.run([o.PY, "-m", "snn2gds", "pnr", str(src / "config.yaml"), f"name={name}",
                            "hw.clk_period_ps=1500", "hw.num_cores=4"], cwd=o.ROOT, env=env,
                           stdout=lf, stderr=subprocess.STDOUT)
    return "ok" if r.returncode == 0 else "FAIL"


def main():
    proto = json.loads((o.OUT / "protocol.json").read_text())
    o.log(f"\n# Lambda-only retraining, started {time.strftime('%Y-%m-%d %H:%M')}")
    o.run_many(jobs(proto, ["train", "export"]), 5, "lambda-only L1: training + export")
    o.run_many(jobs(proto, ["train", "export"], p2=True), 5, "lambda-only L1 + pow2: training + export")
    o.final_table(proto)
    o.run_many(jobs(proto, FLOW, (0,)), 1, "lambda-only L1: synthesis, seed 0")
    o.run_many(jobs(proto, FLOW, (1, 2)), 1, "lambda-only L1: synthesis, seeds 1 and 2")
    o.final_table(proto)
    o.run_many(jobs(proto, FLOW, (0,), p2=True), 1, "lambda-only L1 + pow2: synthesis, seed 0")
    o.run_many(jobs(proto, FLOW, (1, 2), p2=True), 1, "lambda-only L1 + pow2: synthesis, seeds 1 and 2")
    o.final_table(proto)
    o.log("\n## RTL-to-GDS, Yin-Yang seed 0, lambda-only L1")
    for meth in ("r1", "r3"):
        st = gds(meth)
        f = o.RUNS / f"yyG_{meth}_s0" / "metrics_pnr_finish.json"
        o.log(f"- yyG_{meth}_s0: {st}; {f.read_text().strip() if f.exists() else '-'}")
    o.log(f"\nLAMBDA RETRAIN DONE {time.strftime('%H:%M')}")


if __name__ == "__main__":
    if os.environ.get("LIST"):   # LIST=1: print the jobs and exit
        proto = json.loads((o.OUT / "protocol.json").read_text())
        for j in jobs(proto, FLOW) + jobs(proto, FLOW, p2=True):
            print(j[0], " ".join(x for x in j[2] if "lam" in x or "train.c" in x))
    else:
        main()
