"""Plain snnTorch network: Linear(no bias) -> Leaky -> Linear(no bias) -> Leaky.

The only hardware-specific choices are the constructor arguments of snn.Leaky
(beta = 1 - 2^-k, fixed threshold, subtract reset, floor state quantizer) and
fake-quantized weights in forward(). The exporter reads these modules directly.
"""
from __future__ import annotations

import snntorch as snn
import torch
import torch.nn as nn
from snntorch import surrogate

from .config import Config
from .quant import make_state_quant, quantize_weight


class QLinear(nn.Linear):
    """nn.Linear with weights fake-quantized to (bw, f) and an optional prune mask."""

    def __init__(self, n_in, n_out, bw, f):
        super().__init__(n_in, n_out, bias=False)
        self.bw, self.f = bw, f
        self.register_buffer("mask", torch.ones(n_out, n_in))

    def qweight(self):
        return quantize_weight(self.weight * self.mask, self.bw, self.f)

    def forward(self, x):
        return nn.functional.linear(x, self.qweight())


class SNN(nn.Module):
    def __init__(self, cfg: Config, n_in: int, n_out: int):
        super().__init__()
        q = cfg.quant
        beta = 1.0 - 2.0 ** (-q.k)
        sq = make_state_quant(q.f)
        sg = surrogate.fast_sigmoid(slope=cfg.train.surrogate_slope)
        sizes = [n_in, cfg.hidden, n_out]
        self.fcs = nn.ModuleList()
        self.lifs = nn.ModuleList()
        for a, b in zip(sizes[:-1], sizes[1:]):
            self.fcs.append(QLinear(a, b, q.bw, q.f))
            with torch.no_grad():
                self.fcs[-1].weight.mul_(cfg.train.init_gain)
            self.lifs.append(snn.Leaky(beta=beta, threshold=q.theta, learn_beta=False,
                                       learn_threshold=False, reset_mechanism="subtract",
                                       spike_grad=sg, state_quant=sq, init_hidden=False))

    def forward(self, x):
        """x: [T, B, N_in] -> list of per-layer spike tensors [T, B, N_l]."""
        mems = [lif.reset_mem() if hasattr(lif, "reset_mem") else lif.init_leaky() for lif in self.lifs]
        recs = [[] for _ in self.lifs]
        for t in range(x.shape[0]):
            h = x[t]
            for l, (fc, lif) in enumerate(zip(self.fcs, self.lifs)):
                h, mems[l] = lif(fc(h), mems[l])
                recs[l].append(h)
        return [torch.stack(r) for r in recs]
