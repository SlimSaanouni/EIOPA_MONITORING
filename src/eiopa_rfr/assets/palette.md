# Monochrome design system — color, type, layout

A reusable design system validated across two production tools (a treasury
decision app and the SLIM front-end). Light mode is the default and only
automatic theme (no OS dark auto-switch). Black, white, and grays
everywhere, with two deliberate exceptions: green/red for rise/fall
indicators (a value's sign, a delta vs. a benchmark), and green/red for
run/stage status (success/failure — launch progress and pipeline stage
dots, `--up`/`--down` reused) — never for anything else (no categorical
chart hues, no other colored badges).

Generic by design: drop the CSS block into any project's `:root`, swap the
logo asset, and everything else — chips, tables, KPI strips, the sidebar
shell — carries over unchanged.

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

  --font-display: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, "Times New Roman", serif;
  --font-ui: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Consolas, monospace;
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
  /* font-* tokens are unchanged in dark mode — only colors flip */
}
```

## Typography

Three system font stacks, no web-font loading (no `@import`, no `<link>` to
a font host) — this keeps the system copy-pasteable with zero external
dependencies and zero flash-of-unstyled-text.

- `--font-ui` (sans): the default. Set once on `body`; everything inherits
  it — nav, buttons, labels, form fields, body copy.
- `--font-display` (serif): reserved for the brand wordmark and page-level
  `<h1>` titles only. Regular weight (400), slightly negative letter-spacing
  on large sizes. Using it sparingly is what makes it read as intentional
  rather than decorative.
- `--font-mono`: for anything numeric, technical, or machine-generated —
  table figures, KPI values, timestamps, file names, status/env badges,
  breadcrumbs, code-like hints. Pair with `font-variant-numeric:
  tabular-nums` on any numeric column so digits align.

Base body size is 14px. Small print (table headers, mono badges, hints)
runs 10.5–12px with `letter-spacing: .02em`–`.05em` and
`text-transform: uppercase` on labels only, never on values. Display
headings run 19–27px; nothing in the UI goes larger than that — this system
has no oversized hero type.

## Layout & component conventions

- **App shell**: two-column CSS grid, `grid-template-columns: 248px 1fr` —
  fixed-width sidebar (nav + contextual info) and a fluid main column
  (`max-width` capped around 1200px, generous padding). Below ~860px,
  collapse to a single column and hide the sidebar rather than turning it
  into an overlay/drawer — simplicity over a mobile nav pattern.
- **Cards/panels**: 1px `--border`, `border-radius: 10px`, `--surface`
  background, ~20px padding. Stack multiple panels with margin between
  them rather than nesting borders.
- **Radius scale**: 6–7px for inputs and small buttons, 8–10px for cards
  and larger controls, `99px` (full pill) for badges, chips, and status
  pills. Nothing else in between — pick from this scale, don't invent
  intermediate values.
- **Hairline-grid stat strips**: a KPI/stat row built as a CSS grid with
  `gap: 1px` and the grid's own background set to `--border`, each cell
  filled with `--surface` — the 1px gaps read as hairline dividers without
  adding per-cell border rules. Reuse this trick anywhere you need a clean
  divided row of equal-width stats.
- **Pills/chips/badges**: pill radius, 1px border, small mono or ui text.
  State is carried by border style and fill, not by hue: solid border +
  `--surface-2` fill = neutral, dashed border = informational/warning/
  disabled, `--accent-soft` fill = selected/primary/"mono" state.
- **Tables**: numeric columns right-aligned in `--font-mono` with
  `tabular-nums`; the first column (labels/names) left-aligned in the UI
  font. Header row is uppercase, small, `--muted`, letter-spaced, with a
  bottom border only. Body rows separated by a bottom border only — no
  vertical rules, no zebra striping.
- **Buttons**: `--btn-primary` solid `--accent` fill with `--surface` text;
  `--btn-ghost` transparent with a `--border` outline and `--muted` text.
  13px, weight 600, radius 7px, no uppercase.
- **Progress/status lists**: a small round dot (6–9px) per row, colored by
  state — `--muted` pending, `--ink` running (optionally with a `pulse`
  keyframe), `--up` done, `--down` failed. Same dot vocabulary works for a
  linear DAG/pipeline view or a flat run list.
- **Focus state**: `outline: 2px solid var(--accent)` with a 1–2px offset
  on every interactive element — no custom focus rings per component.

## How status/identity is encoded without hue

Since color is reserved for rise/fall and run/stage status, everything else
that would normally lean on hue (warning states, categorical identity)
leans on:

- **Glyphs**: ✓ (success), ! (warning), ✕ (error), ▲/▼ (up/down — paired
  with `--up`/`--down` color, since these are the deliberate exceptions,
  along with run/stage status dots).
- **Weight**: bold for emphasis/success, regular otherwise.
- **Border style**: dashed for informational, solid for neutral, thicker
  for errors (`.status-msg` in the original treasury tool's app shell —
  see Provenance below).
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

Colors extracted 2026-08 from the treasury decision tool while adapting its
visual identity from an initial teal accent to this black/white/gray
system, per the user's request to keep it black/white/gray with a
red/green exception for trend indicators only, and to reuse the actual
company logo. Typography and layout conventions added 2026-08 from the
SLIM front-end (`alm_model/frontend/src/theme.css`), which consumed this
same token set and layered a consistent component system on top of it.
This file is meant to be copied as-is into new projects — keep it generic,
swap only the logo asset and any project-specific naming.
