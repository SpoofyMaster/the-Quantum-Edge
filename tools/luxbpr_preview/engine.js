// LuxAlgo BPR engine (JavaScript port, used by the live preview page).
// Derived from the FVG / Balance Price Range logic of "ICT Concepts [LuxAlgo]" (Pine v5), (c) LuxAlgo.
// Licence: CC BY-NC-SA 4.0 https://creativecommons.org/licenses/by-nc-sa/4.0/ (non-commercial, share-alike).
// This is a port; changes vs. the original are listed in research/indicators/LUXALGO_BPR_SPEC.md section 10.
// Parity with the Python reference (qe/indicators/luxalgo_bpr.py) is checked by tools/luxbpr_preview/parity_test.js.
// ENGINE-BEGIN
const LuxBPR = (() => {
  const DEFAULTS = {
    mode: 'Present', presentBars: 500, length: 5, percBody: 0.36, showFVG: true, bpr: true,
    fvgMode: 'FVG', visBoxes: 2, bxBack: 10, ext: 8,
  };

  const emptyZone = () => ({ box: null, active: false, pos: null });

  function perStartFor(lastBarIndex, p) {
    return p.mode === 'Present' ? lastBarIndex - p.presentBars : null;
  }

  class Engine {
    constructor(params, perStart) {
      this.p = Object.assign({}, DEFAULTS, params || {});
      this.perStart = perStart === undefined ? null : perStart;
      this.fu = []; this.fd = []; this.bu = []; this.bd = [];
      // Pine barstate.isfirst (lines 598-604)
      for (let i = 0; i < this.p.visBoxes; i++) {
        this.fu.unshift(emptyZone());
        this.fd.unshift(emptyZone());
        if (this.p.bpr) { this.bu.unshift(emptyZone()); this.bd.unshift(emptyZone()); }
      }
      this.hist = [];        // recent bars with their features, oldest first
      this.events = [];      // [bar, kind, what]
      this.last = null;
      this.dispUp = false; this.dispDn = false;
    }

    clone() {
      const e = Object.create(Engine.prototype);
      e.p = this.p; e.perStart = this.perStart;
      const cz = (z) => ({ box: z.box ? Object.assign({}, z.box) : null, active: z.active, pos: z.pos });
      e.fu = this.fu.map(cz); e.fd = this.fd.map(cz); e.bu = this.bu.map(cz); e.bd = this.bd.map(cz);
      e.hist = this.hist.slice();          // records are never mutated after push
      e.events = this.events.slice();
      e.last = this.last; e.dispUp = this.dispUp; e.dispDn = this.dispDn;
      return e;
    }

    process(n, o, h, l, c) {
      const p = this.p;
      if (this.last !== null && n !== this.last + 1) throw new Error('bars must be consecutive');
      const body = Math.abs(c - o), mx = Math.max(c, o), mn = Math.min(c, o);
      // meanBody = sma(body, len): oldest first, na during warm-up (line 130)
      let mean = null;
      if (this.hist.length >= p.length - 1) {
        let s = 0.0;
        for (let k = p.length - 1; k >= 1; k--) s += this.hist[this.hist.length - k].body;
        s += body;
        mean = s / p.length;
      }
      const lBody = (h - mx < body * p.percBody) && (mn - l < body * p.percBody);           // lines 548-550
      const dispUp = mean !== null && body > mean && lBody && c > o;                           // line 552
      const dispDn = mean !== null && body > mean && lBody && c < o;                           // line 553
      const b1 = this.hist.length >= 1 ? this.hist[this.hist.length - 1] : null;               // bar n-1
      const b2 = this.hist.length >= 2 ? this.hist[this.hist.length - 2] : null;               // bar n-2
      const fvg = p.fvgMode === 'FVG';
      const imbUp = !!(b1 && b1.dispUp && b2 && (fvg ? l > b2.h : l < b2.h));                  // line 565
      const imbDn = !!(b1 && b1.dispDn && b2 && (fvg ? h < b2.l : h > b2.l));                  // line 566
      const prevImbUp = !!(b1 && b1.imbUp), prevImbDn = !!(b1 && b1.imbDn);
      const per = this.perStart === null || n >= this.perStart;                                // line 122

      // Bullish FVG (lines 606-624)
      if (imbUp && per && p.showFVG) {
        if (prevImbUp) {
          const z = this.fu[0];
          if (z.box) {                                       // QUIRK 3: na box -> no-op
            z.box.left = n - 2; z.box.top = l; z.box.right = n + 8; z.box.bottom = b2.h;   // QUIRK 1, 2
            this.events.push([n, 'FVG_UP', 'update']);
          }
        } else {
          this.fu.unshift({ box: { left: n - 2, top: fvg ? l : b2.h, right: n, bottom: fvg ? b2.h : l,
            border: 'solid', brokenFill: false }, active: true, pos: null });
          this.fu.pop();
          this.events.push([n, 'FVG_UP', 'new']);
        }
      }
      // Bearish FVG (lines 626-644)
      if (imbDn && per && p.showFVG) {
        if (prevImbDn) {
          const z = this.fd[0];
          if (z.box) {
            z.box.left = n - 2; z.box.top = b2.l; z.box.right = n + 8; z.box.bottom = h;
            this.events.push([n, 'FVG_DN', 'update']);
          }
        } else {
          this.fd.unshift({ box: { left: n - 2, top: fvg ? b2.l : h, right: n, bottom: fvg ? h : b2.l,
            border: 'solid', brokenFill: false }, active: true, pos: null });
          this.fd.pop();
          this.events.push([n, 'FVG_DN', 'new']);
        }
      }
      // Balance Price Range (lines 647-697)
      if (p.bpr && this.fu.length > 0 && this.fd.length > 0) {
        const up = this.fu[0].box, dn = this.fd[0].box;
        if (up && dn) {                                      // na boxes: every comparison is false
          const left = Math.min(up.left, dn.left), right = Math.max(up.right, dn.right);
          if (up.bottom < dn.top && dn.bottom < up.bottom) {
            const z0 = this.bu[0];
            if (z0.box && left === z0.box.left) {            // QUIRK 6: identity by left edge
              if (z0.active) z0.box.right = right;           // QUIRK 8: overwritten below
            } else {
              const pos = c > up.bottom ? 1 : (c < dn.top ? -1 : 0);
              this.bu.unshift({ box: { left, top: dn.top, right, bottom: up.bottom, border: 'solid', brokenFill: false },
                active: true, pos });                        // QUIRK 4
              this.bu.pop();
              this.events.push([n, 'BPR_UP', 'new']);
            }
          }
          if (dn.bottom < up.top && up.bottom < dn.bottom) {
            const z0 = this.bd[0];
            if (z0.box && left === z0.box.left) {
              if (z0.active) z0.box.right = right;
            } else {
              const pos = c > dn.bottom ? 1 : (c < up.top ? -1 : 0);
              this.bd.unshift({ box: { left, top: up.top, right, bottom: dn.bottom, border: 'solid', brokenFill: false },
                active: true, pos });
              this.bd.pop();
              this.events.push([n, 'BPR_DN', 'new']);
            }
          }
        }
      }
      // FVG breaks (lines 700-724)
      const lastI = (arr) => Math.min(p.bxBack, arr.length - 1);
      for (let i = 0; i <= lastI(this.fu); i++) {
        const z = this.fu[i];
        if (!z.active) continue;
        z.box.right = n + 8;
        if (l < z.box.top && !p.bpr) z.box.border = 'dashed';
        if (l < z.box.bottom) {
          if (!p.bpr) { z.box.brokenFill = true; z.box.border = 'dotted'; }
          z.box.right = n; z.active = false;
          this.events.push([n, 'FVG_UP', 'broken']);
        }
      }
      for (let i = 0; i <= lastI(this.fd); i++) {
        const z = this.fd[i];
        if (!z.active) continue;
        z.box.right = n + 8;
        if (h > z.box.bottom && !p.bpr) z.box.border = 'dashed';
        if (h > z.box.top) {
          if (!p.bpr) { z.box.brokenFill = true; z.box.border = 'dotted'; }
          z.box.right = n; z.active = false;
          this.events.push([n, 'FVG_DN', 'broken']);
        }
      }
      // BPR breaks (lines 726-769)
      if (p.bpr) {
        const loop = (arr, kind) => {
          for (let i = 0; i <= lastI(arr); i++) {
            const z = arr[i];
            if (!z.active) continue;
            z.box.right = n + 8;
            if (z.pos === -1) {
              if (h > z.box.bottom) z.box.border = 'dashed';
              if (h > z.box.top) {
                z.box.brokenFill = true; z.box.border = 'dotted'; z.box.right = n; z.active = false;
                this.events.push([n, kind, 'broken']);
              }
            } else if (z.pos === 1) {
              if (l < z.box.top) z.box.border = 'dashed';
              if (l < z.box.bottom) {
                z.box.brokenFill = true; z.box.border = 'dotted'; z.box.right = n; z.active = false;
                this.events.push([n, kind, 'broken']);
              }
            }
          }
        };
        loop(this.bu, 'BPR_UP');
        loop(this.bd, 'BPR_DN');
      }
      this.hist.push({ n, o, h, l, c, body, dispUp, dispDn, imbUp, imbDn });
      const keep = Math.max(p.length, 3) + 2;
      if (this.hist.length > keep) this.hist.splice(0, this.hist.length - keep);
      this.last = n; this.dispUp = dispUp; this.dispDn = dispDn;
    }

    // Fibonacci between the last BPR up and the last BPR down (lines 976-990, 1093-1118)
    fib() {
      if (!(this.bu.length > 0 && this.bd.length > 0)) return null;
      const up = this.bu[0].box, dn = this.bd[0].box;
      if (!up || !dn) return null;
      const dnFirst = up.left > dn.left, dnBottm = up.top > dn.top;
      const x1 = dnFirst ? dn.left : up.left;
      const x2 = dnFirst ? up.right : dn.right;
      const y1 = dnFirst ? (dnBottm ? dn.bottom : dn.top) : (dnBottm ? up.top : up.bottom);
      const y2 = dnFirst ? (dnBottm ? up.top : up.bottom) : (dnBottm ? dn.bottom : dn.top);
      const rt = Math.max(x1, x2);
      const zero = rt === x1 ? y1 : y2, one = rt === x1 ? y2 : y1;
      const df = one - zero;
      const levels = {};
      for (const k of [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.618]) levels[k] = zero + df * k;
      levels[1] = one;
      return { x1, y1, x2, y2, rt, zero, one, levels, lineEnd: rt + 50 };
    }
  }

  return { DEFAULTS, Engine, perStartFor };
})();
// ENGINE-END
if (typeof module !== 'undefined') module.exports = LuxBPR;
