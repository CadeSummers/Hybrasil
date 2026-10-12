# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Command-line entry point for the Hybrasil Star and Exoplanet Map."""

import argparse
import json
import sys
from .data.loader import get_system
from .data.builtin_systems import (get_builtin_system, BUILTIN_NAMES,
                                   BODY_METADATA, FEATURED_CATALOG_HOSTS,
                                   canonical_builtin_name)
from .mechanics.solvent_bands import (DEFAULT_ALBEDO, DEFAULT_GREENHOUSE_K,
                                     DEFAULT_PRESSURE_BAR,
                                     MAX_ALBEDO, MAX_GREENHOUSE_K,
                                     MAX_PRESSURE_BAR,
                                     MIN_ALBEDO, MIN_GREENHOUSE_K,
                                     MIN_PRESSURE_BAR,
                                     PRESSURES_BAR, SOLVENTS, SolventChoice,
                                     band_absent_reason)
from .mechanics.units import jd_from_date, jd_now
from .viz.export import (show_in_browser_multi, save_html,
                         save_png, build_body_info_js,
                         build_solvent_table_js)
from .viz.three_viewer import save_three_html, show_three_in_browser
from .views import FEATURED_VIEWS, build_view


# The spans and the build step live in figures.py, shared with the web app;
# re-exported here because tests and older callers import them from the CLI.
from .figures import _NATURAL_SPANS, _natural_span_days, build_figure  # noqa: E402,F401


def _bounded(value: str, lo: float, hi: float, what: str) -> float:
    """A float argument that has to land in a range, as the slider's does."""
    try:
        v = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{what} must be a number, not '{value}'")
    if not lo <= v <= hi:
        raise argparse.ArgumentTypeError(
            f"{what} must be between {lo:g} and {hi:g}, not {v:g}")
    return v


def _pressure_bar(value: str) -> float:
    return _bounded(value, MIN_PRESSURE_BAR, MAX_PRESSURE_BAR, "pressure")


def _albedo(value: str) -> float:
    return _bounded(value, MIN_ALBEDO, MAX_ALBEDO, "albedo")


def _greenhouse_k(value: str) -> float:
    return _bounded(value, MIN_GREENHOUSE_K, MAX_GREENHOUSE_K, "greenhouse offset")


def _viewer_js(systems: dict, bands: SolventChoice) -> str:
    """The constants the viewer's JavaScript reads, as one block.

    Two of them: what every body is, for the info panel, and what every
    solvent is, so the pressure, albedo and greenhouse sliders can rebuild the
    bands in the browser instead of asking for a new figure.
    """
    return "\n".join([
        build_body_info_js(systems, BODY_METADATA),
        build_solvent_table_js(bands),
    ])


def _with_views(ordered: dict) -> tuple[dict, str]:
    """The featured views, placed after the built-ins, and their info-panel JS.

    Three.js only: a view is drawn in light years, which the Plotly viewer's
    AU-native zoom does not understand.  A view that cannot be built is left
    out with a warning, as a built-in that fails is.
    """
    views, info = {}, {}
    for key in FEATURED_VIEWS:
        try:
            views[key], body_info = build_view(key)
            info.update(body_info)
        except Exception as e:
            print(f"Warning: could not build '{key}': {e}", file=sys.stderr)
    keys = list(ordered)
    cut = max((i + 1 for i, k in enumerate(keys) if k in BUILTIN_NAMES), default=0)
    out = {k: ordered[k] for k in keys[:cut]}
    out.update(views)
    out.update({k: ordered[k] for k in keys[cut:]})
    js = ("window._SA_BODY_INFO = Object.assign(window._SA_BODY_INFO || {}, "
          + json.dumps(info, separators=(",", ":")).replace("</", "<\\/") + ");") if info else ""
    return out, js


def _featured_twin(system) -> "str | None":
    """The featured system a catalog system is already drawn as, if any.

    The same fold the web app makes: `--source catalog --system "55 Cnc g"`
    opens the literature-built 55 Cancri rather than a thinner duplicate of
    it beside the real one in the switcher.
    """
    if system.source != "catalog":
        return None
    return next((key for key, hosts in FEATURED_CATALOG_HOSTS.items()
                 if system.name in hosts), None)


