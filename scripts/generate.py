import json, os, colorsys
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "themes")
SCHEMA = "https://raw.githubusercontent.com/TabularisDB/tabularis/main/src/schemas/theme-definition-v1.json"
AUTHOR = "Andrea Debernardi"

# ---------- color math ----------
def rgb(h):
    h = h.lstrip('#'); return [int(h[i:i+2],16)/255 for i in (0,2,4)]
def hexs(c): return "#%02x%02x%02x" % tuple(min(255,max(0,round(x*255))) for x in c)
def lum(h):
    f = lambda v: v/12.92 if v <= 0.03928 else ((v+0.055)/1.055)**2.4
    r,g,b = rgb(h); return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)
def cr(a, b):
    la, lb = lum(a), lum(b); return (max(la,lb)+0.05)/(min(la,lb)+0.05)
def with_l(h, L):
    r,g,b = rgb(h); hh, l, s = colorsys.rgb_to_hls(r,g,b); return hexs(colorsys.hls_to_rgb(hh, max(0,min(1,L)), s))
def L_of(h):
    r,g,b = rgb(h); return colorsys.rgb_to_hls(r,g,b)[1]
def is_dark(h): return lum(h) < 0.25

def fix_fg(fg, bgs, need):
    """Move fg lightness away from the backgrounds until min contrast >= need. Keeps hue/sat."""
    if isinstance(bgs, str): bgs = [bgs]
    if min(cr(fg, b) for b in bgs) >= need: return fg
    dark_bg = sum(lum(b) for b in bgs)/len(bgs) < 0.3
    L = L_of(fg); step = 0.01
    for _ in range(120):
        L = L + step if dark_bg else L - step
        if L > 1 or L < 0: break
        c = with_l(fg, L)
        if min(cr(c, b) for b in bgs) >= need: return c
    return "#ffffff" if dark_bg else "#000000"

def fix_bg(bg, fg, need, toward):
    """Move a background's lightness toward `toward` (theme base) until contrast with fg >= need."""
    if cr(fg, bg) >= need: return bg
    dark = is_dark(toward); L = L_of(bg); step = 0.01
    for _ in range(120):
        L = L - step if dark else L + step
        if L > 1 or L < 0: break
        c = with_l(bg, L)
        if cr(fg, c) >= need: return c
    return toward

def set_lum(h, target):
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo+hi)/2; c = with_l(h, mid)
        if lum(c) < target: lo = mid
        else: hi = mid
    return with_l(h, (lo+hi)/2)

def spread(colors, bgs, need, dark, min_ratio=1.6):
    """Give a group of colors distinct luminance levels (ratio >= min_ratio between neighbours)
    while each stays >= need on bgs. Order preserved by current luminance rank."""
    order = sorted(range(len(colors)), key=lambda i: lum(colors[i]))
    n = len(colors)
    if dark:
        base = max(lum(b) for b in bgs); lo = (base+0.05)*need - 0.05 + 0.02
        levels = [lo * (min_ratio ** k) + 0.05*(min_ratio**k - 1) for k in range(n)]
    else:
        base = min(lum(b) for b in bgs); hi = (base+0.05)/need - 0.05 - 0.005
        levels = [hi]
        for k in range(1, n): levels.insert(0, (levels[0]+0.05)/min_ratio - 0.05)
        levels = [max(0.004, l) for l in levels]
    if max(levels) > 1.0 or min(levels) < 0.004:
        nxt = {1.6: 1.52, 1.52: 1.4, 1.4: 1.3}.get(min_ratio)
        return spread(colors, bgs, need, dark, nxt) if nxt else colors
    out = list(colors)
    for rank, i in enumerate(order): out[i] = set_lum(colors[i], levels[rank])
    return out

def alpha(h, a): return h + "%02x" % a
def mix(a, b, pct):
    """CSS color-mix: a at pct over b (both opaque)."""
    A, B = rgb(a), rgb(b); return hexs([A[i]*pct + B[i]*(1-pct) for i in range(3)])

def fix_on_tint(fg, base, pct, need, extra=()):
    """Keep fg readable on its own tint (fg at pct over base) and on `extra` backgrounds.
    The tint moves with fg, so iterate a few rounds. When the pair cannot reach `need`
    without collapsing to pure white/black, keep the original hue and let the audit warn."""
    start = fg
    for _ in range(6):
        nxt = fix_fg(fg, [mix(fg, base, pct), *extra], need)
        if nxt == fg: break
        fg = nxt
    if fg in ("#ffffff", "#000000") and start not in ("#ffffff", "#000000"): return start
    return fg

