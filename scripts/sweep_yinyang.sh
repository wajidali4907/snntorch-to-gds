#!/usr/bin/env bash
# Area-reduction sweep on Yin-Yang: pruning and silicon-aware training vs. the qat baseline.
# Runs 3 jobs in parallel; each: train -> export -> rtl -> sim -> synth -> report.
set -uo pipefail
cd "$(dirname "$0")/.."
C0=0.0734   # from runs/calib/calibration.json
one() {
  name=$1; shift
  for s in train export rtl sim synth report; do
    .venv/bin/python -m snn2gds $s configs/yinyang.yaml name=$name "$@" >> runs/sweep_logs/$name.log 2>&1 || { echo "FAIL $name at $s"; return 1; }
  done
  echo "DONE $name"
}
export -f one; export C0
mkdir -p runs/sweep_logs
cat <<JOBS | xargs -P 3 -L 1 bash -c 'one "$@"' _
yy_prune0.5 train.method=qat_prune train.prune_frac=0.5
yy_prune0.7 train.method=qat_prune train.prune_frac=0.7
yy_prune0.9 train.method=qat_prune train.prune_frac=0.9
yy_l1_0.3  train.method=qat_silicon train.lam=0.3 train.c0=$C0 train.c1=0
yy_l1_1    train.method=qat_silicon train.lam=1   train.c0=$C0 train.c1=0
yy_l1_3    train.method=qat_silicon train.lam=3   train.c0=$C0 train.c1=0
yy_l1_10   train.method=qat_silicon train.lam=10  train.c0=$C0 train.c1=0
yy_eq2_1   train.method=qat_silicon train.lam=1   train.c0=$C0 train.c1=$C0
yy_eq2_3   train.method=qat_silicon train.lam=3   train.c0=$C0 train.c1=$C0
JOBS
