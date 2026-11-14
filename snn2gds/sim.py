"""Replay the exported test stimuli through the generated RTL and check every spike."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np

from .config import Config

REPO = Path(__file__).resolve().parent.parent


def _verilator() -> str | None:
    local = REPO / "tools" / "verilator" / "bin" / "verilator"
    if local.exists():
        return str(local)
    return shutil.which("verilator")


def run(cfg: Config, simulator: str = "auto") -> dict:
    out = cfg.run_dir.resolve()
    rtl, ref = out / "rtl", out / "ref"
    sim = out / "sim"
    shutil.rmtree(sim, ignore_errors=True)
    sim.mkdir(parents=True)
    srcs = [str(p) for p in sorted(rtl.glob("*.v"))]
    vl = _verilator()
    if simulator == "auto":
        simulator = "verilator" if vl else "iverilog"

    if simulator == "verilator":
        build = [vl, "--binary", "--timing", "-j", str(os.cpu_count()), "-Wno-fatal", "-Wno-lint",
                 "-Wno-WIDTH", "--top-module", "tb", "-O3", "-Mdir", str(sim / "obj"), *srcs]
        exe = [str(sim / "obj" / "Vtb"), f"+REF={ref}"]
    else:
        build = ["iverilog", "-g2012", "-s", "tb", "-o", str(sim / "tb.vvp"), *srcs]
        exe = ["vvp", "-n", str(sim / "tb.vvp"), f"+REF={ref}"]

    subprocess.run(build, check=True, cwd=sim, stdout=open(sim / "build.log", "w"), stderr=subprocess.STDOUT)
    res = subprocess.run(exe, cwd=sim, capture_output=True, text=True)
    (sim / "sim.log").write_text(res.stdout + res.stderr)
    print(res.stdout[-2000:])

    passed = "SPIKE_MATCH PASS" in res.stdout
    counts = np.loadtxt(sim / "rtl_counts.txt", dtype=np.int64, ndmin=2)
    labels = np.load(ref / "labels.npy")[: len(counts)]
    acc_rtl = float(np.mean(counts.argmax(1) == labels))
    m = {"simulator": simulator, "spike_match": passed, "n_samples": int(len(counts)),
         "acc_rtl_on_verify_set": acc_rtl}
    (out / "metrics_sim.json").write_text(json.dumps(m, indent=1))
    print(json.dumps(m, indent=1))
    if not passed:
        raise SystemExit("RTL spike mismatch, see " + str(sim / "sim.log"))
    return m
