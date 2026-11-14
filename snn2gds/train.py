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


def silicon_cost(model: SNN, c0: float, c1: float, lam0: float = 1.0, lam1: float = 1.0,
                 p2_zero: bool = False) -> torch.Tensor:
    """lam0*c0*sum|w| + lam1*c1*sum(w - p2(w))^2 on integer-scaled weights (Eq. 2 with separate lambdas)."""
    p2 = nearest_cheap if p2_zero else nearest_pow2
    total = 0.0
    for fc in model.fcs:
        w = fc.weight * fc.mask * 2.0 ** fc.f        # integer units
        total = total + lam0 * c0 * w.abs().sum() + lam1 * c1 * ((w - p2(w).detach()) ** 2).sum()
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
                loss = loss + silicon_cost(model, tc.c0, tc.c1, tc.lam, lam1, tc.p2_zero) / n_w
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(yb)
            n += len(yb)
        sched.step()
        acc = evaluate(model, xte, yte, device)
        log.append({"epoch": ep, "loss": tot / n, "test_acc": float(acc)})
        print(f"[{cfg.name}] epoch {ep:3d} loss {tot / n:.4f} test_acc {acc:.4f}", flush=True)

    torch.save(model.state_dict(), out / "model.pt")
    (out / "train_log.json").write_text(json.dumps(log, indent=1))
    return model
