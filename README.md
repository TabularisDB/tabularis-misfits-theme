# Misfits for Tabularis

[![Validate theme](https://github.com/TabularisDB/tabularis-misfits-theme/actions/workflows/validate.yml/badge.svg)](https://github.com/TabularisDB/tabularis-misfits-theme/actions/workflows/validate.yml)
[![Accessibility](https://github.com/TabularisDB/tabularis-misfits-theme/actions/workflows/accessibility.yml/badge.svg)](https://github.com/TabularisDB/tabularis-misfits-theme/actions/workflows/accessibility.yml)

Eight deliberately odd themes for [Tabularis](https://tabularis.dev), in one package.
None of them is trying to be tasteful. Some of them are trying to be funny. All of
them are declarative JSON, not executable plugins.

| Variant | Mode | Background | Text | Accent | The idea |
| --- | --- | --- | --- | --- | --- |
| Spreadsheet 97 | light | `#c0c0c0` | `#000000` | `#000080` | A 1997 office suite: grey chrome, white cells, navy selection, square corners, system fonts. |
| Hot Dog Stand | dark | `#9c0000` | `#ffff00` | `#ffff00` | The infamous ketchup-and-mustard desktop scheme with mustard borders, the red cooked a little darker so every pair reaches AA. You were warned. |
| Traffic Light | dark | `#1a1c1f` | `#e8e8e8` | `#ffb300` | Neutral graphite chrome. Data follows road rules: `NULL` is red, booleans are amber, everything else is green. |
| Breadbin 64 | dark | `#352879` | `#e6e2ff` | `#7869c4` | The 1982 home computer: blue screen, lighter border, a sixteen-color palette for data types. |
| Highlighter | light | `#ffffff` | `#1a1a1a` | `#ffe600` | Paper, ink and fluorescent markers. Selections and search hits are literally highlighted. |
| Watermelon | light | `#fff0f2` | `#3b1f1f` | `#2e8b57` | Pink flesh, green rind, and dark seeds for `NULL`. |
| Bubblegum | light | `#ffe6f2` | `#4a1a33` | `#ff4fa3` | Pink on pink on pink, from powder to fuchsia (status colors excepted, so success and warning never look alike). |
| Green Rain | dark | `#000000` | `#00ff41` | `#00ff41` | Pure black and phosphor green. There is no spoon. |
Spreadsheet 97, Hot Dog Stand and Breadbin 64 also set square corners and a period
font stack through the theme's `typography` and `layout` sections. Fonts fall back
to whatever the system provides, so nothing needs to be installed.

## Accessibility

Odd does not mean unreadable. Every variant passes `scripts/a11y-audit.py`, which checks
the color pairs Tabularis actually draws, with WCAG 2.2 thresholds:

- **Text (AA, 4.5:1):** primary, secondary, muted and accent text on every background and
  surface, including tooltips, hover, selected rows (`surface.active` under `::selection`),
  buttons (`text.inverse` on `accent.primary`) and every status accent used as text.
- **Tinted surfaces (4.5:1):** status accents on their own 12% banner and 20% chip tints,
  `text.accent` on rows and chips tinted with `accent.primary`, edited grid cells
  (`semantic.modified` at 30%, `semantic.new` at 15%, and the primary text over edited JSON
  cells), plus the black-or-white label Tabularis derives for solid success, warning, error
  and secondary buttons.
- **Data values (4.5:1):** all eleven `semantic` colors on grid cells and on the base background.
- **Non-text (3:1):** default and strong borders, the focus ring on the base, inputs and
  dialogs, cursor, line numbers, bracket-match border, diagnostic squiggles and the faded,
  struck-through pending-delete rows.
- **Editor:** every SQL token color on the editor background, and the editor foreground over
  every highlight background (selection, inactive selection, find matches, word highlight,
  bracket match, current line, suggest and hover widgets), with alpha composited.
- **Color-blind safety:** row states (`modified` / `deleted` / `new`) and key kinds
  (`primaryKey` / `foreignKey` / `index`) are separated by luminance as well as hue, and
  checked under simulated protanopia, deuteranopia and tritanopia. `NULL` never looks like
  ordinary text. Status badges (`success` / `warning` / `error`) are checked for hue
  distance as well.

The palettes in `scripts/generate.py` are the artistic intent. The generator first nudges
lightness, never hue, until the basic pairs pass, then uses the audit itself as an oracle: a
greedy search moves the lightness of accents, text and data colors (one at a time, then in
pairs) until no check warns, preferring the passing color closest to the palette as written,
and never pushing a color into pure white or black. It then writes `themes/*.json`. Run the
audit with:

```sh
python3 scripts/a11y-audit.py          # summary, non-passing checks only
python3 scripts/a11y-audit.py -v       # every check
```

The **Accessibility** workflow runs the same audit with `--github` on every push and pull
request that touches `themes/` or the script: a failing pair fails the check and is
annotated on the theme file, warnings are grouped into one annotation per variant, and the
job summary shows a pass/warn/fail table.

Every variant currently passes every check with no warnings. Pending deletes are faded on
purpose, so they are held to the 3:1 non-text ratio rather than 4.5:1. Accessibility cost a
few liberties with the originals: Hot Dog Stand's red is darker than the 1992 scheme and its
borders are mustard (black lines do not reach 3:1 on a red dark enough for AA text), and
Breadbin 64 uses the darker of the two classic blues as its screen.

## Compatibility

Requires Tabularis **0.25.1-1 or later**: the nightly that first accepts a manifest
with a stable package `id` and a free-form display `name`, following the current
Tabularium manifest schema. Any later nightly and the next stable release (0.25.1 or
newer) also work. Tabularis 0.25.0 rejects this package, because its bundled schema
predates the `id` field.

Builds that include [TabularisDB/tabularis#809](https://github.com/TabularisDB/tabularis/pull/809)
paint the whole application from these definitions: square corners apply to every
control, `typography` replaces the UI font unless the user picked one, `text.accent`
colors links and labels, `border.focus` outlines focused fields, and row states, keys
and status banners use the `semantic` and `accent` colors. Older builds keep their own
blue/red/green for those parts and ignore `typography` and `layout`.

## Installation

1. Download `theme-universal.zip` from this repository's GitHub Releases.
2. In Tabularis, open **Settings → Appearance → Manage themes → Local package**.
3. Preview and install the package.
4. Select a variant and apply it. Installation alone does not change the selected theme.

The ZIP is universal: the same file works on all supported operating systems.

## Editing and validation

Each variant lives in `themes/<id>.json`, generated by `scripts/generate.py`: edit the
palette there and re-run it, then run the accessibility audit. Application colors live under
`colors`, fonts under `typography`, corner radii under `layout`; Monaco colors and SQL token
rules remain under `editor`.

The `$schema` hints let external editors offer completion and validation. The
manifest uses Tabularium's schema; theme definitions use the canonical schema on GitHub:

| File | Public schema |
| --- | --- |
| `.tabularium` | https://registry.tabularis.dev/manifest.schema.json?kind=theme |
| `themes/*.json` | https://raw.githubusercontent.com/TabularisDB/tabularis/main/src/schemas/theme-definition-v1.json |

To check the manifest against the live registry schema and build the package
locally, with Node.js 22 and no account or token:

```sh
npx --yes @tabularium/cli validate .tabularium --registry https://registry.tabularis.dev --kind theme
zip -X -D -r theme-universal.zip .tabularium LICENSE.txt README.md themes
```

Validation does not submit or publish the theme.

## CI and releases

- **Branch pushes / pull requests:** run the accessibility audit (separate
  **Accessibility** check, see above), validate the manifest against the live
  Tabularium schema and build the ZIP. Both workflows have read-only permissions
  and need no secrets.
- **Version tags:** check that the tag matches the manifest version, run the
  accessibility audit, validate,
  build, then create a **draft** GitHub release containing `theme-universal.zip`.

Releasing a version:

1. Increment `version` in `.tabularium`. If the pack starts relying on newer host
   features, raise `min_runtime_version` to the first Tabularis release providing them.
2. Tag and push:

   ```sh
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. Review the generated draft and ZIP, then publish the release.
4. Submit this repository through Tabularium. Registry approval and ingestion are
   separate from GitHub release publication.

Keep the package `id` and variant IDs stable across versions.

## Credits

All palettes are original compositions or reproductions of historical, generic
color schemes. No trademarked names are used for the variants. MIT licensed.
