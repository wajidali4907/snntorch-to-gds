"""Datasets, all returned as dense spike tensors [N, T, C] (uint8) + labels [N].

  yinyang   : generated locally (re-implementation of Kriener et al. 2022), 4 inputs, 3 classes
  braille   : Müller-Cleve et al. 2022, 12 taxels -> 24 ON/OFF channels, 27 classes
  ntidigits : Anumula et al. 2018 (via tonic), 64 cochlea channels, 11 classes

Everything is cached under data/ as .npz after the first call.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np

DATA = Path("data")

N_INPUTS = {"yinyang": 4, "braille": 24, "ntidigits": 64}
N_CLASSES = {"yinyang": 3, "braille": 27, "ntidigits": 11}


# ------------------------------------------------------------------ Yin-Yang
def _yy_class(x, y, r_small=0.1, r_big=0.5):
    d_right = np.hypot(x - 1.5 * r_big, y - r_big)
    d_left = np.hypot(x - 0.5 * r_big, y - r_big)
    if d_right < r_small or d_left < r_small:
        return 2
    yin = (d_right <= r_small) or (r_small < d_left <= 0.5 * r_big) or (y > r_big and d_right > 0.5 * r_big)
    return int(yin)


def _yy_points(n, seed, r_big=0.5):
    rng = np.random.default_rng(seed)
    xs, ys = [], []
    while len(xs) < n:
        want = rng.integers(3)  # balance classes
        while True:
            x, y = rng.random(2) * 2 * r_big
            if np.hypot(x - r_big, y - r_big) > r_big:
                continue
            if _yy_class(x, y) == want:
                break
        xs.append((x, y))
        ys.append(want)
    p = np.array(xs)
    feats = np.stack([p[:, 0], p[:, 1], 1 - p[:, 0], 1 - p[:, 1]], 1)
    return feats.astype(np.float32), np.array(ys, dtype=np.int64)


def _latency_encode(feats, T, t_min=0.0, t_max=0.8):
    """One spike per channel at t = round((t_min + v*(t_max-t_min)) * (T-1)); earlier = smaller value."""
    n, c = feats.shape
    t = np.round((t_min + feats * (t_max - t_min)) * (T - 1)).astype(int)
    out = np.zeros((n, T, c), np.uint8)
    out[np.arange(n)[:, None], t, np.arange(c)[None, :]] = 1
    return out


def load_yinyang(T):
    xtr, ytr = _yy_points(5000, seed=42)
    xte, yte = _yy_points(1000, seed=40)
    return (_latency_encode(xtr, T), ytr), (_latency_encode(xte, T), yte)


# ------------------------------------------------------------------- Braille
BRAILLE_ZIP = "https://zenodo.org/api/records/7050094/files/reading_braille_data.zip/content"
BRAILLE_T_END = 1.25  # seconds; longest recording in the th_1 set


def _download(url, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, dst)
    return dst


def load_braille(T, seed=0, threshold=1):
    """Müller-Cleve et al. 2022 (Zenodo 7050094). Each sample: 12 taxels x {ON, OFF} event-time lists.
    Channel order matches the reference repo: c = 2*taxel + polarity. 80/20 stratified-free random split."""
    import zipfile

    import pandas as pd
    raw = DATA / "braille" / "raw"
    pkl = raw / f"data_braille_letters_th_{threshold}.pkl"
    if not pkl.exists():
        z = _download(BRAILLE_ZIP, raw / "reading_braille_data.zip")
        with zipfile.ZipFile(z) as zf:
            zf.extract(pkl.name, raw)
    d = pd.DataFrame(pd.read_pickle(pkl))
    letters = sorted(set(d["letter"]))
    labels = np.array([letters.index(l) for l in d["letter"]], np.int64)
    X = np.zeros((len(d), T, 24), np.uint8)
    for n, sample in enumerate(d["events"]):
        for taxel, pols in enumerate(sample):
            for pol, times in enumerate(pols):
                if len(times):
                    b = np.minimum((np.asarray(times) / BRAILLE_T_END * T).astype(int), T - 1)
                    X[n, b, 2 * taxel + pol] = 1
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(X))
    n_te = len(X) // 5
    te, tr = idx[:n_te], idx[n_te:]
    return (X[tr], labels[tr]), (X[te], labels[te])


# ----------------------------------------------------------------- N-TIDIGITS
NTIDIGITS_T_END = 1.4  # seconds; covers 99% of single-digit utterances, later events dropped


def load_ntidigits(T):
    """Anumula et al. 2018 via tonic (downloads n-tidigits.hdf5, 441 MB). Single digits, 11 classes.
    Fixed window of NTIDIGITS_T_END seconds binned into T steps."""
    from tonic.datasets import NTIDIGITS18

    def conv(train):
        ds = NTIDIGITS18(save_to=str(DATA), train=train, single_digits=True)
        X = np.zeros((len(ds), T, 64), np.uint8)
        Y = np.zeros(len(ds), np.int64)
        for n in range(len(ds)):
            ev, label = ds[n]
            t = ev["t"].astype(np.float64) * 1e-6          # tonic gives microseconds
            keep = t < NTIDIGITS_T_END
            b = (t[keep] / NTIDIGITS_T_END * T).astype(int)
            X[n, b, ev["x"][keep].astype(int)] = 1
            Y[n] = label
        return X, Y

    return conv(True), conv(False)


# -------------------------------------------------------------------- common
def load(name: str, T: int):
    cache = DATA / f"{name}_T{T}.npz"
    if cache.exists():
        z = np.load(cache)
        return (z["xtr"], z["ytr"]), (z["xte"], z["yte"])
    fn = {"yinyang": load_yinyang, "braille": load_braille, "ntidigits": load_ntidigits}[name]
    (xtr, ytr), (xte, yte) = fn(T)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, xtr=xtr, ytr=ytr, xte=xte, yte=yte)
    return (xtr, ytr), (xte, yte)
