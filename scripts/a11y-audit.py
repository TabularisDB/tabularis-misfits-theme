import json, glob, sys, math, itertools, os
ROOT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "themes")
VERBOSE = "-v" in sys.argv
GITHUB = "--github" in sys.argv  # workflow annotations + job summary

def rgb(h):
    h = h.lstrip('#'); a = int(h[6:8],16)/255 if len(h)==8 else 1.0
    return [int(h[i:i+2],16)/255 for i in (0,2,4)], a
def over(fg, bg):  # composite fg (with alpha) over opaque bg -> opaque rgb
    (f,a),(b,_) = rgb(fg), rgb(bg)
    return [f[i]*a + b[i]*(1-a) for i in range(3)]
def lum(c):
    f = lambda v: v/12.92 if v <= 0.03928 else ((v+0.055)/1.055)**2.4
    return 0.2126*f(c[0]) + 0.7152*f(c[1]) + 0.0722*f(c[2])
def cr(fg, bg, alpha_bg_base=None):
    b = over(bg, alpha_bg_base) if alpha_bg_base else rgb(bg)[0]
    f = over(fg, "#%02x%02x%02x" % tuple(round(x*255) for x in b))
    lf, lb = lum(f), lum(b); return (max(lf,lb)+0.05)/(min(lf,lb)+0.05)
def hexs(c): return "#%02x%02x%02x" % tuple(round(x*255) for x in c)
def alpha(h, a): return h + "%02x" % a
def mix(a, b, pct):  # css color-mix a pct% over b
    A,_ = rgb(a); B,_ = rgb(b); return hexs([A[i]*pct + B[i]*(1-pct) for i in range(3)])

# --- CIEDE2000 + CVD simulation (Machado 2009, severity 1.0) ---
def lin(c):
    return [v/12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4 for v in c]
def to_lab(c):
    r,g,b = lin(c)
    x = (0.4124*r+0.3576*g+0.1805*b)/0.95047; y = (0.2126*r+0.7152*g+0.0722*b); z = (0.0193*r+0.1192*g+0.9505*b)/1.08883
    f = lambda t: t**(1/3) if t > 0.008856 else 7.787*t + 16/116
    fx,fy,fz = f(x),f(y),f(z); return [116*fy-16, 500*(fx-fy), 200*(fy-fz)]
def de2000(c1, c2):
    L1,a1,b1 = to_lab(c1); L2,a2,b2 = to_lab(c2)
    C1,C2 = math.hypot(a1,b1), math.hypot(a2,b2); Cb = (C1+C2)/2
    G = 0.5*(1-math.sqrt(Cb**7/(Cb**7+25**7)))
    a1p,a2p = a1*(1+G), a2*(1+G); C1p,C2p = math.hypot(a1p,b1), math.hypot(a2p,b2)
    h = lambda a,b: (math.degrees(math.atan2(b,a)) % 360) if (a or b) else 0
    h1,h2 = h(a1p,b1), h(a2p,b2)
    dL = L2-L1; dC = C2p-C1p
    dh = 0 if C1p*C2p == 0 else (h2-h1 if abs(h2-h1) <= 180 else (h2-h1-360 if h2-h1 > 180 else h2-h1+360))
    dH = 2*math.sqrt(C1p*C2p)*math.sin(math.radians(dh/2))
    Lb = (L1+L2)/2; Cbp = (C1p+C2p)/2
    if C1p*C2p == 0: hb = h1+h2
    elif abs(h1-h2) <= 180: hb = (h1+h2)/2
    else: hb = (h1+h2+360)/2 if h1+h2 < 360 else (h1+h2-360)/2
    T = 1-0.17*math.cos(math.radians(hb-30))+0.24*math.cos(math.radians(2*hb))+0.32*math.cos(math.radians(3*hb+6))-0.20*math.cos(math.radians(4*hb-63))
    SL = 1+0.015*(Lb-50)**2/math.sqrt(20+(Lb-50)**2); SC = 1+0.045*Cbp; SH = 1+0.015*Cbp*T
    RT = -2*math.sqrt(Cbp**7/(Cbp**7+25**7))*math.sin(math.radians(60*math.exp(-((hb-275)/25)**2)))
    return math.sqrt((dL/SL)**2+(dC/SC)**2+(dH/SH)**2+RT*(dC/SC)*(dH/SH))
