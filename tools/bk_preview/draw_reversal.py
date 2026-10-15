"""Draw the owner's reversal example (2026-10-15) as the BprFvgEA v7 detector reads it, as an SVG chart.

Usage: PYTHONPATH=.:tests python tools/bk_preview/draw_reversal.py [out.svg]
Default output: research/indicators/preview/bpr_reversal_example.svg

The bars are synthetic (tests/bk_scenarios.py v7_sequences()['owner_example']: the v2 example 'two_touches' plus the
drop the owner drew). The records come from the C++ transliteration of the MQL5 detector (tools/mql5_cpp_harness, g++
needed), run with InpSetupType = BOTH: the continuation trade (#1) and then the reversal trade (#2) of the same BPR.
The drawing shows how the EA reads the rule; it is not market data and not a backtest.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "tools/mql5_cpp_harness")]
from bk_scenarios import v7_sequences  # noqa: E402
from mq5_to_cpp import transform_pure  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "research/indicators/preview/bpr_reversal_example.svg")
bars = v7_sequences()["owner_example"]
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
    res = subprocess.run([str(d / "bk"), str(d / "bars.txt"), f"sp={SP}", "hold_bars=50", "fvg_rule=1", "setup_type=2",
                          "ext=1"], capture_output=True, text=True, check=True)
recs = [json.loads(ln) for ln in res.stdout.splitlines()[:-1]]
cont = [r for r in recs if r["id"] == 1]
rev = [r for r in recs if r["id"] == 2]
assert rev and rev[0]["kind"] == 1 and cont[0]["kind"] == 0, "expected BOTH: #1 continuation, #2 reversal"

first, last = 6, len(bars) - 1
lo = min(b[2] for b in bars[first:]) - 0.3
hi = max(b[1] for b in bars[first:]) + 0.4
W, H, L, R, T, B = 1280, 720, 70, 330, 70, 60
cw = (W - L - R) / (last - first + 1)


def x(i):
    return L + (i - first + 0.5) * cw


def y(p):
    return T + (hi - p) / (hi - lo) * (H - T - B)


def text(xx, yy, t, col, anchor="start", size=12, bold=False):
    w = ' font-weight="bold"' if bold else ""
    return f'<text x="{xx:.1f}" y="{yy:.1f}" fill="{col}" text-anchor="{anchor}" font-size="{size}"{w}>{t}</text>'


def hline(xa, xb, p, col, dash=None, width=1.0):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{xa:.1f}" x2="{xb:.1f}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="{col}" '
            f'stroke-width="{width}"{da}/>')


s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Arial" font-size="12">',
     f'<rect width="{W}" height="{H}" fill="#131722"/>',
     text(L, 24, "BprFvgEA v7 - your reversal example as the EA reads it (synthetic bars; records of the MQL5 detector, "
          "InpSetupType = BOTH)", "#d1d4dc", size=15),
     text(L, 44, "T = touch of the BPR | R = rejection | reversal level = the deeper of the T1 / T2 wicks | 1st / 2nd "
          "close = the breakout | Fibonacci from the top of the move (100 %) to the new low (0 %)", "#9598a1"),
     text(L, 60, "#1 = the continuation setup of this BPR (it traded the move up first); #2 = its reversal setup",
          "#9598a1")]
p = round(lo)
while p <= hi:
    s.append(hline(L, W - R, p, "#2a2e39"))
    s.append(text(L - 6, y(p) + 4, f"{p:.2f}", "#787b86", "end"))
    p += 0.5
# BPR box
zB, zT, created = 98.0, 99.9, 13
x0 = x(created) - cw / 2
s.append(f'<rect x="{x0:.1f}" y="{y(zT):.1f}" width="{W - R - x0:.1f}" height="{y(zB) - y(zT):.1f}" fill="#00e676" '
         f'fill-opacity="0.10" stroke="#00e676" stroke-opacity="0.5"/>')
s.append(text(x0 + 4, y(zB) - 6, f"BPR (bullish)  {zB:.2f} - {zT:.2f}", "#00e676"))
# candles
for i in range(first, last + 1):
    o, h, l_, c = bars[i]
    col = "#26a69a" if c >= o else "#ef5350"
    s.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(h):.1f}" y2="{y(l_):.1f}" stroke="{col}"/>')
    top, bot = max(o, c), min(o, c)
    s.append(f'<rect x="{x(i) - cw * 0.3:.1f}" y="{y(top):.1f}" width="{cw * 0.6:.1f}" '
             f'height="{max(1.0, y(bot) - y(top)):.1f}" fill="{col}"/>')
    s.append(text(x(i), H - B + 16, str(i), "#787b86", "middle", 10))
# touches / rejections (one label per bar)
for r in rev:
    if r["ev"] == "TOUCH":
        s.append(text(x(r["n"]), y(bars[r["n"]][2]) + 16, f"T{r['k']}", "#ffeb3b", "middle", bold=True))
    elif r["ev"] == "REJECT" and r["n"] < 20:
        s.append(text(x(r["n"]), y(bars[r["n"]][2]) + 16, "R", "#ffeb3b", "middle", bold=True))
# the continuation trade (#1), muted
cb = next(r for r in cont if r["ev"] == "BREAKOUT")["n"]
cc = next(r for r in cont if r["ev"] == "CONFIRM")["n"]
ccl = next(r for r in cont if r["ev"] == "CLOSED")["n"]
s.append(text(x(cb), y(bars[cb][1]) - 8, "B1", "#787b86", "middle"))
s.append(text(x(cc), y(bars[cc][1]) - 8, "B2", "#787b86", "middle"))
s.append(text(x(cc) - 30, y(101.9), f"#1 continuation: buy limits after B2, target 101.50 reached on bar {ccl}",
              "#787b86", "end", 11))
# the reversal (#2)
br = next(r for r in rev if r["ev"] == "BREAKOUT")
cf = next(r for r in rev if r["ev"] == "CONFIRM")
pl = [r for r in rev if r["ev"] == "PLACE_LIMIT"]
lvl, lvlBar = br["lvl"], br["lvlBar"]
s.append(hline(x(lvlBar), x(cf["n"]) + cw, lvl, "#ff9800", "4,3", 1.4))
s.append(text(x(lvlBar + 5) - cw / 2, y(lvl) - 6, f"reversal level {lvl:.2f} = T1 wick", "#ff9800"))
s.append(text(x(br["n"]) - cw * 0.45, y(bars[br["n"]][3]) + 4, "1st close below", "#ff9800", "end", 11, True))
s.append(text(x(cf["n"]) - cw * 0.45, y(bars[cf["n"]][3]) + 4, "2nd close below = confirmed", "#ff9800", "end", 11,
              True))
O, X = pl[0]["O"], pl[0]["X"]
dec = pl[0]["n"]
o_bar = min(i for i in range(lvlBar, br["n"]) if bars[i][1] == O)        # the top of the move (the 100 %)
xa, xb = x(o_bar) - cw / 2, W - R
names = {1: "50 %", 2: "61.8 %", 3: "71 %"}
cancelled = {r["k"]: r["reason"] for r in rev if r["ev"] == "CANCEL"}
closed = next((r["n"] for r in rev if r["ev"] == "CLOSED"), None)
s.append(hline(xa, xb, O, "#ffc107", width=1.2))
s.append(text(xb + 6, y(O) - 4, f"100 % = top of the move {O:.2f}", "#ffc107"))
s.append(hline(xa, xb, X, "#00c853", width=1.2))
s.append(text(xb + 6, y(X) + 16, f"0 % = the new low {X:.2f}", "#00c853"))
for r in pl:
    st = (f"cancelled ({cancelled[r['k']].lower()} reached)" if r["k"] in cancelled
          else f"filled, closed at the target on bar {closed}")
    s.append(hline(xa, xb, r["P"], "#2196f3"))
    s.append(text(xb + 6, y(r["P"]) + 4, f"{names[r['k']]} sell limit {r['P']:.2f} - {st}", "#2196f3", size=11))
s.append(hline(xa, xb, pl[0]["SL"], "#ff5252", "6,3"))
s.append(text(xb + 6, y(pl[0]["SL"]) - 4, f"SL {pl[0]['SL']:.2f} (100 % + 10 ticks + spread)", "#ff5252", size=11))
s.append(hline(xa, xb, pl[0]["TP"], "#00c853", "6,3"))
s.append(text(xb + 6, y(pl[0]["TP"]) - 5, f"TP {pl[0]['TP']:.2f} (0 % + spread: the buy-back is at the ask)",
              "#00c853", size=11))
s.append(text(x(dec), y(lo + 0.25), "#2 orders (pullback)", "#2196f3", "middle", 11))
s.append("</svg>")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(s))
print("wrote", out)
print("#1", [(r["n"], r["ev"], r["k"], r["reason"]) for r in cont if r["n"] >= 14])
print("#2", [(r["n"], r["ev"], r["k"], r["reason"]) for r in rev if r["n"] >= 14])