# ---------- theme assembly ----------
def rules(kw, string, number, comment, op, delim, ident, identq, predef, invalid):
    r = []
    for t in ["keyword","keyword.block","keyword.choice","keyword.try","keyword.catch"]:
        for s in ("", ".sql"): r.append({"token": t+s, "foreground": kw, "fontStyle": "bold"})
    for t in ["string","string.quote"]:
        for s in ("", ".sql"): r.append({"token": t+s, "foreground": string})
    for s in ("", ".sql"): r.append({"token": "number"+s, "foreground": number})
    for t in ["comment","comment.quote"]:
        for s in ("", ".sql"): r.append({"token": t+s, "foreground": comment, "fontStyle": "italic"})
    for s in ("", ".sql"): r.append({"token": "operator"+s, "foreground": op})
    for t in ["delimiter","delimiter.parenthesis","delimiter.square"]:
        for s in ("", ".sql"): r.append({"token": t+s, "foreground": delim})
    for s in ("", ".sql"): r.append({"token": "identifier"+s, "foreground": ident})
    for s in ("", ".sql"): r.append({"token": "identifier.quote"+s, "foreground": identq})
    for s in ("", ".sql"): r.append({"token": "predefined"+s, "foreground": predef})
    for s in ("", ".sql"): r.append({"token": "invalid"+s, "foreground": invalid, "fontStyle": "underline"})
    return r

