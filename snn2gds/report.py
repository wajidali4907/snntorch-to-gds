"""Merge per-step metrics of a run into runs/<name>/summary.json (one row of the accuracy-vs-area plot)."""
from __future__ import annotations

import json

from .config import Config


def summarize(cfg: Config) -> dict:
    out = cfg.run_dir
    row = {"name": cfg.name, "dataset": cfg.dataset, "method": cfg.train.method,
           "lam": cfg.train.lam, "prune_frac": cfg.train.prune_frac,
           "bw": cfg.quant.bw, "f": cfg.quant.f, "k": cfg.quant.k}
    for f in ["metrics_export.json", "metrics_sim.json", "metrics_pnr_synth.json", "metrics_pnr_grt.json", "metrics_pnr_finish.json"]:
        p = out / f
        if p.exists():
            d = json.loads(p.read_text())
            tag = f.removeprefix("metrics_").removesuffix(".json")
            for k, v in d.items():
                row[f"{tag}.{k}"] = v
    (out / "summary.json").write_text(json.dumps(row, indent=1))
    return row
