"""Fixed-point helpers shared by training, export, and the bit-exact reference.

Conventions (all integers are in units of 2^-f):
  w_int     = clamp(round(w * 2^f), -2^(bw-1), 2^(bw-1)-1)
  theta_int = round(theta * 2^f)
  U is a bu-bit two's-complement register.

Per time step (matches snnTorch Leaky, reset_mechanism="subtract", with a
floor-to-grid state quantizer applied after the update):
  s_prev = U > theta_int
  U      = U - ceil(U / 2^k) + I - theta_int * s_prev
         = U + ((-U) >>> k) + I - theta_int * s_prev
  s      = U > theta_int
"""
from __future__ import annotations

import numpy as np
import torch


# ---------------------------------------------------------------- STE ops
class _RoundSTE(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x):
        return torch.round(x)

    @staticmethod
    def backward(ctx, g):
        return g


class _FloorSTE(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x):
        return torch.floor(x)

    @staticmethod
    def backward(ctx, g):
        return g


def quantize_weight(w: torch.Tensor, bw: int, f: int) -> torch.Tensor:
    """Fake-quantize weights to the bw-bit / f-fractional-bit grid (STE)."""
    scale = 2.0 ** f
    lo, hi = -(2 ** (bw - 1)), 2 ** (bw - 1) - 1
    q = _RoundSTE.apply(w * scale)
    q = torch.clamp(q, lo, hi)
    return q / scale


def make_state_quant(f: int):
    """Membrane state quantizer passed to snn.Leaky(state_quant=...): floor to 2^-f grid."""
    scale = 2.0 ** f

    def state_quant(mem: torch.Tensor) -> torch.Tensor:
        return _FloorSTE.apply(mem * scale) / scale

    return state_quant


def weight_to_int(w: np.ndarray, bw: int, f: int) -> np.ndarray:
    lo, hi = -(2 ** (bw - 1)), 2 ** (bw - 1) - 1
    return np.clip(np.round(w * 2.0 ** f), lo, hi).astype(np.int64)


# ------------------------------------------------- bit-exact integer model
def wrap(x: np.ndarray, bits: int) -> np.ndarray:
    """Two's-complement wrap to `bits` bits (what the RTL register does)."""
    m = 1 << bits
    return ((x + (m >> 1)) % m) - (m >> 1)


def int_forward(spikes_in: np.ndarray, weights: list[np.ndarray], theta_int: int,
                k: int, bu: int):
    """Integer reference model.

    spikes_in: [T, B, N_in] in {0,1}
    weights:   list of integer matrices, layer l has shape [N_out, N_in]
    Returns (list of per-layer spike arrays [T, B, N_l], overflow flag).
    """
    T, B, _ = spikes_in.shape
    layer_spikes = []
    x = spikes_in.astype(np.int64)
    overflow = False
    for W in weights:
        n_out = W.shape[0]
        U = np.zeros((B, n_out), dtype=np.int64)
        out = np.zeros((T, B, n_out), dtype=np.uint8)
        Wt = W.T.astype(np.int64)
        for t in range(T):
            s_prev = (U > theta_int).astype(np.int64)
            I = x[t] @ Wt
            # (-U) >> k is an arithmetic (floor) shift, same as Verilog >>> on signed
            new = U + ((-U) >> k) + I - theta_int * s_prev
            wrapped = wrap(new, bu)
            overflow |= bool(np.any(wrapped != new))
            U = wrapped
            out[t] = (U > theta_int)
        layer_spikes.append(out)
        x = out.astype(np.int64)
    return layer_spikes, overflow


def nearest_pow2(w: torch.Tensor) -> torch.Tensor:
    """Signed nearest power of two (0 maps to 0)."""
    a = w.abs().clamp_min(1e-12)
    p = torch.pow(2.0, torch.round(torch.log2(a)))
    return torch.where(w == 0, torch.zeros_like(w), torch.sign(w) * p)


def nearest_cheap(w: torch.Tensor) -> torch.Tensor:
    """Nearest hardware-cheap integer value: 0 or a signed integer power of two (1, 2, 4, ...).
    w is in integer units. Unlike nearest_pow2, never returns fractional powers and can return 0."""
    a = w.abs()
    p = torch.pow(2.0, torch.round(torch.log2(a.clamp_min(1.0))))   # >= 1
    return torch.where(a < 0.5, torch.zeros_like(w), torch.sign(w) * p)   # |w| < 0.5 rounds to 0 in hardware
