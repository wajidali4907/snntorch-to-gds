"""Paper GDS figure: three OpenROAD GUI screenshots at the same scale."""
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
UM_PER_PX = 0.05
PANELS = [("qat", "QAT (baseline)", "4,588 µm², 95.0%"),
          ("l1_1", "L1, λ0 = 0.073", "3,382 µm² (−26%), 94.9%"),
          ("l1_3", "L1, λ0 = 0.22", "2,421 µm² (−47%), 91.1%")]

def crop(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).max(axis=2) > 40
    ys, xs = np.where(a.any(axis=1))[0], np.where(a.any(axis=0))[0]
    return im.crop((xs[0], ys[0], xs[-1] + 1, ys[-1] + 1))

ims = [crop(ROOT / "results" / "gds_shots" / f"{k}_all.png") for k, _, _ in PANELS]
for (k, _, _), im in zip(PANELS, ims):
    im.save(ROOT / "paper" / "figs" / f"gds_{k}.png")
    print(k, im.size, [round(s * UM_PER_PX, 1) for s in im.size])
big = max(max(im.size) for im in ims)
fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.9), facecolor="white")
for ax, im, (_, title, sub) in zip(axes, ims, PANELS):
    canvas = Image.new("RGB", (big, big), "white")
    canvas.paste(im, ((big - im.size[0]) // 2, big - im.size[1]))
    ax.imshow(canvas)
    ax.set_title(f"{title}\n{sub}", fontsize=10)
    ax.axis("off")
axes[0].set_autoscale_on(False)
bar = 20 / UM_PER_PX
axes[0].plot([40, 40 + bar], [big + 60, big + 60], color="k", lw=2.5, clip_on=False)
axes[0].text(40 + bar / 2, big + 90, "20 µm", ha="center", va="top", fontsize=9)
fig.tight_layout()
fig.savefig(ROOT / "paper" / "figs" / "gds_yinyang.png", dpi=300, bbox_inches="tight")
