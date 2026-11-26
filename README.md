# snn2gds: snnTorch to ASIC

`snn2gds` takes a spiking neural network trained in [snnTorch](https://github.com/jeshraghian/snntorch) and turns it
into a digital circuit on the ASAP7 7 nm kit. It checks that the circuit gives the same spikes as the trained model,
and it measures the circuit area with OpenROAD.

```
train (snnTorch) -> export integer weights -> generate Verilog -> simulate and check spikes -> synthesize (area) -> layout (GDS)
```

What it supports:

- Fully connected networks with one or more hidden layers of leaky integrate-and-fire (LIF) neurons.
- 8-bit weights that are built into the logic as constants (no multiplier, no weight memory).
- Three training methods: quantization-aware training (QAT), magnitude pruning, and weight penalties (L1 and power-of-two).
- Three datasets out of the box: Yin-Yang, Braille and N-TIDIGITS.

ECE 210 (Brain-Inspired Machine Learning), UC Santa Cruz, Fall 2026.
Wajid Ali, Jayaraj Jayakumar, Manish Pragaladan.

---

## 1. Requirements

- Linux, Python 3.10 or newer, and a C++ compiler.
- A built copy of [OpenROAD-flow-scripts](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts) (ORFS).
  It provides Yosys, OpenROAD and the ASAP7 kit.
- A GPU makes training faster but is not required.
- About 16 GB of RAM for synthesis of the larger networks.

## 2. Setup

```bash
git clone git@github.com:wajidali4907/snntorch-to-gds.git
cd snntorch-to-gds
make setup                    # creates .venv, installs torch, snnTorch and tonic, builds Verilator if it is missing
# on a machine without a GPU:
TORCH_CUDA=cpu make setup
```

### Point the tool to OpenROAD-flow-scripts

ORFS is large, so it is not copied into this repository. `snn2gds` looks for it in this order:

1. the environment variable `ORFS_HOME`
2. `third_party/OpenROAD-flow-scripts` (a git submodule)
3. `~/OpenROAD-flow-scripts`

```bash
# option A: you already have a built ORFS
export ORFS_HOME=/path/to/OpenROAD-flow-scripts

# option B: use the submodule and build it (takes about an hour)
git submodule update --init --depth 1 third_party/OpenROAD-flow-scripts
cd third_party/OpenROAD-flow-scripts && ./build_openroad.sh --local
```

If ORFS stops at the end of the report step on a machine without a display, run the flow with
`env -u DISPLAY`, or guard the `gui::show` call in `flow/scripts/final_report.tcl` with
`[info exists ::env(DISPLAY)]`.

---

## 3. Quick start

Run the whole flow for the small Yin-Yang network (about 10 minutes):

```bash
make flow CFG=configs/yinyang.yaml
```

This runs six steps: train, export, rtl, sim, synth, report. When it finishes, look at
`runs/yinyang_qat/summary.json`. The main numbers are:

| Key | Meaning |
|---|---|
| `export.acc_int` | test accuracy of the integer model (this is the accuracy of the circuit) |
| `export.weights` | number of zero, power-of-two and other weights |
| `sim.spike_match` | `true` if every spike of the circuit matched the model |
| `pnr_synth.synth_area_um2` | standard-cell area after synthesis, in µm² |

---

## 4. Running the steps one by one

```bash
PY=.venv/bin/python
$PY -m snn2gds train  configs/yinyang.yaml     # train in snnTorch
$PY -m snn2gds export configs/yinyang.yaml     # weights -> integers, and check snnTorch == integer model
$PY -m snn2gds rtl    configs/yinyang.yaml     # generate Verilog and a testbench
$PY -m snn2gds sim    configs/yinyang.yaml     # simulate (Verilator) and compare every spike
$PY -m snn2gds synth  configs/yinyang.yaml     # synthesis only (minutes) -> area
$PY -m snn2gds report configs/yinyang.yaml     # collect everything into runs/<name>/summary.json
```

Place and route:

```bash
$PY -m snn2gds grt configs/yinyang.yaml        # place and route up to global routing
$PY -m snn2gds pnr configs/yinyang.yaml        # full flow to the final layout (GDS)
```

`sim` uses Verilator by default. Add `--sim iverilog` to use Icarus Verilog.

### Changing settings from the command line

Any setting in the config file can be changed with `key=value` after the config name.
Use `name=...` to give the run its own folder under `runs/`.

```bash
$PY -m snn2gds train configs/yinyang.yaml name=yy_test train.epochs=10 hidden=64
```

The same works with `make`:

```bash
make flow CFG=configs/yinyang.yaml ARGS="name=yy_test train.epochs=10"
```

---

## 5. Training methods

The method is chosen with `train.method`. All three train with 8-bit weights.

### QAT (baseline)

```bash
make flow CFG=configs/braille.yaml ARGS="name=br_qat"
```

### Pruning

Halfway through training, the smallest weights in each layer are set to zero and stay zero.

```bash
make flow CFG=configs/braille.yaml ARGS="name=br_prune50 train.method=qat_prune train.prune_frac=0.5"
```

### L1 penalty

Adds the sum of the absolute weights to the loss. It pushes weights toward zero, and a zero weight needs no hardware.
`train.lam` sets the strength (larger saves more area and costs more accuracy).

```bash
make flow CFG=configs/braille.yaml ARGS="name=br_l1 train.method=qat_silicon train.lam=3 train.c0=0.0734 train.c1=0"
```

### L1 penalty plus a power-of-two term

Adds a second term that pushes each weight toward the nearest power of two.
`train.lam_p2` sets its strength and `train.p2_mode=log` selects the form `sin²(π·log2|w|)`.

```bash
make flow CFG=configs/yinyang.yaml \
  ARGS="name=yy_l1_p2 train.method=qat_silicon train.lam=3 train.c0=0.0734 train.lam_p2=1 train.c1=0.0734 train.p2_mode=log"
```

The loss is `task loss + (lam · c0 · Σ|w| + lam_p2 · c1 · Σ d(w)) / N_w`, with the weights in integer units.

---

## 6. Config file

One YAML file per dataset is in `configs/`. Example:

```yaml
name: yinyang_qat          # run folder: runs/yinyang_qat
dataset: yinyang           # yinyang | braille | ntidigits
T: 100                     # time steps per sample
hidden: 128                # one hidden layer, or a list such as [256, 256]
n_verify: 200              # test samples replayed in the Verilog simulation
quant: {bw: 8, f: 4, bu: 16, k: 5, theta: 1.0}
train: {epochs: 30, batch_size: 128, lr: 0.002, method: qat, init_gain: 6.0}
hw: {clk_period_ps: 1000, core_utilization: 40, place_density: 0.6}
```

| Setting | Meaning |
|---|---|
| `quant.bw` | weight bits (signed) |
| `quant.f` | fractional bits: the stored integer is `round(w · 2^f)` |
| `quant.bu` | membrane register bits |
| `quant.k` | leak: `beta = 1 - 2^-k`, built as a shift and a subtract |
| `quant.theta` | firing threshold |
| `bias_step` | `0` adds one extra input that spikes at the first time step and acts as a bias; `-1` turns it off |
| `train.method` | `qat`, `qat_prune` or `qat_silicon` |
| `train.prune_frac` | share of weights set to zero (`qat_prune`) |
| `train.lam`, `train.lam_p2` | strength of the L1 term and of the power-of-two term (`qat_silicon`) |
| `train.init_gain` | scales the starting weights (sparse spike inputs need larger weights) |
| `train.loss` | `count` (cross-entropy on output spike counts) or a membrane loss |
| `train.seed` | random seed |
| `hw.clk_period_ps` | clock period for synthesis and layout |
| `hw.core_utilization`, `hw.place_density` | layout density settings |
| `hw.num_cores` | threads for OpenROAD (fewer threads use less memory) |

The full list with comments is in `snn2gds/config.py`.

---

## 7. What a run produces

Everything for one run is written to `runs/<name>/`:

| File or folder | Content |
|---|---|
| `config.yaml` | the exact settings of the run |
| `model.pt`, `train_log.json` | trained model and training log |
| `export.json` | integer weights, leak and threshold |
| `ref/` | input spikes and expected spikes for the testbench |
| `rtl/` | generated Verilog and testbench |
| `sim/` | simulation build and log |
| `orfs/` | synthesis and layout files, logs and reports (final layout: `6_final.gds`) |
| `metrics_*.json`, `summary.json` | numbers from each step, and all of them together |

`runs/`, `data/` and `tools/` are created by the tool and are not tracked in git.

---

## 8. How the check works

1. `export` turns the trained weights into integers and builds a bit-exact integer model of the circuit.
   It checks that this model gives the same spikes as snnTorch on the test set, and it flags any membrane overflow.
2. `sim` replays `n_verify` test samples through the generated Verilog and compares **every spike of every layer at
   every time step** with the integer model. It prints `SPIKE_MATCH PASS`, or the first mismatches.

The accuracy that is reported is the accuracy of the integer model on the full test set.

---

## 9. Final layout (GDS)

`pnr` runs placement, clock-tree synthesis, routing and writes the GDS. For the Yin-Yang network we relax the clock
and use fewer threads so that routing fits in 16 GB:

```bash
env -u DISPLAY .venv/bin/python -m snn2gds pnr runs/<name>/config.yaml name=<new_name> hw.clk_period_ps=1500 hw.num_cores=4
```

`scripts/gds_yinyang.sh` does this for three trained Yin-Yang runs. `scripts/render_gds.py` and
`scripts/or_screenshot.tcl` save pictures of the finished layouts.

---

## 10. Experiment scripts

These scripts run many settings and seeds. Each one skips runs that are already finished, so it is safe to restart.

| Script | What it does |
|---|---|
| `scripts/overnight.py` | tunes the learning rate and starting weight size on a validation split, then trains QAT, pruning and L1 with 3 seeds and runs the full flow for each |
| `scripts/prune_extra.py` | adds 70% and 80% pruning |
| `scripts/extra_lambda.py`, `scripts/l1_strong.py` | add stronger L1 settings |
| `scripts/yy_balanced.py` | L1 plus the power-of-two term at several strengths on Yin-Yang |
| `scripts/pow2_experiment.py` | hardware test with no training: layers that differ only in the share of power-of-two weights |
| `scripts/plot_pow2_area.py` | plots the result of that test |
| `scripts/compare.py` | table and plot of accuracy against area for a set of runs |

```bash
.venv/bin/python scripts/overnight.py --dry      # show what would run
.venv/bin/python scripts/overnight.py            # run it (hours)
.venv/bin/python scripts/pow2_experiment.py      # controlled power-of-two test
.venv/bin/python scripts/compare.py yinyang_qat 'yy_*'
```

Results of these scripts are written to `results/`.

---

## 11. Datasets

| Dataset | Source | Inputs | Classes |
|---|---|---|---|
| Yin-Yang | generated by the tool (after Kriener et al., 2022) | 4 (x, y, 1-x, 1-y), one spike each | 3 |
| Braille | Zenodo record 7050094 (Müller-Cleve et al., 2022) | 12 taxels × ON/OFF = 24 | 27 |
| N-TIDIGITS | `tonic` `NTIDIGITS18`, single digits | 64 cochlea channels | 11 |

The data is downloaded on first use into `data/`. Events are binned into `T` time steps and cached.

---

## 12. Repository layout

```
configs/         one YAML file per dataset
snn2gds/
  config.py      settings and command-line overrides
  datasets.py    dataset download and spike encoding
  quant.py       quantizers and the bit-exact integer model
  model.py       the snnTorch network
  train.py       qat | qat_prune | qat_silicon
  export.py      integer weights, and the snnTorch == integer model check
  rtlgen.py      Verilog and testbench generator
  sim.py         Verilator or Icarus simulation, spike comparison
  pnr.py         runs OpenROAD-flow-scripts and collects area and timing
  calibrate.py   synthesizes small test layers to measure the cost of a weight
  report.py      writes runs/<name>/summary.json
rtl/snn_lif.v    the LIF neuron (copied into every generated design)
scripts/         setup and experiment scripts
third_party/     pointer to OpenROAD-flow-scripts (submodule)
```

## 13. Limits

- Only fully connected layers. No convolution, recurrent connections or delays.
- The leak and the threshold are the same for all neurons and are not learned.
- The weights are fixed in the circuit, so one chip computes one network.
- All inputs of a neuron are added in one clock cycle (fully parallel). A time-multiplexed version is not built.

## Tools

snnTorch, tonic, Verilator, Yosys, OpenROAD and OpenROAD-flow-scripts, and the ASAP7 predictive 7 nm kit.
