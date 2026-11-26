#!/usr/bin/env bash
# Experiment plan for the paper (see README "Experiment map"). Each run: train -> export -> rtl -> sim -> synth -> report.
# Runs whose summary.json already exists are skipped, so this script can be re-run after an interruption.
#   A  cost model   : controlled pow2 test at 0% / 80% sparsity, then fit c_p2         (CPU only)
#   B  Yin-Yang     : seeds 1,2 for qat / L1 / prune; hidden-size sweep                (GPU + CPU, parallel with A)
#   C  new pow2 term: L1 + log-domain pow2 term (calibrated c_p2), 3 lambdas x 3 seeds
#   D  real data    : Braille and N-TIDIGITS, qat vs L1 (lambda 1, 3)
#   E  physical     : global route for the Yin-Yang baseline and the best silicon-aware run
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
C0=0.0734
LOG=runs/paper_logs
mkdir -p $LOG

one() {   # one <config> <name> [overrides...]
  cfg=$1; name=$2; shift 2
  if [ -f runs/$name/summary.json ]; then echo "SKIP $name"; return 0; fi
  for s in train export rtl sim synth report; do
    $PY -m snn2gds $s $cfg name=$name "$@" >> $LOG/$name.log 2>&1 || { echo "FAIL $name at $s"; return 1; }
  done
  echo "DONE $name $(date +%H:%M)"
}
export -f one; export PY C0 LOG
par() { xargs -P "$1" -L 1 bash -c 'one "$@"' _; }

phaseA() {
  echo "== A: cost model $(date +%H:%M)"
  $PY scripts/pow2_experiment.py --sparsity 0   --tag _sp0  > $LOG/A_sp0.log 2>&1
  $PY scripts/pow2_experiment.py --sparsity 0.8 --tag _sp80 > $LOG/A_sp80.log 2>&1
  $PY scripts/fit_pow2_cost.py > $LOG/A_fit.log 2>&1
  echo "== A done $(date +%H:%M)"; cat $LOG/A_fit.log
}

phaseB() {
  echo "== B: Yin-Yang seeds + hidden sweep $(date +%H:%M)"
  Y=configs/yinyang.yaml
  {
    for s in 1 2; do
      echo "$Y yy_qat_s$s train.seed=$s"
      echo "$Y yy_l1_3_s$s train.seed=$s train.method=qat_silicon train.lam=3 train.c0=$C0 train.c1=0"
      echo "$Y yy_prune0.5_s$s train.seed=$s train.method=qat_prune train.prune_frac=0.5"
    done
    for h in 32 64 256; do
      echo "$Y yy_h${h}_qat hidden=$h"
      echo "$Y yy_h${h}_l1_3 hidden=$h train.method=qat_silicon train.lam=3 train.c0=$C0 train.c1=0"
    done
  } | par 3
  echo "== B done $(date +%H:%M)"
}

phaseC() {
  CP2=$($PY -c "import json;print(json.load(open('results/pow2_cost_fit.json'))['c_p2_um2_per_nonpow2_weight'])")
  echo "== C: log pow2 term, c_p2=$CP2 $(date +%H:%M)"
  Y=configs/yinyang.yaml
  for s in 0 1 2; do for lp in 0.3 1 3; do
    echo "$Y yy_log${lp}_s$s train.seed=$s train.method=qat_silicon train.lam=3 train.c0=$C0 train.c1=$CP2 train.lam_p2=$lp train.p2_mode=log"
  done; done | par 3
  echo "== C done $(date +%H:%M)"
}

phaseD() {
  echo "== D: Braille / N-TIDIGITS $(date +%H:%M)"
  for ds in braille ntidigits; do
    echo "configs/$ds.yaml ${ds}_qat"
    for l in 1 3; do
      echo "configs/$ds.yaml ${ds}_l1_$l train.method=qat_silicon train.lam=$l train.c0=$C0 train.c1=0"
    done
  done | par 3
  echo "== D done $(date +%H:%M)"
}

phaseE() {
  echo "== E: global route $(date +%H:%M)"
  for n in yinyang_qat yy_l1_3; do
    if [ -f runs/$n/metrics_pnr_grt.json ]; then echo "SKIP grt $n"; continue; fi
    $PY -m snn2gds grt configs/yinyang.yaml name=$n >> $LOG/E_$n.log 2>&1 && \
      $PY -m snn2gds report configs/yinyang.yaml name=$n >> $LOG/E_$n.log 2>&1 && echo "DONE grt $n" || echo "FAIL grt $n"
  done
  echo "== E done $(date +%H:%M)"
}

phaseA &
phaseB
wait
phaseC
phaseD
phaseE
echo "ALL DONE $(date +%H:%M)"
