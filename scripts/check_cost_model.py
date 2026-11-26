"""Does the fitted area model (Eq. count in the paper, fitted on 16x32 test layers) predict the area of the
real trained networks? Read-only: uses export.json (integer weights) and metrics_pnr_synth.json of the final runs."""
import json, glob, os
import numpy as np

FIT = json.load(open("results/pow2_cost_fit.json"))
B, CNZ, CP2 = FIT["base_um2"] / 16, FIT["c_nz_um2_per_nonzero_weight"], FIT["c_p2_um2_per_nonpow2_weight"]
C0 = 0.0734
rows = []
for d in sorted(glob.glob("runs/*F_*_s[012]")):
    m, e = f"{d}/metrics_pnr_synth.json", f"{d}/export.json"
    if not (os.path.exists(m) and os.path.exists(e)):
        continue
    name = os.path.basename(d); ds, rest = name.split("F_"); method, seed = rest.rsplit("_s", 1)
    nz = np2 = l1 = neurons = 0
    for L in json.load(open(e))["layers"]:
        W = np.array(L["W"], float); a = np.abs(W[W != 0])
        nz += a.size; np2 += float(np.sum(np.sin(np.pi * np.log2(a)) ** 2)); l1 += float(a.sum()); neurons += W.shape[0]
    area = json.load(open(m))["synth_area_um2"]
    rows.append(dict(ds=ds, method=method, seed=int(seed), area=area, neurons=neurons, nz=nz, np2=np2, l1=l1,
                     pred=B * neurons + CNZ * nz + CP2 * np2))
print(f"{len(rows)} designs; model: {B:.1f}/neuron + {CNZ:.3f}*Nnz + {CP2:.3f}*Nnp2\n")
out = {}
for ds in ["yy", "braille", "ntidigits"]:
    r = [x for x in rows if x["ds"] == ds]
    A = np.array([x["area"] for x in r]); P = np.array([x["pred"] for x in r])
    syn = np.array([CNZ * x["nz"] + CP2 * x["np2"] for x in r]); L1 = np.array([C0 * x["l1"] for x in r])
    def fit(x):   # A = a + b*x
        b, a = np.polyfit(x, A, 1); res = A - (a + b * x); return a, b, 1 - res.var() / A.var()
    a1, b1, r1 = fit(syn); a2, b2, r2 = fit(L1)
    err = (P - A) / A * 100
    print(f"== {ds}: {len(r)} designs, area {A.min():.0f}..{A.max():.0f} um2")
    print(f"   direct prediction (no refit): mean error {err.mean():+.1f}%, worst {np.abs(err).max():.1f}%")
    print(f"   count model  A = {a1:.0f} + {b1:.2f} * (0.531 Nnz + 1.228 Nnp2):  R2 = {r1:.3f}   (slope 1.00 = constants carry over)")
    print(f"   L1 term      A = {a2:.0f} + {b2:.2f} * (0.0734 sum|w|):            R2 = {r2:.3f}")
    q = np.mean([x["area"] for x in r if x["method"] == "qat"]); qp = np.mean([x["pred"] for x in r if x["method"] == "qat"])
    for mth in ["prune0.5", "l1_1", "l1_3"]:
        s = [x for x in r if x["method"] == mth]
        if s:
            ms = 100 * (1 - np.mean([x["area"] for x in s]) / q); ps = 100 * (1 - np.mean([x["pred"] for x in s]) / qp)
            print(f"   saving vs QAT, {mth:9s}: measured {ms:5.1f}%   predicted {ps:5.1f}%   (n={len(s)})")
    out[ds] = dict(n=len(r), direct_mean_err_pct=float(err.mean()), direct_max_abs_err_pct=float(np.abs(err).max()),
                   count_slope=float(b1), count_r2=float(r1), l1_slope=float(b2), l1_r2=float(r2))
    print()
json.dump(dict(per_dataset=out, rows=rows), open("results/cost_model_check.json", "w"), indent=1)