def _with_featured(primary: str, fig, system, args, bands, t_start: float):
    """Every featured system, plus the one asked for, in switcher order.

    The baseline: whatever opens the viewer, every featured system is a button
    in it.  A system from another source (catalog, file, Horizons) is added
    after them and opens first.  Returns ({key: figure}, {key: system}).
    """
    figures: dict = {primary: fig}
    systems: dict = {primary: system}
    for sys_name in BUILTIN_NAMES:
        if sys_name == primary:
            continue
        try:
            s = get_builtin_system(sys_name, bands)
            s_span = _NATURAL_SPANS.get(sys_name, 365.25)
            figures[sys_name] = build_figure(
                s, t_start, t_start + s_span, mode=args.mode, frames=args.frames,
                frame_duration_ms=args.frame_duration)
            systems[sys_name] = s
        except Exception as e:
            print(f"Warning: could not build '{sys_name}': {e}", file=sys.stderr)
    # BUILTIN_NAMES order, so the buttons appear in order; anything else last.
    order = [n for n in BUILTIN_NAMES if n in figures]
    order += [n for n in figures if n not in order]
    return ({n: figures[n] for n in order}, {n: systems[n] for n in order})


def _parse_date(s: str) -> tuple[int, int, int]:
    try:
        parts = s.split("-")
        return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        raise argparse.ArgumentTypeError(f"Invalid date '{s}'. Use YYYY-MM-DD.")