def finalize(c, tokens):
    """Apply accessibility corrections to a palette in place and derive editor colors."""
    bg, sf, tx, ac, bd, sm = c["bg"], c["surface"], c["text"], c["accent"], c["border"], c["semantic"]
    dark = is_dark(bg["base"]); base = bg["base"]
    # text.primary must read on every background surface
    for k in ["base","elevated","overlay","input"]: bg[k] = fix_bg(bg[k], tx["primary"], 4.5, base)
    for k in ["primary","secondary","tertiary","hover","disabled"]: sf[k] = fix_bg(sf[k], tx["primary"], 4.5, base)
    # ::selection uses surface.active + text.primary
    sf["active"] = fix_bg(sf["active"], tx["primary"], 4.5, base)
    # tooltips draw text.secondary on bg.tooltip: keep tooltip in the theme's own family
    tx["secondary"] = fix_fg(tx["secondary"], [base, sf["primary"]], 4.5)
    bg["tooltip"] = fix_bg(bg["tooltip"], tx["secondary"], 4.5, base)
    tx["muted"] = fix_fg(tx["muted"], [base, sf["primary"]], 4.5)
    tx["accent"] = fix_fg(tx["accent"], [base, sf["primary"]], 4.5)
    # buttons: text.inverse on accent.primary; pick black or white, then tune accent lightness if needed
    tx["inverse"] = "#000000" if cr("#000000", ac["primary"]) >= cr("#ffffff", ac["primary"]) else "#ffffff"
    if cr(tx["inverse"], ac["primary"]) < 4.5:
        ac["primary"] = fix_bg(ac["primary"], tx["inverse"], 4.5, "#ffffff" if tx["inverse"] == "#000000" else "#000000")
    # status accents read as text on the base and on their own 12-20% tints (banners, chips)
    for k in ["secondary","success","warning","error","info"]:
        ac[k] = fix_on_tint(fix_fg(ac[k], [base], 4.5), bg["elevated"], 0.2, 4.5, extra=[base])
    # accent text also sits on selected chips/rows tinted with accent.primary
    tinted = fix_fg(tx["accent"], [base, sf["primary"], mix(ac["primary"], bg["elevated"], 0.2), mix(ac["primary"], base, 0.1)], 4.5)
    if tinted not in ("#ffffff", "#000000"): tx["accent"] = tinted  # keep the hue when only white/black would pass
    # disabled: visible but weaker than muted
    r = cr(tx["disabled"], base)
    if r < 1.6 or r >= cr(tx["muted"], base) - 0.3:
        tx["disabled"] = fix_fg(with_l(tx["muted"], L_of(base)), [base], 1.8)
    # borders: 3:1 for default/strong/focus (non-text contrast), subtle stays subtle
    bd["default"] = fix_fg(bd["default"], [base], 3.0)
    bd["strong"] = fix_fg(bd["strong"], [base], 3.0)
    bd["focus"] = fix_fg(bd["focus"], [base, sf["primary"]], 3.0)
    # data types: 4.5 on cells; row states and key kinds also separated by luminance for CVD users
    surfaces = [sf["primary"], base]
    for k in sm: sm[k] = fix_fg(sm[k], surfaces, 4.5)
    for grp in (["deleted","modified","new"], ["index","foreignKey","primaryKey"]):
        vals = spread([sm[k] for k in grp], surfaces, 4.5, dark)
        for k, v in zip(grp, vals): sm[k] = fix_fg(v, surfaces, 4.5)
    # edited cells draw the row-state color as text on its own tint over the base
    # (modified at 30%, new at 15%); nudge after the spread, never past white/black
    sm["modified"] = fix_on_tint(sm["modified"], base, 0.3, 4.5, extra=surfaces)
    sm["new"] = fix_on_tint(sm["new"], base, 0.15, 4.5, extra=surfaces)
    # the focus ring must stand out on inputs and dialogs too
    bd["focus"] = fix_fg(bd["focus"], [base, sf["primary"], bg["input"], bg["elevated"]], 3.0)
    # NULL must not look like ordinary text: luminance ratio >= 1.5 vs text.primary
    if cr(sm["null"], tx["primary"]) < 2.0:
        target = (lum(tx["primary"])+0.05)/2.1 - 0.05 if dark else (lum(tx["primary"])+0.05)*2.1 - 0.05
        if 0.004 <= target <= 0.95:
            sm["null"] = fix_fg(set_lum(sm["null"], target), surfaces, 4.5)
    # ---- editor, derived from the corrected palette
    eb, ef = base, tx["primary"]
    tok = {k: fix_fg(v, [eb], 4.5) for k, v in tokens.items()}
    sel = fix_bg(sf["active"], ef, 4.5, eb)
    find = fix_bg(ac["warning"], ef, 4.5, eb)
    ed = {
        "editor.background": eb, "editor.foreground": ef,
        "editor.lineHighlightBackground": fix_bg(bg["elevated"], ef, 4.5, eb),
        "editor.selectionBackground": sel,
        "editor.inactiveSelectionBackground": fix_bg(sf["secondary"], ef, 4.5, eb),
        "editor.selectionHighlightBackground": fix_bg(sf["tertiary"], ef, 4.5, eb),
        "editorCursor.foreground": fix_fg(ac["primary"], [eb], 3.0),
        "editorLineNumber.foreground": tx["muted"],
        "editorLineNumber.activeForeground": tx["secondary"],
        "editorIndentGuide.background": bd["subtle"],
        "editorIndentGuide.activeBackground": bd["default"],
        "editorBracketMatch.border": bd["focus"],
        "editorBracketMatch.background": fix_bg(sf["tertiary"], ef, 4.5, eb),
        "editorWidget.background": bg["elevated"], "editorWidget.border": bd["default"],
        "editorSuggestWidget.background": bg["elevated"],
        "editorSuggestWidget.selectedBackground": fix_bg(sf["hover"], ef, 4.5, eb),
        "editorSuggestWidget.border": bd["default"],
        "editorHoverWidget.background": bg["elevated"], "editorHoverWidget.border": bd["default"],
        "editor.findMatchBackground": find,
        "editor.findMatchHighlightBackground": fix_bg(with_l(find, L_of(find) + (-0.08 if dark else 0.08)), ef, 4.5, eb),
        "editor.wordHighlightBackground": fix_bg(sf["secondary"], ef, 4.5, eb),
        "editorWhitespace.foreground": bd["default"],
        "scrollbarSlider.background": alpha(bd["default"], 0x99), "scrollbarSlider.hoverBackground": alpha(bd["strong"], 0xaa),
        "editorError.foreground": ac["error"], "editorWarning.foreground": ac["warning"],
    }
    return c, {"colors": ed, "rules": rules(tok["kw"], tok["string"], tok["number"], tok["comment"], tok["op"], tok["delim"], tok["ident"], tok["identq"], tok["predef"], tok["invalid"])}

def theme(name, mode, note, colors, tokens, typography=None, layout=None):
    colors, editor = finalize(colors, tokens)
    d = {"$schema": SCHEMA, "schemaVersion": 1, "mode": mode,
         "attribution": f"{name} by {AUTHOR}. {note} MIT licensed.", "colors": colors}
    if typography: d["typography"] = typography
    if layout: d["layout"] = layout
    d["editor"] = editor
    return d

def tk(kw, string, number, comment, op, delim, ident, identq, predef, invalid):
    return dict(kw=kw, string=string, number=number, comment=comment, op=op, delim=delim, ident=ident, identq=identq, predef=predef, invalid=invalid)

