"""Yin-Yang only: a power-of-two term that is balanced against the zero term.
Same loss and same zero-term strength as the existing L1 runs (c0 = 0.0734, lam0 = 1 or 3), so the
results compare directly with yyF_l1_1 and yyF_l1_3. Only the power-of-two strength changes.
Strength of the power-of-two term = lam1 * 0.0734 (the old run used 1.228, which is lam1 = 16.7 here).
 A  lam0 in {1, 3} x lam1 in {0.3, 1, 3}
 B  power-of-two term alone: lam0 = 0, lam1 in {1, 3}
3 seeds. Resumable. Training 5 in parallel, then synthesis one at a time, seed 0 first."""
import json, os, sys, time
sys.argv = sys.argv[:1]
sys.path.insert(0, "scripts")
import overnight as o

S = o.C0


def m(lam0, lam1):
    return ["train.method=qat_silicon", f"train.c0={S}", f"train.c1={S}", f"train.lam={lam0}",
            f"train.lam_p2={lam1}", "train.p2_mode=log"]


YY = {f"b{a}_p{p}": m(a, p) for a in (1, 3) for p in (0.3, 1, 3)}
YY.update({f"b0_p{p}": m(0, p) for p in (1, 3)})
o.METHODS.update(YY)
FLOW = ["train", "export", "rtl", "sim", "synth", "report"]


def jobs(proto, steps, seeds=o.SEEDS):
    return [j for j in o.final_jobs(proto, steps, seeds=seeds, methods=YY) if j[1] == "yinyang"]


def main():
    proto = json.loads((o.OUT / "protocol.json").read_text())
    o.log(f"\n# Yin-Yang balanced power-of-two test, started {time.strftime('%Y-%m-%d %H:%M')}")
    o.run_many(jobs(proto, ["train", "export"]), 5, "Yin-Yang balanced pow2: training + export")
    for seeds in ((0,), (1, 2)):
        o.run_many(jobs(proto, FLOW, seeds), 1, f"Yin-Yang balanced pow2: synthesis, seeds {seeds}")
    o.final_table(proto)
    o.log(f"\nYY BALANCED DONE {time.strftime('%H:%M')}")


if __name__ == "__main__":
    if os.environ.get("LIST"):
        proto = json.loads((o.OUT / "protocol.json").read_text())
        for j in jobs(proto, FLOW):
            print(j[0], " ".join(x for x in j[2] if "lam" in x or "train.c" in x))
    else:
        main()