CVD = {
 "protan": [[0.152286,1.052583,-0.204868],[0.114503,0.786281,0.099216],[-0.003882,-0.048116,1.051998]],
 "deutan": [[0.367322,0.860646,-0.227968],[0.280085,0.672501,0.047413],[-0.011820,0.042940,0.968881]],
 "tritan": [[1.255528,-0.076749,-0.178779],[-0.078411,0.930809,0.147602],[0.004733,0.691367,0.303900]],
}
def simulate(c, kind):
    l = lin(c); M = CVD[kind]
    out = [sum(M[i][j]*l[j] for j in range(3)) for i in range(3)]
    g = lambda v: 12.92*v if v <= 0.0031308 else 1.055*v**(1/2.4)-0.055
    return [min(1,max(0,g(v))) for v in out]

def audit(path):
    d = json.load(open(path)); return d, audit_theme(d)

def audit_theme(d):
    c = d["colors"]; e = d["editor"]["colors"]; rules = d["editor"]["rules"]
    bg, sf, tx, ac, bd, sm = c["bg"], c["surface"], c["text"], c["accent"], c["border"], c["semantic"]
    R = []  # (id, status, ratio, need, desc)
    def chk(id_, fg, bgc, need, desc, base=None, warn=None):
        r = cr(fg, bgc, base); st = "PASS" if r >= need else ("WARN" if warn and r >= warn else "FAIL")
        R.append((id_, st, r, need, desc))
    # ---- App
    for k in ["base","elevated","overlay","input"]: chk("A1", tx["primary"], bg[k], 4.5, f"text.primary on bg.{k}")
    for k in ["primary","secondary","tertiary","hover"]: chk("A1", tx["primary"], sf[k], 4.5, f"text.primary on surface.{k}")
    for k in ["base"]: chk("A2", tx["secondary"], bg[k], 4.5, "text.secondary on bg.base")
    chk("A2", tx["secondary"], sf["primary"], 4.5, "text.secondary on surface.primary")
    chk("A2", tx["secondary"], bg["tooltip"], 4.5, "text.secondary on bg.tooltip (tooltips)")
    chk("A3", tx["muted"], bg["base"], 4.5, "text.muted on bg.base", warn=3.0)
    chk("A3", tx["muted"], sf["primary"], 4.5, "text.muted on surface.primary", warn=3.0)
    chk("A4", tx["accent"], bg["base"], 4.5, "text.accent on bg.base")
    chk("A5", tx["inverse"], ac["primary"], 4.5, "text.inverse on accent.primary (buttons)")
    chk("A6", tx["primary"], sf["active"], 4.5, "text.primary on surface.active (::selection)")
    for k in ["secondary","success","warning","error","info"]: chk("A7", ac[k], bg["base"], 4.5, f"accent.{k} as text on bg.base", warn=3.0)
    chk("A8", bd["default"], bg["base"], 3.0, "border.default on bg.base (1.4.11)", warn=1.5)
    chk("A8", bd["focus"], bg["base"], 3.0, "border.focus on bg.base (focus ring)")
    chk("A8", bd["focus"], sf["primary"], 3.0, "border.focus on surface.primary")
    for k,v in sm.items():
        chk("A9", v, sf["primary"], 4.5, f"semantic.{k} on surface.primary")
        chk("A9", v, bg["base"], 4.5, f"semantic.{k} on bg.base")
    # ---- Pairs the host draws since TabularisDB/tabularis#809: tinted fills with accent text,
    #      row-state tints, focus token, derived labels on non-primary fills, status hues
    for k in ["secondary","success","warning","error","info"]:
        for pct, what in ((0.12, "banner"), (0.2, "chip")):
            chk("B1", ac[k], mix(ac[k], bg["elevated"], pct), 4.5, f"accent.{k} as text on its {int(pct*100)}% tint ({what})", warn=3.0)
    chk("B1", tx["accent"], mix(ac["primary"], bg["elevated"], 0.2), 4.5, "text.accent on accent.primary@20% (selected chips)", warn=3.0)
    chk("B1", tx["accent"], mix(ac["primary"], bg["base"], 0.1), 4.5, "text.accent on accent.primary@10% (selected row number)", warn=3.0)
    chk("B2", tx["primary"], mix(ac["primary"], bg["base"], 0.1), 4.5, "text.primary on accent.primary@10% (selected row)", warn=3.0)
    for k, pct in (("modified", 0.3), ("new", 0.15)):
        chk("B2", sm[k], mix(sm[k], bg["base"], pct), 4.5, f"semantic.{k} as text on its {int(pct*100)}% tint (edited cell)", warn=3.0)
        chk("B2", tx["primary"], mix(sm[k], bg["base"], 0.25), 4.5, f"text.primary on semantic.{k}@25% (edited JSON cell)", warn=3.0)
    # pending deletes are struck through and faded on purpose: non-text threshold, like disabled text
    chk("B2", alpha(sm["deleted"], 0x99), mix(sm["deleted"], bg["base"], 0.1), 3.0, "semantic.deleted@60% on its 10% row tint (pending delete, de-emphasized)", base=bg["base"], warn=2.0)
    chk("B2", tx["secondary"], mix(sm["new"], bg["base"], 0.05), 4.5, "text.secondary on semantic.new@5% (untouched new row)", warn=3.0)
    chk("B3", bd["focus"], bg["input"], 3.0, "border.focus on bg.input (focused field)")
    chk("B3", bd["focus"], bg["elevated"], 3.0, "border.focus on bg.elevated (focused field in dialogs)")
    for k in ["secondary","success","warning","error","info"]:
        label = "#000000" if to_lab(rgb(ac[k])[0])[0] > 49.44 else "#ffffff"
        chk("B4", label, ac[k], 4.5, f"host-derived {label} label on accent.{k} (solid button)", warn=3.0)
    for a, b in itertools.combinations(["success","warning","error"], 2):
        de = de2000(rgb(ac[a])[0], rgb(ac[b])[0])
        R.append(("B5", "PASS" if de >= 20 else "WARN", de, 20, f"ΔE2000 accent.{a} vs accent.{b} (status badges)"))
    rd = cr(tx["disabled"], bg["base"]); rm = cr(tx["muted"], bg["base"])
    R.append(("A10", "PASS" if 1.4 <= rd < rm else "WARN", rd, 1.4, "text.disabled visible but weaker than muted"))
    # ---- Distinguishability of row states and key types
    for grp, keys in [("row states", ["modified","deleted","new"]), ("keys", ["primaryKey","foreignKey","index"]), ("null vs text", None)]:
        pairs = list(itertools.combinations(keys, 2)) if keys else [("null", None)]
        for a, b in pairs:
            ca = rgb(sm[a])[0]; cb = rgb(sm[b])[0] if b else rgb(tx["primary"])[0]
            nb = b or "text.primary"
            de = de2000(ca, cb); R.append(("A11", "PASS" if de >= 20 else ("WARN" if de >= 10 else "FAIL"), de, 20, f"ΔE2000 {a} vs {nb} (normal vision)"))
            for kind in CVD:
                des = de2000(simulate(ca, kind), simulate(cb, kind)); lr = (max(lum(ca),lum(cb))+0.05)/(min(lum(ca),lum(cb))+0.05)
                ok = des >= 12 or lr >= 1.5
                R.append(("A12", "PASS" if ok else "WARN", des, 12, f"ΔE {a} vs {nb} under {kind} (lum ratio {lr:.2f})"))
    # ---- Editor
    eb, ef = e["editor.background"], e["editor.foreground"]
    chk("E1", ef, eb, 4.5, "editor.foreground on editor.background")
    seen = set()
    for r in rules:
        t = r["token"].replace(".sql",""); 
        if t in seen: continue
        seen.add(t); chk("E2", r["foreground"], eb, 4.5, f"token {t} on editor.background", warn=3.0)
    for k in ["editor.selectionBackground","editor.inactiveSelectionBackground","editor.selectionHighlightBackground","editor.findMatchBackground","editor.findMatchHighlightBackground","editor.wordHighlightBackground","editorBracketMatch.background","editor.lineHighlightBackground"]:
        chk("E3", ef, e[k], 4.5, f"editor.foreground on {k}", base=eb)
    chk("E3", ef, mix(sf["active"], eb, 0.32), 4.5, "editor.foreground on surface.active@32% (CSS selection override)")
    chk("E4", e["editorLineNumber.foreground"], eb, 3.0, "line numbers on editor.background")
    chk("E4", e["editorLineNumber.activeForeground"], eb, 4.5, "active line number on editor.background")
    chk("E4", e["editorCursor.foreground"], eb, 3.0, "cursor on editor.background")
    chk("E4", e["editorBracketMatch.border"], eb, 3.0, "bracket match border on editor.background")
    chk("E5", ef, e["editorSuggestWidget.background"], 4.5, "editor.foreground on suggest widget")
    chk("E5", ef, e["editorSuggestWidget.selectedBackground"], 4.5, "editor.foreground on suggest selected", base=e["editorSuggestWidget.background"])
    chk("E5", ef, e["editorHoverWidget.background"], 4.5, "editor.foreground on hover widget")
    chk("E5", e["editorWidget.border"], e["editorWidget.background"], 1.5, "widget border on widget background", warn=1.2)
    chk("E6", e["editorError.foreground"], eb, 3.0, "error squiggle on editor.background")
    chk("E6", e["editorWarning.foreground"], eb, 3.0, "warning squiggle on editor.background")
    return R

