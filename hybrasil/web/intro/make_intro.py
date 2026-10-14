# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rebuild the intro slides and intro.json from the maintainer's maps.

    pip install pillow numpy                # conversion only, not a runtime need
    python hybrasil/web/intro/make_intro.py <folder holding the three PNGs>

The inputs are the three "Waer is Hy Brasil?" maps, one per screen shape:
Hy_Brasil_Mobile.png, Hy_Brasil_Standard.png and Hy_Brasil_Ultrawide.png.
For each it writes

* ``<slide>.webp``, the map itself, at its own size;
* ``intro.json``, every slide's size, the island's centre and radius as
  fractions of the image, and the map's mean colour (the overlay's background
  while the image is still loading).  The viewer puts the random body where
  the island is, so it is found there as the map fades.

The island is its fill flood-filled from ``SEEDS``, stopped by its dark ink
outline (thickened by ``SEAL`` px first, as the ultrawide's has gaps), then
grown by ``GROW`` px to take the outline in.

The viewer picks the slide whose aspect ratio is nearest the window's, on a
log scale (``hybrasil/viz/three_viewer.py``, ``_INTRO_PICK``).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent

# Source file, and a point inside the island as a fraction of the image.
SEEDS = {
    "mobile": ("Hy_Brasil_Mobile.png", (0.491, 0.497)),
    "standard": ("Hy_Brasil_Standard.png", (0.491, 0.508)),
    "ultrawide": ("Hy_Brasil_Ultrawide.png", (0.493, 0.544)),
}
INK = 75        # luminance below which a pixel is the island's ink outline
SEAL = 1        # px the ink is thickened by first, closing small gaps in the outline
GROW = 5        # px the filled island grows by, to take its outline in
MAX_AREA = 0.01  # a fill bigger than this share of the image leaked into the sea

src = Path(sys.argv[1])
slides = []
for name, (file, (fx, fy)) in SEEDS.items():
    img = Image.open(src / file).convert("RGB")
    w, h = img.size
    a = np.asarray(img, dtype=float)
    lum = a @ [0.299, 0.587, 0.114]

    # Not-ink is 255, ink 0; flood the island's fill from the seed with 128.
    walls = Image.fromarray(np.where(lum >= INK, 255, 0).astype(np.uint8), "L").filter(
        ImageFilter.MinFilter(2 * SEAL + 1))
    seed = (int(fx * w), int(fy * h))
    if walls.getpixel(seed) != 255:
        sys.exit(f"{name}: the seed {seed} is on ink, not the island")
    ImageDraw.floodfill(walls, seed, 128)
    island = np.asarray(walls) == 128
    share = island.mean()
    if share > MAX_AREA:
        sys.exit(f"{name}: the fill covers {share:.1%} of the map -- it leaked past the outline")

    grown = Image.fromarray(island.astype(np.uint8) * 255, "L").filter(
        ImageFilter.MaxFilter(2 * GROW + 1))
    img.save(HERE / f"{name}.webp", quality=80, method=6)

    ys, xs = np.nonzero(np.asarray(grown) > 127)
    mean = a.reshape(-1, 3).mean(axis=0)
    slides.append({
        "name": name, "image": f"{name}.webp",
        "width": w, "height": h,
        "island": {"x": round(float(xs.mean()) / w, 4), "y": round(float(ys.mean()) / h, 4),
                   "r": round(float(np.sqrt(len(xs) / np.pi)) / w, 4)},
        "colour": "#%02x%02x%02x" % tuple(int(round(c)) for c in mean),
    })
    print(f"{name}: {w}x{h}, island {len(xs)} px at "
          f"({slides[-1]['island']['x']}, {slides[-1]['island']['y']}), "
          f"webp {(HERE / f'{name}.webp').stat().st_size // 1024} KB")

(HERE / "intro.json").write_text(json.dumps({"slides": slides}, indent=2) + "\n", encoding="utf-8")