T = {}
W95 = {"fontFamily": {"base": ["MS Sans Serif", "Tahoma", "Arial", "sans-serif"], "mono": ["Courier New", "Courier", "monospace"]}}
SQUARE = {"borderRadius": {"sm": 0, "base": 0, "lg": 0, "xl": 0}}

T["spreadsheet-97"] = theme("Spreadsheet 97", "light",
  "Classic 16-color desktop office palette, square corners, system fonts.",
  {"bg": {"base": "#c0c0c0", "elevated": "#ffffff", "overlay": "#c0c0c0", "input": "#ffffff", "tooltip": "#ffffe1"},
   "surface": {"primary": "#ffffff", "secondary": "#c0c0c0", "tertiary": "#dfdfdf", "hover": "#dfdfdf", "active": "#0a246a", "disabled": "#c0c0c0"},
   "text": {"primary": "#000000", "secondary": "#000080", "muted": "#606060", "disabled": "#808080", "accent": "#000080", "inverse": "#ffffff"},
   "accent": {"primary": "#000080", "secondary": "#008080", "success": "#008000", "warning": "#808000", "error": "#ff0000", "info": "#0000ff"},
   "border": {"subtle": "#dfdfdf", "default": "#808080", "strong": "#404040", "focus": "#000000"},
   "semantic": {"string": "#000000", "number": "#000080", "boolean": "#800080", "date": "#008080", "null": "#808080",
                "primaryKey": "#800000", "foreignKey": "#000080", "index": "#808000", "modified": "#808000", "deleted": "#ff0000", "new": "#008000"}},
  tk("#0000ff", "#800000", "#000000", "#008000", "#000000", "#000000", "#000000", "#800080", "#000080", "#ff0000"), W95, SQUARE)

T["hot-dog-stand"] = theme("Hot Dog Stand", "dark",
  "Ketchup, mustard and black, after the infamous 1992 desktop scheme.",
  {"bg": {"base": "#e00000", "elevated": "#e00000", "overlay": "#000000", "input": "#b00000", "tooltip": "#b00000"},
   "surface": {"primary": "#e00000", "secondary": "#c00000", "tertiary": "#a00000", "hover": "#c00000", "active": "#7a0000", "disabled": "#a00000"},
   "text": {"primary": "#ffff00", "secondary": "#ffffff", "muted": "#ffe8d1", "disabled": "#ff8080", "accent": "#ffff00", "inverse": "#000000"},
   "accent": {"primary": "#ffff00", "secondary": "#ffffff", "success": "#ffff00", "warning": "#ffff00", "error": "#000000", "info": "#ffffff"},
   "border": {"subtle": "#000000", "default": "#000000", "strong": "#000000", "focus": "#ffff00"},
   "semantic": {"string": "#ffffff", "number": "#ffff00", "boolean": "#ffe8d1", "date": "#ffffff", "null": "#ffe8d1",
                "primaryKey": "#ffff00", "foreignKey": "#ffffff", "index": "#c8ffff", "modified": "#ffff00", "deleted": "#c8ffff", "new": "#ffffff"}},
  tk("#ffffff", "#ffff00", "#ffff00", "#ffe8d1", "#ffffff", "#ffe8d1", "#ffff00", "#ffffff", "#ffffff", "#c8ffff"), W95, SQUARE)

T["traffic-light"] = theme("Traffic Light", "dark",
  "Neutral graphite chrome; data follows road rules: red for NULL, amber for booleans, green for everything else.",
  {"bg": {"base": "#1a1c1f", "elevated": "#202327", "overlay": "#2a2e33", "input": "#15171a", "tooltip": "#2a2e33"},
   "surface": {"primary": "#22252a", "secondary": "#2c3036", "tertiary": "#383d44", "hover": "#2c3036", "active": "#ffb300", "disabled": "#22252a"},
   "text": {"primary": "#e8e8e8", "secondary": "#b0b4ba", "muted": "#7a7f86", "disabled": "#4d5157", "accent": "#ffb300", "inverse": "#1a1c1f"},
   "accent": {"primary": "#ffb300", "secondary": "#34c759", "success": "#34c759", "warning": "#ffcc00", "error": "#ff3b30", "info": "#b0b4ba"},
   "border": {"subtle": "#2a2e33", "default": "#383d44", "strong": "#4d5157", "focus": "#ffb300"},
   "semantic": {"string": "#34c759", "number": "#5ad67a", "boolean": "#ffcc00", "date": "#2ea44f", "null": "#ff3b30",
                "primaryKey": "#ffcc00", "foreignKey": "#34c759", "index": "#8e8e93", "modified": "#ffcc00", "deleted": "#ff3b30", "new": "#34c759"}},
  tk("#ffcc00", "#34c759", "#5ad67a", "#6e6e73", "#ff9500", "#b0b4ba", "#e8e8e8", "#ffcc00", "#5ad67a", "#ff3b30"))