def build_parser() -> argparse.ArgumentParser:
    """Every command-line option, as its own function.

    Split out of main() so the defaults can be asserted on without
    running a command -- `--solvent` defaults to every solvent, and a
    test says so.
    """
    parser = argparse.ArgumentParser(
        prog="hybrasil",
        description="Visualize orbital bodies in 3D using Plotly.",
    )
    parser.add_argument(
        "--source", choices=["builtin", "horizons", "file", "catalog"], default="builtin",
        help="Data source (default: builtin)",
    )
    parser.add_argument(
        "--system", default="solar",
        help="System name (builtin/horizons/catalog) or file path (file source). "
             "Default: solar",
    )
    parser.add_argument(
        "--mode", choices=["static", "animated"], default="animated",
        help="Visualization mode (default: animated)",
    )
    parser.add_argument(
        "--time-start", default=None, metavar="YYYY-MM-DD",
        help="Start date (default: today)",
    )
    parser.add_argument(
        "--time-end", default=None, metavar="YYYY-MM-DD",
        help="End date (default: natural span for the system)",
    )
    parser.add_argument(
        "--frames", type=int, default=120,
        help="Number of animation frames (default: 120)",
    )
    parser.add_argument(
        "--frame-duration", type=int, default=40,
        help="Frame duration in milliseconds (default: 40)",
    )
    parser.add_argument(
        "--output", choices=["browser", "html", "png"], default="browser",
        help="Output format (default: browser)",
    )
    parser.add_argument(
        "--renderer", choices=["plotly", "three"], default=None,
        help="3-D renderer for browser/html output (default: three, the "
             "three.js viewer; smooth zoom at every scale). 'plotly' is the "
             "original viewer. PNG output always uses Plotly.",
    )
    parser.add_argument(
        "--out-file", default=None,
        help="Output file path for html/png output",
    )
    parser.add_argument(
        "--bodies", default=None,
        help="Comma-separated list of body names to include (default: all)",
    )
    parser.add_argument(
        "--title", default=None,
        help="Override the plot title",
    )

    band_group = parser.add_argument_group("solvent bands")
    band_group.add_argument(
        "--solvent", default="all", metavar="NAMES",
        help="Comma-separated solvents to build a liquid band for, or 'all' "
             "(default: all). Names: " + ", ".join(SOLVENTS) + ". "
             "Bands are built hidden: the viewer opens on the orbits, each "
             "band has its own legend entry, and the Bands button switches "
             "the whole set. Narrow this to put fewer in the legend.",
    )
    band_group.add_argument(
        "--pressure", type=_pressure_bar, default=DEFAULT_PRESSURE_BAR,
        metavar="BAR",
        help=f"Where the viewer's pressure slider starts, in bar: any value "
             f"from {MIN_PRESSURE_BAR:g} to {MAX_PRESSURE_BAR:g} "
             f"(default: {DEFAULT_PRESSURE_BAR:g}). The workbook transcribes "
             + ", ".join(f"{p:g}" for p in PRESSURES_BAR) + "; between those "
             "the melting and boiling points are interpolated, and outside a "
             "solvent's own range it has no band.",
    )
    band_group.add_argument(
        "--albedo", type=_albedo, default=DEFAULT_ALBEDO, metavar="A",
        help=f"Where the viewer's albedo slider starts: any value from "
             f"{MIN_ALBEDO:g} to {MAX_ALBEDO:g} (default: {DEFAULT_ALBEDO:g}, "
             f"Earth-like). A darker body is hotter at the same distance, so "
             f"a lower albedo pushes every band outward.",
    )
    band_group.add_argument(
        "--greenhouse", type=_greenhouse_k, default=DEFAULT_GREENHOUSE_K,
        metavar="K",
        help=f"Where the viewer's greenhouse effect (beta) slider starts, in "
             f"K: a flat offset added to the blackbody temperature, any value "
             f"from {MIN_GREENHOUSE_K:g} to {MAX_GREENHOUSE_K:g} (default: "
             f"{DEFAULT_GREENHOUSE_K:g}, Earth's). A warmer surface pushes "
             f"every band outward; 0 is the pure blackbody band.",
    )
    band_group.add_argument(
        "--band-limit", choices=["functional", "thermodynamic"],
        default="functional",
        help="Where the hot edge comes from for sulfur, formamide and "
             "sulfuric acid, which stop working as solvents below their "
             "boiling points. 'functional' (default) caps at that limit; "
             "'thermodynamic' uses the boiling point regardless.",
    )
    band_group.add_argument(
        "--band-plane", choices=["orbits", "reference"], default="orbits",
        help="Which plane a band is drawn in. 'orbits' (default) uses the "
             "mean orbital plane of the system's confirmed bodies, so the "
             "band rings the star the way the planets do; 'reference' lays it "
             "flat on z = 0 whatever the planets do.",
    )
    band_group.add_argument(
        "--star-colour", choices=["on", "off"], default="on",
        help="Whether a star's colour scales its bands. 'on' (default) takes "
             "Kopparapu et al. 2013's runaway-greenhouse S_eff ratio at the "
             "star's effective temperature: a red dwarf's light is absorbed "
             "more readily, so every band around it moves out (x1.10 for "
             "Proxima). The Sun is unchanged. 'off' treats every star as if "
             "it shone like the Sun.",
    )
    band_group.add_argument(
        "--list-solvents", action="store_true",
        help="List the solvents and the pressures each has a band at, then exit",
    )

    catalog_group = parser.add_argument_group("catalog source (Google Sheets)")
    catalog_group.add_argument(
        "--list-catalog", action="store_true",
        help="List every system in the catalog spreadsheet and exit",
    )
    catalog_group.add_argument(
        "--sheet-id", default=None,
        help="Spreadsheet ID or URL (default: the project's catalog workbook)",
    )
    catalog_group.add_argument(
        "--refresh-catalog", action="store_true",
        help="Refetch the spreadsheet instead of using the local cache",
    )
    catalog_group.add_argument(
        "--offline", action="store_true",
        help="Use the cached spreadsheet only; never contact Google",
    )

    web = parser.add_argument_group("web app")
    web.add_argument(
        "--serve", action="store_true",
        help="Run the web app: the three.js viewer with every featured and "
             "catalog system searchable under More Modeled Systems, each built on "
             "demand",
    )
    web.add_argument("--host", default="127.0.0.1",
                     help="Address to serve on (default: 127.0.0.1, this "
                          "machine only)")
    web.add_argument("--port", type=int, default=8765,
                     help="Port to serve on (default: 8765; 0 picks a free one)")
    web.add_argument("--no-open", action="store_true",
                     help="Serve without opening a browser")
    web.add_argument(
        "--build-site", metavar="DIR",
        help="Write the web app as a static site into DIR (replacing it): "
             "every system pre-built, for Cloudflare Pages or GitHub Pages. "
             "Set HYBRASIL_DATA_SOURCE=snapshot to build from the committed "
             "snapshot rather than the live sheet",
    )

    review = parser.add_argument_group("suggestions (Suggest Changes)")
    review.add_argument(
        "--export-suggestions", metavar="FILE.csv",
        help="Write every Suggest Changes submission to a CSV for review. "
             "Nothing is written to the catalog workbook",
    )
    review.add_argument(
        "--suggestions-from", choices=("remote", "local"), default="remote",
        help="remote: the hosted site's Cloudflare D1 database (needs "
             "CLOUDFLARE_ACCOUNT_ID, HYBRASIL_D1_DATABASE_ID and "
             "CLOUDFLARE_API_TOKEN in the environment); local: what --serve "
             "recorded (default: remote)",
    )

    return parser


