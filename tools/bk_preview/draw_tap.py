"""Draw the owner's example of 2026-10-16 (a BPR tapped from above after price went away from it) as the BprFvgEA v8
detector reads it with the EA's default inputs, as an SVG chart.

Usage: PYTHONPATH=.:tests python tools/bk_preview/draw_tap.py [out.svg]
Default output: research/indicators/preview/bpr_tap_example.svg

The bars are synthetic (tests/bk_scenarios.py v8_sequences()['tap_from_above']). The records come from the C++
transliteration of the MQL5 detector (tools/mql5_cpp_harness, g++ needed), run with InpSetupType = REVERSAL and the v8
defaults (anticipated entries, no limit to T1, no FVG wait for the reversal). Not market data, not a backtest.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "tools/mql5_cpp_harness")]
from bk_scenarios import v8_sequences  # noqa: E402
from mq5_to_cpp import transform_pure  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "research/indicators/preview/bpr_tap_example.svg")
bars = v8_sequences()["tap_from_above"]
SP = 0.1

with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    inc = ROOT / "mql5/BprFvgEA/include"
    src = [(inc / f).read_text(encoding="utf-8") for f in ("BfDefines.mqh", "BfEngine.mqh", "BfDetector.mqh")]
    (d / "bf_pure.cpp").write_text(transform_pure(src))
    shutil.copy(ROOT / "tools/mql5_cpp_harness/shim.h", d / "shim.h")
    shutil.copy(ROOT / "tools/mql5_cpp_harness/bk_main.cpp", d / "bk_main.cpp")
    subprocess.run(["g++", "-std=c++17", "-O1", "-w", "-o", str(d / "bk"), str(d / "bk_main.cpp")], check=True)
    (d / "bars.txt").write_text("".join(" ".join(repr(float(v)) for v in b) + "\n" for b in bars))
    res = subprocess.run([str(d / "bk"), str(d / "bars.txt"), f"sp={SP}", "hold_bars=50", "fvg_rule=0", "setup_type=1",
                          "anticipate=1", "t1_wait=0", "rev_fvg=0", "ext=1"], capture_output=True, text=True, check=True)
recs = [json.loads(ln) for ln in res.stdout.splitlines()[:-1]]
rv = [r for r in recs if r["id"] == 1]
assert rv and rv[0]["kind"] == 1

first, last = 6, len(bars) - 1
lo = min(b[2] for b in bars[first:]) - 0.3
hi = max(b[1] for b in bars[first:]) + 0.5
W, H, L, R, T, B = 1280, 720, 70, 330, 78, 60
cw = (W - L - R) / (last - first + 1)


def x(i):
    return L + (i - first + 0.5) * cw


def y(p):
    return T + (hi - p) / (hi - lo) * (H - T - B)


def text(xx, yy, t, col, anchor="start", size=12, bold=False):
    w = ' font-weight="bold"' if bold else ""
    return f'<text x="{xx:.1f}" y="{yy:.1f}" fill="{col}" text-anchor="{anchor}" font-size="{size}"{w}>{t}</text>'


def seg(xa, xb, p, col, dash=None, width=1.0):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{xa:.1f}" x2="{xb:.1f}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="{col}" '
            f'stroke-width="{width}"{da}/>')


s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Arial" font-size="12">',
     f'<rect width="{W}" height="{H}" fill="#131722"/>',
     text(L, 24, "BprFvgEA v8 - your example: the BPR is tapped later, from above (synthetic bars; MQL5 detector "
          "records, REVERSAL, v8 defaults)", "#d1d4dc", size=15),
     text(L, 44, "The BPR forms on 13 and price goes up without touching it. It comes back and taps it from above on "
          "17 (T1), then reacts up (R).", "#9598a1"),
     text(L, 62, "The second close below the T1 wick (24) places the sell limits at once. Every new low moves them "
          "(25). The 50 % fills on 27; the target is hit on 28.", "#9598a1")]
p = round(lo)
while p <= hi:
    s.append(seg(L, W - R, p, "#2a2e39"))
    s.append(text(L - 6, y(p) + 4, f"{p:.2f}", "#787b86", "end"))
    p += 0.5
zB, zT, created = 98.0, 99.9, 13
x0 = x(created) - cw / 2
s.append(f'<rect x="{x0:.1f}" y="{y(zT):.1f}" width="{W - R - x0:.1f}" height="{y(zB) - y(zT):.1f}" fill="#00e676" '
         f'fill-opacity="0.10" stroke="#00e676" stroke-opacity="0.5"/>')
s.append(text(x0 + 4, y(zB) - 6, f"BPR (bullish)  {zB:.2f} - {zT:.2f}, formed on bar {created}", "#00e676"))
for i in range(first, last + 1):
    o, h, l_, c = bars[i]
    col = "#26a69a" if c >= o else "#ef5350"
    s.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(h):.1f}" y2="{y(l_):.1f}" stroke="{col}"/>')
    top, bot = max(o, c), min(o, c)
    s.append(f'<rect x="{x(i) - cw * 0.3:.1f}" y="{y(top):.1f}" width="{cw * 0.6:.1f}" '
             f'height="{max(1.0, y(bot) - y(top)):.1f}" fill="{col}"/>')
    s.append(text(x(i), H - B + 16, str(i), "#787b86", "middle", 10))
t1 = next(r for r in rv if r["ev"] == "TOUCH")["n"]
rj = next(r for r in rv if r["ev"] == "REJECT")["n"]
br = next(r for r in rv if r["ev"] == "BREAKOUT")
cf = next(r for r in rv if r["ev"] == "CONFIRM")
s.append(text(x(14) + cw / 2, y(bars[15][1]) - 10, "no touch: price goes away", "#787b86", "middle", 11))
s.append(text(x(t1), y(bars[t1][2]) + 16, "T1", "#ffeb3b", "middle", bold=True))
s.append(text(x(rj), y(bars[rj][2]) + 16, "R", "#ffeb3b", "middle", bold=True))
lvl = br["lvl"]
s.append(seg(x(t1), x(cf["n"]) + cw, lvl, "#ff9800", "4,3", 1.4))
s.append(text(x(t1) + 10, y(lvl) - 6, f"T1 wick {lvl:.2f}", "#ff9800"))
s.append(text(x(br["n"]) - cw * 0.45, y(bars[br["n"]][3]) + 4, "1st close below", "#ff9800", "end", 11, True))
s.append(text(x(cf["n"]) - cw * 0.45, y(bars[cf["n"]][3]) + 4, "2nd close below: limits now", "#ff9800", "end", 11,
              True))
# limit sets by decision bar: earlier ones short and dashed, the last one long and solid
sets = {}
for r in rv:
    if r["ev"] == "PLACE_LIMIT":
        sets.setdefault(r["n"], []).append(r)
names = {1: "50 %", 2: "61.8 %", 3: "71 %"}
bars_dec = sorted(sets)
for j, n in enumerate(bars_dec):
    final = j == len(bars_dec) - 1
    xa = x(n) - cw / 2
    xb = (W - R) if final else x(bars_dec[j + 1]) - cw / 2
    for r in sets[n]:
        s.append(seg(xa, xb, r["P"], "#2196f3" if final else "#5c7da6", None if final else "3,3", 1.2 if final else 1.0))
        if final:
            s.append(text(W - R + 6, y(r["P"]) + 4, f"{names[r['k']]} sell limit {r['P']:.2f} (moved on {n})",
                          "#2196f3", size=11))
    if final:
        r0 = sets[n][0]
        s.append(seg(xa, xb, r0["SL"], "#ff5252", "6,3"))
        s.append(text(W - R + 6, y(r0["SL"]) - 4, f"SL {r0['SL']:.2f} (100 % {r0['O']:.2f} + 10 ticks + spread)",
                      "#ff5252", size=11))
        s.append(seg(xa, xb, r0["X"], "#00c853", width=1.2))
        s.append(text(W - R + 6, y(r0["X"]) + 16, f"0 % = the new low {r0['X']:.2f}", "#00c853", size=11))
        s.append(seg(xa, xb, r0["TP"], "#00c853", "6,3"))
        s.append(text(W - R + 6, y(r0["TP"]) - 5, f"TP {r0['TP']:.2f}", "#00c853", size=11))
s.append(text(x(bars_dec[0]), y(lo + 0.15), f"first limits on {bars_dec[0]} (dashed), moved at each new low",
              "#5c7da6", "middle", 11))
s.append("</svg>")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(s))
print("wrote", out)
print([(r["n"], r["ev"], r["k"], r["reason"], r["P"]) for r in rv if r["n"] >= 14])
