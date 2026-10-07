// Synthetic OHLC + intrabar tick paths for the BPR live preview (illustration only, not market data).
// SYNTH-BEGIN
const Synth = (() => {
  function mulberry32(seed) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const round2 = (x) => Math.round(x * 100) / 100;

  // Bars: a mean-reverting random walk with occasional large-body "displacement" candles.
  function bars(seed, count, start = 2350.0, sigma = 1.6) {
    const r = mulberry32(seed);
    const gauss = () => {
      let u = 0, v = 0;
      while (u === 0) u = r();
      while (v === 0) v = r();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    };
    const out = [];
    let close = start, anchor = start, drift = 0;
    for (let i = 0; i < count; i++) {
      if (r() < 0.03) drift = (r() - 0.5) * 0.8 * sigma;
      anchor += drift * 0.5;
      const open = round2(close + (r() < 0.15 ? gauss() * 0.15 * sigma : 0));
      let body;
      let wickScale;
      if (r() < 0.16) {                                   // displacement candle
        const dir = (r() < 0.5 ? -1 : 1) * (open > anchor + 6 * sigma ? -1 : 1) * (open < anchor - 6 * sigma ? -1 : 1);
        body = dir * (2.0 + 2.5 * r()) * sigma;
        wickScale = 0.08;
      } else {
        body = gauss() * 0.9 * sigma + drift + (anchor - open) * 0.02;
        wickScale = 0.7;
      }
      const c = round2(open + body);
      const hi = round2(Math.max(open, c) + Math.abs(gauss()) * wickScale * sigma * (wickScale < 0.5 ? Math.abs(body) / sigma * 0.5 : 1));
      const lo = round2(Math.min(open, c) - Math.abs(gauss()) * wickScale * sigma * (wickScale < 0.5 ? Math.abs(body) / sigma * 0.5 : 1));
      out.push({ o: open, h: hi, l: lo, c });
      close = c;
    }
    return out;
  }

  // Tick path inside one bar: open -> first extreme -> second extreme -> close, with noise, bounded by [l, h].
  // Returns `ticks` forming states {o,h,l,c}; the last one equals the final bar.
  function path(bar, ticks, seed) {
    const r = mulberry32(seed);
    const highFirst = bar.c < bar.o ? r() < 0.7 : r() < 0.3;
    const pts = [bar.o, highFirst ? bar.h : bar.l, highFirst ? bar.l : bar.h, bar.c];
    const seg = [0, Math.floor(ticks * 0.3), Math.floor(ticks * 0.7), ticks - 1];
    const prices = [];
    for (let s = 0; s < 3; s++) {
      for (let t = seg[s]; t < seg[s + 1]; t++) {
        const f = (t - seg[s]) / Math.max(1, seg[s + 1] - seg[s]);
        const base = pts[s] + (pts[s + 1] - pts[s]) * f;
        const noise = (r() - 0.5) * (bar.h - bar.l) * 0.15;
        prices.push(Math.min(bar.h, Math.max(bar.l, round2(base + noise))));
      }
    }
    prices.push(bar.c);
    const states = [];
    let hi = bar.o, lo = bar.o;
    for (let t = 0; t < prices.length; t++) {
      hi = Math.max(hi, prices[t]); lo = Math.min(lo, prices[t]);
      states.push({ o: bar.o, h: hi, l: lo, c: prices[t] });
    }
    states[states.length - 1] = { o: bar.o, h: bar.h, l: bar.l, c: bar.c };
    return states;
  }
  return { mulberry32, bars, path };
})();
// SYNTH-END
if (typeof module !== 'undefined') module.exports = Synth;
