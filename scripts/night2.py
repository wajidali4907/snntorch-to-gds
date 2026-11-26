"""Second night queue (2026-11-20). Resumable: every job is skipped if its result file exists.
 1. remaining seed-2 synthesis of the main comparison
 2. training + export: stronger penalty (lam = 10, 30) and L1 lam=3 + log power-of-two term (lam_p2 = 1)
 3. synthesis of those designs, seed 0 first
 4. placement + global routing for seed 0 QAT and L1 lam=3, one design per dataset
Synthesis and routing run one at a time; training never runs next to them."""
import json, os, resource, subprocess, sys, time
sys.argv = sys.argv[:1]
sys.path.insert(0, "scripts")
import overnight as o

CP2 = json.load(open("results/pow2_cost_fit.json"))["c_p2_um2_per_nonpow2_weight"]
SIL = ["train.method=qat_silicon", f"train.c0={o.C0}"]
EXTRA = {"l1_10": SIL + ["train.lam=10", "train.c1=0"],
         "l1_30": SIL + ["train.lam=30", "train.c1=0"],
         "l1_3_log1": SIL + ["train.lam=3", f"train.c1={CP2}", "train.lam_p2=1", "train.p2_mode=log"]}
o.METHODS.update(EXTRA)
FLOW = ["train", "export", "rtl", "sim", "synth", "report"]


def note(msg):
    o.log(msg)


def grt(name, ds, ov):
    d = o.RUNS / name
    if (d / "metrics_pnr_grt.json").exists():
        return "skip"
    if (d / ".grt_tried").exists():
        return "failed before, not retried"
    (d / ".grt_tried").write_text(time.strftime("%H:%M"))
    cap = lambda: resource.setrlimit(resource.RLIMIT_AS, (13 * 2 ** 30, 13 * 2 ** 30))
    try:
        with open(o.LOGS / f"{name}.log", "a") as lf:
            r = subprocess.run([o.PY, "-m", "snn2gds", "grt", f"configs/{ds}.yaml", f"name={name}", *ov], cwd=o.ROOT,
                               stdout=lf, stderr=subprocess.STDOUT, timeout=5 * 3600, preexec_fn=cap)
        return "ok" if r.returncode == 0 else "FAIL"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def main():
    proto = json.loads((o.OUT / "protocol.json").read_text())
    note(f"\n# Night queue 2, started {time.strftime('%Y-%m-%d %H:%M')}")
    note("\n## 1. Remaining synthesis of the main comparison")
    main_methods = ("float", "qat", "prune0.5", "l1_1", "l1_3")
    o.run_many(o.final_jobs(proto, FLOW, methods=main_methods), 1, "synthesis, main comparison")
    note("\n## 2. Extra training: lam = 10, 30 and L1 + log power-of-two term")
    o.run_many(o.final_jobs(proto, ["train", "export"], methods=EXTRA), 5, "extra training + export")
    o.final_table(proto)
    note("\n## 3. Synthesis of the extra designs")
    o.run_many(o.final_jobs(proto, FLOW, seeds=(0,), methods=EXTRA), 1, "extra synthesis, seed 0")
    o.final_table(proto)
    note("\n## 4. Placement and global routing, seed 0 (QAT and L1 lam=3)")
    for j in o.final_jobs(proto, FLOW, seeds=(0,), methods=("qat", "l1_3")):
        st = grt(j[0], j[1], j[2])
        f = o.RUNS / j[0] / "metrics_pnr_grt.json"
        m = json.loads(f.read_text()) if f.exists() else {}
        note(f"- {j[0]}: {st}; stdcell area after global route {m.get('grt_stdcell_area_um2', '-')} um2, "
             f"setup slack {m.get('grt_setup_ws_ps', '-')} ps")
    note("\n## 5. Synthesis of the extra designs, seeds 1 and 2")
    o.run_many(o.final_jobs(proto, FLOW, seeds=(1, 2), methods=EXTRA), 1, "extra synthesis, seeds 1 and 2")
    o.final_table(proto)
    note(f"\nNIGHT2 DONE {time.strftime('%H:%M')}")


if __name__ == "__main__":
    main()
