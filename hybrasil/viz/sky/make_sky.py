# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rebuild milky_way_4k.jpg and milky_way_2k.jpg from NASA's HDR sky map.

    pip install OpenEXR pillow numpy        # conversion only, not a runtime need
    curl -LO https://svs.gsfc.nasa.gov/vis/a000000/a004800/a004851/starmap_2020_4k_gal.exr
    python hybrasil/viz/sky/make_sky.py starmap_2020_4k_gal.exr

The input is NASA SVS Deep Star Maps 2020 (svs.gsfc.nasa.gov/4851), the
galactic-coordinate star map: linear HDR, 4096 x 2048, galactic centre in the
middle, longitude increasing to the left.  This maps it to display sRGB: a
black point at the 60th percentile of luminance so the faint star floor reads
as black, white at the 99.7th so the bright Milky Way sits near white, and a
gentle asinh stretch between.  Dimming for the viewer is done in its shader,
not baked in here.  The last lines check the orientation the viewer relies
on: the galactic centre is the image centre, and the Magellanic Clouds are
right of it and below.
"""
import sys
from pathlib import Path

import numpy as np
import OpenEXR
from PIL import Image

HERE = Path(__file__).parent
src = Path(sys.argv[1])

with OpenEXR.File(str(src)) as f:
    ch = f.parts[0].channels
    rgb = (np.asarray(ch["RGB"].pixels, dtype=np.float64) if "RGB" in ch else
           np.stack([np.asarray(ch[c].pixels, dtype=np.float64) for c in "RGB"], axis=-1))
lum = rgb.mean(axis=-1)

white = np.percentile(lum, 99.7)
black = np.percentile(lum, 60)
x = np.clip((rgb - black) / (white - black), 0, None)
k = 2.0                                   # asinh softening
x = np.clip(np.arcsinh(k * x) / np.arcsinh(k), 0, 1)
srgb = np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)
img = Image.fromarray((srgb * 255 + 0.5).astype(np.uint8), "RGB")
img.save(HERE / "milky_way_4k.jpg", quality=80, optimize=True, progressive=True)
img.resize((2048, 1024), Image.LANCZOS).save(HERE / "milky_way_2k.jpg", quality=84,
                                              optimize=True, progressive=True)

a = np.asarray(img, dtype=float).mean(axis=-1)
H, W = a.shape


def patch(l, b, r=12):
    """Mean brightness around galactic (l, b), longitude increasing leftward."""
    y = int((0.5 - b / 180.0) * H)
    x_ = int((0.5 - (((l + 180) % 360) - 180) / 360.0) * W)
    return a[max(0, y - r):y + r, max(0, x_ - r):x_ + r].mean()


print("galactic centre", patch(0, 0), "vs anti-centre", patch(180, 0))
print("LMC", patch(280.5, -32.9), "vs its mirror", patch(79.5, -32.9))
print("SMC", patch(302.8, -44.3), "vs its mirror", patch(57.2, -44.3))
