"""snn2gds command line.

  python -m snn2gds <step> configs/yinyang.yaml [key=value ...]

steps: train | export | rtl | sim | synth | grt | pnr | report | all  (all = train..pnr)
Overrides use dotted keys, e.g.  train.epochs=5 quant.bw=6 name=yy_bw6
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import load_config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="snn2gds", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["train", "export", "rtl", "sim", "synth", "grt", "pnr", "report", "all"])
    ap.add_argument("config")
    ap.add_argument("overrides", nargs="*", help="dotted key=value overrides")
    ap.add_argument("--sim", default="auto", choices=["auto", "verilator", "iverilog"])
    a = ap.parse_args(argv)
    ov = dict(o.split("=", 1) for o in a.overrides)
    cfg = load_config(a.config, ov)

    steps = ["train", "export", "rtl", "sim", "pnr"] if a.step == "all" else [a.step]
    for s in steps:
        print(f"==> {s} [{cfg.name}]", flush=True)
        if s == "train":
            from .train import train
            train(cfg)
        elif s == "export":
            from .export import run_export
            run_export(cfg)
        elif s == "rtl":
            from .rtlgen import generate
            generate(cfg)
        elif s == "sim":
            from .sim import run
            run(cfg, a.sim)
        elif s in ("synth", "grt", "pnr"):
            from .pnr import run
            run(cfg, {"synth": "synth", "grt": "grt", "pnr": "finish"}[s])
        elif s == "report":
            from .report import summarize
            print(json.dumps(summarize(cfg), indent=1))


if __name__ == "__main__":
    sys.exit(main())