def _renderer(args) -> str:
    """The renderer an invocation uses: three.js unless it has to be Plotly.

    A PNG is written by Plotly (kaleido), so `--output png` picks Plotly when
    no renderer was asked for; asking for three.js *and* a PNG is an error,
    reported in main().
    """
    if args.renderer:
        return args.renderer
    return "plotly" if args.output == "png" else "three"


def _serve(args, bands, catalog_kwargs) -> None:
    """Run the web app, opening on the system --system names."""
    from .web.app import CATALOG_PREFIX, SystemLibrary, serve

    library = SystemLibrary(bands, frames=args.frames,
                            frame_duration_ms=args.frame_duration,
                            catalog_kwargs=catalog_kwargs)
    if args.source == "catalog":
        cat = library.catalog()
        if cat is None:
            print(f"Error loading catalog: {library.catalog_status()['error']}",
                  file=sys.stderr)
            sys.exit(1)
        try:
            host = cat.resolve_host(args.system)
        except ValueError as e:
            print(f"Error loading system: {e}", file=sys.stderr)
            sys.exit(1)
        # A catalog host a featured system covers opens the featured one.
        initial = next((e["id"] for e in library.index()
                        if e["featured"] and host in e["aliases"]),
                       CATALOG_PREFIX + host)
    else:
        initial = canonical_builtin_name(args.system)
    serve(library, initial, host=args.host, port=args.port,
          open_browser=not args.no_open)