def main():
    def gh_escape(s, prop=False):
        s = s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        return s.replace(":", "%3A").replace(",", "%2C") if prop else s

    total = {"PASS":0,"WARN":0,"FAIL":0}
    summary = []
    for path in sorted(glob.glob(f"{ROOT}/*.json")):
        d, R = audit(path)
        n = {s: sum(1 for r in R if r[1]==s) for s in total}
        for s in total: total[s] += n[s]
        name = path.split("/")[-1][:-5]
        print(f"\n=== {name} ({d['mode']}) — {n['PASS']} pass, {n['WARN']} warn, {n['FAIL']} fail")
        for id_, st, r, need, desc in R:
            if st != "PASS" or VERBOSE:
                print(f"  {st:4} {id_:4} {r:6.2f} (need {need:>4}) {desc}")
        summary.append((name, d["mode"], n, [x for x in R if x[1] != "PASS"]))
        if GITHUB:
            f = gh_escape(os.path.relpath(path), prop=True)
            # one annotation per failing check; warnings folded per theme (GitHub caps annotations per step)
            for id_, st, r, need, desc in R:
                if st == "FAIL":
                    print(f"::error file={f},title={gh_escape(f'{name}: {id_}', prop=True)}::{gh_escape(f'{desc}: {r:.2f}, needs {need}')}")
            warns = [x for x in R if x[1] == "WARN"]
            if warns:
                body = "\n".join(f"{id_} {r:.2f} (need {need}) {desc}" for id_, _, r, need, desc in warns)
                print(f"::warning file={f},title={gh_escape(f'{name}: {len(warns)} accessibility warnings', prop=True)}::{gh_escape(body)}")
    print(f"\nTOTAL: {total}")

    if GITHUB and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as out:
            out.write("## Accessibility audit\n\n| Variant | Mode | Pass | Warn | Fail |\n| --- | --- | ---: | ---: | ---: |\n")
            for name, mode, n, _ in summary:
                out.write(f"| {name} | {mode} | {n['PASS']} | {n['WARN']} | {n['FAIL']} |\n")
            out.write(f"| **Total** | | {total['PASS']} | {total['WARN']} | {total['FAIL']} |\n")
            for name, _, _, rows in summary:
                if not rows: continue
                out.write(f"\n<details><summary>{name}: {len(rows)} non-passing checks</summary>\n\n| Status | Check | Ratio | Needs | Pair |\n| --- | --- | ---: | ---: | --- |\n")
                for id_, st, r, need, desc in rows:
                    pair = desc.replace("|", "\\|")
                    out.write(f"| {st} | {id_} | {r:.2f} | {need} | {pair} |\n")
                out.write("\n</details>\n")
    sys.exit(1 if total["FAIL"] else 0)

if __name__ == "__main__":
    main()
