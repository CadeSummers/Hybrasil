# The background sky

`milky_way_4k.jpg` (4096 × 2048) and `milky_way_2k.jpg` (2048 × 1024) are the
Milky Way the three.js viewer draws behind every system. They come from
**NASA's Deep Star Maps 2020**, the galactic-coordinate star map, which is built
from Gaia DR2 star counts:
<https://svs.gsfc.nasa.gov/4851>.

**Credit, as NASA asks for it:** NASA/Goddard Space Flight Center Scientific
Visualization Studio. Gaia DR2: ESA/Gaia/DPAC. The viewer shows this line
whenever the sky is on.

- **Projection:** equirectangular, in galactic coordinates. The galactic centre
  (l = 0, b = 0) is the middle of the image, and longitude increases to the
  left, as on the sky seen from inside.
- **Which file goes where:** `--serve` sends the 4k image as a separate file,
  `/sky/milky_way_4k.jpg`. A standalone HTML file (the non-server launch and
  `--output html`) embeds the 2k image, which adds about 0.75 MB to it.
- **Rebuilding:** `make_sky.py` makes both files from NASA's HDR original; its
  docstring gives the commands. It needs `OpenEXR` and `pillow`, which are
  conversion tools only and not in `requirements.txt`.

How the image is turned into each system's frame, so that the galactic-centre
arrow points at the galactic centre in the picture, is in
`docs/architecture/frames.md`.
