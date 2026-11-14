# snn2gds top-level flow.  Usage:
#   make setup                      # venv + python deps + verilator (once)
#   make all CFG=configs/yinyang.yaml
#   make sim CFG=configs/yinyang.yaml ARGS="name=yy_bw6 quant.bw=6"
PY   ?= .venv/bin/python
CFG  ?= configs/yinyang.yaml
ARGS ?=

.PHONY: setup train export rtl sim synth grt pnr report all flow clean
setup:
	./scripts/setup.sh

train export rtl sim synth grt pnr report all:
	$(PY) -m snn2gds $@ $(CFG) $(ARGS)

# train -> export -> rtl -> sim -> synth (fast, no place & route)
flow:
	$(PY) -m snn2gds train  $(CFG) $(ARGS)
	$(PY) -m snn2gds export $(CFG) $(ARGS)
	$(PY) -m snn2gds rtl    $(CFG) $(ARGS)
	$(PY) -m snn2gds sim    $(CFG) $(ARGS)
	$(PY) -m snn2gds synth  $(CFG) $(ARGS)
	$(PY) -m snn2gds report $(CFG) $(ARGS)

clean:
	rm -rf runs