T["breadbin-64"] = theme("Breadbin 64", "dark",
  "Sixteen-color 1982 home computer palette on the classic blue screen with a lighter border.",
  {"bg": {"base": "#40318d", "elevated": "#352879", "overlay": "#000000", "input": "#352879", "tooltip": "#352879"},
   "surface": {"primary": "#40318d", "secondary": "#4a3a9a", "tertiary": "#5a4bab", "hover": "#4a3a9a", "active": "#7869c4", "disabled": "#352879"},
   "text": {"primary": "#e6e2ff", "secondary": "#a9a0e8", "muted": "#9a90dc", "disabled": "#4a3a9a", "accent": "#aaffee", "inverse": "#000000"},
   "accent": {"primary": "#7869c4", "secondary": "#aaffee", "success": "#00cc55", "warning": "#eeee77", "error": "#ff7777", "info": "#0088ff"},
   "border": {"subtle": "#4a3a9a", "default": "#7869c4", "strong": "#aaffee", "focus": "#ffffff"},
   "semantic": {"string": "#eeee77", "number": "#aaffee", "boolean": "#e070e0", "date": "#aaff66", "null": "#a0a0a0",
                "primaryKey": "#dd8855", "foreignKey": "#5cb0ff", "index": "#c9a3ff", "modified": "#eeee77", "deleted": "#e070e0", "new": "#00cc55"}},
  tk("#aaffee", "#eeee77", "#aaff66", "#a9a0e8", "#ffffff", "#bbbbbb", "#e6e2ff", "#e070e0", "#5cb0ff", "#ff7777"),
  {"fontFamily": {"base": ["C64 Pro", "Press Start 2P", "Verdana", "sans-serif"], "mono": ["C64 Pro Mono", "Press Start 2P", "Courier New", "monospace"]}}, SQUARE)

T["highlighter"] = theme("Highlighter", "light",
  "White paper, black ink and fluorescent marker tones; selections are literally highlighted.",
  {"bg": {"base": "#ffffff", "elevated": "#fafafa", "overlay": "#ffffff", "input": "#ffffff", "tooltip": "#fff9c4"},
   "surface": {"primary": "#ffffff", "secondary": "#f5f5f5", "tertiary": "#ebebeb", "hover": "#fff9c4", "active": "#ffe600", "disabled": "#f5f5f5"},
   "text": {"primary": "#1a1a1a", "secondary": "#4a4a4a", "muted": "#6e6e6e", "disabled": "#bdbdbd", "accent": "#8a6d00", "inverse": "#1a1a1a"},
   "accent": {"primary": "#ffe600", "secondary": "#e0006b", "success": "#1e8449", "warning": "#b56a00", "error": "#d50032", "info": "#0072a3"},
   "border": {"subtle": "#eeeeee", "default": "#8a8a8a", "strong": "#1a1a1a", "focus": "#e0006b"},
   "semantic": {"string": "#c8006f", "number": "#c85a00", "boolean": "#00806f", "date": "#6a3fd6", "null": "#767676",
                "primaryKey": "#9a7700", "foreignKey": "#0072a3", "index": "#4f8a10", "modified": "#b56a00", "deleted": "#d50032", "new": "#1e8449"}},
  tk("#c8006f", "#c85a00", "#6a3fd6", "#767676", "#1a1a1a", "#4a4a4a", "#1a1a1a", "#00806f", "#0072a3", "#d50032"))

