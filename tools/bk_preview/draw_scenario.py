"""Draw one hand-built BprFvgEA v2 setup as an SVG chart, from the Python reference detector's own records.

Usage: PYTHONPATH=.:tests python tools/bk_preview/draw_scenario.py [scenario] [out.svg]
Default: scenario 'fill_target' -> research/indicators/preview/bpr_breakout_example.svg
The bars are synthetic (tests/bk_scenarios.py); the drawing shows how the EA reads the owner's rule, not market data.
"""
import sys
from pathlib import Path

from bk_scenarios import scenarios
from qe.strategies.bpr_breakout import BreakoutParams, harness_detector

name = sys.argv[1] if len(sys.argv) > 1 else "fill_target"
out = Path(sys.argv[2] if len(sys.argv) > 2 else "research/indicators/preview/bpr_breakout_example.svg")
bars = scenarios()[name]
params = BreakoutParams(fvg_rule="LUXALGO")
det = harness_detector(bars, params, 0.1, hold_bars=3)
st = det.setup(1)
ev = [e for e in det.events if e["id"] == 1]
first, last = 6, len(bars) - 1
lo = min(b[2] for b in bars[first:]) - 0.3
hi = max(b[1] for b in bars[first:]) + 0.3
W, H, L, R, T, B = 1200, 640, 70, 300, 62, 60
cw = (W - L - R) / (last - first + 1)


def x(i):
    return L + (i - first + 0.5) * cw


def y(p):
    return T + (hi - p) / (hi - lo) * (H - T - B)


s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Arial" font-size="12">',
     f'<rect width="{W}" height="{H}" fill="#131722"/>',
     f'<text x="{L}" y="24" fill="#d1d4dc" font-size="15">BprFvgEA v2 - how the EA reads the rule (synthetic bars, '
     f'scenario "{name}", Python reference records)</text>']
# price grid
p = round(lo, 0)
while p <= hi:
    s.append(f'<line x1="{L}" x2="{W - R}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="#2a2e39"/>')
    s.append(f'<text x="{L - 6}" y="{y(p) + 4:.1f}" fill="#787b86" text-anchor="end">{p:.2f}</text>')
    p += 0.5
# BPR box
x0, x1 = x(st.created) - cw / 2, W - R
s.append(f'<rect x="{x0:.1f}" y="{y(st.T):.1f}" width="{x1 - x0:.1f}" height="{y(st.B) - y(st.T):.1f}" '
         f'fill="#00e676" fill-opacity="0.12" stroke="#00e676" stroke-opacity="0.5"/>')
s.append(f'<text x="{x0 + 4:.1f}" y="{y(st.B) - 4:.1f}" fill="#00e676">BPR (bullish, pos=+1)  {st.B:.2f} - {st.T:.2f}</text>')
# candles
for i in range(first, last + 1):
    o, h, l_, c = bars[i]
    col = "#26a69a" if c >= o else "#ef5350"
    s.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(h):.1f}" y2="{y(l_):.1f}" stroke="{col}"/>')
    top, bot = max(o, c), min(o, c)
    s.append(f'<rect x="{x(i) - cw * 0.3:.1f}" y="{y(top):.1f}" width="{cw * 0.6:.1f}" '
             f'height="{max(1.0, y(bot) - y(top)):.1f}" fill="{col}"/>')
    s.append(f'<text x="{x(i):.1f}" y="{H - B + 16}" fill="#787b86" text-anchor="middle" font-size="10">{i}</text>')
# records
lab = {"TOUCH": "T", "BREAKOUT": "B1", "CONFIRM": "B2", "REJECT": "R"}
dec = None
for e in ev:
    n = e["n"]
    if e["ev"] in lab:
        t = lab[e["ev"]] + (str(e["k"]) if e["ev"] == "TOUCH" else "")
        below = e["ev"] in ("TOUCH", "REJECT")
        yy = y(bars[n][2]) + 16 if below else y(bars[n][1]) - 8
        s.append(f'<text x="{x(n):.1f}" y="{yy:.1f}" fill="#ffeb3b" text-anchor="middle" font-weight="bold">{t}</text>')
    if e["ev"] == "BREAKOUT":
        s.append(f'<line x1="{x(st.ref):.1f}" x2="{x(n):.1f}" y1="{y(st.lvl):.1f}" y2="{y(st.lvl):.1f}" '
                 f'stroke="#ffeb3b" stroke-dasharray="3,3"/>')
        s.append(f'<text x="{x(st.ref) - 4:.1f}" y="{y(st.lvl) - 40:.1f}" fill="#ffeb3b" text-anchor="end">'
                 f'breakout level = high of the last touching candle ({st.lvl:.2f})</text>')
        s.append(f'<line x1="{x(st.ref) - 4:.1f}" x2="{x(st.ref):.1f}" y1="{y(st.lvl) - 36:.1f}" '
                 f'y2="{y(st.lvl):.1f}" stroke="#ffeb3b" stroke-width="0.6"/>')
    if e["ev"] == "PLACE_LIMIT" and dec is None:
        dec = n
O, X = st.dec_O, st.dec_X
xa, xb = x(st.o_bar if st.o_bar <= (dec or last) else first), W - R
for f, lbl, col in [(0.0, "0% = leg high = TP", "#00c853"), (100.0, "100% = leg origin", "#ffc107")]:
    p = X - f / 100 * (X - O)
    s.append(f'<line x1="{xa:.1f}" x2="{xb:.1f}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="{col}"/>')
    s.append(f'<text x="{xb + 6:.1f}" y="{y(p) - 10:.1f}" fill="{col}">{lbl} {p:.2f}</text>')
for k, lv in enumerate(st.levels, start=1):
    p = X - lv.fib / 100 * (X - O)
    s.append(f'<line x1="{xa:.1f}" x2="{xb:.1f}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="#2196f3"/>')
    s.append(f'<text x="{xb + 6:.1f}" y="{y(p) + 4:.1f}" fill="#2196f3">{lv.fib:.1f}% L{k} buy limit {lv.P:.2f} '
             f'({lv.status})</text>')
s.append(f'<line x1="{xa:.1f}" x2="{xb:.1f}" y1="{y(st.SL):.1f}" y2="{y(st.SL):.1f}" stroke="#ff5252"/>')
s.append(f'<text x="{xb + 6:.1f}" y="{y(st.SL) + 14:.1f}" fill="#ff5252">SL {st.SL:.2f} (origin - 10 ticks)</text>')
if dec is not None:
    s.append(f'<text x="{x(dec):.1f}" y="{y(bars[dec][1]) - 22:.1f}" fill="#2196f3" text-anchor="middle">'
             f'pullback: orders</text>')
# legend
s.append(f'<text x="{L}" y="42" fill="#9598a1">T = touch of the BPR (max 2, a rejection candle R between) | '
         f'B1 = breakout close above the level | B2 = second close above (confirmation) | an FVG must form after the '
         f'last touching candle</text>')
s.append("</svg>")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("\n".join(s))
print("wrote", out, "| records:", [(e["n"], e["ev"], e["k"], e["reason"]) for e in ev])
