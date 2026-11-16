"""Train an SNN three ways: qat | qat_prune | qat_silicon (Eq. 2 of the proposal)."""
from __future__ import annotations

import json

import numpy as np
import torch
import torch.nn.functional as F

from . import datasets
from .config import Config, save_config
from .model import SNN
from .quant import nearest_cheap, nearest_pow2


def pow2_log_dist(w: torch.Tensor) -> torch.Tensor:
    """sin^2(pi*log2|w|) for |w| >= 1 (w in integer units): 0 at 1, 2, 4, ..., 1 halfway between in
    log scale. Weights below 1 round to 0 or 1 in hardware, both cheap, so they cost 0 here."""
    a = w.abs()
    return torch.where(a >= 1, torch.sin(torch.pi * torch.log2(a.clamp_min(1.0))) ** 2, torch.zeros_like(a))


def silicon_cost(model: SNN, c0: float, c1: float, lam0: float = 1.0, lam1: float = 1.0,
                 p2_zero: bool = False, p2_mode: str = "sq") -> torch.Tensor:
    """lam0*c0*sum|w| + lam1*c1*sum pow2_term(w) on integer-scaled weights (Eq. 2 with separate lambdas)."""
    p2 = nearest_cheap if p2_zero else nearest_pow2
    total = 0.0
    for fc in model.fcs:
        w = fc.weight * fc.mask * 2.0 ** fc.f        # integer units
        if p2_mode == "log":
            p2_term = pow2_log_dist(w).sum()
        else:
            p2_term = ((w - p2(w).detach()) ** 2).sum()
        total = total + lam0 * c0 * w.abs().sum() + lam1 * c1 * p2_term
    return total


def apply_prune(model: SNN, frac: float):
    for fc in model.fcs:
        w = fc.weight.detach().abs()
        thr = torch.quantile(w.flatten(), frac)
        fc.mask.copy_((w > thr).float())


def _batches(X, Y, bs, shuffle, rng):
    idx = rng.permutation(len(X)) if shuffle else np.arange(len(X))
    for i in range(0, len(X), bs):
        j = idx[i:i + bs]
        yield X[j], Y[j]


@torch.no_grad()
def evaluate(model, X, Y, device, bs=512):
    model.eval()
    correct = 0
    for xb, yb in _batches(X, Y, bs, False, None):
        x = torch.from_numpy(xb).float().transpose(0, 1).to(device)
        counts = model(x)[-1].sum(0)
        correct += (counts.argmax(1).cpu().numpy() == yb).sum()
    return correct / len(X)


def train(cfg: Config):
    tc = cfg.train
    torch.manual_seed(tc.seed)
    rng = np.random.default_rng(tc.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    (xtr, ytr), (xte, yte) = datasets.load(cfg.dataset, cfg.T)
    tag = "test_acc"
    if tc.val_frac > 0:   # tuning mode: evaluate on a held-out part of the training set (fixed split)
        perm = np.random.default_rng(12345).permutation(len(xtr))
        n_val = int(round(tc.val_frac * len(xtr)))
        xte, yte = xtr[perm[:n_val]], ytr[perm[:n_val]]
        xtr, ytr = xtr[perm[n_val:]], ytr[perm[n_val:]]
        tag = "val_acc"
    n_in, n_out = datasets.N_INPUTS[cfg.dataset], datasets.N_CLASSES[cfg.dataset]
    model = SNN(cfg, n_in, n_out).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=tc.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, tc.epochs)
    prune_at = tc.epochs // 2 if tc.method == "qat_prune" else None

    out = cfg.run_dir
    out.mkdir(parents=True, exist_ok=True)
    save_config(cfg, out / "config.yaml")
    log = []
    for ep in range(tc.epochs):
        if ep == prune_at:
            apply_prune(model, tc.prune_frac)
        model.train()
        tot, n = 0.0, 0
        for xb, yb in _batches(xtr, ytr, tc.batch_size, True, rng):
            x = torch.from_numpy(xb).float().transpose(0, 1).to(device)
            y = torch.from_numpy(yb).to(device)
            counts = model(x)[-1].sum(0)
            loss = F.cross_entropy(counts, y)
            if tc.method == "qat_silicon":
                n_w = sum(fc.weight.numel() for fc in model.fcs)
                lam1 = tc.lam if tc.lam_p2 < 0 else tc.lam_p2
                loss = loss + silicon_cost(model, tc.c0, tc.c1, tc.lam, lam1, tc.p2_zero, tc.p2_mode) / n_w
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(yb)
            n += len(yb)
        sched.step()
        acc = evaluate(model, xte, yte, device)
        log.append({"epoch": ep, "loss": tot / n, tag: float(acc)})
        print(f"[{cfg.name}] epoch {ep:3d} loss {tot / n:.4f} {tag} {acc:.4f}", flush=True)

    torch.save(model.state_dict(), out / "model.pt")
    (out / "train_log.json").write_text(json.dumps(log, indent=1))
    return model
