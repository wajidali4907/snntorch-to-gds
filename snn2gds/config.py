"""Experiment configuration (one YAML file per run, see configs/)."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class QuantCfg:
    bw: int = 8          # weight bits (signed)
    f: int = 4           # fractional bits: w_int = round(w * 2^f)
    bu: int = 16         # membrane register bits (signed)
    k: int = 3           # leak: beta = 1 - 2^-k
    theta: float = 1.0   # firing threshold (real units); theta_int = round(theta * 2^f)


@dataclass
class TrainCfg:
    epochs: int = 30
    batch_size: int = 128
    lr: float = 2e-3
    seed: int = 0
    method: str = "qat"          # qat | qat_prune | qat_silicon
    prune_frac: float = 0.0      # qat_prune: fraction of smallest weights forced to 0
    lam: float = 0.0             # qat_silicon: lambda in Eq. (2) (weight of the zero term c0*|w|)
    lam_p2: float = -1.0         # qat_silicon: separate lambda for the pow2 term c1*(w-p2)^2; <0 => same as lam
    p2_zero: bool = False        # pow2 target includes 0 and only integer powers (nearest_cheap)
    p2_mode: str = "sq"          # pow2 term: "sq" = (w - p2(w))^2 (Eq. 2 as proposed);
                                 # "log" = sin^2(pi*log2|w|): 0 at powers of two, 1 midway, scale-free
                                 #         (c1 is then um^2 per fully non-pow2 weight)
    c0: float = 1.0              # qat_silicon: area cost per |w|  (calibrated)
    c1: float = 1.0              # qat_silicon: area cost of distance to power of two (calibrated)
    surrogate_slope: float = 5.0
    qat: bool = True             # False: train in float (no fake-quant of weights or membrane), round to
                                 #        integers only at export (post-training quantization baseline)
    init_gain: float = 1.0       # multiply default nn.Linear init (sparse inputs need larger weights)
    val_frac: float = 0.0        # >0: hold out this fraction of the TRAIN set for tuning (logs val_acc,
                                 #     the test set is not used during training)


@dataclass
class HwCfg:
    P: int = 0                   # inputs added per cycle; 0 => P = N_in (fully parallel). Only P=N_in implemented.
    clk_period_ps: float = 1000.0
    place_density: float = 0.6
    core_utilization: float = 40.0
    num_cores: int = 8           # ORFS threads; detailed route memory grows with threads (~13 GB at 20)


@dataclass
class Config:
    name: str = "yinyang_qat"
    dataset: str = "yinyang"     # yinyang | braille | ntidigits
    T: int = 100                 # time steps
    hidden: int = 128
    n_verify: int = 100          # test samples replayed in RTL simulation
    quant: QuantCfg = field(default_factory=QuantCfg)
    train: TrainCfg = field(default_factory=TrainCfg)
    hw: HwCfg = field(default_factory=HwCfg)

    @property
    def run_dir(self) -> Path:
        return Path("runs") / self.name


def _build(cls, d):
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name not in d:
            continue
        v = d[f.name]
        if dataclasses.is_dataclass(f.default_factory() if f.default_factory is not dataclasses.MISSING else None):
            v = _build(f.default_factory().__class__, v or {})
        kwargs[f.name] = v
    unknown = set(d) - {f.name for f in dataclasses.fields(cls)}
    if unknown:
        raise ValueError(f"unknown keys for {cls.__name__}: {sorted(unknown)}")
    return cls(**kwargs)


def load_config(path: str | Path, overrides: dict | None = None) -> Config:
    d = yaml.safe_load(Path(path).read_text()) or {}
    for key, val in (overrides or {}).items():   # "train.lam=0.1" style
        node = d
        parts = key.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = yaml.safe_load(str(val))
    return _build(Config, d)


def save_config(cfg: Config, path: Path) -> None:
    path.write_text(yaml.safe_dump(dataclasses.asdict(cfg), sort_keys=False))
