"""Extra pruning levels (70% and 80%) for the main comparison, 3 seeds, 3 datasets.
Resumable: every job is skipped if its result file exists.
Training runs first (5 in parallel); synthesis runs one at a time, seed 0 first."""
import json, sys, time
sys.argv = sys.argv[:1]
sys.path.insert(0, "scripts")
import overnight as o

EXTRA = {"prune0.7": ["train.method=qat_prune", "train.prune_frac=0.7"],
         "prune0.8": ["train.method=qat_prune", "train.prune_frac=0.8"]}
o.METHODS.update(EXTRA)
FLOW = ["train", "export", "rtl", "sim", "synth", "report"]


def main():
    proto = json.loads((o.OUT / "protocol.json").read_text())
    o.log(f"\n# Extra pruning levels, started {time.strftime('%Y-%m-%d %H:%M')}")
    o.run_many(o.final_jobs(proto, ["train", "export"], methods=EXTRA), 5, "pruning 70% and 80%: training + export")
    for seeds in ((0,), (1, 2)):
        o.run_many(o.final_jobs(proto, FLOW, seeds=seeds, methods=EXTRA), 1, f"pruning 70% and 80%: synthesis, seeds {seeds}")
        o.final_table(proto)
    o.log(f"\nPRUNE EXTRA DONE {time.strftime('%H:%M')}")


if __name__ == "__main__":
    main()