T["watermelon"] = theme("Watermelon", "light",
  "Pink flesh, green rind and black seeds for NULL values.",
  {"bg": {"base": "#fff0f2", "elevated": "#ffe1e6", "overlay": "#ffffff", "input": "#ffffff", "tooltip": "#ffe1e6"},
   "surface": {"primary": "#ffe1e6", "secondary": "#ffd0d8", "tertiary": "#ffbcc8", "hover": "#ffd0d8", "active": "#c8e6d2", "disabled": "#ffe1e6"},
   "text": {"primary": "#3b1f1f", "secondary": "#7a3b45", "muted": "#8f4f5a", "disabled": "#d19aa3", "accent": "#1f6b42", "inverse": "#ffffff"},
   "accent": {"primary": "#2e8b57", "secondary": "#c92a4c", "success": "#1f6b42", "warning": "#a85400", "error": "#b71c1c", "info": "#1f5f3f"},
   "border": {"subtle": "#ffd0d8", "default": "#c98a95", "strong": "#2e8b57", "focus": "#2e8b57"},
   "semantic": {"string": "#b8203f", "number": "#1f6b42", "boolean": "#1f5f3f", "date": "#a8125a", "null": "#1a1a1a",
                "primaryKey": "#a85400", "foreignKey": "#1f6b42", "index": "#6d4c41", "modified": "#a85400", "deleted": "#b71c1c", "new": "#1f6b42"}},
  tk("#1f6b42", "#b8203f", "#a8125a", "#8f4f5a", "#1a1a1a", "#7a3b45", "#3b1f1f", "#a85400", "#1f5f3f", "#b71c1c"))

T["bubblegum"] = theme("Bubblegum", "light",
  "Pink on pink on pink, from powder to fuchsia.",
  {"bg": {"base": "#ffe6f2", "elevated": "#ffd6ea", "overlay": "#fff0f7", "input": "#fff5fa", "tooltip": "#ffd6ea"},
   "surface": {"primary": "#ffd6ea", "secondary": "#ffc2e0", "tertiary": "#ffb3d9", "hover": "#ffb3d9", "active": "#ff9ccf", "disabled": "#ffd6ea"},
   "text": {"primary": "#4a1a33", "secondary": "#7a2f5a", "muted": "#8f4a70", "disabled": "#d9a6c2", "accent": "#b3005c", "inverse": "#4a1a33"},
   "accent": {"primary": "#ff4fa3", "secondary": "#8a2be2", "success": "#a8207a", "warning": "#b3457f", "error": "#a3003a", "info": "#7a2ea6"},
   "border": {"subtle": "#ffc2e0", "default": "#c97aa8", "strong": "#b3005c", "focus": "#b3005c"},
   "semantic": {"string": "#b3005c", "number": "#7a007a", "boolean": "#a01050", "date": "#5e2a8c", "null": "#8c7f86",
                "primaryKey": "#c00068", "foreignKey": "#6a35c8", "index": "#6f6470", "modified": "#b85c1e", "deleted": "#a3003a", "new": "#7b1fa2"}},
  tk("#b3005c", "#7a007a", "#5e2a8c", "#8f4a70", "#8a2be2", "#7a2f5a", "#4a1a33", "#a01050", "#8a30b0", "#a3003a"))

T["green-rain"] = theme("Green Rain", "dark",
  "Pure black and phosphor green; there is no spoon.",
  {"bg": {"base": "#000000", "elevated": "#020a04", "overlay": "#041a0a", "input": "#000000", "tooltip": "#041a0a"},
   "surface": {"primary": "#03130a", "secondary": "#05200e", "tertiary": "#083016", "hover": "#05200e", "active": "#0a4a1c", "disabled": "#03130a"},
   "text": {"primary": "#00ff41", "secondary": "#00d636", "muted": "#00a82a", "disabled": "#004d19", "accent": "#7dff9a", "inverse": "#000000"},
   "accent": {"primary": "#00ff41", "secondary": "#7dff9a", "success": "#00ff41", "warning": "#ccff00", "error": "#ff3b5c", "info": "#00d636"},
   "border": {"subtle": "#041a0a", "default": "#0e5a24", "strong": "#00802a", "focus": "#00ff41"},
   "semantic": {"string": "#7dff9a", "number": "#00ff41", "boolean": "#baffc9", "date": "#4dff70", "null": "#00892a",
                "primaryKey": "#ffffff", "foreignKey": "#7dff9a", "index": "#a0b8a8", "modified": "#e6ff00", "deleted": "#ff3b5c", "new": "#00ff41"}},
  tk("#ffffff", "#7dff9a", "#baffc9", "#00a82a", "#ccff00", "#00d636", "#00ff41", "#4dff70", "#7dff9a", "#ff3b5c"),
  {"fontFamily": {"mono": ["IBM Plex Mono", "Courier New", "monospace"]}})

for vid, d in T.items():
    with open(os.path.join(OUT, vid + ".json"), "w") as f:
        json.dump(d, f, indent=2); f.write("\n")
print("generated", len(T))