def _build_site(args, bands, catalog_kwargs) -> None:
    """Write the static site, opening on the system --system names."""
    from .web.app import SystemLibrary
    from .web.static_site import SiteBuildError, build_site

    library = SystemLibrary(bands, frames=args.frames,
                            frame_duration_ms=args.frame_duration,
                            catalog_kwargs=catalog_kwargs)

    def progress(n, total, system_id):
        if n == 1 or n % 25 == 0 or n == total:
            print(f"  {n}/{total}  {system_id}", flush=True)

    try:
        summary = build_site(library, args.build_site,
                             canonical_builtin_name(args.system), progress=progress)
    except SiteBuildError as e:
        print(f"Error building the site: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"{summary['systems']} systems, {summary['bytes'] / 1e6:.1f} MB, from "
          f"{summary['catalog']} -> {args.build_site}")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.renderer = _renderer(args)

    # --- List solvents and exit ---
    if args.list_solvents:
        print(f"{'solvent':<16}{'formula':<9}{'bands at (bar)':<28}"
              f"functional ceiling")
        for solvent in SOLVENTS.values():
            at = [f"{p:g}" for p in PRESSURES_BAR
                  if solvent.liquid_range_k(p) is not None]
            ceiling = solvent.ceiling_reason.split(",")[0]
            print(f"{solvent.name:<16}{solvent.formula:<9}"
                  f"{', '.join(at):<28}{ceiling}")
        return

    try:
        bands = SolventChoice.parse(
            args.solvent, args.pressure,
            apply_ceiling=args.band_limit == "functional",
            align_to_orbits=args.band_plane == "orbits",
            albedo=args.albedo, greenhouse_k=args.greenhouse,
            star_colour=args.star_colour == "on")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # A pressure where nothing asked for is liquid is almost certainly a
    # mistake at the command line, so say so rather than drawing a bare scene.
    # A greenhouse offset past every boiling point is the same mistake.
    if not any(band_absent_reason(s, args.pressure, bands.apply_ceiling,
                                  args.greenhouse) is None
               for s in bands.solvents):
        names = ", ".join(s.name.lower() for s in bands.solvents)
        print(f"Warning: no band at {args.pressure:g} bar and "
              f"{args.greenhouse:g} K greenhouse for {names}; "
              f"drawing the system without one.", file=sys.stderr)

    catalog_kwargs = {
        "spreadsheet_id": args.sheet_id,
        "refresh": args.refresh_catalog,
        "offline": args.offline,
    }

    # --- List catalog systems and exit ---
    if args.list_catalog:
        from .data.catalog_loader import get_catalog, catalog_listing
        try:
            catalog = get_catalog(**catalog_kwargs)
        except (ValueError, RuntimeError, ImportError, FileNotFoundError) as e:
            print(f"Error reading catalog: {e}", file=sys.stderr)
            sys.exit(1)
        lines = catalog_listing(catalog)
        print(f"{catalog.workbook_title or 'Catalog'} — {len(lines)} systems with "
              f"plottable planets\n")
        for line in lines:
            print(line)
        return

    if args.export_suggestions:
        from .web import suggestions
        try:
            records = (suggestions.load_local() if args.suggestions_from == "local"
                       else suggestions.load_remote())
        except Exception as e:
            print(f"Error reading suggestions: {e}", file=sys.stderr)
            sys.exit(1)
        n = suggestions.write_csv(records, args.export_suggestions)
        print(f"{n} suggestion(s) -> {args.export_suggestions}")
        return

    # --- The web app: everything from here on happens on request ---
    if args.build_site:
        if args.source != "builtin":
            print("Error: --build-site opens on a built-in system; it always "
                  "includes the whole catalog", file=sys.stderr)
            sys.exit(2)
        _build_site(args, bands, catalog_kwargs)
        return
    if args.serve:
        if args.source not in ("builtin", "catalog"):
            print("Error: --serve opens built-in or catalog systems",
                  file=sys.stderr)
            sys.exit(2)
        _serve(args, bands, catalog_kwargs)
        return

    # --- Load primary system ---
    try:
        if args.source == "catalog":
            system = get_system(args.source, args.system, bands, **catalog_kwargs)
        else:
            system = get_system(args.source, args.system, bands)
    except (ValueError, RuntimeError, FileNotFoundError, ImportError) as e:
        print(f"Error loading system: {e}", file=sys.stderr)
        sys.exit(1)

    # A catalog system a featured one already draws opens as the featured one,
    # which the switcher below is going to contain anyway.
    twin = _featured_twin(system) if args.output == "browser" else None
    if twin:
        print(f"'{system.name}' is the featured system '{twin}'; opening that.",
              file=sys.stderr)
        args.source, args.system = "builtin", twin
        system = get_builtin_system(twin, bands)

    # --- Filter bodies ---
    if args.bodies:
        names = [n.strip() for n in args.bodies.split(",")]
        system = system.filter_bodies(names)

    # --- Resolve time range for the primary system ---
    t_start = jd_from_date(*_parse_date(args.time_start)) if args.time_start else jd_now()
    if args.time_end:
        t_end = jd_from_date(*_parse_date(args.time_end))
    elif args.source == "catalog":
        t_end = t_start + _natural_span_days(system)
    else:
        # Canonicalise first: _NATURAL_SPANS is keyed by canonical name, so
        # `--system ups-and` would otherwise silently fall back to 365.25 days
        # and draw a window far too short for the system it names.
        span = _NATURAL_SPANS.get(canonical_builtin_name(args.system), 365.25)
        t_end = t_start + span

    # --- Build primary figure ---
    fig = build_figure(system, t_start, t_end, mode=args.mode, frames=args.frames,
                       frame_duration_ms=args.frame_duration, title=args.title)

    # --- Output ---
    if args.output == "browser":
        # Every featured system is always in the switcher, whatever the
        # source; the system asked for opens first.
        #
        # A built-in is keyed by its CANONICAL name, not by what the user
        # typed: the switcher is ordered by BUILTIN_NAMES, which holds
        # canonical keys only, so an alias like `--system proxima` would
        # otherwise appear twice.  Anything else is keyed by its own name.
        primary = (canonical_builtin_name(args.system)
                   if args.source == "builtin" else system.name)
        ordered, systems_for_info = _with_featured(primary, fig, system, args,
                                                   bands, t_start)
        if args.renderer == "three":
            ordered, views_js = _with_views(ordered)
            show_three_in_browser(ordered, primary,
                                  extra_js="\n".join([_viewer_js(systems_for_info, bands),
                                                      views_js]))
        else:
            show_in_browser_multi(
                ordered, primary,
                extra_js=_viewer_js(systems_for_info, bands))

    elif args.output == "html":
        out = args.out_file or f"{system.name.replace(' ', '_')}.html"
        if args.renderer == "three":
            save_three_html({args.system: fig}, args.system, out,
                            extra_js=_viewer_js({args.system: system}, bands))
        else:
            save_html(fig, out, extra_js=_viewer_js({args.system: system}, bands))

    elif args.output == "png":
        if args.renderer == "three":
            print("Error: --output png uses Plotly; drop --renderer three",
                  file=sys.stderr)
            sys.exit(2)
        out = args.out_file or f"{system.name.replace(' ', '_')}.png"
        save_png(fig, out)


if __name__ == "__main__":
    main()
