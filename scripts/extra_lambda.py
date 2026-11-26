"""Extra final runs: stronger area penalty (lam = 10, 30) with the tuned protocol. Same recipe as stage D of overnight.py.
Runs on the GPU while synthesis (CPU) is in progress. Prints its own table; does not write to REPORT.md."""
import json, statistics as st, sys
from concurrent.futures import ThreadPoolExecutor
sys.argv = sys.argv[:1]
sys.path.insert(0, "scripts")
import overnight as o

EXTRA = {f"l1_{l}": ["train.method=qat_silicon", f"train.lam={l}", f"train.c0={o.C0}", "train.c1=0"] for l in (10, 30)}
o.METHODS.update(EXTRA)
proto = json.loads((o.OUT / "protocol.json").read_text())
import os
proto["datasets"] = {k: v for k, v in proto["datasets"].items() if k not in os.environ.get("SNN_SKIP", "").split(",")}
jobs = o.final_jobs(proto, ["train", "export"], methods=EXTRA)
o.LOGS.mkdir(parents=True, exist_ok=True)
with ThreadPoolExecutor(3) as ex:
    for name, status in ex.map(o.run_job, jobs):
        print(name, status, flush=True)
print("| dataset | method | n | test acc % | sd | zero % |\n|---|---|---|---|---|---|")
for ds in proto["datasets"]:
    for m in EXTRA:
        acc, zero = [], []
        for s in o.SEEDS:
            f = o.RUNS / f"{o.DS[ds]}F_{m}_s{s}" / "metrics_export.json"
            if f.exists():
                e = json.loads(f.read_text()); acc.append(100 * e["acc_int"]); zero.append(100 * e["weights"]["zero"] / e["weights"]["n_weights"])
        if acc:
            print(f"| {ds} | {m} | {len(acc)} | {st.mean(acc):.1f} | {st.stdev(acc):.1f} | {st.mean(zero):.1f} |")
print("EXTRA_DONE", flush=True)
