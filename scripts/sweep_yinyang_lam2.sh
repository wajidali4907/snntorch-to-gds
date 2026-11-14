#!/usr/bin/env bash
# Separate lambdas for Eq. 2: zero term fixed at its best (lam=3), sweep the pow2-term lambda,
# with the original p2 and with the zero-aware p2 (nearest of 0, ±1, ±2, ±4, ...).
set -uo pipefail
cd "$(dirname "$0")/.."
C0=0.0734
one() {
  name=$1; shift
  for s in train export rtl sim synth report; do
    .venv/bin/python -m snn2gds $s configs/yinyang.yaml name=$name "$@" >> runs/sweep_logs/$name.log 2>&1 || { echo "FAIL $name at $s"; return 1; }
  done
  echo "DONE $name"
}
export -f one
mkdir -p runs/sweep_logs
B="train.method=qat_silicon train.lam=3 train.c0=$C0 train.c1=$C0"
cat <<JOBS | xargs -P 3 -L 1 bash -c 'one "$@"' _
yy_l2_0.03  $B train.lam_p2=0.03
yy_l2_0.1   $B train.lam_p2=0.1
yy_l2_0.3   $B train.lam_p2=0.3
yy_l2_1     $B train.lam_p2=1
yy_l2z_0.03 $B train.lam_p2=0.03 train.p2_zero=true
yy_l2z_0.1  $B train.lam_p2=0.1  train.p2_zero=true
yy_l2z_0.3  $B train.lam_p2=0.3  train.p2_zero=true
yy_l2z_1    $B train.lam_p2=1    train.p2_zero=true
JOBS
