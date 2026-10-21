"""Draw the owner's rule of 2026-10-21 (BprFvgEA v11): for a BPR tapped from above, the bodies of the T1 / T2
candles and of the rejection candles C1, C2 must not close out of the box (below it); otherwise no trade. Four panels,
each drawn from the records of the v11 detector with the EA's default inputs (REVERSAL):
  1. allowed: the T1 wick goes below the box, its body stays in it; C1 in the box, C2 above it -> trade;
  2. the owner's "T1 NO": the T1 body closes below the box -> no trade;
  3. C2 opens and closes below the box -> no trade (drawn with a gap: without it, the candle before C2 would close
     below the box and end the setup there, as a later candle of the T1 touch);
  4. a BPR tapped from below (the mirror image): the T1 body closes above the box -> no trade.

Usage: PYTHONPATH=.:tests python tools/bk_preview/draw_body_rule.py [out.svg]
Default output: research/indicators/preview/bpr_body_rule_example.svg

The bars are synthetic (tests/bk_scenarios.py v11_sequences()). The records come from the C++ transliteration of the
MQL5 detector (tools/mql5_cpp_harness, g++ needed). Not market data, not a backtest.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "tools/mql5_cpp_harness")]
from bk_scenarios import mirror, v11_sequences  # noqa: E402
from mq5_to_cpp import transform_pure  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "research/indicators/preview/bpr_body_rule_example.svg")
SP = 0.1
SEQ = v11_sequences()
EA = ["fvg_rule=0", "setup_type=1", "anticipate=1", "t1_wait=0", "rev_fvg=0", "rev_rej_c=2", "ext=1"]

with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    inc = ROOT / "mql5/BprFvgEA/include"
    src = [(inc / f).read_text(encoding="utf-8") for f in ("BfDefines.mqh", "BfEngine.mqh", "BfDetector.mqh")]
    (d / "bf_pure.cpp").write_text(transform_pure(src))
    shutil.copy(ROOT / "tools/mql5_cpp_harness/shim.h", d / "shim.h")
    shutil.copy(ROOT / "tools/mql5_cpp_harness/bk_main.cpp", d / "bk_main.cpp")
    subprocess.run(["g++", "-std=c++17", "-O1", "-w", "-o", str(d / "bk"), str(d / "bk_main.cpp")], check=True)

    def records(bars, body_rule):
        (d / "bars.txt").write_text("".join(" ".join(repr(float(v)) for v in b) + "\n" for b in bars))
        res = subprocess.run([str(d / "bk"), str(d / "bars.txt"), f"sp={SP}", "hold_bars=50",
                              f"rev_body_box={body_rule}", *EA], capture_output=True, text=True, check=True)
        recs = [json.loads(ln) for ln in res.stdout.splitlines()[:-1]]
        sid = next(r["id"] for r in recs if r["ev"] == "ARMED" and r["n"] == 13 and r["kind"] == 1)  # the BPR of 13
        return [r for r in recs if r["id"] == sid]

    PANELS = [
        ("t1_wick_out_ok", False, "1. VALID: the bodies stay in the box -> trade",
         ["T1 (17): its WICK goes below the box (allowed), its BODY closes in it (98.20).",
          "C1 (18) closes in the box, C2 (19) above it: the rejection. Then 2 closes below the T1 wick: limits."]),
        ("t1_body_out", False, "2. NO TRADE: the T1 body closes below the box",
         ["Your 'T1 NO': T1 (17) opens above the box and closes BELOW it (97.80 < 98.00).",
          "v11 ends the setup on that close (DONE BROKEN). v10 traded it: limits on 23."]),
        ("c2_body_out", False, "3. NO TRADE: C2 closes below the box",
         ["T1 (17): wick below the box, body in it: valid. C1 (18) in the box: valid.",
          "C2 (20) opens and closes BELOW the box: no trade (DONE BROKEN on 20). v10 traded it (limits on 25).",
          "Drawn with a GAP (20 opens 0.60 below 19's close). Without it, 19 closes below the box: the setup ends on",
          "19 (a later candle of the T1 touch). On M1 a C body below the box mostly needs such a gap."]),
        ("t1_body_out", True, "4. Tap from BELOW (bearish BPR): the mirror image",
         ["The BPR is tested from below: the T1 / T2 bodies and the red C1 / C2 must stay in the box or below it.",
          "Here T1 (17) closes ABOVE the box: no trade (DONE BROKEN on 17)."]),
    ]
    data = []
    for name, mir, title, lines in PANELS:
        bars = mirror(SEQ[name]) if mir else SEQ[name]
        data.append((bars, records(bars, 1), records(bars, 0), mir, title, lines))

W, H = 1600, 1040
PW, PH = 790, 470
s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Arial" font-size="12">',
     f'<rect width="{W}" height="{H}" fill="#131722"/>']


def text(xx, yy, t, col, anchor="start", size=12, bold=False):
    w = ' font-weight="bold"' if bold else ""
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<text x="{xx:.1f}" y="{yy:.1f}" fill="{col}" text-anchor="{anchor}" font-size="{size}"{w}>{t}</text>'


s.append(text(20, 30, "BprFvgEA v11 - your rule: the BODIES of T1 / T2 and of C1 / C2 must not close out of the BPR box "
              "(synthetic bars; MQL5 detector records, REVERSAL, v11 defaults)", "#d1d4dc", size=17, bold=True))
s.append(text(20, 54, "BPR tapped from ABOVE (bullish BPR): each body (open and close) must stay in the box or above it. "
              "The WICKS may go out. A body below the box -> NO TRADE.", "#ffeb3b", size=13))
s.append(text(20, 74, "BPR tapped from BELOW (bearish BPR): the mirror image - each body must stay in the box or below "
              "it. On the edge of the box counts as in the box.", "#ffeb3b", size=13))


def panel(ox, oy, bars, rv, rv10, mir, title, lines):
    first, last = 12, min(len(bars) - 1, 29)
    lo = min(b[2] for b in bars[first:last + 1]) - 0.3
    hi = max(b[1] for b in bars[first:last + 1]) + 0.4
    L, R, T, B = 52, 150, 70 + 16 * max(0, len(lines) - 2), 26
    cw = (PW - L - R) / (last - first + 1)

    def x(i):
        return ox + L + (i - first + 0.5) * cw

    def y(p):
        return oy + T + (hi - p) / (hi - lo) * (PH - T - B)

    s.append(f'<rect x="{ox}" y="{oy}" width="{PW}" height="{PH}" fill="#161a25" stroke="#2a2e39"/>')
    s.append(text(ox + 12, oy + 22, title, "#d1d4dc", size=15, bold=True))
    for j, ln in enumerate(lines):
        s.append(text(ox + 12, oy + 40 + 16 * j, ln, "#9598a1", size=11))
    p = round(lo * 2) / 2
    while p <= hi:
        if p >= lo:
            s.append(f'<line x1="{ox + L}" x2="{ox + PW - R}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="#222631"/>')
            s.append(text(ox + L - 5, y(p) + 4, f"{p:.1f}", "#787b86", "end", 10))
        p += 0.5
    # the BPR box [98.0, 99.9]; mirror() reflects prices around 100 (p -> 200 - p)
    zB, zT = (98.0, 99.9) if not mir else (200.0 - 99.9, 200.0 - 98.0)
    zc = "#00e676" if not mir else "#ff5252"
    x0 = x(13) - cw / 2
    s.append(f'<rect x="{x0:.1f}" y="{y(zT):.1f}" width="{ox + PW - R - x0:.1f}" height="{y(zB) - y(zT):.1f}" '
             f'fill="{zc}" fill-opacity="0.09" stroke="{zc}" stroke-opacity="0.55"/>')
    s.append(text(ox + PW - R + 6, y(zT) + 4, f"box top {zT:.2f}", zc, size=10))
    s.append(text(ox + PW - R + 6, y(zB) + 4, f"box bottom {zB:.2f}", zc, size=10))
    s.append(text(x0 + 4, y(zB if not mir else zT) + (14 if not mir else -6),
                  "BPR " + ("(bullish, tapped from above)" if not mir else "(bearish, tapped from below)"), zc, size=10))
    done = next((r for r in rv if r["ev"] == "DONE"), None)
    bad = done["n"] if done and done.get("bo") else None
    for i in range(first, last + 1):
        o, h, l_, c = bars[i]
        col = "#26a69a" if c >= o else "#ef5350"
        dim = bad is not None and i > bad
        op = ' opacity="0.35"' if dim else ""
        s.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(h):.1f}" y2="{y(l_):.1f}" stroke="{col}"{op}/>')
        top, bot = max(o, c), min(o, c)
        s.append(f'<rect x="{x(i) - cw * 0.32:.1f}" y="{y(top):.1f}" width="{cw * 0.64:.1f}" '
                 f'height="{max(1.0, y(bot) - y(top)):.1f}" fill="{col}"{op}/>')
        s.append(text(x(i), oy + PH - 8, str(i), "#787b86", "middle", 9))
    zd = 1 if not mir else -1
    touches = [r["n"] for r in rv if r["ev"] == "TOUCH"]
    for k, n in enumerate(touches):
        yy = y(bars[n][2]) + 15 if zd > 0 else y(bars[n][1]) - 7
        s.append(text(x(n), yy, f"T{k + 1}", "#ffeb3b", "middle", 12, True))
    # rejection candles: in the BPR's direction, after T1, before the breakout / the end, not beyond the T1 wick
    t1 = touches[0]
    lvl = bars[t1][2] if zd > 0 else bars[t1][1]
    endn = bad if bad is not None else next((r["n"] for r in rv if r["ev"] == "BREAKOUT"), last)
    cn = 0
    for u in range(t1 + 1, endn + 1):
        o, h, l_, c = bars[u]
        if (c > o if zd > 0 else c < o) and (c >= lvl if zd > 0 else c <= lvl):
            cn += 1
            yy = y(h) - 7 if zd > 0 else y(l_) + 15
            s.append(text(x(u), yy, f"C{cn}", "#ffeb3b", "middle", 12, True))
    if bad is not None:
        o, h, l_, c = bars[bad]
        edge = zB if zd > 0 else zT
        yb = y(min(o, c)) if zd > 0 else y(max(o, c))
        s.append(f'<line x1="{x(bad) - cw * 0.9:.1f}" x2="{x(bad) + cw * 0.9:.1f}" y1="{y(edge):.1f}" '
                 f'y2="{y(edge):.1f}" stroke="#ff1744" stroke-width="2"/>')
        r_ = cw * 0.55
        cy = (y(edge) + yb) / 2
        s.append(f'<line x1="{x(bad) - r_:.1f}" y1="{cy - r_:.1f}" x2="{x(bad) + r_:.1f}" y2="{cy + r_:.1f}" '
                 f'stroke="#ff1744" stroke-width="3"/>')
        s.append(f'<line x1="{x(bad) - r_:.1f}" y1="{cy + r_:.1f}" x2="{x(bad) + r_:.1f}" y2="{cy - r_:.1f}" '
                 f'stroke="#ff1744" stroke-width="3"/>')
        bo = done["bo"]
        who = f"T{bo - 1000}-touch candle" if bo >= 1000 else f"T{bo}" if bo < 10 else f"C{bo - 10}"
        side = "below" if zd > 0 else "above"
        body = min(o, c) if zd > 0 else max(o, c)
        yt = y(edge) + (40 if zd > 0 else -32)
        s.append(text(x(bad) + cw, yt, f"{who} body {side} the box ({body:.2f})", "#ff1744", "start", 12, True))
        s.append(text(x(bad) + cw, yt + 16, "NO TRADE: DONE (BROKEN)", "#ff1744", "start", 12, True))
        pl10 = sorted({r["n"] for r in rv10 if r["ev"] == "PLACE_LIMIT"})
        if pl10:
            s.append(text(x(pl10[0]), y(lo + 0.12), f"v10 would have placed limits on {pl10[0]} (dimmed bars)",
                          "#787b86", "middle", 10))
    else:
        sets = {}
        for r in rv:
            if r["ev"] == "PLACE_LIMIT":
                sets.setdefault(r["n"], []).append(r)
        n0 = min(sets)
        nl = max(sets)
        for r in sets[nl]:
            xa = x(n0) - cw / 2
            s.append(f'<line x1="{xa:.1f}" x2="{ox + PW - R:.1f}" y1="{y(r["P"]):.1f}" y2="{y(r["P"]):.1f}" '
                     f'stroke="#2196f3" stroke-width="1.2"/>')
        r0 = sets[nl][0]
        s.append(text(ox + PW - R + 6, y(r0["P"]) + 4, "sell limits", "#2196f3", size=10))
        brk = next(r for r in rv if r["ev"] == "BREAKOUT")
        s.append(f'<line x1="{x(t1):.1f}" x2="{x(brk["n"] + 1) + cw / 2:.1f}" y1="{y(brk["lvl"]):.1f}" '
                 f'y2="{y(brk["lvl"]):.1f}" stroke="#ff9800" stroke-dasharray="4,3" stroke-width="1.3"/>')
        s.append(text(x(t1) + cw * 0.8, y(brk["lvl"]) - 5, f"T1 wick {brk['lvl']:.2f}: below the box, allowed",
                      "#ff9800", size=11))
        s.append(text(x(brk["n"] + 1) + cw * 0.6, y(bars[brk["n"] + 1][3]) + 4, "2nd close below the wick: limits",
                      "#ff9800", size=11, bold=True))
        s.append(text(x(n0), y(lo + 0.12), f"TRADE: limits from {n0}, moved at each new low", "#00e676", "middle",
                      11, True))
        o, h, l_, c = bars[t1]
        s.append(text(x(t1) - cw * 0.45, y(min(o, c)) - 4, "T1 body in the box", "#00e676", "end", 11, True))


for j, item in enumerate(data):
    panel(10 + (j % 2) * (PW + 0), 90 + (j // 2) * (PH + 6), *item)
s.append("</svg>")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(s))
print("wrote", out)
