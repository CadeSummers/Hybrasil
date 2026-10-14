# The intro maps

The web app opens on one of these "Waer is Hy Brasil?" maps when someone arrives
(`docs/architecture/web-app.md`, "Intro"). The whole map then fades away and
leaves a random body where the island was.

The maps are the maintainer's own work (Cade Summers, 2026). No other credit is
needed.

| Slide | Size | Shape | For |
|---|---|---|---|
| `mobile.webp` | 940 × 1672 | 0.56 | a phone held upright |
| `standard.webp` | 1672 × 941 | 1.78 (16:9) | most monitors and laptops |
| `ultrawide.webp` | 1915 × 821 | 2.33 (21:9) | ultrawide monitors |

- **Which slide a window gets:** the one whose shape is nearest the window's, on
  a log scale. In practice a window narrower than square gets `mobile`, one up
  to about 2.04 : 1 gets `standard`, and a wider one gets `ultrawide`. Only that
  one image is downloaded. It is drawn `cover`, so the island stays in the
  centre and the edges crop.
- **`intro.json`:** each slide's size, the island's centre and radius as
  fractions of the image, and the map's mean colour, which shows while the
  image loads. The viewer uses the centre and radius to place the body where
  the island is.
- **Rebuilding:** `make_intro.py` makes the slides and `intro.json` from the original PNGs;
  its docstring gives the command. It needs `pillow` and `numpy` for the
  conversion only, not at runtime. If a new map's island outline has gaps
  wider than `SEAL` allows, the script refuses rather than letting the fill
  leak into the sea and misplace the island.
