#!/bin/bash
# Full RTL-to-GDS for the Yin-Yang 4-120-3 network (seed 0), relaxed clock (1.5 ns), 4 cores.
# Reuses the trained, spike-checked RTL of runs/yyF_<method>_s0; writes runs/yyG_<method>_s0.
cd "$(dirname "$0")/.."
for m in l1_3 l1_1 qat; do
  src=runs/yyF_${m}_s0; dst=runs/yyG_${m}_s0
  [ -f $dst/metrics_pnr_finish.json ] && continue
  mkdir -p $dst && cp -r $src/rtl $src/export.json $src/metrics_export.json $src/metrics_sim.json $dst/
  echo "[$(date +%H:%M)] start $dst"
  env -u DISPLAY .venv/bin/python -m snn2gds pnr $src/config.yaml name=yyG_${m}_s0 hw.clk_period_ps=1500 hw.num_cores=4 \
    && echo "[$(date +%H:%M)] OK $dst" || echo "[$(date +%H:%M)] FAIL $dst"
done
echo "GDS DONE $(date +%H:%M)"
