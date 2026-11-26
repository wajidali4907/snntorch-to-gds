#!/usr/bin/env bash
# Yin-Yang: which training loss / bias input gives the best baseline? Scored on a 20% validation split
# (the test set is not used), 3 seeds each, common recipe: 100 epochs, batch 64, lr 0.002, gain 6.
cd "$(dirname "$0")/.."
PY=.venv/bin/python
C="configs/yinyang.yaml train.epochs=100 train.batch_size=64 train.val_frac=0.2"
run() { name=$1; shift
  [ -f runs/$name/train_log.json ] && { echo "SKIP $name"; return; }
  $PY -m snn2gds train $C name=$name "$@" > runs/explore_logs/$name.log 2>&1 && echo "DONE $name" || echo "FAIL $name"; }
export -f run; export PY C
for s in 0 1 2; do
  echo "yyx_count_s$s train.seed=$s train.loss=count"
  echo "yyx_count_b0_s$s train.seed=$s train.loss=count bias_step=0"
  echo "yyx_memstep_s$s train.seed=$s train.loss=mem_step"
  echo "yyx_memstep_b0_s$s train.seed=$s train.loss=mem_step bias_step=0"
  echo "yyx_memstep_b40_s$s train.seed=$s train.loss=mem_step bias_step=40"
  echo "yyx_memmax_b0_s$s train.seed=$s train.loss=mem_max bias_step=0"
  echo "yyx_memmean_b0_s$s train.seed=$s train.loss=mem_mean bias_step=0"
done | xargs -P 4 -L 1 bash -c 'run "$@"' _
echo ALL_DONE
