# SSA Invest — monochrome palette

Validated on the treasury decision tool (`tools/app_shell.html`) — light mode
is the default and only automatic theme (no OS dark auto-switch). Black,
white, and grays everywhere, with two deliberate exceptions: green/red for
rise/fall indicators (a value's sign, a delta vs. a benchmark), and
green/red for run/stage status (success/failure — SLIM front-end's launch
progress and pipeline stage dots, `--up`/`--down` reused) — never for
anything else (no categorical chart hues, no other colored badges).

## Tokens (CSS custom properties)

```css
:root {
  --bg: #FAFAFA;
  --surface: #FFFFFF;
  --surface-2: #F0F0F0;
  --ink: #0A0A0A;
  --muted: #6E6E6E;
  --border: #DADADA;
  --accent: #111111;
  --accent-ink: #000000;
  --accent-soft: #ECECEC;
  --chart-surface: #FFFFFF;
  --grid: #E9E9E9;
  --axis: #BFBFBF;
  --cat-1: #0D0D0D;  /* categorical steps for multi-series charts —      */
  --cat-2: #4A4A4A;  /* lightness only, no hue. Pair with direct labels  */
  --cat-3: #808080;  /* rather than relying on a legend alone.           */
  --cat-4: #ABABAB;
  --up: #0F8A3C;    /* rise/positive delta, and run/stage success — the only green usage */
  --down: #C4291C;  /* fall/negative delta, and run/stage failure — the only red usage   */
  --shadow: 0 1px 2px rgba(0,0,0,0.05), 0 8px 24px rgba(0,0,0,0.08);
}

/* Manual-only dark variant — do not wire to prefers-color-scheme unless
   the user asks for it; this palette's whole point was "light by default". */
:root[data-theme="dark"] {
  --bg: #0A0A0A;
  --surface: #161616;
  --surface-2: #202020;
  --ink: #F2F2F2;
  --muted: #9C9C9C;
  --border: #2E2E2E;
  --accent: #F2F2F2;
  --accent-ink: #FFFFFF;
  --accent-soft: #262626;
  --chart-surface: #161616;
  --grid: #262626;
  --axis: #3D3D3D;
  --cat-1: #F2F2F2;
  --cat-2: #BABABA;
  --cat-3: #8A8A8A;
  --cat-4: #6B6B6B;
  --up: #3FC168;
  --down: #E15B4D;
  --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 8px 24px rgba(0,0,0,0.35);
}
```

## How status/identity is encoded without hue

Since color is reserved for rise/fall and run/stage status, everything else
that would normally lean on hue (warning states, categorical identity)
leans on:

- **Glyphs**: ✓ (success), ! (warning), ✕ (error), ▲/▼ (up/down — paired
  with `--up`/`--down` color, since these are the deliberate exceptions,
  along with run/stage status dots).
- **Weight**: bold for emphasis/success, regular otherwise.
- **Border style**: dashed for informational, solid for neutral, thicker
  for errors — see `.status-msg` in `tools/app_shell.html`.
- **Direct labels**: multi-series charts (e.g. a stacked area of several
  assets) rely on `--cat-1..4` lightness steps *plus* labels next to each
  segment — never color identity alone.

## Logo usage

See `logo-mark.svg` in this folder. Key points, don't relearn these by
re-deriving from the original source files:

- Use `logo-mark.svg`, not the original `Logo_white.svg` / `Logo Noir.svg`
  from the brand charter folder — the black variant is a ~100KB raster PNG
  wrapped in SVG masking, unusable inline; the white one is the clean
  vector but ships a lot of empty margin.
- `stroke="currentColor"` throughout — tint by setting `color` on a
  wrapping element (e.g. `color: var(--ink)`), not by editing the SVG. This
  is what makes it invert automatically between light and dark surfaces.
- The `viewBox` is already cropped to the mark's ink. To size it against a
  heading, set the SVG's CSS `height` to that heading's rendered
  line-height and leave `width: auto` — no extra math needed, 100% of that
  height is visible mark.

## Provenance

Extracted 2026-08 from the SSA Invest treasury decision tool while adapting
its visual identity from an initial teal accent to this black/white/gray
system, per the user's request to keep it black/white/gray with a red/green
exception for trend indicators only, and to reuse the actual company logo.
