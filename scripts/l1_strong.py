"""Stronger L1 settings on N-TIDIGITS (lam = 100, 300, 1000; paper lambda0 = 7.3, 22, 73), 3 seeds.
Purpose: reach the area of 70% and 80% pruning with the L1 penalty.
Resumable: every job is skipped if its result file exists.
Training runs first (3 in parallel); synthesis runs one at a time, seed 0 first."""
import json, sys, time
sys.argv = sys.argv[:1]
sys.path.insert(0, "scripts")
import overnight as o

EXTRA = {f"l1_{l}": ["train.method=qat_silicon", f"train.lam={l}", f"train.c0={o.C0}", "train.c1=0"] for l in (100, 300, 1000)}
o.METHODS.update(EXTRA)
FLOW = ["train", "export", "rtl", "sim", "synth", "report"]


def main():
    proto = json.loads((o.OUT / "protocol.json").read_text())
    proto["datasets"] = {k: v for k, v in proto["datasets"].items() if k == "ntidigits"}
    o.log(f"\n# Stronger L1 on N-TIDIGITS, started {time.strftime('%Y-%m-%d %H:%M')}")
    o.run_many(o.final_jobs(proto, ["train", "export"], methods=EXTRA), 3, "strong L1: training + export")
    for seeds in ((0,), (1, 2)):
        o.run_many(o.final_jobs(proto, FLOW, seeds=seeds, methods=EXTRA), 1, f"strong L1: synthesis, seeds {seeds}")
        o.final_table(proto)
    o.log(f"\nL1 STRONG DONE {time.strftime('%H:%M')}")


if __name__ == "__main__":
    main()
